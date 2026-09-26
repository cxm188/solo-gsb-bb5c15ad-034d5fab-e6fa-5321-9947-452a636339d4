"""管网漏点隔离规划台 — FastAPI 入口。

API:
  GET  /api/network                 读取当前管网输入
  PUT  /api/network                 整体保存管网输入(校验后覆盖)
  POST /api/plan                    常规求解并保存方案
  POST /api/plan-failover           单阀失效备援求解并保存方案
  POST /api/plan-siting             新增阀门选址预览(只读, 不写管网/不入库)
  POST /api/plan-tradeoff           关阀成本与断水影响权衡预览(只读, 不写管网/不入库)
  GET  /api/plans                   最近方案列表
  GET  /api/plans/{id}              方案详情(含节点/管段状态)
  POST /api/plans/{id}/sequence     可行方案的现场执行顺序规划(只读计算)
  POST /api/plans/{id}/jumpers      可行方案的临时供水跨接预览(只读计算)
  POST /api/plans/{id}/monitors     可行方案的失效监测点布设预览(只读计算)
  POST /api/plans/{id}/water-delivery
                                    可行方案的应急送水分配预览(只读计算)
  POST /api/plans/{id}/spare-parts  可行方案的关阀作业备件包采购预览(只读计算)
  POST /api/plans/{id}/capacity-check
                                    可行方案的供水容量校核(只读计算)
  POST /api/demo                    恢复内置示例管网
  POST /api/clear                   清空管网输入
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

import database
from demo import DEMO_NETWORK
from solver import (MAX_VALVES, NetworkValidationError, plan_capacity_check,
                    plan_jumpers, plan_monitors, plan_sequence,
                    plan_spare_parts, plan_water_delivery, solve,
                    solve_failover, solve_siting, solve_tradeoff)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class NodeIn(BaseModel):
    id: str = Field(min_length=1)
    role: Literal["inlet", "leak", "must_keep", "normal"] = "normal"
    label: str | None = None

    @field_validator("id")
    @classmethod
    def _strip_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("节点编号不能为空")
        return v


class SegmentIn(BaseModel):
    id: str = Field(min_length=1)
    endpoint_a: str = Field(min_length=1)
    endpoint_b: str = Field(min_length=1)

    @field_validator("id", "endpoint_a", "endpoint_b")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class ValveIn(BaseModel):
    id: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    cost: int = Field(gt=0)

    @field_validator("id", "segment_id")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class NetworkIn(BaseModel):
    nodes: list[NodeIn] = Field(default_factory=list)
    segments: list[SegmentIn] = Field(default_factory=list)
    valves: list[ValveIn] = Field(default_factory=list, max_length=MAX_VALVES)


class SequenceIn(BaseModel):
    """执行顺序规划录入: 计划阀门操作时长 + 漏点漏水权重。

    值的正整数校验在 solver.plan_sequence 中逐条进行, 以便返回明确错误。
    """
    durations: dict[str, Any] = Field(default_factory=dict)
    leak_weights: dict[str, Any] = Field(default_factory=dict)


class CandidateIn(BaseModel):
    """选址候选新阀录入。

    各字段(唯一新阀编号/尚无阀门的管段/正整数安装费与关阀代价)在
    solver.solve_siting 中复用图校验逐条检查, 以便返回明确错误。
    """
    id: Any = None
    segment_id: Any = None
    install_cost: Any = None
    close_cost: Any = None


class SitingIn(BaseModel):
    """选址预览请求: 当前编辑中的管网(可空, 空则用已保存管网) + 候选位置。"""
    network: NetworkIn | None = None
    candidates: list[CandidateIn] = Field(default_factory=list)


class TradeoffIn(BaseModel):
    """权衡预览请求: 当前编辑中的管网(可空, 空则用已保存管网) + 用水权重。

    weights 的键必须恰好是全部普通节点编号、值为正整数, 逐条校验在
    solver.solve_tradeoff 中进行, 以便返回明确错误。
    """
    network: NetworkIn | None = None
    weights: dict[str, Any] = Field(default_factory=dict)


class JumperIn(BaseModel):
    """临时供水跨接候选录入。

    各字段(唯一跨接编号/两个不同的现有节点/正整数铺设费)在
    solver.plan_jumpers 中逐条校验, 以便返回明确错误。
    """
    id: Any = None
    endpoint_a: Any = None
    endpoint_b: Any = None
    cost: Any = None


class JumpersIn(BaseModel):
    """临时供水跨接预览录入: 至多 6 条候选跨接。"""
    candidates: list[JumperIn] = Field(default_factory=list)


class MonitorIn(BaseModel):
    """失效监测点候选录入。

    各字段(方案快照中的非进水节点/正整数布设费)在 solver.plan_monitors
    中逐条校验, 以便返回明确错误。
    """
    node_id: Any = None
    cost: Any = None


class MonitorsIn(BaseModel):
    """失效监测点布设预览录入: 至多 12 个候选监测点。"""
    candidates: list[MonitorIn] = Field(default_factory=list)


class WaterVehicleIn(BaseModel):
    """应急送水车候选录入。

    各字段(唯一车辆编号/正整数出车费与载水量/可服务需求点列表)在
    solver.plan_water_delivery 中逐条校验, 以便返回明确错误。
    """
    id: Any = None
    cost: Any = None
    capacity: Any = None
    serves: Any = None


class WaterDeliveryIn(BaseModel):
    """应急送水分配预览录入: 逐需求点正整数需水量 + 至多 6 辆候选车。

    车辆数量上限在 solver.plan_water_delivery 中校验(与其他预览一致,
    返回 detail.errors 逐条错误)。
    """
    demands: dict[str, Any] = Field(default_factory=dict)
    vehicles: list[WaterVehicleIn] = Field(default_factory=list)


class SparePartsIn(BaseModel):
    """关阀作业备件包采购预览录入: 逐计划阀门备件需求 + 至多 12 个采购包。

    每枚计划关闭阀门一条 {备件种类: 正整数数量}; 每个采购包含唯一编号、
    正整数价格及 {备件种类: 非负整数件数}。逐条校验(数量上限、编号唯一、
    正/非负整数等)在 solver.plan_spare_parts 中进行, 以便返回明确错误。
    """
    valve_demands: dict[str, Any] = Field(default_factory=dict)
    packages: list[dict[str, Any]] = Field(default_factory=list)


class CapacityCheckIn(BaseModel):
    """供水容量校核录入: 未关阀管段流量上限 + 进水点供给上限 + 必保点需求。

    三类编号集合必须与方案快照完整对应(未关阀管段/进水点/必保点, 不多
    不少), 值均为正整数; 逐条校验在 solver.plan_capacity_check 中进行,
    以便返回明确错误。
    """
    capacities: dict[str, Any] = Field(default_factory=dict)
    supplies: dict[str, Any] = Field(default_factory=dict)
    demands: dict[str, Any] = Field(default_factory=dict)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


app = FastAPI(title="管网漏点隔离规划台", version="1.0.0", lifespan=lifespan)


def _payload(net: NetworkIn) -> dict:
    return net.model_dump()


@app.get("/api/network")
def get_network() -> dict:
    with database.get_conn() as conn:
        return database.load_network(conn)


@app.put("/api/network")
def save_network(net: NetworkIn) -> dict:
    payload = _payload(net)
    try:
        # 提前用求解器的完整校验(端点存在、阀门绑定等), 保证保存的是有效管网
        from solver import validate_network
        validate_network(payload)
    except NetworkValidationError as exc:
        raise HTTPException(status_code=422, detail={"errors": exc.errors})
    with database.get_conn() as conn:
        database.replace_network(conn, payload)
    return {"ok": True, "counts": {
        "nodes": len(payload["nodes"]),
        "segments": len(payload["segments"]),
        "valves": len(payload["valves"]),
    }}


@app.post("/api/plan")
def create_plan(net: NetworkIn | None = None) -> dict:
    """常规求解。请求体可空: 为空时使用数据库中已保存的管网。"""
    with database.get_conn() as conn:
        payload = _payload(net) if net is not None else database.load_network(conn)
        try:
            result = solve(payload)
        except NetworkValidationError as exc:
            raise HTTPException(status_code=422,
                                detail={"errors": exc.errors})
        plan_id = database.save_plan(conn, result, payload)
    result["id"] = plan_id
    return result


@app.post("/api/plan-failover")
def create_failover_plan(net: NetworkIn | None = None) -> dict:
    """单阀失效备援求解(独立 API)。请求体可空: 为空时用已保存管网。

    要求计划关阀方案在正常执行及任意一枚计划阀门关不上(保持开启)时,
    全部漏点与进水点断开、全部必保点仍连通至少一个进水点。
    """
    with database.get_conn() as conn:
        payload = _payload(net) if net is not None else database.load_network(conn)
        try:
            result = solve_failover(payload)
        except NetworkValidationError as exc:
            raise HTTPException(status_code=422,
                                detail={"errors": exc.errors})
        plan_id = database.save_plan(conn, result, payload)
    result["id"] = plan_id
    return result


@app.post("/api/plan-siting")
def create_siting_plan(req: SitingIn) -> dict:
    """新增阀门选址预览(独立 API, 只读: 不写管网、不写入历史方案)。

    对当前编辑中的管网(请求体未带 network 时使用已保存管网), 在尚无阀门
    的管段上评估至多 6 个候选新阀, 寻找漏点全隔离且必保点全有水的增设及
    关阀方案: 只为实际关闭的候选阀计安装费, 先最小化安装费合计, 再最小化
    本次关阀代价, 仍并列按新增管段编号列表、关阀编号列表字典序决胜。
    """
    if req.network is not None:
        payload = _payload(req.network)
    else:
        with database.get_conn() as conn:
            payload = database.load_network(conn)
    try:
        return solve_siting(payload,
                            [c.model_dump() for c in req.candidates])
    except NetworkValidationError as exc:
        raise HTTPException(status_code=422,
                            detail={"errors": exc.errors})


@app.post("/api/plan-tradeoff")
def create_tradeoff_preview(req: TradeoffIn) -> dict:
    """关阀成本与断水影响权衡预览(独立 API, 只读: 不写管网、不入库方案)。

    对当前编辑中的管网(请求体未带 network 时使用已保存管网), 为每个普通
    节点录入正整数用水权重; 枚举全部关阀组合, 仅保留全部漏点与进水点断开
    且必保点仍有水的方案, 以(关阀代价合计, 原本有水而关阀后断水的普通
    节点权重和)为双目标返回全部非支配方案; 同一对指标只保留关阀编号升序
    列表字典序最小者, 结果按代价、断水影响、编号升序排列。
    """
    if req.network is not None:
        payload = _payload(req.network)
    else:
        with database.get_conn() as conn:
            payload = database.load_network(conn)
    try:
        return solve_tradeoff(payload, req.weights)
    except NetworkValidationError as exc:
        raise HTTPException(status_code=422,
                            detail={"errors": exc.errors})


@app.get("/api/plans")
def get_plans(limit: int = 20) -> dict:
    limit = max(1, min(limit, 100))
    with database.get_conn() as conn:
        return {"plans": database.list_plans(conn, limit)}


@app.get("/api/plans/{plan_id}")
def get_plan(plan_id: int) -> dict:
    with database.get_conn() as conn:
        plan = database.get_plan(conn, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="方案不存在")
    return plan


@app.post("/api/plans/{plan_id}/sequence")
def plan_execution_sequence(plan_id: int, seq: SequenceIn) -> dict:
    """已保存可行方案的现场执行顺序规划(独立 API)。

    只读计算: 仅读取方案及其管网快照, 不修改、不新增任何数据。
    不可行方案、遗漏/多余编号、非正整数数值都会返回明确错误。
    """
    with database.get_conn() as conn:
        plan = database.get_plan(conn, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="方案不存在")
    if not plan.get("feasible"):
        reason = plan.get("reason_code")
        raise HTTPException(status_code=422, detail={"errors": [
            f"方案 #{plan_id} 为不可行方案"
            + (f"(reason_code: {reason})" if reason else "")
            + ", 没有可执行的关阀清单, 不能规划执行顺序"
        ]})
    try:
        result = plan_sequence(plan["network_snapshot"],
                               plan.get("closed_valves", []),
                               seq.durations, seq.leak_weights)
    except NetworkValidationError as exc:
        raise HTTPException(status_code=422, detail={"errors": exc.errors})
    result["plan_id"] = plan_id
    result["solver"] = plan.get("solver", "base")
    return result


@app.post("/api/plans/{plan_id}/jumpers")
def plan_jumper_preview(plan_id: int, req: JumpersIn) -> dict:
    """已保存可行方案的临时供水跨接预览(独立 API, 只读计算)。

    基于方案快照与已关阀管段, 评估至多 6 条候选跨接(新增通水管段):
    在保持全部漏点与进水点断开、全部必保点有水的前提下, 先最大化由断水
    转为有水的普通节点数, 再最小化铺设费合计, 并列时按跨接编号升序列表
    字典序选取; 无法恢复普通节点时返回空方案。不修改管网与历史方案。
    """
    with database.get_conn() as conn:
        plan = database.get_plan(conn, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="方案不存在")
    if not plan.get("feasible"):
        reason = plan.get("reason_code")
        raise HTTPException(status_code=422, detail={"errors": [
            f"方案 #{plan_id} 为不可行方案"
            + (f"(reason_code: {reason})" if reason else "")
            + ", 没有已关阀管段可作为跨接预览的基础, 不能规划临时供水跨接"
        ]})
    try:
        result = plan_jumpers(plan["network_snapshot"],
                              plan.get("closed_valves", []),
                              [c.model_dump() for c in req.candidates])
    except NetworkValidationError as exc:
        raise HTTPException(status_code=422, detail={"errors": exc.errors})
    result["plan_id"] = plan_id
    result["solver"] = plan.get("solver", "base")
    return result


@app.post("/api/plans/{plan_id}/monitors")
def plan_monitor_preview(plan_id: int, req: MonitorsIn) -> dict:
    """已保存可行方案的失效监测点布设预览(独立 API, 只读计算)。

    从方案快照的非进水节点中录入至多 12 个候选监测点(编号不得重复)及
    各自正整数布设费; 模拟正常执行与每枚计划关闭阀门单独关不上时的供水
    连通状态, 选出布设费总和最低、同费按节点编号升序列表字典序最小的
    点集, 使任意两种情形在所选点的有水/无水读数不同; 候选点无法区分
    某些情形时列出这些情形对。不修改管网与历史方案。
    """
    with database.get_conn() as conn:
        plan = database.get_plan(conn, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="方案不存在")
    if not plan.get("feasible"):
        reason = plan.get("reason_code")
        raise HTTPException(status_code=422, detail={"errors": [
            f"方案 #{plan_id} 为不可行方案"
            + (f"(reason_code: {reason})" if reason else "")
            + ", 没有可监测的关阀方案, 不能规划失效监测点布设"
        ]})
    try:
        result = plan_monitors(plan["network_snapshot"],
                               plan.get("closed_valves", []),
                               [c.model_dump() for c in req.candidates])
    except NetworkValidationError as exc:
        raise HTTPException(status_code=422, detail={"errors": exc.errors})
    result["plan_id"] = plan_id
    result["solver"] = plan.get("solver", "base")
    return result


@app.post("/api/plans/{plan_id}/water-delivery")
def plan_water_delivery_preview(plan_id: int, req: WaterDeliveryIn) -> dict:
    """已保存可行方案的应急送水分配预览(独立 API, 只读计算)。

    以方案快照中关阀后断水的普通节点为需求点, 逐点录入正整数需水量;
    录入至多 6 辆候选送水车(唯一编号 + 正整数出车费与载水量 + 可服务
    需求点), 允许一个需求点由多车分担。选出满足全部需求且出车费最低的
    车辆组合, 同费按车辆编号升序列表字典序决胜, 返回各车向各点的配送量
    与总费用; 全部候选车仍无法满足时返回最大可配送量与总缺口; 无断水
    需求时返回空调度。不修改管网与历史方案。
    """
    with database.get_conn() as conn:
        plan = database.get_plan(conn, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="方案不存在")
    if not plan.get("feasible"):
        reason = plan.get("reason_code")
        raise HTTPException(status_code=422, detail={"errors": [
            f"方案 #{plan_id} 为不可行方案"
            + (f"(reason_code: {reason})" if reason else "")
            + ", 没有关阀后供水状态快照, 不能规划应急送水分配"
        ]})
    try:
        result = plan_water_delivery(plan["network_snapshot"],
                                     plan.get("closed_valves", []),
                                     req.demands,
                                     [v.model_dump() for v in req.vehicles])
    except NetworkValidationError as exc:
        raise HTTPException(status_code=422, detail={"errors": exc.errors})
    result["plan_id"] = plan_id
    result["solver"] = plan.get("solver", "base")
    return result


@app.post("/api/plans/{plan_id}/spare-parts")
def plan_spare_parts_preview(plan_id: int, req: SparePartsIn) -> dict:
    """已保存可行方案的关阀作业备件包采购预览(独立 API, 只读计算)。

    为方案中每枚计划关闭的阀门录入所需备件种类及正整数数量(无需备件的
    阀门录空表), 合并各阀需求; 录入至多 12 个采购包(唯一编号 + 正整数
    价格 + 按备件种类的非负整数件数, 每包只能买一次)。枚举全部采购包
    组合, 选出覆盖全部需求的最低总价组合, 同价按采购包编号升序列表
    字典序决胜, 返回采购清单与各类需求/到货/余量; 全部包仍不足时返回
    逐类缺口; 无关阀备件需求时返回零费用空清单。不修改管网与历史方案。
    """
    with database.get_conn() as conn:
        plan = database.get_plan(conn, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="方案不存在")
    if not plan.get("feasible"):
        reason = plan.get("reason_code")
        raise HTTPException(status_code=422, detail={"errors": [
            f"方案 #{plan_id} 为不可行方案"
            + (f"(reason_code: {reason})" if reason else "")
            + ", 没有计划关闭的阀门, 不能规划关阀作业备件采购"
        ]})
    try:
        result = plan_spare_parts(plan["network_snapshot"],
                                  plan.get("closed_valves", []),
                                  req.valve_demands,
                                  req.packages)
    except NetworkValidationError as exc:
        raise HTTPException(status_code=422, detail={"errors": exc.errors})
    result["plan_id"] = plan_id
    result["solver"] = plan.get("solver", "base")
    return result


@app.post("/api/plans/{plan_id}/capacity-check")
def plan_capacity_check_preview(plan_id: int,
                                req: CapacityCheckIn) -> dict:
    """已保存可行方案的供水容量校核(独立 API, 只读计算)。

    以方案快照中未关阀管段构成无向输水网: 录入每条管段正整数流量上限
    (管段净流量的绝对值受同一个上限约束)、每个进水点正整数供给上限、
    每个必保供水点正整数需求, 三类编号须与方案快照完整对应。通过整数
    最大流求可送达必保点的最大总量, 返回需求总量、最大送达量、总缺口与
    各必保点实际送达量; 总送达量等于总需求才标记容量充足, 仅连通但容量
    不足显示不足; 无必保点时返回充足及零需求。不修改管网与历史方案。
    """
    with database.get_conn() as conn:
        plan = database.get_plan(conn, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="方案不存在")
    if not plan.get("feasible"):
        reason = plan.get("reason_code")
        raise HTTPException(status_code=422, detail={"errors": [
            f"方案 #{plan_id} 为不可行方案"
            + (f"(reason_code: {reason})" if reason else "")
            + ", 没有可行的关阀后输水网, 不能进行供水容量校核"
        ]})
    try:
        result = plan_capacity_check(plan["network_snapshot"],
                                     plan.get("closed_valves", []),
                                     req.capacities,
                                     req.supplies,
                                     req.demands)
    except NetworkValidationError as exc:
        raise HTTPException(status_code=422, detail={"errors": exc.errors})
    result["plan_id"] = plan_id
    result["solver"] = plan.get("solver", "base")
    return result


@app.post("/api/demo")
def load_demo() -> dict:
    with database.get_conn() as conn:
        database.replace_network(conn, DEMO_NETWORK)
    return {"ok": True, "network": DEMO_NETWORK}


@app.post("/api/clear")
def clear_network() -> dict:
    with database.get_conn() as conn:
        database.replace_network(conn,
                                 {"nodes": [], "segments": [], "valves": []})
    return {"ok": True}


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


# ---- 静态页面 ----
STATIC_DIR = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
