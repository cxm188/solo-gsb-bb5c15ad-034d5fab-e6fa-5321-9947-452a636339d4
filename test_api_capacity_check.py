"""供水容量校核 API 端到端测试: FastAPI TestClient + 临时 SQLite。

重点验证: 独立 API 可用、充足/不足/无必保点三类结果、录入编号与方案快照
完整对应校验 422、以及**只读**——不修改当前管网、不写入历史方案、不改变
原方案。
"""
import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DB_PATH"] = os.path.join(_tmp, "test.db")

import sys  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402
from demo import DEMO_NETWORK  # noqa: E402

_client_cm = TestClient(main.app)
client = _client_cm.__enter__()  # 进入生命周期: lifespan 建表

ok = 0


def check(cond, msg):
    global ok
    assert cond, "FAIL: " + msg
    ok += 1


# 健康检查
r = client.get("/api/health")
check(r.status_code == 200, "health")

# ---- 示例管网常规方案: 关 V2+V4, 未关阀管段 s1..s4, 必保点 H1,H2 ----
r = client.post("/api/plan", json=DEMO_NETWORK)
check(r.status_code == 200, f"plan {r.status_code}")
plan = r.json()
check(plan["feasible"] and plan["closed_valves"] == ["V2", "V4"], "plan saved")
pid = plan["id"]
before = client.get(f"/api/plans/{pid}").json()
plans_before = client.get("/api/plans?limit=100").json()["plans"]
net_before = client.get("/api/network").json()

CAPS = {"s1": 10, "s2": 3, "s3": 10, "s4": 4}
SUP = {"S": 100}
DEM = {"H1": 3, "H2": 4}
BODY = {"capacities": CAPS, "supplies": SUP, "demands": DEM}

# ---- 容量充足 ----
r = client.post(f"/api/plans/{pid}/capacity-check", json=BODY)
check(r.status_code == 200, f"capacity status {r.status_code} {r.text}")
res = r.json()
check(res["ok"] and res["sufficient"] and not res["empty"], "flags")
check(res["plan_id"] == pid and res["solver"] == "base", "meta fields")
check(res["closed_valves"] == ["V2", "V4"], "closed echo")
check(res["total_demand"] == 7 and res["delivered_total"] == 7
      and res["shortage_total"] == 0, "totals")
summary = {ns["node_id"]: ns for ns in res["node_summary"]}
check(summary["H1"]["delivered"] == 3 and summary["H2"]["delivered"] == 4,
      "per-node delivered")
check(res["open_segment_ids"] == ["s1", "s2", "s3", "s4"], "open segments")
check(res["capacities"] == CAPS and res["supplies"] == SUP
      and res["demands"] == DEM, "echoes")
check("只读" in res["message"], "readonly note")

# ---- 只读: 原方案、历史列表、当前管网均未改变 ----
check(client.get(f"/api/plans/{pid}").json() == before, "plan unchanged")
check(client.get("/api/plans?limit=100").json()["plans"] == plans_before,
      "no plan saved by capacity check")
check(client.get("/api/network").json() == net_before, "network untouched")

# ---- 仅连通但容量不足: 干管 s1 上限 5 ----
r = client.post(f"/api/plans/{pid}/capacity-check", json={
    "capacities": {"s1": 5, "s2": 3, "s3": 10, "s4": 4},
    "supplies": SUP, "demands": DEM,
})
check(r.status_code == 200, f"insufficient status {r.status_code}")
res = r.json()
check(res["ok"] and not res["sufficient"], "insufficient flags")
check(res["delivered_total"] == 5 and res["shortage_total"] == 2
      and res["total_demand"] == 7, "insufficient totals")
summary = {ns["node_id"]: (ns["delivered"], ns["shortage"])
           for ns in res["node_summary"]}
check(summary == {"H1": (3, 0), "H2": (2, 2)},
      f"insufficient per-node {summary}")
check("不足" in res["message"], "insufficient message")

# ---- 无必保点: 充足 + 零需求 ----
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
r = client.post("/api/plan", json=NET_NO_KEEP)
nk = r.json()
check(nk["feasible"] and nk["closed_valves"] == ["V1"], "no-keep plan saved")
nkid = nk["id"]
r = client.post(f"/api/plans/{nkid}/capacity-check",
                json={"capacities": {"p1": 5}, "supplies": {"S": 9},
                      "demands": {}})
