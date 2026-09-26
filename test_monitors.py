"""plan_monitors 失效监测点布设预览测试: 目标次序 / 字典序决胜 / 情形对列举 /
录入校验 / 空情形 / 随机暴力对拍。"""
import itertools
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from solver import (  # noqa: E402
    NetworkValidationError, plan_monitors, solve, _Graph, validate_network,
)
from demo import DEMO_NETWORK  # noqa: E402

passed = 0


def check(cond, msg):
    global passed
    assert cond, "FAIL: " + msg
    passed += 1


def expect_errors(snapshot, closed, cands, keys):
    try:
        plan_monitors(snapshot, closed, cands)
    except NetworkValidationError as exc:
        joined = " | ".join(exc.errors)
        for key in keys:
            check(key in joined, f"error contains {key!r}; got: {exc.errors}")
        return
    raise AssertionError("should have raised: " + str(keys))


# ---- 双支路管网: 计划关闭 V1+V2 分别隔离漏点 L1、L2 ----
# S --p1(V1)-- A --p3-- L1(漏点)
# S --p2(V2)-- B --p4-- L2(漏点)
# S --p5----- H(必保)
# 正常执行: A,B,L1,L2 无水; V1 关不上: A,L1 有水; V2 关不上: B,L2 有水。
NET2 = {
    "nodes": [
        {"id": "S", "role": "inlet"},
        {"id": "A", "role": "normal"}, {"id": "B", "role": "normal"},
        {"id": "L1", "role": "leak"}, {"id": "L2", "role": "leak"},
        {"id": "H", "role": "must_keep"},
    ],
    "segments": [
        {"id": "p1", "endpoint_a": "S", "endpoint_b": "A"},
        {"id": "p2", "endpoint_a": "S", "endpoint_b": "B"},
        {"id": "p3", "endpoint_a": "A", "endpoint_b": "L1"},
        {"id": "p4", "endpoint_a": "B", "endpoint_b": "L2"},
        {"id": "p5", "endpoint_a": "S", "endpoint_b": "H"},
    ],
    "valves": [
        {"id": "V1", "segment_id": "p1", "cost": 2},
        {"id": "V2", "segment_id": "p2", "cost": 2},
    ],
}
BASE2 = solve(NET2)
check(BASE2["feasible"] and BASE2["closed_valves"] == ["V1", "V2"],
      f"net2 plan {BASE2.get('closed_valves')}")
CLOSED2 = BASE2["closed_valves"]


def cands2(a=1, b=1, l1=1, l2=5, h=9):
    return [{"node_id": "A", "cost": a}, {"node_id": "B", "cost": b},
            {"node_id": "L1", "cost": l1}, {"node_id": "L2", "cost": l2},
            {"node_id": "H", "cost": h}]


# 1. 基本选取 + 同费字典序: {A,B} 与 {L1,B} 同费 2, 取 ["A","B"]
r = plan_monitors(NET2, CLOSED2, cands2())
check(r["ok"] is True, "net2 ok")
check(r["selected_node_ids"] == ["A", "B"], f"net2 sel {r['selected_node_ids']}")
check(r["selected_points"] == [{"node_id": "A", "cost": 1},
                               {"node_id": "B", "cost": 1}], "net2 points")
check(r["total_cost"] == 2, "net2 cost")
check(r["closed_valves"] == ["V1", "V2"], "net2 closed")
check(r["candidate_count"] == 5 and r["scenario_count"] == 3, "net2 counts")
check(r["subset_count"] == 32, "net2 subsets")
check(r["distinguishing_subset_count"] == 18,
      f"net2 distinguishing {r['distinguishing_subset_count']}")
# 情形读数: 行 = 情形, 列 = 选中点 (A, B)
scen = r["scenarios"]
check([s["scenario"] for s in scen] == ["normal", "valve_failure", "valve_failure"],
      "net2 scenario kinds")
check(scen[0]["failed_valve"] is None
      and scen[1]["failed_valve"] == "V1" and scen[2]["failed_valve"] == "V2",
      "net2 failed valves")
