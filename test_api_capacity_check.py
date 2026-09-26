"""供水容量校核 API 端到端测试: FastAPI TestClient + 临时 SQLite。

重点验证: 独立 API 可用、充足/不足/无必保点三类结果、录入校验 422、
以及**只读**——不修改当前管网、不写入历史方案、不改变原方案。
"""
import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DB_PATH"] = os.path.join(_tmp, "test.db")

import sys  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402

_client_cm = TestClient(main.app)
client = _client_cm.__enter__()  # 进入生命周期: lifespan 建表

ok = 0


def check(cond, msg):
    global ok
    assert cond, "FAIL: " + msg
    ok += 1


# 管网: S(进水) -p1- J -p2- K1(必保); J -p3- K2(必保); J -p4(V1)- L(漏点)
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
CAPS = {"p1": 10, "p2": 4, "p3": 6}
SUP = {"S": 20}
DEM = {"K1": 4, "K2": 6}

# 健康检查
r = client.get("/api/health")
check(r.status_code == 200, "health")

# ---- 可行方案上的容量校核 ----
r = client.post("/api/plan", json=NET)
check(r.status_code == 200, f"plan {r.status_code}")
plan = r.json()
check(plan["feasible"] and plan["closed_valves"] == ["V1"], "plan saved")
pid = plan["id"]
before = client.get(f"/api/plans/{pid}").json()
plans_before = client.get("/api/plans?limit=100").json()["plans"]
net_before = client.get("/api/network").json()

# 充足: 需求 4+6=10, 管段恰好送达 10
r = client.post(f"/api/plans/{pid}/capacity-check",
                json={"segment_capacities": CAPS, "inlet_supplies": SUP,
                      "keep_demands": DEM})
check(r.status_code == 200, f"capacity status {r.status_code} {r.text}")
res = r.json()
check(res["ok"] and res["sufficient"] and not res["empty"], "sufficient flags")
check(res["plan_id"] == pid and res["solver"] == "base", "meta fields")
check(res["closed_valves"] == ["V1"], "closed valves echo")
check(res["open_segment_ids"] == ["p1", "p2", "p3"]
      and res["closed_segment_ids"] == ["p4"], "segment partition")
check(res["total_demand"] == 10 and res["delivered_total"] == 10
      and res["shortage_total"] == 0, "sufficient totals")
check(res["supply_total"] == 20 and res["segment_count"] == 3, "counts")
summary = {ns["node_id"]: ns for ns in res["node_summary"]}
check(summary["K1"]["delivered"] == 4 and summary["K2"]["delivered"] == 6,
      "per-keep delivered")
check("充足" in res["message"] and "只读" in res["message"],
      "sufficient message")

# ---- 只读: 原方案、历史列表、当前管网均未改变 ----
check(client.get(f"/api/plans/{pid}").json() == before, "plan unchanged")
check(client.get("/api/plans?limit=100").json()["plans"] == plans_before,
      "no plan saved by capacity check")
check(client.get("/api/network").json() == net_before, "network untouched")

# ---- 仅连通但容量不足: K1 需求 5 但 p2 上限 4 ----
r = client.post(f"/api/plans/{pid}/capacity-check",
                json={"segment_capacities": CAPS, "inlet_supplies": SUP,
                      "keep_demands": {"K1": 5, "K2": 6}})
check(r.status_code == 200, f"insufficient status {r.status_code}")
res = r.json()
check(not res["ok"] and not res["sufficient"]
      and res["reason_code"] == "INSUFFICIENT_CAPACITY", "insufficient flags")
check(res["total_demand"] == 11 and res["delivered_total"] == 10
      and res["shortage_total"] == 1, "insufficient totals")
summary = {ns["node_id"]: ns for ns in res["node_summary"]}
check(summary["K1"]["delivered"] == 4 and summary["K1"]["shortage"] == 1,
      "K1 capped")
check(summary["K2"]["delivered"] == 6 and summary["K2"]["shortage"] == 0,
      "K2 full")
check("不足" in res["message"], "insufficient message")

# ---- 备援方案上的校核(停水管段 p4 仍属未关阀管段, 需录流量上限) ----
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
r = client.post("/api/plan-failover", json=NET_FO)
fo = r.json()
check(fo["feasible"] and fo["closed_valves"] == ["V1", "V2"], "failover saved")
fid = fo["id"]
r = client.post(f"/api/plans/{fid}/capacity-check",
                json={"segment_capacities": {"p3": 8, "p4": 100},
                      "inlet_supplies": {"S": 10},
                      "keep_demands": {"H": 5}})
check(r.status_code == 200, f"failover capacity {r.status_code}")
res = r.json()
check(res["ok"] and res["sufficient"] and res["solver"] == "failover",
      "failover sufficient")
check(res["open_segment_ids"] == ["p3", "p4"], "dead segment still open")

