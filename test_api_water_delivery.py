"""应急送水分配预览 API 端到端测试: FastAPI TestClient + 临时 SQLite。

重点验证: 独立 API 可用、满足/不足/空调度三类结果、录入校验 422、
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
from demo import DEMO_NETWORK  # noqa: E402

_client_cm = TestClient(main.app)
client = _client_cm.__enter__()  # 进入生命周期: lifespan 建表

ok = 0


def check(cond, msg):
    global ok
    assert cond, "FAIL: " + msg
    ok += 1


# 备援方案管网: 关 V1+V2 后普通节点 M,X 断水
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
DEMANDS = {"M": 10, "X": 7}
VEHS = [
    {"id": "T1", "cost": 5, "capacity": 8, "serves": ["M"]},
    {"id": "T2", "cost": 3, "capacity": 8, "serves": ["M", "X"]},
    {"id": "T3", "cost": 4, "capacity": 7, "serves": ["X"]},
]

# 健康检查
r = client.get("/api/health")
check(r.status_code == 200, "health")

# ---- 可行方案上的送水分配预览 ----
r = client.post("/api/plan-failover", json=NET_FO)
check(r.status_code == 200, f"failover plan {r.status_code}")
fo = r.json()
check(fo["feasible"] and fo["closed_valves"] == ["V1", "V2"], "failover saved")
pid = fo["id"]
before = client.get(f"/api/plans/{pid}").json()
plans_before = client.get("/api/plans?limit=100").json()["plans"]
net_before = client.get("/api/network").json()

r = client.post(f"/api/plans/{pid}/water-delivery",
                json={"demands": DEMANDS, "vehicles": VEHS})
check(r.status_code == 200, f"water status {r.status_code} {r.text}")
res = r.json()
check(res["ok"] and res["satisfied"] and not res["empty"], "flags")
check(res["plan_id"] == pid and res["solver"] == "failover", "meta fields")
check(res["closed_valves"] == ["V1", "V2"], "closed valves echo")
check(res["selected_vehicle_ids"] == ["T1", "T2", "T3"],
      f"selected {res['selected_vehicle_ids']}")
check(res["total_cost"] == 12, "total cost")
check(res["delivered_total"] == 17 and res["total_demand"] == 17
      and res["shortage_total"] == 0, "totals")
check(res["deliveries"] == {"T1": {"M": 8, "X": 0},
                            "T2": {"M": 2, "X": 6},
                            "T3": {"M": 0, "X": 1}},
      f"deliveries {res['deliveries']}")
# 配送矩阵: 行按车辆编号升序, 每车载量不超容量, 行合计正确
ids_in_matrix = [row["vehicle_id"] for row in res["delivery_matrix"]]
check(ids_in_matrix == ["T1", "T2", "T3"], "matrix order")
for row in res["delivery_matrix"]:
    v = next(x for x in VEHS if x["id"] == row["vehicle_id"])
    check(row["delivered_total"] == sum(d["amount"] for d in row["deliveries"]),
          f"{row['vehicle_id']} row sum")
    check(row["delivered_total"] <= v["capacity"],
          f"{row['vehicle_id']} capacity")
# 各需求点汇总
summary = {ns["node_id"]: ns for ns in res["node_summary"]}
check(summary["M"]["delivered"] == 10 and summary["M"]["shortage"] == 0,
      "M summary")
check(summary["X"]["delivered"] == 7 and summary["X"]["shortage"] == 0,
      "X summary")
check([n["id"] for n in res["demand_nodes"]] == ["M", "X"], "demand nodes")
check("只读" in res["message"], "readonly note")

# ---- 只读: 原方案、历史列表、当前管网均未改变 ----
check(client.get(f"/api/plans/{pid}").json() == before, "plan unchanged")
check(client.get("/api/plans?limit=100").json()["plans"] == plans_before,
      "no plan saved by water preview")
check(client.get("/api/network").json() == net_before, "network untouched")

# ---- 同费字典序决胜: A、B 单车同费均可独力完成, 选 A ----
r = client.post(f"/api/plans/{pid}/water-delivery", json={
    "demands": DEMANDS,
    "vehicles": [
        {"id": "B", "cost": 5, "capacity": 100, "serves": ["M", "X"]},
        {"id": "A", "cost": 5, "capacity": 100, "serves": ["M", "X"]},
    ],
})
res = r.json()
check(r.status_code == 200 and res["selected_vehicle_ids"] == ["A"],
      f"tie {res.get('selected_vehicle_ids')}")
check(res["total_cost"] == 5, "tie cost")

# ---- 全部候选车无法满足: 最大可配送量 + 总缺口 ----
r = client.post(f"/api/plans/{pid}/water-delivery", json={
    "demands": DEMANDS,
    "vehicles": [
        {"id": "T1", "cost": 5, "capacity": 8, "serves": ["M"]},
    ],
})
check(r.status_code == 200, f"shortage status {r.status_code}")
res = r.json()
check(not res["ok"] and not res["satisfied"]
      and res["reason_code"] == "INSUFFICIENT_CAPACITY", "shortage flags")
check(res["delivered_total"] == 8 and res["shortage_total"] == 9
      and res["total_demand"] == 17, "shortage totals")
check(res["selected_vehicle_ids"] == [] and res["total_cost"] is None,
      "shortage selection/cost")
check(res["used_vehicle_ids"] == ["T1"], "used vehicles")
check(res["deliveries"]["T1"] == {"M": 8, "X": 0}, "shortage matrix")
by_node = {ns["node_id"]: (ns["delivered"], ns["shortage"])
           for ns in res["node_summary"]}
check(by_node == {"M": (8, 2), "X": (0, 7)}, f"shortage nodes {by_node}")

# ---- 无断水需求: 空调度 ----
r = client.post("/api/plan", json=DEMO_NETWORK)
demo_plan = r.json()
did = demo_plan["id"]
r = client.post(f"/api/plans/{did}/water-delivery",
                json={"demands": {}, "vehicles": []})
check(r.status_code == 200, f"empty status {r.status_code}")
res = r.json()
check(res["ok"] and res["satisfied"] and res["empty"], "empty flags")
check(res["selected_vehicle_ids"] == [] and res["deliveries"] == {}
      and res["delivery_matrix"] == [] and res["node_summary"] == [],
      "empty payload")
check(res["total_cost"] == 0 and res["delivered_total"] == 0
      and res["shortage_total"] == 0, "empty zeros")
check("空调度" in res["message"], "empty message")

# ---- 空请求体 ----
r = client.post(f"/api/plans/{pid}/water-delivery", json={})
check(r.status_code == 422, f"missing demands should 422, got {r.status_code}")
errs = r.json()["detail"]["errors"]
check(any("缺少断水需求点的需水量" in e for e in errs),
      f"missing demand errors {errs}")

# ---- 方案不存在 ----
r = client.post("/api/plans/9999/water-delivery",
                json={"demands": {}, "vehicles": []})
check(r.status_code == 404, f"404 got {r.status_code}")

# ---- 不可行方案: 不能做送水分配预览 ----
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
r = client.post(f"/api/plans/{bad_id}/water-delivery",
                json={"demands": {}, "vehicles": []})
check(r.status_code == 422, f"infeasible water {r.status_code}")
errs = r.json()["detail"]["errors"]
check(any("不可行" in e and str(bad_id) in e for e in errs),
      f"infeasible msg {errs}")

# ---- 录入校验: 422 + detail.errors ----
def expect_422(body, keys):
    r = client.post(f"/api/plans/{pid}/water-delivery", json=body)
    check(r.status_code == 422, f"422 for {keys}: got {r.status_code} {r.text}")
    errs = r.json()["detail"]["errors"]
    joined = " | ".join(errs)
    for key in keys:
        check(key in joined, f"error contains {key!r}; got: {errs}")


# 缺少需求点需水量 / 多余编号 / 非正整数
expect_422({"demands": {"M": 10}, "vehicles": []}, ["缺少断水需求点的需水量: X"])
expect_422({"demands": {"M": 10, "X": 7, "H": 3}, "vehicles": []},
           ["提供了非断水普通节点的需水量(多余编号)"])
for bad in [0, -1, 1.5, "5", True, None]:
    expect_422({"demands": {"M": bad, "X": 7}, "vehicles": []},
               ["需求点 M 的需水量必须是正整数"])
# 车辆超过 6 辆 -> 422 + detail.errors(在 solver 中统一校验)
r = client.post(f"/api/plans/{pid}/water-delivery", json={
    "demands": DEMANDS,
    "vehicles": [{"id": f"T{i}", "cost": 1, "capacity": 1, "serves": ["M"]}
                 for i in range(7)],
})
check(r.status_code == 422, f"7 vehicles 422 got {r.status_code}")
errs = r.json()["detail"]["errors"]
check(any("超过上限 6 辆" in e for e in errs), f"7 vehicles errors {errs}")
# 车辆编号缺失 / 重复
expect_422({"demands": DEMANDS,
            "vehicles": [{"cost": 1, "capacity": 1, "serves": ["M"]}]},
           ["缺少车辆编号"])
expect_422({"demands": DEMANDS, "vehicles": [
    {"id": "A", "cost": 1, "capacity": 1, "serves": ["M"]},
    {"id": "A", "cost": 1, "capacity": 1, "serves": ["M"]}]},
    ["车辆编号重复: A"])
# 出车费 / 载水量非法
for bad in [0, -1, 1.5, "5", True, None]:
    expect_422({"demands": DEMANDS, "vehicles": [
        {"id": "A", "cost": bad, "capacity": 1, "serves": ["M"]}]},
        ["出车费必须是正整数"])
    expect_422({"demands": DEMANDS, "vehicles": [
        {"id": "A", "cost": 1, "capacity": bad, "serves": ["M"]}]},
        ["载水量必须是正整数"])
# 可服务点不是断水需求点
expect_422({"demands": DEMANDS, "vehicles": [
    {"id": "A", "cost": 1, "capacity": 1, "serves": ["L"]}]},
    ["可服务点 L 不是本次关阀后断水的普通节点"])
expect_422({"demands": DEMANDS, "vehicles": [
    {"id": "A", "cost": 1, "capacity": 1, "serves": ["ZZ"]}]},
    ["可服务点 ZZ 不是本次关阀后断水的普通节点"])
# serves 非数组
expect_422({"demands": DEMANDS, "vehicles": [
    {"id": "A", "cost": 1, "capacity": 1, "serves": "M"}]},
    ["可服务需求点必须是数组"])

# ---- 预览未新增任何历史方案(只读) ----
plans = client.get("/api/plans?limit=100").json()["plans"]
ids = sorted(p["id"] for p in plans)
check(ids == sorted(set([pid, did, bad_id])), f"plan ids {ids}")

print(f"water delivery API tests: {ok} checks passed")