check(scen[0]["effective_closed_valves"] == ["V1", "V2"]
      and scen[1]["effective_closed_valves"] == ["V2"]
      and scen[2]["effective_closed_valves"] == ["V1"], "net2 effective")
check(scen[0]["readings"] == [{"node_id": "A", "supplied": False},
                              {"node_id": "B", "supplied": False}], "net2 r0")
check(scen[1]["readings"] == [{"node_id": "A", "supplied": True},
                              {"node_id": "B", "supplied": False}], "net2 r1")
check(scen[2]["readings"] == [{"node_id": "A", "supplied": False},
                              {"node_id": "B", "supplied": True}], "net2 r2")
sigs = [tuple(x["supplied"] for x in s["readings"]) for s in scen]
check(len(set(sigs)) == 3, "net2 distinct sigs")
check("只读" in r["message"] and "不修改" in r["message"], "net2 readonly msg")

# 2. 费用优先: {L1,L2}=2 优于 {A,L2}=6 等
r = plan_monitors(NET2, CLOSED2, cands2(a=5, b=5, l1=1, l2=1, h=1))
check(r["ok"] and r["selected_node_ids"] == ["L1", "L2"],
      f"net2 cost-first {r['selected_node_ids']}")
check(r["total_cost"] == 2, "net2 cost-first total")

# 3. 四方同费 6: {A,B}/{A,L2}/{L1,B}/{L1,L2} 取字典序最小 ["A","B"]
r = plan_monitors(NET2, CLOSED2, cands2(a=1, b=5, l1=1, l2=5, h=9))
check(r["ok"] and r["selected_node_ids"] == ["A", "B"]
      and r["total_cost"] == 6, f"net2 4-way tie {r['selected_node_ids']}")

# 4. 单点不足: 候选只有 A -> 正常执行 与 V2 关不上 无法区分
r = plan_monitors(NET2, CLOSED2, [{"node_id": "A", "cost": 1}])
check(r["ok"] is False, "net2 A-only not ok")
check(r["reason_code"] == "INDISTINGUISHABLE_SCENARIOS", "net2 A-only code")
pairs = r["indistinguishable_pairs"]
check(len(pairs) == 1, f"net2 A-only pairs {pairs}")
check(pairs[0]["a"]["scenario"] == "normal"
      and pairs[0]["a"]["failed_valve"] is None
      and pairs[0]["b"]["failed_valve"] == "V2", "net2 A-only pair")
check("正常执行" in pairs[0]["a"]["label"]
      and "V2" in pairs[0]["b"]["label"], "net2 A-only labels")
# 失败响应: 各情形在全部候选点上的读数矩阵
check(len(r["scenarios"]) == 3
      and all(len(s["readings"]) == 1 for s in r["scenarios"]),
      "net2 A-only readings all cands")
check(r["scenarios"][0]["readings"] == [{"node_id": "A", "supplied": False}]
      and r["scenarios"][2]["readings"] == [{"node_id": "A", "supplied": False}],
      "net2 A-only identical readings")
check("无法区分" in r["message"] and "候选" in r["message"], "net2 A-only msg")

# 5. 候选只有必保点 H(任何情形都有水) -> 全部 3 对情形都无法区分
r = plan_monitors(NET2, CLOSED2, [{"node_id": "H", "cost": 2}])
check(r["ok"] is False and len(r["indistinguishable_pairs"]) == 3,
      f"net2 H-only pairs {r.get('indistinguishable_pairs')}")
fv = [(p["a"]["failed_valve"], p["b"]["failed_valve"])
      for p in r["indistinguishable_pairs"]]
check(fv == [(None, "V1"), (None, "V2"), ("V1", "V2")],
      f"net2 H-only pair list {fv}")

# 6. 无候选 -> 全部 3 对都无法区分
r = plan_monitors(NET2, CLOSED2, [])
check(r["ok"] is False and len(r["indistinguishable_pairs"]) == 3
      and r["candidate_count"] == 0, "net2 no-cand")

