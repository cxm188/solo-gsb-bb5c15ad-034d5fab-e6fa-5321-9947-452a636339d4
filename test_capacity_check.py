"""plan_capacity_check 供水容量校核测试。

覆盖: 整数最大流(未关阀管段双向容量/进水点供给上限/必保点需求)、
充足判定(总送达量等于总需求才充足)、仅连通但容量不足、管段净流量
绝对值受同一上限约束、各必保点实际送达量、无必保点充足零需求、
录入编号与方案快照完整对应校验。
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


def expect_errors(snapshot, closed, caps, sups, dems, keys):
    try:
        plan_capacity_check(snapshot, closed, caps, sups, dems)
    except NetworkValidationError as exc:
        joined = " | ".join(exc.errors)
        for key in keys:
            check(key in joined, f"error contains {key!r}; got: {exc.errors}")
        return
    raise AssertionError("should have raised: " + str(keys))


# ---- 管网: S(进水) -p1- J -p2- K1(必保); J -p3- K2(必保); J -p4(V1)- L(漏点) ----
NET = {
    "nodes": [
        {"id": "S", "role": "inlet"},
        {"id": "J", "role": "normal"},
        {"id": "K1", "role": "must_keep"},
        {"id": "K2", "role": "must_keep"},
        {"id": "L", "role": "leak"},
    ],
    "segments": [
        {"id": "p1", "endpoint_a": "S", "endpoint_b": "J"},
        {"id": "p2", "endpoint_a": "J", "endpoint_b": "K1"},
        {"id": "p3", "endpoint_a": "J", "endpoint_b": "K2"},
        {"id": "p4", "endpoint_a": "J", "endpoint_b": "L"},
    ],
    "valves": [{"id": "V1", "segment_id": "p4", "cost": 1}],
}
PLAN = solve(NET)
check(PLAN["feasible"] and PLAN["closed_valves"] == ["V1"], "base plan")
CV = PLAN["closed_valves"]
CAPS = {"p1": 10, "p2": 4, "p3": 6}
SUP = {"S": 20}

# 1. 容量充足: 需求 4+6=10, 管段恰好送达 10
r = plan_capacity_check(NET, CV, CAPS, SUP, {"K1": 4, "K2": 6})
check(r["ok"] and r["sufficient"] and not r["empty"], "sufficient flags")
check("reason_code" not in r, "sufficient has no reason_code")
check(r["total_demand"] == 10 and r["delivered_total"] == 10
      and r["shortage_total"] == 0, "sufficient totals")
summary = {ns["node_id"]: ns for ns in r["node_summary"]}
check(summary["K1"]["delivered"] == 4 and summary["K1"]["shortage"] == 0,
      "K1 delivered")
check(summary["K2"]["delivered"] == 6 and summary["K2"]["shortage"] == 0,
      "K2 delivered")
check(r["open_segment_ids"] == ["p1", "p2", "p3"]
      and r["closed_segment_ids"] == ["p4"], "segment partition")
check(r["segment_capacities"] == CAPS and r["inlet_supplies"] == SUP
      and r["keep_demands"] == {"K1": 4, "K2": 6}, "echo inputs")
check(r["segment_count"] == 3 and r["supply_total"] == 20, "counts")
check([n["id"] for n in r["inlet_nodes"]] == ["S"]
      and [n["id"] for n in r["keep_nodes"]] == ["K1", "K2"], "node lists")
check("充足" in r["message"] and "只读" in r["message"], "sufficient message")

# 2. 管段容量不足: K1 需求 5 但 p2 上限 4 -> 仅连通但容量不足
r = plan_capacity_check(NET, CV, CAPS, SUP, {"K1": 5, "K2": 6})
check(not r["ok"] and not r["sufficient"]
      and r["reason_code"] == "INSUFFICIENT_CAPACITY", "insufficient flags")
check(r["total_demand"] == 11 and r["delivered_total"] == 10
      and r["shortage_total"] == 1, "insufficient totals")
summary = {ns["node_id"]: ns for ns in r["node_summary"]}
check(summary["K1"]["delivered"] == 4 and summary["K1"]["shortage"] == 1,
      "K1 capped by pipe p2")
check(summary["K2"]["delivered"] == 6 and summary["K2"]["shortage"] == 0,
      "K2 full")
check("不足" in r["message"] and "连通" in r["message"], "insufficient message")

# 3. 进水点供给上限约束: 供给 5 < 需求 10 -> 送达 5
r = plan_capacity_check(NET, CV, CAPS, {"S": 5}, {"K1": 4, "K2": 6})
check(not r["sufficient"] and r["delivered_total"] == 5
      and r["shortage_total"] == 5, "supply limited totals")
summary = {ns["node_id"]: ns for ns in r["node_summary"]}
check(summary["K1"]["delivered"] + summary["K2"]["delivered"] == 5,
      "supply split sums to 5")
check(r["supply_total"] == 5, "supply total")

# 4. 干管共享容量: p1=7 限制两必保点合计送达
r = plan_capacity_check(NET, CV, {"p1": 7, "p2": 10, "p3": 10}, SUP,
                        {"K1": 5, "K2": 5})
check(r["delivered_total"] == 7 and r["shortage_total"] == 3,
      "trunk shared capacity")

# 5. 无向管段净流量绝对值受同一上限约束:
#    S-q1-K(2), S-q2-A(5), A-q3-K(5); 需求 9 -> 最多送达 2+5=7
#    (q1 正反两个方向合计净流量不能超过 2, 而不是各方向各 2)
NET2 = {
    "nodes": [
        {"id": "S", "role": "inlet"},
        {"id": "A", "role": "normal"},
        {"id": "K", "role": "must_keep"},
    ],
    "segments": [
        {"id": "q1", "endpoint_a": "S", "endpoint_b": "K"},
        {"id": "q2", "endpoint_a": "S", "endpoint_b": "A"},
        {"id": "q3", "endpoint_a": "A", "endpoint_b": "K"},
    ],
    "valves": [],
}
PLAN2 = solve(NET2)
check(PLAN2["feasible"] and PLAN2["closed_valves"] == [], "no-valve plan")
r = plan_capacity_check(NET2, [], {"q1": 2, "q2": 5, "q3": 5}, {"S": 20},
                        {"K": 9})
check(not r["sufficient"] and r["delivered_total"] == 7
      and r["shortage_total"] == 2, "undirected net flow bound")
check(r["node_summary"][0]["delivered"] == 7, "K delivered 7")
r = plan_capacity_check(NET2, [], {"q1": 2, "q2": 5, "q3": 5}, {"S": 20},
                        {"K": 7})
check(r["ok"] and r["sufficient"] and r["delivered_total"] == 7,
      "demand 7 exactly sufficient")

# 6. 无必保供水点: 充足及零需求
NET_NK = {
    "nodes": [
        {"id": "S", "role": "inlet"},
        {"id": "L", "role": "leak"},
    ],
    "segments": [{"id": "p1", "endpoint_a": "S", "endpoint_b": "L"}],
    "valves": [{"id": "V1", "segment_id": "p1", "cost": 1}],
}
PLAN_NK = solve(NET_NK)
check(PLAN_NK["feasible"] and PLAN_NK["closed_valves"] == ["V1"],
      "no-keep plan")
r = plan_capacity_check(NET_NK, ["V1"], {}, {"S": 5}, {})
check(r["ok"] and r["sufficient"] and r["empty"], "empty flags")
check(r["total_demand"] == 0 and r["delivered_total"] == 0
      and r["shortage_total"] == 0, "empty zeros")
check(r["node_summary"] == [] and r["keep_nodes"] == []
      and r["open_segment_ids"] == [], "empty payload")
check("零需求" in r["message"] and "只读" in r["message"], "empty message")
# 无必保点时提供需求 -> 多余编号 422
expect_errors(NET_NK, ["V1"], {}, {"S": 5}, {"K": 1},
              ["提供了非必保供水点的需求(多余编号): K"])

# 7. 备援方案上的校核: 关 V1+V2 后 p4(M-X) 为停水但未关阀管段, 仍需流量上限
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
check(FO["feasible"] and FO["closed_valves"] == ["V1", "V2"], "failover plan")
r = plan_capacity_check(NET_FO, FO["closed_valves"],
                        {"p3": 3, "p4": 100}, {"S": 10}, {"H": 5})
check(r["open_segment_ids"] == ["p3", "p4"]
      and r["closed_segment_ids"] == ["p1", "p2"],
      "dead segment p4 still in open network")
check(not r["sufficient"] and r["delivered_total"] == 3
      and r["shortage_total"] == 2, "failover insufficient via p3 cap")
check(r["node_summary"][0]["node_id"] == "H"
      and r["node_summary"][0]["delivered"] == 3, "H delivered 3")
r = plan_capacity_check(NET_FO, FO["closed_valves"],
                        {"p3": 8, "p4": 100}, {"S": 10}, {"H": 5})
check(r["ok"] and r["sufficient"] and r["delivered_total"] == 5,
      "failover sufficient")

# 8. 示例管网: 关 V2+V4 后 s1..s4 未关阀
DEMO = solve(DEMO_NETWORK)
check(DEMO["feasible"] and DEMO["closed_valves"] == ["V2", "V4"], "demo plan")
demo_caps = {"s1": 10, "s2": 3, "s3": 4, "s4": 5}
r = plan_capacity_check(DEMO_NETWORK, DEMO["closed_valves"], demo_caps,
                        {"S": 20}, {"H1": 3, "H2": 5})
check(not r["sufficient"] and r["delivered_total"] == 7
      and r["shortage_total"] == 1, "demo insufficient totals")
summary = {ns["node_id"]: ns for ns in r["node_summary"]}
check(summary["H1"]["delivered"] == 3 and summary["H2"]["delivered"] == 4,
      "demo per-keep delivered")
r = plan_capacity_check(DEMO_NETWORK, DEMO["closed_valves"],
                        {"s1": 10, "s2": 5, "s3": 6, "s4": 5}, {"S": 20},
                        {"H1": 3, "H2": 5})
check(r["ok"] and r["sufficient"] and r["delivered_total"] == 8,
      "demo sufficient")

# ---- 录入校验: 编号须与方案快照完整对应, 值为正整数 ----
DEM = {"K1": 4, "K2": 6}
# 缺少/多余未关阀管段流量上限(已关阀管段 p4 与不存在的 pz 都算多余)
expect_errors(NET, CV, {"p1": 10, "p2": 4}, SUP, DEM,
              ["缺少未关阀管段的流量上限: p3"])
expect_errors(NET, CV, {**CAPS, "p4": 1}, SUP, DEM,
              ["提供了非未关阀管段的流量上限(多余编号): p4"])
expect_errors(NET, CV, {**CAPS, "pz": 1}, SUP, DEM,
              ["提供了非未关阀管段的流量上限(多余编号): pz"])
for bad in [0, -1, 1.5, "5", True, None]:
    expect_errors(NET, CV, {"p1": bad, "p2": 4, "p3": 6}, SUP, DEM,
                  ["管段 p1 的流量上限必须是正整数"])
# 缺少/多余进水点供给上限
expect_errors(NET, CV, CAPS, {}, DEM, ["缺少进水点的供给上限: S"])
expect_errors(NET, CV, CAPS, {"S": 5, "J": 3}, DEM,
              ["提供了非进水点的供给上限(多余编号): J"])
for bad in [0, -2, 1.5, "5", True, None]:
    expect_errors(NET, CV, CAPS, {"S": bad}, DEM,
                  ["进水点 S 的供给上限必须是正整数"])
# 缺少/多余必保点需求
expect_errors(NET, CV, CAPS, SUP, {"K1": 4},
              ["缺少必保供水点的需求: K2"])
expect_errors(NET, CV, CAPS, SUP, {"K1": 4, "K2": 6, "J": 1},
              ["提供了非必保供水点的需求(多余编号): J"])
for bad in [0, -1, 2.5, "5", True, None]:
    expect_errors(NET, CV, CAPS, SUP, {"K1": bad, "K2": 6},
                  ["必保点 K1 的需求必须是正整数"])
# 非对象录入
expect_errors(NET, CV, [1, 2], SUP, DEM,
              ["segment_capacities 必须是以管段编号为键的对象"])
expect_errors(NET, CV, CAPS, "x", DEM,
              ["inlet_supplies 必须是以进水点编号为键的对象"])
expect_errors(NET, CV, CAPS, SUP, 5,
              ["keep_demands 必须是以必保供水点编号为键的对象"])
# 计划阀门不存在于快照
expect_errors(NET, ["V9"], CAPS, SUP, DEM,
              ["方案关闭的阀门 V9 不存在于方案快照的管网中"])

print(f"capacity check solver tests: {passed} checks passed")
