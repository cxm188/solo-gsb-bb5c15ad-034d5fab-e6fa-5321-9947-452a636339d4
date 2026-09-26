"""关阀作业备件包采购预览 API 端到端测试: FastAPI TestClient + 临时 SQLite。

重点验证: 独立 API 可用、满足/不足/空清单三类结果、录入校验 422、
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


# 备援方案管网: 计划关闭 V1+V2
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
VD = {"V1": {"gasket": 2, "bolt": 4}, "V2": {"gasket": 1}}
PKGS = [
    {"id": "P1", "price": 10, "contents": {"gasket": 2, "bolt": 2}},
    {"id": "P2", "price": 8, "contents": {"gasket": 1, "bolt": 2}},
    {"id": "P3", "price": 6,
     "contents": {"gasket": 1, "bolt": 2, "nut": 5}},
]

# 健康检查
r = client.get("/api/health")
check(r.status_code == 200, "health")

# ---- 可行方案上的备件采购预览 ----
r = client.post("/api/plan-failover", json=NET_FO)
check(r.status_code == 200, f"failover plan {r.status_code}")
fo = r.json()
check(fo["feasible"] and fo["closed_valves"] == ["V1", "V2"], "failover saved")
pid = fo["id"]
before = client.get(f"/api/plans/{pid}").json()
plans_before = client.get("/api/plans?limit=100").json()["plans"]
net_before = client.get("/api/network").json()

r = client.post(f"/api/plans/{pid}/spare-parts",
                json={"valve_demands": VD, "packages": PKGS})
check(r.status_code == 200, f"spare status {r.status_code} {r.text}")
res = r.json()
check(res["ok"] and res["satisfied"] and not res["empty"], "flags")
check(res["plan_id"] == pid and res["solver"] == "failover", "meta fields")
check(res["closed_valves"] == ["V1", "V2"], "closed valves echo")
check(res["selected_package_ids"] == ["P1", "P3"],
      f"selected {res['selected_package_ids']}")
check(res["total_cost"] == 16, "total cost")
check(res["merged_demands"] == {"bolt": 4, "gasket": 3}, "merged")
check(res["arrived_total"] == 7 and res["total_demand"] == 7
      and res["surplus_total"] == 0 and res["shortage_total"] == 0, "totals")
# 采购清单内容
sel = {p["id"]: p for p in res["selected_packages"]}
check(set(sel) == {"P1", "P3"}, "selected packages set")
check([c for c in sel["P3"]["contents"] if c["part_id"] == "nut"][0]
      ["quantity"] == 5, "P3 nut contents")
# 各类需求/到货/余量
summary = {ps["part_id"]: ps for ps in res["part_summary"]}
check(summary["bolt"]["demand"] == 4 and summary["bolt"]["arrived"] == 4
      and summary["bolt"]["surplus"] == 0 and summary["bolt"]["shortage"] == 0,
      "bolt summary")
check(summary["gasket"]["demand"] == 3 and summary["gasket"]["arrived"] == 3,
      "gasket summary")
# 逐阀明细
details = {d["valve_id"]: d for d in res["valve_demand_details"]}
check([d["valve_id"] for d in res["valve_demand_details"]] == ["V1", "V2"],
      "detail order")
check(details["V1"]["segment_id"] == "p1"
      and details["V1"]["quantity_total"] == 6, "V1 detail")
check(res["combination_count"] == 8
      and res["feasible_combination_count"] == 3, "combo counts")
check("只读" in res["message"], "readonly note")

# ---- 只读: 原方案、历史列表、当前管网均未改变 ----
check(client.get(f"/api/plans/{pid}").json() == before, "plan unchanged")
check(client.get("/api/plans?limit=100").json()["plans"] == plans_before,
      "no plan saved by spare preview")
check(client.get("/api/network").json() == net_before, "network untouched")

# ---- 同价字典序决胜: B、A 同价均可独力完成, 选 A ----
r = client.post(f"/api/plans/{pid}/spare-parts", json={
    "valve_demands": {"V1": {"x": 1}, "V2": {}},
    "packages": [
        {"id": "B", "price": 5, "contents": {"x": 2}},
        {"id": "A", "price": 5, "contents": {"x": 1}},
    ],
})
res = r.json()
check(r.status_code == 200 and res["selected_package_ids"] == ["A"],
      f"tie {res.get('selected_package_ids')}")
check(res["total_cost"] == 5, "tie cost")

# ---- 全部采购包仍不足: 逐类缺口 ----
r = client.post(f"/api/plans/{pid}/spare-parts", json={
    "valve_demands": {"V1": {"x": 5}, "V2": {"y": 2}},
    "packages": [
        {"id": "P1", "price": 3, "contents": {"x": 4}},
    ],
})
check(r.status_code == 200, f"shortage status {r.status_code}")
res = r.json()
check(not res["ok"] and not res["satisfied"]
      and res["reason_code"] == "INSUFFICIENT_PACKAGES", "shortage flags")
check(res["arrived_total"] == 4 and res["shortage_total"] == 3
      and res["total_demand"] == 7, "shortage totals")
check(res["selected_package_ids"] == [] and res["total_cost"] is None,
      "shortage selection/cost")
gaps = {g["part_id"]: g for g in res["shortages"]}
check(gaps["x"]["shortage"] == 1 and gaps["y"]["shortage"] == 2,
      f"gaps {gaps}")
# 不足时仍回显逐阀需求
check(res["valve_demands"] == {"V1": {"x": 5}, "V2": {"y": 2}},
      "shortage valve demands echo")

# ---- 无备件需求: 零费用空清单(不关闭阀门的示例方案也走空清单) ----
r = client.post("/api/plan", json=DEMO_NETWORK)
demo_plan = r.json()
did = demo_plan["id"]
check(demo_plan["closed_valves"] == ["V2", "V4"], "demo closed valves")
r = client.post(f"/api/plans/{did}/spare-parts",
                json={"valve_demands": {"V2": {}, "V4": {}}, "packages": []})
check(r.status_code == 200, f"empty status {r.status_code}")
res = r.json()
check(res["ok"] and res["satisfied"] and res["empty"], "empty flags")
check(res["selected_package_ids"] == [] and res["selected_packages"] == []
      and res["part_summary"] == [], "empty payload")
check(res["total_cost"] == 0 and res["arrived_total"] == 0
      and res["surplus_total"] == 0 and res["shortage_total"] == 0
      and res["total_demand"] == 0, "empty zeros")
check("零费用空清单" in res["message"], "empty message")

# ---- 空请求体: 缺阀门录入 -> 422 ----
r = client.post(f"/api/plans/{pid}/spare-parts", json={})
check(r.status_code == 422, f"missing valve demands should 422, got {r.status_code}")
errs = r.json()["detail"]["errors"]
check(any("缺少计划关闭阀门的备件需求" in e for e in errs),
      f"missing valve demand errors {errs}")

# ---- 方案不存在 ----
r = client.post("/api/plans/9999/spare-parts",
                json={"valve_demands": {}, "packages": []})
check(r.status_code == 404, f"404 got {r.status_code}")

# ---- 不可行方案: 不能做备件采购预览 ----
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
r = client.post(f"/api/plans/{bad_id}/spare-parts",
                json={"valve_demands": {}, "packages": []})
check(r.status_code == 422, f"infeasible spare {r.status_code}")
errs = r.json()["detail"]["errors"]
check(any("不可行" in e and str(bad_id) in e for e in errs),
      f"infeasible msg {errs}")

# ---- 录入校验: 422 + detail.errors ----
def expect_422(body, keys):
    r = client.post(f"/api/plans/{pid}/spare-parts", json=body)
    check(r.status_code == 422, f"422 for {keys}: got {r.status_code} {r.text}")
    errs = r.json()["detail"]["errors"]
    joined = " | ".join(errs)
    for key in keys:
        check(key in joined, f"error contains {key!r}; got: {errs}")


# 缺少阀门录入 / 多余编号 / 非正整数
expect_422({"valve_demands": {"V1": {"x": 1}}, "packages": []},
           ["缺少计划关闭阀门的备件需求: V2"])
expect_422({"valve_demands": {"V1": {}, "V2": {}, "V9": {}}, "packages": []},
           ["提供了非计划关闭阀门的备件需求(多余编号): V9"])
for bad in [0, -1, 1.5, "5", True, None]:
    expect_422({"valve_demands": {"V1": {"x": bad}, "V2": {}}, "packages": []},
               ["阀门 V1 的备件 x 数量必须是正整数"])
# 采购包超 12 个 -> 422 + detail.errors
r = client.post(f"/api/plans/{pid}/spare-parts", json={
    "valve_demands": {"V1": {}, "V2": {}},
    "packages": [{"id": f"P{i}", "price": 1, "contents": {"x": 1}}
                 for i in range(13)],
})
check(r.status_code == 422, f"13 packages 422 got {r.status_code}")
errs = r.json()["detail"]["errors"]
check(any("超过上限 12 个" in e for e in errs), f"13 packages errors {errs}")
# 采购包编号缺失 / 重复
expect_422({"valve_demands": {"V1": {}, "V2": {}},
            "packages": [{"price": 1, "contents": {"x": 1}}]},
           ["采购包 #1: 缺少采购包编号"])
expect_422({"valve_demands": {"V1": {}, "V2": {}}, "packages": [
    {"id": "A", "price": 1, "contents": {"x": 1}},
    {"id": "A", "price": 1, "contents": {"x": 1}}]},
    ["采购包编号重复: A"])
# 价格非法
for bad in [0, -1, 1.5, "5", True, None]:
    expect_422({"valve_demands": {"V1": {}, "V2": {}},
                "packages": [{"id": "A", "price": bad,
                              "contents": {"x": 1}}]},
               ["采购包 A: 价格必须是正整数"])
# 件数为非负整数: 0 合法, 负数/小数等非法
r = client.post(f"/api/plans/{pid}/spare-parts", json={
    "valve_demands": {"V1": {"x": 1}, "V2": {}},
    "packages": [{"id": "A", "price": 1, "contents": {"x": 0}}],
})
check(r.status_code == 200, f"zero qty valid, got {r.status_code} {r.text}")
for bad in [-1, 1.5, "0", True, None]:
    expect_422({"valve_demands": {"V1": {}, "V2": {}},
                "packages": [{"id": "A", "price": 1,
                              "contents": {"x": bad}}]},
               ["采购包 A 的备件 x 件数必须是非负整数"])
# 空 contents
expect_422({"valve_demands": {"V1": {}, "V2": {}},
            "packages": [{"id": "A", "price": 1, "contents": {}}]},
           ["采购包 A: 必须至少列出一种备件"])

# ---- 预览未新增任何历史方案(只读) ----
plans = client.get("/api/plans?limit=100").json()["plans"]
ids = sorted(p["id"] for p in plans)
check(ids == sorted(set([pid, did, bad_id])), f"plan ids {ids}")

print(f"spare parts API tests: {ok} checks passed")