# 7. 方案不关闭任何阀门 -> 仅正常执行一种情形 -> 空点集(费用 0)
NET_NOLEAK = {
    "nodes": [{"id": "S", "role": "inlet"}, {"id": "H", "role": "must_keep"}],
    "segments": [{"id": "p1", "endpoint_a": "S", "endpoint_b": "H"}],
    "valves": [],
}
r = plan_monitors(NET_NOLEAK, [], [{"node_id": "H", "cost": 3}])
check(r["ok"] is True and r["selected_node_ids"] == [], "noleak empty sel")
check(r["total_cost"] == 0 and r["scenario_count"] == 1, "noleak counts")
check(r["subset_count"] == 2 and r["distinguishing_subset_count"] == 2,
      "noleak subsets")
check(r["scenarios"][0]["readings"] == [], "noleak readings empty")
check("无需布设监测点" in r["message"], "noleak msg")

# 8. 备援方案管网(串联冗余): 正常执行 与 V2 关不上 在任何节点读数都相同
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
r = plan_monitors(NET_FO, ["V1", "V2"],
                  [{"node_id": "M", "cost": 1}, {"node_id": "X", "cost": 1},
                   {"node_id": "L", "cost": 1}])
check(r["ok"] is False, "fo not ok")
pairs = r["indistinguishable_pairs"]
check(len(pairs) == 1 and pairs[0]["a"]["scenario"] == "normal"
      and pairs[0]["b"]["failed_valve"] == "V2", f"fo pair {pairs}")

# 9. 示例管网(计划 V2+V4): V2/V4 关不上时都是只有 L 复通 -> 互相无法区分
r = plan_monitors(DEMO_NETWORK, ["V2", "V4"],
                  [{"node_id": "A", "cost": 1}, {"node_id": "B", "cost": 1},
                   {"node_id": "L", "cost": 1}, {"node_id": "H1", "cost": 1},
                   {"node_id": "H2", "cost": 1}])
check(r["ok"] is False, "demo not ok")
pairs = r["indistinguishable_pairs"]
check(len(pairs) == 1 and pairs[0]["a"]["failed_valve"] == "V2"
      and pairs[0]["b"]["failed_valve"] == "V4", f"demo pair {pairs}")
# 但只候选 L 时: 正常执行 与 任一失效 都可区分 -> 只剩 (V2,V4) 一对
check(len(r["scenarios"]) == 3
      and all(len(s["readings"]) == 5 for s in r["scenarios"]),
      "demo readings all cands")

# 10. 三支路管网: 4 种情形, 至少 3 个监测点
NET3 = {
    "nodes": [
        {"id": "S", "role": "inlet"},
        {"id": "A", "role": "normal"}, {"id": "B", "role": "normal"},
        {"id": "C", "role": "normal"},
        {"id": "L1", "role": "leak"}, {"id": "L2", "role": "leak"},
        {"id": "L3", "role": "leak"},
        {"id": "H", "role": "must_keep"},
    ],
    "segments": [
        {"id": "p1", "endpoint_a": "S", "endpoint_b": "A"},
        {"id": "p2", "endpoint_a": "S", "endpoint_b": "B"},
        {"id": "p3", "endpoint_a": "S", "endpoint_b": "C"},
        {"id": "q1", "endpoint_a": "A", "endpoint_b": "L1"},
        {"id": "q2", "endpoint_a": "B", "endpoint_b": "L2"},
        {"id": "q3", "endpoint_a": "C", "endpoint_b": "L3"},
        {"id": "p5", "endpoint_a": "S", "endpoint_b": "H"},
    ],
    "valves": [
        {"id": "V1", "segment_id": "p1", "cost": 1},
        {"id": "V2", "segment_id": "p2", "cost": 1},
        {"id": "V3", "segment_id": "p3", "cost": 1},
    ],
}
BASE3 = solve(NET3)
check(BASE3["feasible"] and BASE3["closed_valves"] == ["V1", "V2", "V3"],
      f"net3 plan {BASE3.get('closed_valves')}")
