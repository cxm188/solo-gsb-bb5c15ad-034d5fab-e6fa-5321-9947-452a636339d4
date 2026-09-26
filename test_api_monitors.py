"""失效监测点布设预览 API 端到端测试: FastAPI TestClient + 临时 SQLite。

重点验证: 独立 API 可用、结果字段完整、录入校验 422、以及**只读**——
不修改当前管网、不写入历史方案、不改变原方案。
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


# 双支路管网: 计划关闭 V1+V2 分别隔离漏点 L1、L2
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
CANDS = [
    {"node_id": "A", "cost": 1}, {"node_id": "B", "cost": 1},
    {"node_id": "L1", "cost": 1}, {"node_id": "L2", "cost": 5},
    {"node_id": "H", "cost": 9},
]

# 健康检查
r = client.get("/api/health")
check(r.status_code == 200, "health")

# ---- 常规可行方案上的监测点布设预览 ----
r = client.post("/api/plan", json=NET2)
check(r.status_code == 200, f"plan {r.status_code}")
base = r.json()
check(base["feasible"] and base["closed_valves"] == ["V1", "V2"], "plan saved")
pid = base["id"]
before = client.get(f"/api/plans/{pid}").json()
plans_before = client.get("/api/plans?limit=100").json()["plans"]
net_before = client.get("/api/network").json()

r = client.post(f"/api/plans/{pid}/monitors", json={"candidates": CANDS})
check(r.status_code == 200, f"monitors status {r.status_code} {r.text}")
res = r.json()
check(res["ok"] and res["plan_id"] == pid, "monitors meta")
check(res["solver"] == "base", "monitors solver field")
check(res["closed_valves"] == ["V1", "V2"], "monitors closed valves")
check(res["selected_node_ids"] == ["A", "B"], f"selected {res['selected_node_ids']}")
check(res["selected_points"] == [{"node_id": "A", "cost": 1},
                                 {"node_id": "B", "cost": 1}], "selected detail")
check(res["total_cost"] == 2, "total cost")
check(res["candidate_count"] == 5 and res["scenario_count"] == 3, "counts")
check(res["subset_count"] == 32 and res["distinguishing_subset_count"] == 18,
      "subsets")
scen = res["scenarios"]
check([s["scenario"] for s in scen] == ["normal", "valve_failure", "valve_failure"],
      "scenario kinds")
check(scen[0]["failed_valve"] is None and scen[1]["failed_valve"] == "V1"
      and scen[2]["failed_valve"] == "V2", "failed valves")
check(scen[0]["effective_closed_valves"] == ["V1", "V2"]
      and scen[1]["effective_closed_valves"] == ["V2"], "effective closed")
check(scen[0]["readings"] == [{"node_id": "A", "supplied": False},
                              {"node_id": "B", "supplied": False}], "readings n")
check(scen[1]["readings"] == [{"node_id": "A", "supplied": True},
                              {"node_id": "B", "supplied": False}], "readings v1")
check(scen[2]["readings"] == [{"node_id": "A", "supplied": False},
                              {"node_id": "B", "supplied": True}], "readings v2")
check("只读" in res["message"] and "不修改" in res["message"], "readonly note")

# ---- 只读: 原方案、历史列表、当前管网均未改变 ----
check(client.get(f"/api/plans/{pid}").json() == before, "plan unchanged")
check(client.get("/api/plans?limit=100").json()["plans"] == plans_before,
      "no plan saved by monitors")
check(client.get("/api/network").json() == net_before, "network untouched")

# ---- 备援方案(串联冗余): 正常执行 与 V2 关不上 无法区分 ----
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
r = client.post(f"/api/plans/{fid}/monitors",
                json={"candidates": [{"node_id": "M", "cost": 1},
                                     {"node_id": "X", "cost": 1},
                                     {"node_id": "L", "cost": 1}]})
res = r.json()
check(r.status_code == 200 and res["ok"] is False, "fo not ok")
check(res["reason_code"] == "INDISTINGUISHABLE_SCENARIOS", "fo reason")
check(res["solver"] == "failover" and res["plan_id"] == fid, "fo meta")
pairs = res["indistinguishable_pairs"]
check(len(pairs) == 1 and pairs[0]["a"]["scenario"] == "normal"
      and pairs[0]["b"]["failed_valve"] == "V2", f"fo pairs {pairs}")
check(len(res["scenarios"]) == 3
      and all(len(s["readings"]) == 3 for s in res["scenarios"]),
      "fo readings all candidates")

# ---- 无漏点管网: 方案不关阀, 仅一种情形 -> 空点集 ----
NET_NOLEAK = {
    "nodes": [{"id": "S", "role": "inlet"}, {"id": "H", "role": "must_keep"}],
    "segments": [{"id": "p1", "endpoint_a": "S", "endpoint_b": "H"}],
    "valves": [],
}
r = client.post("/api/plan", json=NET_NOLEAK)
nl = r.json()
check(nl["feasible"] and nl["closed_valves"] == [], "noleak plan saved")
nid = nl["id"]
r = client.post(f"/api/plans/{nid}/monitors",
                json={"candidates": [{"node_id": "H", "cost": 3}]})
res = r.json()
check(r.status_code == 200 and res["ok"], "noleak ok")
check(res["selected_node_ids"] == [] and res["total_cost"] == 0, "noleak empty")
check(res["scenario_count"] == 1, "noleak scenario count")

# ---- 空请求体: 无候选 -> 全部情形对无法区分 ----
r = client.post(f"/api/plans/{pid}/monitors", json={})
res = r.json()
check(r.status_code == 200 and res["ok"] is False, "empty body not ok")
check(len(res["indistinguishable_pairs"]) == 3, "empty body pairs")

# ---- 方案不存在 ----
r = client.post("/api/plans/9999/monitors", json={"candidates": []})
check(r.status_code == 404, f"404 got {r.status_code}")

# ---- 不可行方案: 不能规划监测点布设 ----
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
r = client.post(f"/api/plans/{bad_id}/monitors", json={"candidates": []})
check(r.status_code == 422, f"infeasible monitors {r.status_code}")
errs = r.json()["detail"]["errors"]
check(any("不可行" in e and str(bad_id) in e for e in errs),
      f"infeasible msg {errs}")

# ---- 录入校验: 422 + detail.errors ----
def expect_422(body, keys):
    r = client.post(f"/api/plans/{pid}/monitors", json=body)
    check(r.status_code == 422, f"422 for {keys}: got {r.status_code} {r.text}")
    errs = r.json()["detail"]["errors"]
    joined = " | ".join(errs)
    for key in keys:
        check(key in joined, f"error contains {key!r}; got: {errs}")


# 候选超过 12 个
expect_422({"candidates": [
    {"node_id": "A", "cost": 1}] + [
    {"node_id": n, "cost": 1} for n in ["B", "L1", "L2", "H"] ] + [
    {"node_id": "A", "cost": 1}] * 8}, ["超过上限 12"])
# 编号重复 / 节点不存在 / 进水点 / 缺少节点编号
expect_422({"candidates": [
    {"node_id": "A", "cost": 1}, {"node_id": "A", "cost": 2}]},
    ["监测点编号重复"])
expect_422({"candidates": [{"node_id": "ZZ", "cost": 1}]}, ["不存在于方案快照"])
expect_422({"candidates": [{"node_id": "S", "cost": 1}]},
           ["是进水点, 只能在非进水节点布设"])
expect_422({"candidates": [{"cost": 1}]}, ["缺少节点编号"])
# 布设费非法: 0 / 负 / 小数 / 字符串 / bool / null
for bad in [0, -1, 1.5, "5", True, None]:
    expect_422({"candidates": [{"node_id": "A", "cost": bad}]},
               ["布设费必须是正整数"])

# ---- 监测点预览未新增任何历史方案(只读) ----
plans = client.get("/api/plans?limit=100").json()["plans"]
ids = sorted(p["id"] for p in plans)
check(ids == sorted(set([pid, fid, nid, bad_id])),
      f"plan ids {ids}")

print(f"monitors API tests: {ok} checks passed")
