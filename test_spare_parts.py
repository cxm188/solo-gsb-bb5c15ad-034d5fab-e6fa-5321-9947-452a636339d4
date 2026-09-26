"""plan_spare_parts 关阀作业备件包采购预览测试。

覆盖: 逐阀需求合并、枚举采购包组合、最低总价、同价采购包编号升序列表
字典序决胜、非负整数件数与余量、不足时逐类缺口、无关阀需求空清单、
录入校验。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from solver import (  # noqa: E402
    NetworkValidationError, plan_spare_parts, solve_failover,
)

passed = 0


def check(cond, msg):
    global passed
    assert cond, "FAIL: " + msg
    passed += 1


def expect_errors(snapshot, closed, valve_demands, packages, keys):
    try:
        plan_spare_parts(snapshot, closed, valve_demands, packages)
    except NetworkValidationError as exc:
        joined = " | ".join(exc.errors)
        for key in keys:
            check(key in joined, f"error contains {key!r}; got: {exc.errors}")
        return
    raise AssertionError("should have raised: " + str(keys))


# ---- 备援方案管网: 计划关闭 V1, V2 ----
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

# 1. 基本覆盖: 合并需求 gasket=3, bolt=4; 可行组合 P1+P2(18)/P1+P3(16)/三包
VD = {"V1": {"gasket": 2, "bolt": 4}, "V2": {"gasket": 1}}
PKGS = [
    {"id": "P1", "price": 10, "contents": {"gasket": 2, "bolt": 2}},
    {"id": "P2", "price": 8, "contents": {"gasket": 1, "bolt": 2}},
    {"id": "P3", "price": 6,
     "contents": {"gasket": 1, "bolt": 2, "nut": 5}},
]
r = plan_spare_parts(NET_FO, CV, VD, PKGS)
check(r["ok"] and r["satisfied"] and not r["empty"], "satisfied flags")
check(r["selected_package_ids"] == ["P1", "P3"],
      f"selected {r['selected_package_ids']}")
check(r["total_cost"] == 16, "total cost")
check(r["combination_count"] == 8
      and r["feasible_combination_count"] == 3, "combination counts")
check(r["merged_demands"] == {"bolt": 4, "gasket": 3}, "merged demands")
check(r["part_ids"] == ["bolt", "gasket"], "part ids sorted")
check(r["total_demand"] == 7 and r["arrived_total"] == 7
      and r["surplus_total"] == 0 and r["shortage_total"] == 0, "totals")
summary = {ps["part_id"]: ps for ps in r["part_summary"]}
check(summary["bolt"] == {"part_id": "bolt", "demand": 4, "arrived": 4,
                          "surplus": 0, "shortage": 0}, "bolt summary")
check(summary["gasket"] == {"part_id": "gasket", "demand": 3, "arrived": 3,
                            "surplus": 0, "shortage": 0}, "gasket summary")
# 非需求种类 nut 不在 part_summary(余量只统计需求种类), 但在采购清单回显
check("nut" not in summary, "extra type excluded from summary")
p3 = next(p for p in r["selected_packages"] if p["id"] == "P3")
check([c for c in p3["contents"] if c["part_id"] == "nut"][0]["quantity"] == 5,
      "extra type echoed in package contents")
# 逐阀明细: 编号升序, 各类按种类名升序
check([d["valve_id"] for d in r["valve_demand_details"]] == ["V1", "V2"],
      "valve detail order")
v1 = r["valve_demand_details"][0]
check(v1["segment_id"] == "p1"
      and [p["part_id"] for p in v1["parts"]] == ["bolt", "gasket"]
      and v1["quantity_total"] == 6, "V1 detail")
v2 = r["valve_demand_details"][1]
check(v2["parts"] == [{"part_id": "gasket", "quantity": 1}]
      and v2["quantity_total"] == 1 and v2["part_count"] == 1, "V2 detail")
check(r["valve_demands"] == {"V1": {"gasket": 2, "bolt": 4}, "V2": {"gasket": 1}},
      "valve demands echo")
check("只读" in r["message"], "readonly note")

# 2. 最低总价: 单包贵但可独力完成; 两个便宜包合起来更省
r = plan_spare_parts(NET_FO, CV, {"V1": {"x": 10}, "V2": {}}, [
    {"id": "Q9", "price": 9, "contents": {"x": 100}},
    {"id": "A", "price": 3, "contents": {"x": 6}},
    {"id": "B", "price": 3, "contents": {"x": 4}},
])
check(r["satisfied"] and r["selected_package_ids"] == ["A", "B"],
      f"cheapest combo {r['selected_package_ids']}")
check(r["total_cost"] == 6, "cheapest cost")

# 3. 同价决胜: A、B 单车同价均可独力完成, 取编号小的 A(与录入顺序无关)
r = plan_spare_parts(NET_FO, CV, {"V1": {"x": 1}, "V2": {}}, [
    {"id": "B", "price": 5, "contents": {"x": 2}},
    {"id": "A", "price": 5, "contents": {"x": 1}},
])
check(r["selected_package_ids"] == ["A"], f"tie {r['selected_package_ids']}")
check(r["total_cost"] == 5 and r["feasible_combination_count"] == 3,
      "tie cost/count")
check(r["surplus_total"] == 0, "A exact, no surplus")

# 4. 同价不同组合: 捆绑包使 [A,B] 与 [C,D] 同为最低总价 8, 取字典序小的
#    [A,B](交叉组合如 A+C 各缺一类, 不可行; 单包也都无法覆盖)
r = plan_spare_parts(NET_FO, CV, {"V1": {"a": 2, "b": 2}, "V2": {}}, [
    {"id": "B", "price": 4, "contents": {"a": 1, "b": 1}},
    {"id": "C", "price": 4, "contents": {"a": 2}},
    {"id": "A", "price": 4, "contents": {"a": 1, "b": 1}},
    {"id": "D", "price": 4, "contents": {"b": 2}},
])
check(r["selected_package_ids"] == ["A", "B"],
      f"lex combo {r['selected_package_ids']}")
check(r["total_cost"] == 8, "lex combo cost")

# 5. 非负整数件数: 0 件允许; 覆盖时产生需求种类的到货余量
r = plan_spare_parts(NET_FO, CV, {"V1": {"x": 2}, "V2": {}}, [
    {"id": "A", "price": 5, "contents": {"x": 0, "y": 3}},
    {"id": "B", "price": 4, "contents": {"x": 3}},
])
check(r["satisfied"] and r["selected_package_ids"] == ["B"], "zero qty package")
check(r["surplus_total"] == 1 and r["arrived_total"] == 3, "surplus of demanded")
sx = next(ps for ps in r["part_summary"] if ps["part_id"] == "x")
check(sx["arrived"] == 3 and sx["surplus"] == 1 and sx["shortage"] == 0,
      "surplus summary")

# 6. 全部包仍不足: 逐类缺口, 不产生方案
r = plan_spare_parts(NET_FO, CV, {"V1": {"x": 5, "bolt": 1}, "V2": {"y": 2}}, [
    {"id": "P1", "price": 3, "contents": {"x": 4}},
    {"id": "P2", "price": 2, "contents": {"x": 0, "bolt": 1}},
])
check(not r["ok"] and r["reason_code"] == "INSUFFICIENT_PACKAGES",
      "shortage flags")
check(r["selected_package_ids"] == [] and r["total_cost"] is None,
      "shortage selection")
check(r["feasible_combination_count"] == 0, "no feasible combos")
check(r["total_demand"] == 8 and r["arrived_total"] == 5
      and r["shortage_total"] == 3, "shortage totals")
gaps = {g["part_id"]: g for g in r["shortages"]}
check(set(gaps) == {"x", "y"}, f"gap parts {set(gaps)}")
check(gaps["x"] == {"part_id": "x", "demand": 5, "available": 4,
                    "shortage": 1}, "x gap")
check(gaps["y"] == {"part_id": "y", "demand": 2, "available": 0,
                    "shortage": 2}, "y gap")
# bolt 不缺, 不进 shortages 但仍在 part_summary
sbolt = next(ps for ps in r["part_summary"] if ps["part_id"] == "bolt")
check(sbolt["demand"] == 1 and sbolt["arrived"] == 1 and sbolt["shortage"] == 0,
      "bolt covered")
# 采购包候选数与组合数照常给出
check(r["candidate_count"] == 2 and r["combination_count"] == 4,
      "shortage counts")
check("只读" in r["message"], "shortage readonly note")

# 7. 无任何备件需求: 零费用空清单(即使提供了采购包也不使用)
r = plan_spare_parts(NET_FO, CV, {"V1": {}, "V2": {}}, [
    {"id": "P1", "price": 3, "contents": {"x": 1}}])
check(r["ok"] and r["empty"] and r["satisfied"], "empty flags")
check(r["selected_package_ids"] == [] and r["selected_packages"] == [],
      "empty selection")
check(r["total_cost"] == 0 and r["total_demand"] == 0
      and r["arrived_total"] == 0 and r["surplus_total"] == 0
      and r["shortage_total"] == 0, "empty zeros")
check(r["part_summary"] == [] and r["merged_demands"] == {}
      and r["part_ids"] == [], "empty summaries")
check(r["combination_count"] == 1 and r["feasible_combination_count"] == 1,
      "empty combo counts")
# 空清单时逐阀明细仍回显(两阀均无备件)
check([d["valve_id"] for d in r["valve_demand_details"]] == ["V1", "V2"]
      and all(d["parts"] == [] for d in r["valve_demand_details"]),
      "empty valve details")
check("零费用空清单" in r["message"], "empty message")

# 8. 不关闭任何阀门的方案: 同样空清单
r = plan_spare_parts(NET_FO, [], {}, [])
check(r["empty"] and r["closed_valves"] == [] and r["total_cost"] == 0,
      "no closed valves empty")
check(r["valve_demand_details"] == [], "no valve details")

# 9. 同一种类在多枚阀门上的需求被合并
r = plan_spare_parts(NET_FO, CV,
                     {"V1": {"gasket": 2}, "V2": {"gasket": 3}},
                     [{"id": "P1", "price": 1, "contents": {"gasket": 5}}])
check(r["satisfied"] and r["merged_demands"] == {"gasket": 5}
      and r["total_demand"] == 5, "merge across valves")

# ---- 录入校验 ----
# 缺少某枚计划阀门的录入
expect_errors(NET_FO, CV, {"V1": {"x": 1}}, [],
              ["缺少计划关闭阀门的备件需求: V2"])
# 多余阀门编号
expect_errors(NET_FO, CV, {"V1": {}, "V2": {}, "V9": {}}, [],
              ["提供了非计划关闭阀门的备件需求(多余编号): V9"])
# 备件数量非正整数
for bad in [0, -1, 1.5, "2", True, None]:
    expect_errors(NET_FO, CV, {"V1": {"x": bad}, "V2": {}}, [],
                  ["阀门 V1 的备件 x 数量必须是正整数"])
# 备件种类名空
expect_errors(NET_FO, CV, {"V1": {"  ": 1}, "V2": {}}, [],
              ["阀门 V1: 备件种类名称不能为空"])
# 阀门条目不是对象
expect_errors(NET_FO, CV, {"V1": [], "V2": {}}, [],
              ["阀门 V1: 备件需求必须是以备件种类为键的对象"])
# 采购包超 12 个
expect_errors(NET_FO, CV, {"V1": {}, "V2": {}},
              [{"id": f"P{i}", "price": 1, "contents": {"x": 1}}
               for i in range(13)],
              ["采购包数量为 13, 超过上限 12 个"])
# 编号缺失 / 重复
expect_errors(NET_FO, CV, {"V1": {}, "V2": {}},
              [{"price": 1, "contents": {"x": 1}}],
              ["采购包 #1: 缺少采购包编号"])
expect_errors(NET_FO, CV, {"V1": {}, "V2": {}}, [
    {"id": "A", "price": 1, "contents": {"x": 1}},
    {"id": "A", "price": 1, "contents": {"x": 1}}],
    ["采购包编号重复: A"])
# 价格非正整数
for bad in [0, -2, 1.5, "9", False, None]:
    expect_errors(NET_FO, CV, {"V1": {}, "V2": {}},
                  [{"id": "A", "price": bad, "contents": {"x": 1}}],
                  ["采购包 A: 价格必须是正整数"])
# 件数为负 / 小数 / 布尔 / 字符串 / null
for bad in [-1, 1.5, "0", True, None]:
    expect_errors(NET_FO, CV, {"V1": {}, "V2": {}},
                  [{"id": "A", "price": 1, "contents": {"x": bad}}],
                  ["采购包 A 的备件 x 件数必须是非负整数"])
# 件数 0 合法, 但至少要列出一种备件
expect_errors(NET_FO, CV, {"V1": {}, "V2": {}},
              [{"id": "A", "price": 1}],
              ["采购包 A: 必须至少列出一种备件"])
expect_errors(NET_FO, CV, {"V1": {}, "V2": {}},
              [{"id": "A", "price": 1, "contents": {}}],
              ["采购包 A: 必须至少列出一种备件"])
# contents 不是对象
expect_errors(NET_FO, CV, {"V1": {}, "V2": {}},
              [{"id": "A", "price": 1, "contents": []}],
              ["采购包 A: 备件件数必须是以备件种类为键的对象"])
# 采购包条目不是对象 / packages 不是数组
expect_errors(NET_FO, CV, {"V1": {}, "V2": {}}, [5],
              ["采购包 #1: 必须是对象"])
try:
    plan_spare_parts(NET_FO, CV, {"V1": {}, "V2": {}}, "nope")
    raise AssertionError("packages non-list should raise")
except NetworkValidationError as exc:
    check("packages 必须是数组" in exc.errors, "packages non-list")
try:
    plan_spare_parts(NET_FO, CV, [], [])
    raise AssertionError("valve_demands non-dict should raise")
except NetworkValidationError as exc:
    check("valve_demands 必须是以阀门编号为键的对象" in exc.errors,
          "valve_demands non-dict")
# 计划阀门不在快照中
expect_errors(NET_FO, ["V8"], {"V8": {}}, [],
              ["方案关闭的阀门 V8 不存在于方案快照的管网中"])

# 10. 12 个采购包上限内全枚举可正常工作(2^12=4096 组合)
many = [{"id": f"B{i:02d}", "price": 1, "contents": {"x": 1}}
        for i in range(12)]
r = plan_spare_parts(NET_FO, CV, {"V1": {"x": 7}, "V2": {}}, many)
check(r["satisfied"] and len(r["selected_package_ids"]) == 7
      and r["total_cost"] == 7 and r["combination_count"] == 4096,
      "12 packages enumeration")

print(f"spare parts solver tests: {passed} checks passed")