r = plan_monitors(NET3, BASE3["closed_valves"],
                  [{"node_id": nid, "cost": 1}
                   for nid in ["A", "B", "C", "L1", "L2", "L3", "H"]])
check(r["ok"] and r["selected_node_ids"] == ["A", "B", "C"],
      f"net3 sel {r['selected_node_ids']}")
check(r["total_cost"] == 3 and r["scenario_count"] == 4, "net3 counts")
check(r["subset_count"] == 128 and r["distinguishing_subset_count"] == 54,
      f"net3 subsets {r['distinguishing_subset_count']}")
sigs = [tuple(x["supplied"] for x in s["readings"]) for s in r["scenarios"]]
check(sigs == [(False, False, False), (True, False, False),
               (False, True, False), (False, False, True)],
      f"net3 sigs {sigs}")

# ---- 11. 录入校验 ----
expect_errors(NET2, CLOSED2,
              [{"node_id": f"N{i}", "cost": 1} for i in range(13)],
              ["超过上限 12"])
expect_errors(NET2, CLOSED2, [["A", 1]], ["必须是对象"])
expect_errors(NET2, CLOSED2, [{"cost": 1}], ["缺少节点编号"])
expect_errors(NET2, CLOSED2,
              [{"node_id": "A", "cost": 1}, {"node_id": "A", "cost": 2}],
              ["监测点编号重复: A"])
expect_errors(NET2, CLOSED2, [{"node_id": "ZZ", "cost": 1}],
              ["不存在于方案快照的节点中"])
expect_errors(NET2, CLOSED2, [{"node_id": "S", "cost": 1}],
              ["是进水点, 只能在非进水节点布设"])
for bad in [0, -1, 1.5, "5", True, None]:
    expect_errors(NET2, CLOSED2, [{"node_id": "A", "cost": bad}],
                  ["布设费必须是正整数"])
expect_errors(NET2, ["V9"], [], ["阀门 V9 不存在于方案快照的管网中"])
expect_errors({"nodes": [{"id": "S", "role": "inlet"},
                         {"id": "S", "role": "leak"}],
               "segments": [], "valves": []}, [], [],
              ["方案快照数据不合法"])

# ---- 12. 随机暴力对拍 ----
def brute_monitors(snapshot, closed_valves, cands):
    """直接按定义暴力: 返回 ((cost, ids) 或 None, 无法区分情形对,
    可区分子集数, 各情形可达位掩码, 计划阀门升序)。"""
    nodes, segments, valves = validate_network(snapshot)
    g = _Graph(nodes, segments, valves)
    v_idx = {v["id"]: i for i, v in enumerate(g.valves_sorted)}
    closed = sorted(dict.fromkeys(closed_valves))
    base = 0
    for v in closed:
        base |= 1 << v_idx[v]
    masks = [base] + [base ^ (1 << v_idx[v]) for v in closed]
    feds = [g.reachable(mm, g.inlet_set) for mm in masks]
    m = len(cands)
    nidx = [g.idx[c["node_id"]] for c in cands]
    full_sigs = [tuple(bool((fed >> ni) & 1) for ni in nidx) for fed in feds]
    pairs = [(i, j) for i in range(len(masks)) for j in range(i + 1, len(masks))
             if full_sigs[i] == full_sigs[j]]
    best = None
    dcount = 0
    for s in range(1 << m):
        sel = [j for j in range(m) if (s >> j) & 1]
        sigs = [tuple(full_sigs[si][j] for j in sel) for si in range(len(masks))]
        if len(set(sigs)) != len(sigs):
            continue
        dcount += 1
        cost = sum(cands[j]["cost"] for j in sel)
        ids = tuple(sorted(cands[j]["node_id"] for j in sel))
        key = (cost, ids)
        if best is None or key < best:
            best = key
    return best, pairs, dcount, feds, closed


