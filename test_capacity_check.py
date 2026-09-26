"""plan_capacity_check 供水容量校核测试。

覆盖: 整数最大流总量、容量充足/不足判定、无向管段净流量上限(同一上限
约束绝对值)、多进水点供给上限、各必保点实际送达量(编号升序贪心唯一)、
无必保点零需求充足、录入编号与方案快照完整对应校验。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from solver import (  # noqa: E402
    NetworkValidationError, plan_capacity_check, solve, solve_failover,
)
from demo import DEMO_NETWORK  # noqa: E402

passed = 0


def check(cond, msg):
    global passed
    assert cond, "FAIL: " + msg
    passed += 1


def expect_errors(snapshot, closed, capacities, supplies, demands, keys):
    try:
        plan_capacity_check(snapshot, closed, capacities, supplies, demands)
    except NetworkValidationError as exc:
        joined = " | ".join(exc.errors)
        for key in keys:
            check(key in joined, f"error contains {key!r}; got: {exc.errors}")
        return
    raise AssertionError("should have raised: " + str(keys))


# ---- 示例管网: 常规最优方案关闭 V2(s5)+V4(s6), 未关阀管段 s1..s4 ----
DEMO = solve(DEMO_NETWORK)
check(DEMO["feasible"] and DEMO["closed_valves"] == ["V2", "V4"],
      f"demo plan {DEMO.get('closed_valves')}")
CV = DEMO["closed_valves"]
# 未关阀管段: s1(S-A), s2(A-H1), s3(A-B), s4(B-H2); 进水点 S; 必保点 H1,H2
CAPS = {"s1": 10, "s2": 3, "s3": 10, "s4": 4}
SUP = {"S": 100}
DEM = {"H1": 3, "H2": 4}

# 1. 容量充足: 最大送达量 == 需求总量, 各点送达量 == 需求
r = plan_capacity_check(DEMO_NETWORK, CV, CAPS, SUP, DEM)
check(r["ok"] and r["sufficient"] and not r["empty"], "sufficient flags")
check(r["total_demand"] == 7 and r["delivered_total"] == 7
      and r["shortage_total"] == 0, "sufficient totals")
summary = {ns["node_id"]: ns for ns in r["node_summary"]}
check(summary["H1"]["delivered"] == 3 and summary["H1"]["shortage"] == 0,
      "H1 delivered")
check(summary["H2"]["delivered"] == 4 and summary["H2"]["shortage"] == 0,
      "H2 delivered")
check(r["closed_valves"] == ["V2", "V4"], "closed echo")
check(r["open_segment_ids"] == ["s1", "s2", "s3", "s4"], "open segments")
check(r["capacities"] == CAPS and r["supplies"] == SUP
      and r["demands"] == DEM, "input echoes")
check([k["id"] for k in r["keep_nodes"]] == ["H1", "H2"], "keep nodes")
check("只读" in r["message"] and "容量充足" in r["message"], "message")

# 2. 仅连通但容量不足: 干管 s1 上限 5 < 需求 7 -> 不足, 缺口 2
r = plan_capacity_check(DEMO_NETWORK, CV,
                        {"s1": 5, "s2": 3, "s3": 10, "s4": 4}, SUP, DEM)
check(r["ok"] and not r["sufficient"], "insufficient flags")
check(r["total_demand"] == 7 and r["delivered_total"] == 5
      and r["shortage_total"] == 2, "insufficient totals")
# 各点送达量: 编号升序 H1 先锁定最多 3, H2 再取剩余 2
summary = {ns["node_id"]: (ns["delivered"], ns["shortage"])
           for ns in r["node_summary"]}
check(summary == {"H1": (3, 0), "H2": (2, 2)},
      f"insufficient per-node {summary}")
check("不足" in r["message"], "insufficient message")

# 3. 进水点供给上限约束: 供给 4 < 管段能力 -> 最大送达量 4
r = plan_capacity_check(DEMO_NETWORK, CV, CAPS, {"S": 4}, DEM)
check(not r["sufficient"] and r["delivered_total"] == 4
      and r["shortage_total"] == 3, "supply bound")
summary = {ns["node_id"]: ns["delivered"] for ns in r["node_summary"]}
check(summary == {"H1": 3, "H2": 1}, f"supply bound split {summary}")

# 4. 管段净流量绝对值受同一上限约束: 单管容量 6, 不能按双向 12 计
NET_LINE = {
    "nodes": [
        {"id": "S", "role": "inlet"}, {"id": "M", "role": "normal"},
        {"id": "H", "role": "must_keep"},
    ],
    "segments": [
        {"id": "p1", "endpoint_a": "S", "endpoint_b": "M"},
        {"id": "p2", "endpoint_a": "M", "endpoint_b": "H"},
    ],
    "valves": [],
}
plan = solve(NET_LINE)
check(plan["feasible"] and plan["closed_valves"] == [], "line plan")
r = plan_capacity_check(NET_LINE, [], {"p1": 10, "p2": 6},
                        {"S": 100}, {"H": 10})
check(not r["sufficient"] and r["delivered_total"] == 6
      and r["shortage_total"] == 4, "net flow |f|<=cap on single pipe")
check(r["node_summary"][0]["delivered"] == 6, "line delivered")

# 5. 多进水点供给上限: 两个进水点各自受限, 合计受管段约束
NET_TWO_INLETS = {
    "nodes": [
        {"id": "S1", "role": "inlet"}, {"id": "S2", "role": "inlet"},
        {"id": "X", "role": "normal"}, {"id": "H", "role": "must_keep"},
    ],
    "segments": [
        {"id": "a", "endpoint_a": "S1", "endpoint_b": "X"},
        {"id": "b", "endpoint_a": "S2", "endpoint_b": "X"},
        {"id": "c", "endpoint_a": "X", "endpoint_b": "H"},
    ],
    "valves": [],
}
plan = solve(NET_TWO_INLETS)
check(plan["feasible"], "two inlets plan")
# 管段足够, 供给各自受限: 5+5=10, 需求 8 -> 充足
r = plan_capacity_check(NET_TWO_INLETS, [],
                        {"a": 5, "b": 5, "c": 8},
                        {"S1": 5, "S2": 5}, {"H": 8})
check(r["sufficient"] and r["delivered_total"] == 8, "two inlets sufficient")
# 供给 S2 降为 1: 总供给 6 < 8 -> 不足
r = plan_capacity_check(NET_TWO_INLETS, [],
                        {"a": 5, "b": 5, "c": 8},
                        {"S1": 5, "S2": 1}, {"H": 8})
check(not r["sufficient"] and r["delivered_total"] == 6
      and r["shortage_total"] == 2, "two inlets supply bound")
# 管段 c 上限 4: 供给够但出口不够
r = plan_capacity_check(NET_TWO_INLETS, [],
                        {"a": 5, "b": 5, "c": 4},
                        {"S1": 5, "S2": 5}, {"H": 8})
check(not r["sufficient"] and r["delivered_total"] == 4, "two inlets pipe cap")

# 6. 贪心送达量唯一: 编号升序逐个最大化(前序点锁定后本点尽可能多送)
#    s1=10, s2=6: H1 经 s2 最多 6; H2 只能走 s1 剩余 4
r = plan_capacity_check(DEMO_NETWORK, CV,
                        {"s1": 10, "s2": 6, "s3": 10, "s4": 10},
                        SUP, {"H1": 10, "H2": 10})
check(r["delivered_total"] == 10 and r["shortage_total"] == 10,
      "greedy totals")
summary = {ns["node_id"]: ns["delivered"] for ns in r["node_summary"]}
check(summary == {"H1": 6, "H2": 4}, f"greedy order {summary}")
# 再次调用结果一致(确定性)
r2 = plan_capacity_check(DEMO_NETWORK, CV,
                         {"s1": 10, "s2": 6, "s3": 10, "s4": 10},
                         SUP, {"H1": 10, "H2": 10})
check(r2["node_summary"] == r["node_summary"], "deterministic")

# 7. 无必保点: 充足 + 零需求(仍需完整录入未关阀管段与进水点)
NET_NO_KEEP = {
    "nodes": [
        {"id": "S", "role": "inlet"}, {"id": "A", "role": "normal"},
        {"id": "L", "role": "leak"},
    ],
    "segments": [
        {"id": "p1", "endpoint_a": "S", "endpoint_b": "A"},
        {"id": "p2", "endpoint_a": "A", "endpoint_b": "L"},
    ],
    "valves": [{"id": "V1", "segment_id": "p2", "cost": 1}],
}
plan = solve(NET_NO_KEEP)
check(plan["feasible"] and plan["closed_valves"] == ["V1"], "no-keep plan")
r = plan_capacity_check(NET_NO_KEEP, ["V1"], {"p1": 5}, {"S": 9}, {})
check(r["ok"] and r["sufficient"] and r["empty"], "empty flags")
check(r["total_demand"] == 0 and r["delivered_total"] == 0
      and r["shortage_total"] == 0, "empty zeros")
check(r["node_summary"] == [] and r["keep_nodes"] == []
      and r["demands"] == {}, "empty payload")
check("没有必保供水点" in r["message"], "empty message")
# 无必保点时提供需求 -> 多余编号
expect_errors(NET_NO_KEEP, ["V1"], {"p1": 5}, {"S": 9}, {"H": 1},
              ["提供了非必保供水点的需求(多余编号): H"])

# 8. 备援方案上同样可用
NET_FO = {
    "nodes": [
        {"id": "S", "role": "inlet"}, {"id": "M", "role": "normal"},
        {"id": "L", "role": "leak"}, {"id": "H", "role": "must_keep"},
    ],
    "segments": [
        {"id": "p1", "endpoint_a": "S", "endpoint_b": "M"},
        {"id": "p2", "endpoint_a": "M", "endpoint_b": "L"},
        {"id": "p3", "endpoint_a": "S", "endpoint_b": "H"},
    ],
    "valves": [
        {"id": "V1", "segment_id": "p1", "cost": 1},
        {"id": "V2", "segment_id": "p2", "cost": 2},
    ],
}
fo = solve_failover(NET_FO)
check(fo["feasible"] and fo["closed_valves"] == ["V1", "V2"], "failover plan")
# 未关阀管段只有 p3
r = plan_capacity_check(NET_FO, fo["closed_valves"], {"p3": 4},
                        {"S": 10}, {"H": 5})
check(r["open_segment_ids"] == ["p3"], "failover open segments")
check(not r["sufficient"] and r["delivered_total"] == 4
      and r["shortage_total"] == 1, "failover insufficient")

# ---- 录入校验: 编号须与方案快照完整对应 ----
# 缺少/多余管段流量上限(已关阀管段 s5/s6 不属于输水网)
expect_errors(DEMO_NETWORK, CV, {"s1": 1, "s2": 1, "s3": 1}, SUP, DEM,
              ["缺少未关阀管段的流量上限: s4"])
expect_errors(DEMO_NETWORK, CV, {**CAPS, "s5": 1}, SUP, DEM,
              ["提供了非未关阀管段的流量上限(多余编号): s5"])
expect_errors(DEMO_NETWORK, CV, {**CAPS, "zz": 1}, SUP, DEM,
              ["提供了非未关阀管段的流量上限(多余编号): zz"])
# 流量上限非正整数
for bad in [0, -1, 1.5, "5", True, None]:
    expect_errors(DEMO_NETWORK, CV, {**CAPS, "s1": bad}, SUP, DEM,
                  ["管段 s1 的流量上限必须是正整数"])
# 缺少/多余进水点供给上限
expect_errors(DEMO_NETWORK, CV, CAPS, {}, DEM,
              ["缺少进水点的供给上限: S"])
expect_errors(DEMO_NETWORK, CV, CAPS, {"S": 1, "A": 1}, DEM,
              ["提供了非进水点的供给上限(多余编号): A"])
for bad in [0, -2, 1.5, "3", True, None]:
    expect_errors(DEMO_NETWORK, CV, CAPS, {"S": bad}, DEM,
                  ["进水点 S 的供给上限必须是正整数"])
# 缺少/多余必保点需求
expect_errors(DEMO_NETWORK, CV, CAPS, SUP, {"H1": 3},
              ["缺少必保供水点的需求: H2"])
expect_errors(DEMO_NETWORK, CV, CAPS, SUP, {"H1": 3, "H2": 4, "A": 1},
              ["提供了非必保供水点的需求(多余编号): A"])
for bad in [0, -1, 2.5, "7", True, None]:
    expect_errors(DEMO_NETWORK, CV, CAPS, SUP, {"H1": 3, "H2": bad},
                  ["必保点 H2 的需求必须是正整数"])
# 计划阀门不存在于快照
expect_errors(DEMO_NETWORK, ["V9"], CAPS, SUP, DEM,
              ["方案关闭的阀门 V9 不存在于方案快照的管网中"])
# 非对象录入
expect_errors(DEMO_NETWORK, CV, [1, 2], SUP, DEM,
              ["capacities 必须是以管段编号为键的对象"])
expect_errors(DEMO_NETWORK, CV, CAPS, "x", DEM,
              ["supplies 必须是以进水点编号为键的对象"])
expect_errors(DEMO_NETWORK, CV, CAPS, SUP, 5,
              ["demands 必须是以必保供水点编号为键的对象"])

print(f"capacity check tests: {passed} checks passed")