# ---- 无必保供水点: 充足及零需求 ----
NET_NK = {
    "nodes": [
        {"id": "S", "role": "inlet"},
        {"id": "L", "role": "leak"},
    ],
    "segments": [{"id": "p1", "endpoint_a": "S", "endpoint_b": "L"}],
    "valves": [{"id": "V1", "segment_id": "p1", "cost": 1}],
}
r = client.post("/api/plan", json=NET_NK)
nk = r.json()
check(nk["feasible"], "no-keep plan saved")
nid = nk["id"]
r = client.post(f"/api/plans/{nid}/capacity-check",
                json={"segment_capacities": {}, "inlet_supplies": {"S": 5},
                      "keep_demands": {}})
check(r.status_code == 200, f"empty status {r.status_code}")
res = r.json()
check(res["ok"] and res["sufficient"] and res["empty"], "empty flags")
check(res["total_demand"] == 0 and res["delivered_total"] == 0
      and res["shortage_total"] == 0, "empty zeros")
check(res["node_summary"] == [] and res["keep_nodes"] == [], "empty payload")
check("零需求" in res["message"], "empty message")

# ---- 空请求体: 缺少全部录入 -> 422 ----
r = client.post(f"/api/plans/{pid}/capacity-check", json={})
check(r.status_code == 422, f"empty body 422, got {r.status_code}")
errs = r.json()["detail"]["errors"]
joined = " | ".join(errs)
check("缺少未关阀管段的流量上限" in joined
      and "缺少进水点的供给上限" in joined
      and "缺少必保供水点的需求" in joined, f"empty body errors {errs}")

# ---- 方案不存在 ----
r = client.post("/api/plans/9999/capacity-check",
                json={"segment_capacities": {}, "inlet_supplies": {},
                      "keep_demands": {}})
check(r.status_code == 404, f"404 got {r.status_code}")

# ---- 不可行方案: 不能进行容量校核 ----
BAD = {
    "nodes": [
        {"id": "S", "role": "inlet"}, {"id": "L", "role": "leak"},
        {"id": "H", "role": "must_keep"},
    ],
    "segments": [
        {"id": "p1", "endpoint_a": "S", "endpoint_b": "L"},
        {"id": "p2", "endpoint_a": "S", "endpoint_b": "H"},
    ],
    "valves": [],
}
r = client.post("/api/plan", json=BAD)
bad_plan = r.json()
check(bad_plan["feasible"] is False, "infeasible plan saved")
bad_id = bad_plan["id"]
r = client.post(f"/api/plans/{bad_id}/capacity-check",
                json={"segment_capacities": {}, "inlet_supplies": {},
                      "keep_demands": {}})
check(r.status_code == 422, f"infeasible capacity {r.status_code}")
errs = r.json()["detail"]["errors"]
check(any("不可行" in e and str(bad_id) in e for e in errs),
      f"infeasible msg {errs}")


# ---- 录入校验: 422 + detail.errors ----
def expect_422(body, keys):
    r = client.post(f"/api/plans/{pid}/capacity-check", json=body)
    check(r.status_code == 422,
          f"422 for {keys}: got {r.status_code} {r.text}")
    errs = r.json()["detail"]["errors"]
    joined = " | ".join(errs)
    for key in keys:
        check(key in joined, f"error contains {key!r}; got: {errs}")


FULL = {"segment_capacities": CAPS, "inlet_supplies": SUP,
        "keep_demands": DEM}
# 缺少/多余未关阀管段流量上限
expect_422({**FULL, "segment_capacities": {"p1": 10, "p2": 4}},
           ["缺少未关阀管段的流量上限: p3"])
expect_422({**FULL, "segment_capacities": {**CAPS, "p4": 1}},
           ["提供了非未关阀管段的流量上限(多余编号): p4"])
for bad in [0, -1, 1.5, "5", True, None]:
    expect_422({**FULL,
                "segment_capacities": {"p1": bad, "p2": 4, "p3": 6}},
               ["管段 p1 的流量上限必须是正整数"])
# 缺少/多余进水点供给上限
expect_422({**FULL, "inlet_supplies": {}}, ["缺少进水点的供给上限: S"])
expect_422({**FULL, "inlet_supplies": {"S": 5, "K1": 3}},
           ["提供了非进水点的供给上限(多余编号): K1"])
for bad in [0, -2, 1.5, "5", True, None]:
    expect_422({**FULL, "inlet_supplies": {"S": bad}},
               ["进水点 S 的供给上限必须是正整数"])
# 缺少/多余必保点需求
expect_422({**FULL, "keep_demands": {"K1": 4}},
           ["缺少必保供水点的需求: K2"])
expect_422({**FULL, "keep_demands": {"K1": 4, "K2": 6, "J": 1}},
           ["提供了非必保供水点的需求(多余编号): J"])
for bad in [0, -1, 2.5, "5", True, None]:
    expect_422({**FULL, "keep_demands": {"K1": bad, "K2": 6}},
               ["必保点 K1 的需求必须是正整数"])

# ---- 校核未新增任何历史方案(只读) ----
plans = client.get("/api/plans?limit=100").json()["plans"]
ids = sorted(p["id"] for p in plans)
check(ids == sorted(set([pid, fid, nid, bad_id])), f"plan ids {ids}")

print(f"capacity check API tests: {ok} checks passed")