def random_network(rng):
    n_nodes = rng.randint(2, 8)
    ids = [f"N{i}" for i in range(n_nodes)]
    nodes = [{"id": ids[0], "role": "inlet"}]
    for nid in ids[1:]:
        nodes.append({"id": nid,
                      "role": rng.choice(["leak", "must_keep", "normal"])})
    segments, valves = [], []
    for i, j in itertools.combinations(range(n_nodes), 2):
        if rng.random() >= 0.45:
            continue
        sid = f"p{len(segments)}"
        segments.append({"id": sid, "endpoint_a": ids[i], "endpoint_b": ids[j]})
        if rng.random() < 0.5 and len(valves) < 6:
            valves.append({"id": f"V{len(valves)}", "segment_id": sid,
                           "cost": rng.randint(1, 9)})
    return {"nodes": nodes, "segments": segments, "valves": valves}


rng = random.Random(20260925)
for trial in range(300):
    net = random_network(rng)
    vids = [v["id"] for v in net["valves"]]
    closed = sorted(v for v in vids if rng.random() < 0.6)
    non_inlet = [n["id"] for n in net["nodes"] if n["role"] != "inlet"]
    rng.shuffle(non_inlet)
    cands = [{"node_id": nid, "cost": rng.randint(1, 9)}
             for nid in non_inlet[:rng.randint(0, len(non_inlet))]]
    res = plan_monitors(net, closed, cands)
    best, pairs, dcount, feds, closed_sorted = brute_monitors(net, closed, cands)
    check(res["closed_valves"] == closed_sorted, f"t{trial} closed")
    check(res["scenario_count"] == 1 + len(closed_sorted), f"t{trial} scount")
    check(res["candidate_count"] == len(cands), f"t{trial} ccount")
    if pairs:
        check(res["ok"] is False, f"t{trial} should be indistinguishable")
        fv = [(p["a"]["failed_valve"], p["b"]["failed_valve"])
              for p in res["indistinguishable_pairs"]]
        expect = [(None if i == 0 else closed_sorted[i - 1],
                   None if j == 0 else closed_sorted[j - 1]) for i, j in pairs]
        check(fv == expect, f"t{trial} pairs {fv} != {expect}")
        # 失败响应的读数矩阵覆盖全部候选点(按编号升序), 且与暴力 BFS 一致
        ids_sorted = sorted(c["node_id"] for c in cands)
        for si, sc in enumerate(res["scenarios"]):
            check([x["node_id"] for x in sc["readings"]] == ids_sorted,
                  f"t{trial} fail readings ids")
            for x in sc["readings"]:
                ni = int(x["node_id"][1:])
                check(x["supplied"] == bool((feds[si] >> ni) & 1),
                      f"t{trial} fail reading value")
    else:
        check(res["ok"] is True, f"t{trial} should be ok")
        check(res["subset_count"] == 1 << len(cands), f"t{trial} subsets")
        check(tuple(res["selected_node_ids"]) == best[1],
              f"t{trial} sel {res['selected_node_ids']} != {best[1]}")
        check(res["total_cost"] == best[0], f"t{trial} cost")
        check(res["distinguishing_subset_count"] == dcount, f"t{trial} dcount")
        check(sum(p["cost"] for p in res["selected_points"]) == res["total_cost"],
              f"t{trial} cost sum")
        check([p["node_id"] for p in res["selected_points"]]
              == res["selected_node_ids"], f"t{trial} points order")
        # 选中点读数与暴力 BFS 一致, 且任意两情形读数不同
        sigs = []
        for si, sc in enumerate(res["scenarios"]):
            sig = []
            for x in sc["readings"]:
                ni = int(x["node_id"][1:])
                val = bool((feds[si] >> ni) & 1)
                check(x["supplied"] == val, f"t{trial} reading value")
                sig.append(val)
            sigs.append(tuple(sig))
        check(len(set(sigs)) == len(sigs), f"t{trial} distinct readings")

print(f"monitors solver tests: {passed} checks passed")