check(r.status_code == 200, f"empty status {r.status_code}")
res = r.json()
check(res["ok"] and res["sufficient"] and res["empty"], "empty flags")
check(res["total_demand"] == 0 and res["delivered_total"] == 0
      and res["shortage_total"] == 0, "empty zeros")
check(res["node_summary"] == [] and res["demands"] == {}, "empty payload")
check("没有必保供水点" in res["message"], "empty message")

# ---- 空请求体: 缺少全部录入 -> 422 ----
r = client.post(f"/api/plans/{pid}/capacity-check", json={})
check(r.status_code == 422, f"empty body 422, got {r.status_code}")
errs = r.json()["detail"]["errors"]
joined = " | ".join(errs)
check("缺少未关阀管段的流量上限" in joined
      and "缺少进水点的供给上限" in joined
      and "缺少必保供水点的需求" in joined, f"empty body errors {errs}")

# ---- 方案不存在 ----
r = client.post("/api/plans/9999/capacity-check", json=BODY)
check(r.status_code == 404, f"404 got {r.status_code}")

# ---- 不可行方案: 不能做容量校核 ----
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
r = client.post(f"/api/plans/{bad_id}/capacity-check", json=BODY)
check(r.status_code == 422, f"infeasible capacity {r.status_code}")
errs = r.json()["detail"]["errors"]
check(any("不可行" in e and str(bad_id) in e for e in errs),
      f"infeasible msg {errs}")


# ---- 录入校验: 422 + detail.errors ----
def expect_422(body, keys):
    r = client.post(f"/api/plans/{pid}/capacity-check", json=body)
    check(r.status_code == 422, f"422 for {keys}: got {r.status_code} {r.text}")
    errs = r.json()["detail"]["errors"]
    joined = " | ".join(errs)
    for key in keys:
        check(key in joined, f"error contains {key!r}; got: {errs}")


# 缺少/多余管段流量上限(已关阀管段 s5 不属于输水网)
expect_422({"capacities": {"s1": 1, "s2": 1, "s3": 1},
            "supplies": SUP, "demands": DEM},
           ["缺少未关阀管段的流量上限: s4"])
expect_422({"capacities": {**CAPS, "s5": 1}, "supplies": SUP, "demands": DEM},
           ["提供了非未关阀管段的流量上限(多余编号): s5"])
# 流量上限非正整数
for bad in [0, -1, 1.5, "5", True, None]:
    expect_422({"capacities": {**CAPS, "s1": bad},
                "supplies": SUP, "demands": DEM},
               ["管段 s1 的流量上限必须是正整数"])
# 缺少/多余进水点供给上限
expect_422({"capacities": CAPS, "supplies": {}, "demands": DEM},
           ["缺少进水点的供给上限: S"])
expect_422({"capacities": CAPS, "supplies": {"S": 1, "A": 1}, "demands": DEM},
           ["提供了非进水点的供给上限(多余编号): A"])
for bad in [0, -1, 1.5, "5", True, None]:
    expect_422({"capacities": CAPS, "supplies": {"S": bad}, "demands": DEM},
               ["进水点 S 的供给上限必须是正整数"])
# 缺少/多余必保点需求
expect_422({"capacities": CAPS, "supplies": SUP, "demands": {"H1": 3}},
           ["缺少必保供水点的需求: H2"])
expect_422({"capacities": CAPS, "supplies": SUP,
            "demands": {"H1": 3, "H2": 4, "A": 1}},
           ["提供了非必保供水点的需求(多余编号): A"])
for bad in [0, -1, 1.5, "5", True, None]:
    expect_422({"capacities": CAPS, "supplies": SUP,
                "demands": {"H1": 3, "H2": bad}},
               ["必保点 H2 的需求必须是正整数"])

# ---- 校核未新增任何历史方案(只读) ----
plans = client.get("/api/plans?limit=100").json()["plans"]
ids = sorted(p["id"] for p in plans)
check(ids == sorted(set([pid, nkid, bad_id])), f"plan ids {ids}")

print(f"capacity check API tests: {ok} checks passed")
