"""plan_water_delivery 应急送水分配预览测试。

覆盖: 最大流可行性、最低出车费组合、同费车辆编号字典序决胜、多车分担、
确定性配送量、不足时最大可配送量与缺口、无断水需求空调度、录入校验。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from solver import (  # noqa: E402
    NetworkValidationError, plan_water_delivery, solve, solve_failover,
)
from demo import DEMO_NETWORK  # noqa: E402

passed = 0


def check(cond, msg):
    global passed
    assert cond, "FAIL: " + msg
    passed += 1


def expect_errors(snapshot, closed, demands, vehicles, keys):
    try:
        plan_water_delivery(snapshot, closed, demands, vehicles)
    except NetworkValidationError as exc:
        joined = " | ".join(exc.errors)
        for key in keys:
            check(key in joined, f"error contains {key!r}; got: {exc.errors}")
        return
    raise AssertionError("should have raised: " + str(keys))


# ---- 备援方案管网: 关 V1+V2 后普通节点 M,X 断水; 漏点 L 隔离, 必保点 H 有水 ----
NET_FO = {
    "nodes": [
        {"id": "S", "role": "inlet"}, {"id": "M", "role": "normal"},
        {"id": "X", "role": "normal"}, {"id": "L", "role": "leak"},
        {"id": "H", "role": "must_keep"},
    ],
    "segments": [
        {"id": "p1", "endpoint_a": "S", "endpoint_b": "M"},
        {"id": "p2", "endpoint_a": "M", "endpoint_b": "L"},
        {"id": "p4", "endpoint_a": "M", "endpoint_b": "X"},
        {"id": "p3", "endpoint_a": "S", "endpoint_b": "H"},
    ],
    "valves": [
        {"id": "V1", "segment_id": "p1", "cost": 1},
        {"id": "V2", "segment_id": "p2", "cost": 2},
    ],
}
FO = solve_failover(NET_FO)
check(FO["feasible"] and FO["closed_valves"] == ["V1", "V2"],
      f"failover plan {FO.get('closed_valves')}")
CV = FO["closed_valves"]

# 1. 基本满足: 只有 T1+T2+T3 三车齐上才够(T1 只服务 M 8, T2 8, T3 只服务 X 7)
DEMANDS = {"M": 10, "X": 7}
VEHS = [
    {"id": "T1", "cost": 5, "capacity": 8, "serves": ["M"]},
    {"id": "T2", "cost": 3, "capacity": 8, "serves": ["M", "X"]},
    {"id": "T3", "cost": 4, "capacity": 7, "serves": ["X"]},
]
r = plan_water_delivery(NET_FO, CV, DEMANDS, VEHS)
base_r = r
check(r["ok"] and r["satisfied"] and not r["empty"], "satisfied flags")
check(r["selected_vehicle_ids"] == ["T1", "T2", "T3"],
      f"selected {r['selected_vehicle_ids']}")
check(r["total_cost"] == 12, "total cost")
check(r["feasible_combination_count"] == 1
      and r["combination_count"] == 8, "combination counts")
check(r["delivered_total"] == 17 and r["shortage_total"] == 0, "totals")
# 配送量: 按(M/X, 车辆编号)双关键字贪心, 结果确定
check(r["deliveries"] == {"T1": {"M": 8, "X": 0},
                          "T2": {"M": 2, "X": 6},
                          "T3": {"M": 0, "X": 1}},
      f"deliveries {r['deliveries']}")
# 每车不超载、只向可服务点配送
for row in r["delivery_matrix"]:
    v = next(x for x in VEHS if x["id"] == row["vehicle_id"])
    check(row["delivered_total"] <= v["capacity"],
          f"{row['vehicle_id']} capacity")
    for d in row["deliveries"]:
        check(d["amount"] == 0 or d["node_id"] in v["serves"],
              f"{row['vehicle_id']} serves {d['node_id']}")
for ns in r["node_summary"]:
    check(ns["delivered"] == ns["demand"] and ns["shortage"] == 0,
          f"node {ns['node_id']} full")
check("只读" in r["message"], "readonly note")

# 2. 最低出车费: 单车 T9 虽贵但可独力完成; 两辆便宜车合起来更省
r = plan_water_delivery(NET_FO, CV, DEMANDS, [
    {"id": "T9", "cost": 9, "capacity": 100, "serves": ["M", "X"]},
    {"id": "A", "cost": 3, "capacity": 10, "serves": ["M", "X"]},
    {"id": "B", "cost": 3, "capacity": 10, "serves": ["M", "X"]},
])
check(r["satisfied"] and r["selected_vehicle_ids"] == ["A", "B"],
      f"cheapest combo {r['selected_vehicle_ids']}")
check(r["total_cost"] == 6 and r["feasible_combination_count"] >= 3,
      "cheapest cost")

# 3. 同费决胜: A、B 单车都能独力完成且同费, 取编号升序列表字典序最小
r = plan_water_delivery(NET_FO, CV, DEMANDS, [
    {"id": "B", "cost": 5, "capacity": 100, "serves": ["M", "X"]},
    {"id": "A", "cost": 5, "capacity": 100, "serves": ["M", "X"]},
])
check(r["selected_vehicle_ids"] == ["A"], f"tie break {r['selected_vehicle_ids']}")
check(r["total_cost"] == 5, "tie cost")
# 选中的 A 同时向两点配送(贪心先填满 M, 再配 X)
check(r["deliveries"]["A"] == {"M": 10, "X": 7},
      f"single vehicle split {r['deliveries']}")

# 4. 允许多车分担: 需 10 单位, 两辆载 6 的车必须分担
r = plan_water_delivery(NET_FO, CV, {"M": 10, "X": 1}, [
    {"id": "C1", "cost": 2, "capacity": 6, "serves": ["M"]},
    {"id": "C2", "cost": 2, "capacity": 6, "serves": ["M", "X"]},
])
check(r["satisfied"] and r["selected_vehicle_ids"] == ["C1", "C2"],
      "split combo")
check(r["deliveries"]["C1"]["M"] == 6
      and r["deliveries"]["C2"]["M"] == 4
      and r["deliveries"]["C2"]["X"] == 1,
      f"split amounts {r['deliveries']}")

# 5. 确定性: 候选录入顺序不同, 选中结果与配送量一致
r_rev = plan_water_delivery(NET_FO, CV, DEMANDS, list(reversed(VEHS)))
check(r_rev["selected_vehicle_ids"] == base_r["selected_vehicle_ids"],
      "order-independent selection")
check(r_rev["deliveries"] == base_r["deliveries"], "order-independent deliveries")

# 6. 全部候选车仍无法满足: 最大可配送量与总缺口
r = plan_water_delivery(NET_FO, CV, DEMANDS, [
    {"id": "T1", "cost": 5, "capacity": 8, "serves": ["M"]},
])
check(not r["ok"] and not r["satisfied"]
      and r["reason_code"] == "INSUFFICIENT_CAPACITY", "shortage flags")
check(r["selected_vehicle_ids"] == [] and r["used_vehicle_ids"] == ["T1"],
      "shortage selection")
check(r["delivered_total"] == 8 and r["shortage_total"] == 9,
      f"shortage totals {r['delivered_total']}/{r['shortage_total']}")
check(r["total_cost"] is None, "no cost on shortage")
by_node = {ns["node_id"]: (ns["delivered"], ns["shortage"])
           for ns in r["node_summary"]}
check(by_node == {"M": (8, 2), "X": (0, 7)}, f"shortage by node {by_node}")
check(r["deliveries"]["T1"] == {"M": 8, "X": 0}, "shortage matrix")

# 缺口逐点分配: 编号靠前的需求点优先(结果确定); A 可服务 M,X, 载 9
r = plan_water_delivery(NET_FO, CV, DEMANDS, [
    {"id": "A", "cost": 5, "capacity": 9, "serves": ["M", "X"]},
])
by_node = {ns["node_id"]: (ns["delivered"], ns["shortage"])
           for ns in r["node_summary"]}
check(by_node == {"M": (9, 1), "X": (0, 7)},
      f"lex shortage by node {by_node}")
check(r["deliveries"]["A"] == {"M": 9, "X": 0}, "lex shortage matrix")

# 7. 无断水需求: 空调度
DEMO = solve(DEMO_NETWORK)
r = plan_water_delivery(DEMO_NETWORK, DEMO["closed_valves"], {}, [])
check(r["ok"] and r["satisfied"] and r["empty"], "empty flags")
check(r["selected_vehicle_ids"] == [] and r["deliveries"] == {},
      "empty dispatch")
check(r["total_cost"] == 0 and r["delivered_total"] == 0
      and r["shortage_total"] == 0 and r["total_demand"] == 0, "empty zeros")
check("空调度" in r["message"], "empty message")

# 常规方案无关阀但普通点天然孤岛: 孤岛点也是需求点
NET_ISLAND = {
    "nodes": [
        {"id": "S", "role": "inlet"}, {"id": "L", "role": "leak"},
        {"id": "H", "role": "must_keep"},
        {"id": "Y", "role": "normal"},
    ],
    "segments": [
        {"id": "p1", "endpoint_a": "S", "endpoint_b": "L"},
        {"id": "p2", "endpoint_a": "S", "endpoint_b": "H"},
    ],
    "valves": [{"id": "V1", "segment_id": "p1", "cost": 1}],
}
P = solve(NET_ISLAND)
check(P["feasible"] and P["closed_valves"] == ["V1"], "island plan")
r = plan_water_delivery(NET_ISLAND, P["closed_valves"], {"Y": 3}, [
    {"id": "W1", "cost": 2, "capacity": 3, "serves": ["Y"]}])
check(r["satisfied"] and r["selected_vehicle_ids"] == ["W1"]
      and r["total_cost"] == 2, "island served")

# 8. 录入校验
# 缺少需求点需水量 / 多余编号 / 非正整数
expect_errors(NET_FO, CV, {"M": 10}, VEHS[:1], ["缺少断水需求点的需水量: X"])
expect_errors(NET_FO, CV, {"M": 10, "X": 7, "H": 3}, VEHS[:1],
              ["提供了非断水普通节点的需水量(多余编号)"])
for bad in [0, -2, 1.5, "5", True, None]:
    expect_errors(NET_FO, CV, {"M": bad, "X": 7}, VEHS[:1],
                  ["需求点 M 的需水量必须是正整数"])
expect_errors(NET_FO, CV, "notdict", VEHS[:1], ["demands 必须是以需求点编号"])

# 车辆超过 6 辆
expect_errors(NET_FO, CV, DEMANDS,
              [{"id": f"T{i}", "cost": 1, "capacity": 1, "serves": ["M"]}
               for i in range(7)],
              ["超过上限 6 辆"])
# 车辆编号缺失 / 重复
expect_errors(NET_FO, CV, DEMANDS,
              [{"cost": 1, "capacity": 1, "serves": ["M"]}],
              ["缺少车辆编号"])
expect_errors(NET_FO, CV, DEMANDS,
              [{"id": "A", "cost": 1, "capacity": 1, "serves": ["M"]},
               {"id": "A", "cost": 1, "capacity": 1, "serves": ["M"]}],
              ["车辆编号重复: A"])
# 出车费 / 载水量非法
for bad in [0, -1, 1.5, "5", False, None]:
    expect_errors(NET_FO, CV, DEMANDS,
                  [{"id": "A", "cost": bad, "capacity": 1, "serves": ["M"]}],
                  ["出车费必须是正整数"])
for bad in [0, -1, 1.5, "5", False, None]:
    expect_errors(NET_FO, CV, DEMANDS,
                  [{"id": "A", "cost": 1, "capacity": bad, "serves": ["M"]}],
                  ["载水量必须是正整数"])
# 可服务点必须是本次断水需求点
expect_errors(NET_FO, CV, DEMANDS,
              [{"id": "A", "cost": 1, "capacity": 1, "serves": ["L"]}],
              ["可服务点 L 不是本次关阀后断水的普通节点"])
expect_errors(NET_FO, CV, DEMANDS,
              [{"id": "A", "cost": 1, "capacity": 1, "serves": ["ZZ"]}],
              ["可服务点 ZZ 不是本次关阀后断水的普通节点"])
expect_errors(NET_FO, CV, DEMANDS,
              [{"id": "A", "cost": 1, "capacity": 1, "serves": "X,X"}],
              ["可服务需求点必须是数组"])
# 空可服务列表允许(车不会被任何点使用)
r = plan_water_delivery(NET_FO, CV, DEMANDS,
                        [{"id": "A", "cost": 1, "capacity": 1, "serves": []}])
check(not r["satisfied"] and r["used_vehicle_ids"] == [],
      "empty-serves vehicle unused")

# 计划阀门不属于快照
expect_errors(NET_FO, ["V9"], DEMANDS, VEHS,
              ["方案关闭的阀门 V9 不存在于方案快照的管网中"])

print(f"water delivery solver tests: {passed} checks passed")
