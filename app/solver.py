"""管网漏点隔离求解器。

模型:
  - 节点 = 无向管网上的点; 每个节点有角色: inlet(进水点)/leak(漏点)/
    must_keep(必保供水点)/normal(普通点)。
  - 管段 = 无向边; 每条管段最多绑定 1 个阀门。关闭阀门即删除对应管段。
  - 目标: 选择代价之和最小的阀门组合, 使
      (A) 每个漏点与所有进水点都不连通(漏点被隔离);
      (B) 每个必保点仍与至少一个进水点连通。
    同代价时, 取关闭阀门编号升序表的字典序最小者。

两种求解:
  - solve(payload): 常规规划, 只要求方案本身满足 (A)(B)。
  - solve_failover(payload): 单阀失效备援规划。计划关闭的每一枚阀门都可能
    "关不上" 而保持开启; 要求方案正常执行时, 以及任意一枚计划阀门失效(其
    绑定管段保持通水)时, (A)(B) 仍然成立。位掩码 M 的方案备援可行, 当且
    仅当 M 本身以及每个 M\\{j}(j∈M) 都是常规可行方案。

另提供 plan_sequence(snapshot, closed_valves, durations, leak_weights):
对已保存的可行方案做现场执行顺序规划(只读计算)。每枚计划阀门有正整数
操作时长, 每个漏点有正整数漏水权重; 操作某阀的时段内该阀仍开启, 该时段
暴露量 = 时长 × 仍通水漏点权重之和; 用子集 DP 求累计暴露量最小的执行
顺序, 同暴露量取阀门编号序列字典序最小者。

以及 solve_siting(payload, candidates): 新增阀门选址预览(只读计算)。
在尚无阀门的管段上给出至多 6 个候选新阀(唯一新阀编号 + 正整数安装费 +
正整数关阀代价, 原阀与候选合计仍不超过 14 个), 枚举"原阀 + 全部候选"
的关阀子集, 寻找漏点全隔离且必保点全有水的增设及关阀方案。只为实际关闭
的候选阀计安装费; 优化次序: 安装费合计最小 -> 本次关阀代价最小 ->
新增管段编号升序列表字典序 -> 关阀编号升序列表字典序。无解时说明候选
范围内不可修复。

以及 plan_jumpers(snapshot, closed_valves, raw_candidates): 已保存可行
方案的临时供水跨接预览(只读计算)。基于方案快照与已关阀管段, 录入至多
6 条候选跨接(唯一编号 + 两个不同的现有节点 + 正整数铺设费), 跨接视为
新增通水管段。枚举全部候选组合, 始终保持全部漏点与进水点断开、全部必保
点有水; 先最大化由断水转为有水的普通节点数, 再最小化铺设费合计, 并列时
按跨接编号升序列表字典序选取; 无法恢复普通节点时返回空方案。

以及 solve_tradeoff(payload, raw_weights): 关阀成本与断水影响权衡预览
(只读计算, 针对当前编辑管网)。为每个普通节点录入正整数用水权重, 枚举
全部关阀子集, 仅保留全部漏点与进水点断开且全部必保点仍有水的方案, 以
(关阀代价合计, 原本有水而关阀后断水的普通节点权重和) 为双目标, 返回
全部非支配方案; 同一对指标只保留关阀编号升序列表字典序最小者, 结果按
(代价, 断水影响, 关阀编号列表) 升序排列。

以及 plan_monitors(snapshot, closed_valves, raw_candidates): 已保存可行
方案的失效监测点布设预览(只读计算)。从方案快照的非进水节点中录入至多
12 个候选监测点(编号不得重复, 各自正整数布设费); 模拟正常执行与每枚
计划关闭阀门单独关不上时的供水连通状态, 选出布设费总和最低、同费按
节点编号升序列表字典序最小的点集, 使任意两种情形在所选点的有水/无水
读数不同; 候选点无法区分某些情形时列出这些情形对。

以及 plan_water_delivery(snapshot, closed_valves, raw_demands,
raw_vehicles): 已保存可行方案的应急送水分配预览(只读计算)。以方案
快照中关阀后断水的普通节点为需求点, 逐点录入正整数需水量; 录入至多
6 辆候选送水车, 每辆含唯一编号、正整数出车费与载水量、可服务的需求点
集合。允许一个需求点由多车分担(整数水量), 枚举全部车辆组合, 用整数
最大流判定该组合能否满足全部需求, 选出出车费合计最低的组合, 同费按
车辆编号升序列表字典序决胜; 全部候选车也无法满足时, 给出最大可配送
量(最大流)与总缺口; 没有断水需求点时返回空调度。选中组合内各车向各
点的配送量按(需求点编号, 车辆编号)双关键字贪心确定, 结果唯一。

以及 plan_spare_parts(snapshot, closed_valves, raw_valve_demands,
raw_packages): 已保存可行方案的关阀作业备件包采购预览(只读计算)。
为每枚计划关闭的阀门录入所需备件种类及正整数数量(无需备件的阀门录
空表), 合并各阀需求得到各类总需求; 录入至多 12 个采购包, 每包有唯一
编号、正整数价格, 以及按备件种类列出的非负整数件数, 每包只能买一次。
枚举全部采购包组合(每类到货量为包内件数之和), 选出覆盖全部需求的
最低总价组合, 同价按采购包编号升序列表字典序决胜, 返回采购清单与各类
需求/到货/余量; 全部包合起来仍不足时返回逐类缺口; 无关阀备件需求时
返回零费用空清单。

以及 plan_capacity_check(snapshot, closed_valves, raw_capacities,
raw_supplies, raw_demands): 已保存可行方案的供水容量校核(只读计算)。
以方案快照中未关阀管段构成无向输水网, 每条管段录入正整数流量上限
(管段净流量的绝对值受同一个上限约束, 用两条容量相同的反向有向弧建模),
每个进水点录入正整数供给上限,每个必保供水点录入正整数需求; 三类录入
的编号集合都必须与方案快照完整对应(不多不少)。用整数最大流(Dinic)
求可送达必保点的最大总量, 返回需求总量、最大送达量、总缺口与各必保点
实际送达量(按必保点编号升序逐个锁定、本点尽可能多送, 结果唯一);
总送达量等于需求总量才判容量充足, 仅连通但容量不足时返回不足;
无必保点时返回充足及零需求。

阀门最多 14 个, 枚举全部 2^V 个子集(V<=14 => 16384), 对每个子集做
BFS 连通性检查即可, 简单且确定。
"""

from __future__ import annotations

from collections import deque
from typing import Any

MAX_VALVES = 14
MAX_CANDIDATES = 6
MAX_MONITOR_CANDIDATES = 12
MAX_WATER_VEHICLES = 6
MAX_SPARE_PACKAGES = 12


class NetworkValidationError(ValueError):
    """输入管网数据不合法, errors 字段携带逐条原因。"""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def _norm_id(raw: Any) -> str:
    return str(raw if raw is not None else "").strip()


def _strict_pos_int(value: Any) -> int | None:
    """严格正整数: 接受 int 或其十进制字符串; 拒绝 bool/浮点/其他, 非法返回 None。"""
    try:
        iv = int(value)
        if iv <= 0 or str(iv) != str(value).strip():
            return None
        return iv
    except (TypeError, ValueError):
        return None


def validate_network(payload: dict[str, Any]) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
    """校验并规整 {nodes, segments, valves}。

    返回 (nodes, segments, valves), 均为带规整字段的 dict 列表。
    """
    errors: list[str] = []

    raw_nodes = payload.get("nodes") or []
    raw_segments = payload.get("segments") or []
    raw_valves = payload.get("valves") or []
    if not isinstance(raw_nodes, list) or not isinstance(raw_segments, list) \
            or not isinstance(raw_valves, list):
        raise NetworkValidationError(["nodes/segments/valves 必须是数组"])

    # ---- 节点 ----
    node_role = {"inlet", "leak", "must_keep", "normal"}
    nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    for i, nd in enumerate(raw_nodes):
        if not isinstance(nd, dict):
            errors.append(f"节点 #{i + 1}: 必须是对象")
            continue
        nid = _norm_id(nd.get("id"))
        if not nid:
            errors.append(f"节点 #{i + 1}: 缺少编号")
        elif nid in node_ids:
            errors.append(f"节点编号重复: {nid}")
        role = nd.get("role", "normal")
        if role not in node_role:
            errors.append(f"节点 {nid or i + 1}: 角色非法({role}), "
                          f"应为 inlet/leak/must_keep/normal")
        label = _norm_id(nd.get("label")) or nid
        node_ids.add(nid)
        nodes.append({"id": nid, "role": role, "label": label})

    # ---- 阀门 ----
    valves: list[dict[str, Any]] = []
    valve_ids: set[str] = set()
    for i, vl in enumerate(raw_valves):
        if not isinstance(vl, dict):
            errors.append(f"阀门 #{i + 1}: 必须是对象")
            continue
        vid = _norm_id(vl.get("id"))
        if not vid:
            errors.append(f"阀门 #{i + 1}: 缺少编号")
        elif vid in valve_ids:
            errors.append(f"阀门编号重复: {vid}")
        cost = vl.get("cost")
        cost_int = _strict_pos_int(cost)
        if cost_int is None:
            errors.append(f"阀门 {vid or i + 1}: 关闭代价必须是正整数")
        seg_id = _norm_id(vl.get("segment_id"))
        if not seg_id:
            errors.append(f"阀门 {vid or i + 1}: 必须绑定一条管段")
        valve_ids.add(vid)
        valves.append({"id": vid, "cost": cost_int, "segment_id": seg_id})

    if len(valves) > MAX_VALVES:
        errors.append(f"阀门数量为 {len(valves)}, 超过上限 {MAX_VALVES} 个")

    # ---- 管段 ----
    segments: list[dict[str, Any]] = []
    segment_ids: set[str] = set()
    seg_valves: dict[str, str] = {}
    for vl in valves:
        if vl["segment_id"]:
            if vl["segment_id"] in seg_valves:
                errors.append(
                    f"管段 {vl['segment_id']} 同时绑定了阀门 "
                    f"{seg_valves[vl['segment_id']]} 和 {vl['id']}"
                    f"(每条管段最多 1 个阀门)"
                )
            else:
                seg_valves[vl["segment_id"]] = vl["id"]

    for i, sg in enumerate(raw_segments):
        if not isinstance(sg, dict):
            errors.append(f"管段 #{i + 1}: 必须是对象")
            continue
        sid = _norm_id(sg.get("id"))
        if not sid:
            errors.append(f"管段 #{i + 1}: 缺少编号")
        elif sid in segment_ids:
            errors.append(f"管段编号重复: {sid}")
        a, b = _norm_id(sg.get("endpoint_a")), _norm_id(sg.get("endpoint_b"))
        if a not in node_ids:
            errors.append(f"管段 {sid or i + 1}: 端点 {a or '(空)'} 不存在")
        if b not in node_ids:
            errors.append(f"管段 {sid or i + 1}: 端点 {b or '(空)'} 不存在")
        if a and a == b:
            errors.append(f"管段 {sid or i + 1}: 两个端点不能相同({a})")
        segment_ids.add(sid)
        segments.append({
            "id": sid,
            "endpoint_a": a,
            "endpoint_b": b,
            "valve_id": seg_valves.get(sid),
        })

    for vl in valves:
        if vl["segment_id"] and vl["segment_id"] not in segment_ids:
            errors.append(f"阀门 {vl['id']}: 绑定的管段 {vl['segment_id']} 不存在")

    if errors:
        raise NetworkValidationError(errors)
    return nodes, segments, valves


class _Graph:
    """校验后管网的图表示: 邻接表 + 关阀位掩码 + BFS 连通性。"""

    def __init__(self, nodes: list[dict[str, Any]],
                 segments: list[dict[str, Any]],
                 valves: list[dict[str, Any]]):
        self.nodes = nodes
        self.segments = segments
        self.ids = [nd["id"] for nd in nodes]
        self.idx = {nid: i for i, nid in enumerate(self.ids)}
        n = len(self.ids)
        self.n = n

        self.inlet_set = {i for i, nd in enumerate(nodes)
                          if nd["role"] == "inlet"}
        self.leak_set = {i for i, nd in enumerate(nodes)
                         if nd["role"] == "leak"}
        self.keep_set = {i for i, nd in enumerate(nodes)
                         if nd["role"] == "must_keep"}
        self.leak_bits = sum(1 << i for i in self.leak_set)
        self.keep_bits = sum(1 << i for i in self.keep_set)

        # 阀门按编号升序: 保证位序确定, 同代价时用编号列表直接做字典序比较
        self.valves_sorted = sorted(valves, key=lambda vl: vl["id"])
        self.nv = len(self.valves_sorted)
        self.total_masks = 1 << self.nv
        v_idx = {vl["id"]: i for i, vl in enumerate(self.valves_sorted)}
        self.costs = [vl["cost"] for vl in self.valves_sorted]

        # 邻接表: adj[u] = [(v, edge_index)]; edge_closed_bit[e] = 该边阀门的位
        adj: list[list[tuple[int, int]]] = [[] for _ in range(n)]
        self.edge_closed_bit: list[int] = []
        for sg in segments:
            u, v = self.idx[sg["endpoint_a"]], self.idx[sg["endpoint_b"]]
            e = len(self.edge_closed_bit)
            bit = ((1 << v_idx[sg["valve_id"]])
                   if sg["valve_id"] is not None else 0)
            self.edge_closed_bit.append(bit)
            adj[u].append((v, e))
            adj[v].append((u, e))
        self.adj = adj

    def reachable(self, mask: int, sources: set[int]) -> int:
        """从 sources 出发、避开 mask 关阀管段后可达节点的位掩码。"""
        seen = 0
        dq: deque[int] = deque()
        for s in sources:
            if not (seen >> s) & 1:
                seen |= 1 << s
                dq.append(s)
        while dq:
            u = dq.popleft()
            for w, e in self.adj[u]:
                bit = self.edge_closed_bit[e]
                if bit and (mask & bit):
                    continue
                if not (seen >> w) & 1:
                    seen |= 1 << w
                    dq.append(w)
        return seen

    def subset_costs(self) -> list[int]:
        """所有阀门子集的代价; 按 lowbit DP 递推。"""
        costs = [0] * self.total_masks
        for m in range(1, self.total_masks):
            low = m & -m
            costs[m] = costs[m ^ low] + self.costs[low.bit_length() - 1]
        return costs

    def closed_names(self, mask: int) -> list[str]:
        """mask 中关闭的阀门编号(编号升序)。"""
        return [self.valves_sorted[b]["id"]
                for b in range(self.nv) if (mask >> b) & 1]


def solve(payload: dict[str, Any]) -> dict[str, Any]:
    """求解最低代价关阀组合, 返回规划结果(见 README 的返回示例)。"""
    nodes, segments, valves = validate_network(payload)
    g = _Graph(nodes, segments, valves)

    # ---- 前置检查(不关任何阀门时) ----
    if not g.inlet_set:
        return _infeasible("NO_INLET",
                           "管网中没有进水点, 任何方案都无法供水。")
    base_reach = g.reachable(0, g.inlet_set)
    already_off = g.keep_bits & ~base_reach
    if already_off:
        names = [g.nodes[i]["id"] for i in range(g.n)
                 if (already_off >> i) & 1]
        return _infeasible(
            "GUARANTEED_ALREADY_DISCONNECTED",
            "即使不关任何阀门, 以下必保点也无法连通任何进水点(关阀只会进一步"
            "减少连通性, 故无解): " + ", ".join(names),
            {"starved_guaranteed": names},
        )

    isolating_count = 0
    if not g.leak_set:
        # 没有漏点: 无需关阀即可满足全部要求
        best_mask = 0
        isolating_count = 1
    else:
        subset_cost = g.subset_costs()
        best_mask = -1
        best_cost = None
        best_list: tuple[str, ...] = ()

        for m in range(g.total_masks):
            fed = g.reachable(m, g.inlet_set)
            if (fed & g.leak_bits) == 0:
                isolating_count += 1
            else:
                continue
            if (fed & g.keep_bits) != g.keep_bits:
                continue
            closed = tuple(g.closed_names(m))
            c = subset_cost[m]
            if (best_cost is None or c < best_cost
                    or (c == best_cost and closed < best_list)):
                best_cost, best_mask, best_list = c, m, closed

        if best_mask < 0:
            return _explain_infeasible(g, isolating_count)

    result = _build_statuses(g, best_mask, isolating_count)
    result["solver"] = "base"
    return result


def solve_failover(payload: dict[str, Any]) -> dict[str, Any]:
    """求解单阀失效备援关阀组合。

    方案 mask 备援可行 <=> mask 常规可行, 且对其中每个已关阀 j,
    mask\\{j}(j 关不上、保持开启)也常规可行。无解时用 infeasible_kind
    区分: no_base_plan(本来就没有常规可行方案) / no_failover_plan
    (常规方案存在, 但没有备援方案)。
    """
    nodes, segments, valves = validate_network(payload)
    g = _Graph(nodes, segments, valves)

    # ---- 与常规规划一致的前置检查; 此类情况下"原本就没有常规可行方案" ----
    if not g.inlet_set:
        return _infeasible(
            "NO_INLET", "管网中没有进水点, 任何方案都无法供水。",
            solver="failover", kind="no_base_plan")
    base_reach = g.reachable(0, g.inlet_set)
    already_off = g.keep_bits & ~base_reach
    if already_off:
        names = [g.nodes[i]["id"] for i in range(g.n)
                 if (already_off >> i) & 1]
        return _infeasible(
            "GUARANTEED_ALREADY_DISCONNECTED",
            "即使不关任何阀门, 以下必保点也无法连通任何进水点(关阀只会进一步"
            "减少连通性, 故无解): " + ", ".join(names),
            {"starved_guaranteed": names},
            solver="failover", kind="no_base_plan")

    # ---- 预计算每个阀门子集的常规可行性 ----
    # fed[m]: 关闭 m 时所有进水点可达节点; feasible[m]: 是否满足 (A)(B)
    isolating_count = 0
    feasible = [False] * g.total_masks
    for m in range(g.total_masks):
        fed = g.reachable(m, g.inlet_set)
        isolated = (fed & g.leak_bits) == 0
        if isolated:
            isolating_count += 1
        feasible[m] = isolated and (fed & g.keep_bits) == g.keep_bits

    base_feasible = [m for m in range(g.total_masks) if feasible[m]]
    if not base_feasible:
        # 常规规划本身无解: 复用常规无解原因分析
        result = _explain_infeasible(g, isolating_count)
        result["solver"] = "failover"
        result["infeasible_kind"] = "no_base_plan"
        return result

    # ---- 在常规可行方案中枚举备援可行方案 ----
    subset_cost = g.subset_costs()
    best_mask = -1
    best_cost = None
    best_list: tuple[str, ...] = ()
    failover_count = 0
    for m in base_feasible:
        # 每一枚计划阀门关不上时, 少关这枚阀的方案仍须常规可行
        robust = True
        bits = m
        while bits:
            low = bits & -bits
            if not feasible[m ^ low]:
                robust = False
                break
            bits ^= low
        if not robust:
            continue
        failover_count += 1
        closed = tuple(g.closed_names(m))
        c = subset_cost[m]
        if (best_cost is None or c < best_cost
                or (c == best_cost and closed < best_list)):
            best_cost, best_mask, best_list = c, m, closed

    if best_mask < 0:
        return _explain_no_failover(g, base_feasible, subset_cost)

    # ---- 构造正常执行 + 逐阀失效校验结果 ----
    result = _build_statuses(g, best_mask, isolating_count)
    result["solver"] = "failover"
    result["base_feasible_subset_count"] = len(base_feasible)
    result["failover_candidate_count"] = failover_count
    result["normal_check"] = _scenario_check(g, best_mask, None)
    result["failure_checks"] = [
        _scenario_check(g, best_mask ^ (1 << b), b)
        for b in range(g.nv) if (best_mask >> b) & 1
    ]
    n_closed = len(result["closed_valves"])
    result["message"] = (
        f"已找到单阀失效备援方案: 关闭 {n_closed} 个阀门, 总代价 "
        f"{result['total_cost']}。正常执行及任意一枚计划阀门关不上"
        f"(保持开启)时, 全部漏点均与进水点断开、全部必保点仍有供水。"
    )
    return result


def solve_siting(payload: dict[str, Any],
                 raw_candidates: Any) -> dict[str, Any]:
    """新增阀门选址预览求解(只读计算, 不写管网、不入库方案)。

    在已校验管网基础上, 允许在尚无阀门的管段上增设至多 MAX_CANDIDATES 个
    候选新阀(唯一新阀编号 + 正整数安装费 + 正整数关阀代价, 原阀与候选
    合计仍不超过 MAX_VALVES)。枚举"原阀 + 全部候选"的所有关阀子集(安装
    但不关闭的候选阀不影响连通性也不计费, 最优解不会包含它, 故关阀子集
    即方案), 要求全部漏点与进水点断开且全部必保点仍有水。优化次序:
      1) 安装费合计最小(只为实际关闭的候选阀计安装费);
      2) 本次关阀代价最小(被关闭的原阀关闭代价 + 新阀关阀代价之和);
      3) 新增管段编号升序列表字典序最小;
      4) 关阀编号升序列表字典序最小。
    无解时复用常规无解原因分析, 并说明候选范围内不可修复。
    """
    # ---- 1) 原管网校验(复用现有图校验) ----
    nodes, segments, valves = validate_network(payload)

    # ---- 2) 候选录入校验: 数量 / 新阀编号 / 安装管段 / 安装费 ----
    if raw_candidates is None:
        raw_candidates = []
    if not isinstance(raw_candidates, list):
        raise NetworkValidationError(["candidates 必须是数组"])
    errors: list[str] = []
    if len(raw_candidates) > MAX_CANDIDATES:
        errors.append(f"候选位置数量为 {len(raw_candidates)}, "
                      f"超过上限 {MAX_CANDIDATES} 个")
    candidates: list[dict[str, Any]] = []
    for i, cd in enumerate(raw_candidates):
        if not isinstance(cd, dict):
            errors.append(f"候选 #{i + 1}: 必须是对象")
            continue
        vid = _norm_id(cd.get("id"))
        seg_id = _norm_id(cd.get("segment_id"))
        if not vid:
            errors.append(f"候选 #{i + 1}: 缺少新阀编号")
        if not seg_id:
            errors.append(f"候选阀门 {vid or f'#{i + 1}'}: 必须选择安装管段")
        install = _strict_pos_int(cd.get("install_cost"))
        if install is None:
            errors.append(f"候选阀门 {vid or f'#{i + 1}'}: 安装费必须是正整数, "
                          f"收到: {cd.get('install_cost')!r}")
        candidates.append({"id": vid, "segment_id": seg_id,
                           "install_cost": install,
                           "close_cost": cd.get("close_cost")})

    # ---- 3) 扩展管网校验(复用现有图校验): 新阀编号唯一、管段存在且尚无
    #        阀门、关阀代价为正整数、原阀 + 候选合计 <= MAX_VALVES ----
    ext_payload = {
        "nodes": nodes,
        "segments": segments,
        "valves": ([{"id": v["id"], "segment_id": v["segment_id"],
                     "cost": v["cost"]} for v in valves]
                   + [{"id": c["id"], "segment_id": c["segment_id"],
                       "cost": c["close_cost"]} for c in candidates]),
    }
    try:
        nodes2, segments2, valves2 = validate_network(ext_payload)
    except NetworkValidationError as exc:
        raise NetworkValidationError(errors + exc.errors) from exc
    if errors:
        raise NetworkValidationError(errors)

    # ---- 4) 在扩展管网上枚举全部关阀子集(复用连通性判定) ----
    g = _Graph(nodes2, segments2, valves2)
    cand_by_id = {c["id"]: c for c in candidates}
    norm_valve = {v["id"]: v for v in valves2}
    # 每个阀门位上的安装费: 原阀为 0, 候选阀为其安装费
    installs = [0] * g.nv
    for b, vl in enumerate(g.valves_sorted):
        c = cand_by_id.get(vl["id"])
        if c is not None:
            installs[b] = c["install_cost"]

    def _unfixable(result: dict[str, Any]) -> dict[str, Any]:
        result["solver"] = "siting"
        result["message"] = ("候选范围内不可修复(已计入全部候选新阀): "
                             + result["message"])
        return result

    # 前置检查(与常规规划一致)
    if not g.inlet_set:
        return _unfixable(_infeasible(
            "NO_INLET", "管网中没有进水点, 任何方案都无法供水。"))
    base_reach = g.reachable(0, g.inlet_set)
    already_off = g.keep_bits & ~base_reach
    if already_off:
        names = [g.nodes[i]["id"] for i in range(g.n)
                 if (already_off >> i) & 1]
        return _unfixable(_infeasible(
            "GUARANTEED_ALREADY_DISCONNECTED",
            "即使不关任何阀门, 以下必保点也无法连通任何进水点(关阀只会进一步"
            "减少连通性, 故无解): " + ", ".join(names),
            {"starved_guaranteed": names}))

    # 全部子集的本次关阀代价 / 安装费(只计实际关闭的候选阀), lowbit DP
    close_sum = g.subset_costs()
    install_sum = [0] * g.total_masks
    for m in range(1, g.total_masks):
        low = m & -m
        install_sum[m] = install_sum[m ^ low] + installs[low.bit_length() - 1]

    best_key: tuple[int, int, tuple[str, ...], tuple[str, ...]] | None = None
    best_mask = -1
    isolating_count = 0
    for m in range(g.total_masks):
        fed = g.reachable(m, g.inlet_set)
        if (fed & g.leak_bits) == 0:
            isolating_count += 1
        else:
            continue
        if (fed & g.keep_bits) != g.keep_bits:
            continue
        new_segs = tuple(sorted(
            g.valves_sorted[b]["segment_id"]
            for b in range(g.nv)
            if (m >> b) & 1 and g.valves_sorted[b]["id"] in cand_by_id))
        key = (install_sum[m], close_sum[m], new_segs,
               tuple(g.closed_names(m)))
        if best_key is None or key < best_key:
            best_key, best_mask = key, m

    if best_mask < 0:
        return _unfixable(_explain_infeasible(g, isolating_count))

    # ---- 5) 构造选址预览结果(复用节点/管段状态构造) ----
    result = _build_statuses(g, best_mask, isolating_count)
    closed = result["closed_valves"]
    # 管段状态反映方案执行后的管网: 未被增设(未关闭)的候选阀不落在管段上
    for st in result["segment_status"]:
        vid = st["valve_id"]
        if vid is not None and vid in cand_by_id and vid not in closed:
            st["valve_id"] = None
    new_valves = [{
        "id": vid,
        "segment_id": norm_valve[vid]["segment_id"],
        "install_cost": cand_by_id[vid]["install_cost"],
        "close_cost": norm_valve[vid]["cost"],
    } for vid in closed if vid in cand_by_id]
    details = []
    for vid in closed:
        v = norm_valve[vid]
        d: dict[str, Any] = {"id": vid, "segment_id": v["segment_id"],
                             "close_cost": v["cost"],
                             "is_new": vid in cand_by_id}
        if vid in cand_by_id:
            d["install_cost"] = cand_by_id[vid]["install_cost"]
        details.append(d)

    install_total = install_sum[best_mask]
    close_total = result.pop("total_cost")  # _build_statuses 的总代价即本次关阀代价
    new_segment_ids = [v["segment_id"] for v in
                       sorted(new_valves, key=lambda x: x["segment_id"])]
    if new_valves:
        add_part = (f"在管段 {', '.join(new_segment_ids)} 增设 "
                    f"{len(new_valves)} 个新阀(安装费合计 {install_total})")
    else:
        add_part = "无需增设新阀(安装费 0)"
    result["solver"] = "siting"
    result["new_valves"] = new_valves
    result["new_segment_ids"] = new_segment_ids
    result["install_cost_total"] = install_total
    result["close_cost_total"] = close_total
    result["closed_valve_details"] = details
    result["candidate_count"] = len(candidates)
    result["message"] = (
        f"选址预览(只读, 不写入管网与历史方案): {add_part}; 本次共关闭 "
        f"{len(closed)} 个阀门, 关阀代价合计 {close_total}, "
        f"全部漏点已隔离、全部必保点仍有供水。")
    return result


def _scenario_check(g: _Graph, mask: int, failed_bit: int | None) -> dict[str, Any]:
    """一种执行情形下的 (A)(B) 校验; failed_bit=None 表示正常执行。"""
    fed = g.reachable(mask, g.inlet_set)
    leaks_reachable = [g.nodes[i]["id"] for i in range(g.n)
                       if ((g.leak_bits >> i) & 1 and (fed >> i) & 1)]
    keeps_starved = [g.nodes[i]["id"] for i in range(g.n)
                     if ((g.keep_bits >> i) & 1 and not (fed >> i) & 1)]
    check: dict[str, Any] = {
        "scenario": "normal" if failed_bit is None else "valve_failure",
        "failed_valve": (None if failed_bit is None
                         else g.valves_sorted[failed_bit]["id"]),
        "effective_closed_valves": g.closed_names(mask),
        "leaks_isolated": not leaks_reachable,
        "leaks_reachable": leaks_reachable,
        "keeps_supplied": not keeps_starved,
        "keeps_starved": keeps_starved,
        "ok": not leaks_reachable and not keeps_starved,
    }
    if failed_bit is not None:
        vl = g.valves_sorted[failed_bit]
        check["segment_id"] = vl["segment_id"]
        check["cost"] = vl["cost"]
    return check


def _explain_no_failover(g: _Graph, base_feasible: list[int],
                         subset_cost: list[int]) -> dict[str, Any]:
    """常规可行方案存在, 但没有任何备援可行方案。"""
    # 取最低代价(同代价字典序最小)的常规方案, 逐阀展示其失效后果
    base_best = -1
    base_best_cost = None
    base_best_list: tuple[str, ...] = ()
    for m in base_feasible:
        closed = tuple(g.closed_names(m))
        c = subset_cost[m]
        if (base_best_cost is None or c < base_best_cost
                or (c == base_best_cost and closed < base_best_list)):
            base_best_cost, base_best, base_best_list = c, m, closed

    checks = [
        _scenario_check(g, base_best ^ (1 << b), b)
        for b in range(g.nv) if (base_best >> b) & 1
    ]
    failing = [chk for chk in checks if not chk["ok"]]
    fail_desc = "; ".join(_describe_failure(chk) for chk in failing)
    message = (
        f"存在 {len(base_feasible)} 个常规可行方案, 但没有任何方案能承受单阀"
        f"失效。最低代价常规方案为关闭 "
        f"{', '.join(base_best_list) or '(无)'}(代价 {base_best_cost}); "
    )
    if not checks:
        message += "该方案不关任何阀门, 无需备援。"
    else:
        message += f"当其计划阀门关不上时: {fail_desc}。"

    return _infeasible(
        "NO_FAILOVER_PLAN", message,
        {
            "base_feasible_subset_count": len(base_feasible),
            "best_base_plan": {
                "closed_valves": list(base_best_list),
                "total_cost": base_best_cost,
                "failure_checks": checks,
            },
        },
        solver="failover", kind="no_failover_plan",
    )


def _describe_failure(chk: dict[str, Any]) -> str:
    reasons = []
    if chk["leaks_reachable"]:
        reasons.append("漏点 " + ", ".join(chk["leaks_reachable"]) + " 仍通进水点")
    if chk["keeps_starved"]:
        reasons.append("必保点 " + ", ".join(chk["keeps_starved"]) + " 断水")
    return f"阀门 {chk['failed_valve']} 关不上 -> {'; '.join(reasons)}"


def _build_statuses(g: _Graph, best_mask: int,
                    isolating_count: int) -> dict[str, Any]:
    """构造某方案下的节点/管段状态及汇总字段(方案正常执行视角)。"""
    n = g.n
    fed = g.reachable(best_mask, g.inlet_set)
    # 每个节点在该方案下可连通的进水点(逐进水点 BFS)
    inlet_of: list[list[str]] = [[] for _ in range(n)]
    for j in sorted(g.inlet_set):
        r = g.reachable(best_mask, {j})
        for i in range(n):
            if (r >> i) & 1:
                inlet_of[i].append(g.nodes[j]["id"])

    node_status: list[dict[str, Any]] = []
    for i, nd in enumerate(g.nodes):
        is_fed = bool((fed >> i) & 1)
        if nd["role"] == "leak":
            status = "isolated" if not is_fed else "leak_not_isolated"
        elif not is_fed:
            status = "disconnected"
        elif nd["role"] == "inlet":
            status = "inlet_supply"
        else:
            status = "supplied"
        node_status.append({
            "id": nd["id"], "label": nd["label"], "role": nd["role"],
            "supplied": is_fed, "status": status,
            "connected_inlets": inlet_of[i],
        })

    closed_valve_ids = set(g.closed_names(best_mask))
    segment_status: list[dict[str, Any]] = []
    for sg in g.segments:
        u, v = g.idx[sg["endpoint_a"]], g.idx[sg["endpoint_b"]]
        if sg["valve_id"] in closed_valve_ids:
            status, flowing = "closed", False
        elif (fed >> u) & 1 and (fed >> v) & 1:
            status, flowing = "flowing", True
        else:
            status, flowing = "dead", False
        segment_status.append({
            "id": sg["id"], "endpoint_a": sg["endpoint_a"],
            "endpoint_b": sg["endpoint_b"], "valve_id": sg["valve_id"],
            "status": status, "flowing": flowing,
        })

    closed = g.closed_names(best_mask)
    total_cost = sum(g.costs[b] for b in range(g.nv)
                     if (best_mask >> b) & 1)
    return {
        "feasible": True,
        "total_cost": total_cost,
        "closed_valves": closed,
        "closed_count": len(closed),
        "subset_count": g.total_masks,
        "isolating_subset_count": isolating_count,
        "node_status": node_status,
        "segment_status": segment_status,
        "message": (f"已找到最优关阀方案: 关闭 {len(closed)} 个阀门, "
                    f"总代价 {total_cost}。"),
    }


def _explain_infeasible(g: _Graph, isolating_count: int) -> dict[str, Any]:
    """常规无解原因分析(已有方案都不满足必保约束)。"""
    n, nv = g.n, g.nv

    if isolating_count == 0:
        # 全关阀后仍有漏点可达进水点: 存在不含阀门的通路
        all_closed = (1 << nv) - 1
        fed_all_closed = g.reachable(all_closed, g.inlet_set)
        reachable_leaks = [g.nodes[i]["id"] for i in range(n)
                           if ((g.leak_bits >> i) & 1
                               and (fed_all_closed >> i) & 1)]
        witness = _witness_path(g, all_closed, reachable_leaks)
        detail = "关闭全部阀门后, 漏点仍可经不含阀门的管段到达进水点, 无法切断。"
        if witness:
            detail += f" 无阀通路示例: {witness}。"
        return _infeasible(
            "UNCUTTABLE_LEAK_PATH", detail,
            {"reachable_leaks_when_all_closed": reachable_leaks,
             "witness_path": witness},
        )

    # 枚举所有"能隔离漏点"的方案, 求在每一方案中都断水的必保点交集
    always_starved: set[int] = set(g.keep_set)
    witness_valves: list[str] = []
    for m in range(1 << nv):
        fed = g.reachable(m, g.inlet_set)
        if (fed & g.leak_bits) != 0:
            continue
        starved = {i for i in g.keep_set if not (fed >> i) & 1}
        always_starved &= starved
        if not witness_valves and starved:
            witness_valves = g.closed_names(m)

    if always_starved:
        names = [g.nodes[i]["id"] for i in sorted(always_starved)]
        return _infeasible(
            "GUARANTEED_CONFLICT",
            "任何能隔离全部漏点的关阀组合, 都会使以下必保点与所有进水点断开, "
            "故不存在可行方案: " + ", ".join(names) + "。",
            {"starved_in_every_isolation": names,
             "example_isolation_valves": witness_valves},
        )
    return _infeasible(
        "GUARANTEED_CONFLICT",
        "每个能隔离漏点的关阀组合都会使至少一个必保点断水(不同组合影响的"
        "必保点不同), 无法同时满足隔离与必保供水要求。",
        {"example_isolation_valves": witness_valves},
    )


def _witness_path(g: _Graph, mask: int, target_node_ids: list[str]) -> str:
    """在关闭 mask 后仍走得通的图里, BFS 重建一条 进水点->目标漏点 的路径。"""
    if not target_node_ids:
        return ""
    targets = {g.idx[t] for t in target_node_ids}
    prev_node = [-1] * g.n
    prev_edge = [-1] * g.n
    dq: deque[int] = deque()
    for s in g.inlet_set:
        if prev_node[s] == -1:
            prev_node[s] = s
            dq.append(s)
    found = -1
    while dq:
        u = dq.popleft()
        if u in targets:
            found = u
            break
        for w, e in g.adj[u]:
            bit = g.edge_closed_bit[e]
            if bit and (mask & bit):
                continue
            if prev_node[w] == -1:
                prev_node[w] = u
                prev_edge[w] = e
                dq.append(w)
    if found < 0:
        return ""
    path_nodes: list[str] = []
    path_segs: list[str] = []
    cur = found
    while prev_node[cur] != cur:
        path_nodes.append(g.nodes[cur]["id"])
        path_segs.append(g.segments[prev_edge[cur]]["id"])
        cur = prev_node[cur]
    path_nodes.append(g.nodes[cur]["id"])
    path_nodes.reverse()
    path_segs.reverse()
    text = path_nodes[0]
    for sid, nid in zip(path_segs, path_nodes[1:]):
        text += f" --管段 {sid}--> {nid}"
    return text


def _infeasible(code: str, message: str, extra: dict | None = None,
                *, solver: str = "base", kind: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "feasible": False,
        "solver": solver,
        "reason_code": code,
        "message": message,
        "closed_valves": [],
        "total_cost": None,
        "node_status": [],
        "segment_status": [],
    }
    if kind is not None:
        out["infeasible_kind"] = kind
    if extra:
        out["reason_detail"] = extra
    return out


# ---------------------------------------------------------------------------
# 现场执行顺序规划(只读计算, 针对已保存的可行方案)
# ---------------------------------------------------------------------------

class SequenceInputError(NetworkValidationError):
    """执行顺序规划的录入数据不合法, errors 字段携带逐条原因。"""


def _positive_int(value: Any) -> int | None:
    """严格正整数: 拒绝 bool/浮点/字符串/0/负数, 合法时返回 int。"""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _non_negative_int(value: Any) -> int | None:
    """非负整数: 拒绝 bool/浮点/字符串/负数, 合法时返回 int(含 0)。"""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def plan_sequence(snapshot: dict[str, Any],
                  closed_valves: list[str],
                  durations: dict[str, Any],
                  leak_weights: dict[str, Any]) -> dict[str, Any]:
    """为可行关阀方案规划现场执行顺序(只读, 不修改任何已存数据)。

    模型:
      - 计划阀门逐枚关闭; 操作阀门 v 的时段内 v 仍开启(未关上), 该时段的
        暴露量 = v 的操作时长 × 此时段仍与进水点连通的漏点权重之和。
      - 每步完成后按多进水点连通性(BFS)更新仍通水漏点。
      - 目标: 排列全部计划阀门, 使各时段暴露量之和(累计暴露量)最小;
        同暴露量时取阀门编号序列字典序最小的排列, 保证顺序唯一。

    解法: 仍通水漏点集合只取决于"已关闭阀门集合 S"而与顺序无关, 故用
    子集 DP: suffix[S] = 从已关闭集合 S 做到全部关完的最小累计暴露量,
    suffix[S] = min_{v∉S}(d_v × W(S) + suffix[S∪{v}])。k≤14 => 2^k×k
    次转移。之后从空集出发, 每步在保持最优的候选阀门中取编号最小者,
    即得字典序最小的最优排列。
    """
    try:
        nodes, segments, valves = validate_network(snapshot)
    except NetworkValidationError as exc:
        raise SequenceInputError(
            ["方案快照数据不合法: " + e for e in exc.errors])
    g = _Graph(nodes, segments, valves)

    errors: list[str] = []

    # ---- 计划阀门必须存在于快照中 ----
    valve_by_id = {vl["id"]: vl for vl in valves}
    plan_valves = sorted(dict.fromkeys(closed_valves))
    plan_set = set(plan_valves)
    for vid in plan_valves:
        if vid not in valve_by_id:
            errors.append(f"计划阀门 {vid} 不存在于方案快照的管网中")

    # ---- 操作时长: 编号集合必须恰好等于计划阀门集合, 值为正整数 ----
    raw_dur = durations if isinstance(durations, dict) else {}
    dur: dict[str, int] = {}
    missing = [v for v in plan_valves if v not in raw_dur]
    extra = sorted(k for k in raw_dur if k not in plan_set)
    if missing:
        errors.append("缺少计划阀门的操作时长: " + ", ".join(missing))
    if extra:
        errors.append("提供了非计划阀门的操作时长(多余编号): "
                      + ", ".join(extra))
    for v in plan_valves:
        if v in raw_dur:
            val = _positive_int(raw_dur[v])
            if val is None:
                errors.append(
                    f"阀门 {v} 的操作时长必须是正整数(分钟), "
                    f"收到: {raw_dur[v]!r}")
            else:
                dur[v] = val

    # ---- 漏水权重: 编号集合必须恰好等于快照漏点集合, 值为正整数 ----
    leak_ids = sorted(nd["id"] for nd in nodes if nd["role"] == "leak")
    leak_set = set(leak_ids)
    raw_w = leak_weights if isinstance(leak_weights, dict) else {}
    weight: dict[str, int] = {}
    missing_l = [lid for lid in leak_ids if lid not in raw_w]
    extra_l = sorted(k for k in raw_w if k not in leak_set)
    if missing_l:
        errors.append("缺少漏点的漏水权重: " + ", ".join(missing_l))
    if extra_l:
        errors.append("提供了非漏点的漏水权重(多余编号): "
                      + ", ".join(extra_l))
    for lid in leak_ids:
        if lid in raw_w:
            val = _positive_int(raw_w[lid])
            if val is None:
                errors.append(
                    f"漏点 {lid} 的漏水权重必须是正整数, "
                    f"收到: {raw_w[lid]!r}")
            else:
                weight[lid] = val

    if not g.inlet_set and (plan_valves or leak_ids):
        errors.append("方案快照中没有进水点, 无法评估漏点连通性")

    if errors:
        raise SequenceInputError(errors)

    k = len(plan_valves)
    full = (1 << k) - 1
    v_idx = {vl["id"]: i for i, vl in enumerate(g.valves_sorted)}
    plan_bits = [1 << v_idx[v] for v in plan_valves]
    leak_index = {lid: i for i, lid in enumerate(leak_ids)}

    # ---- 每个计划阀门子集 S: 实际关阀掩码 / 仍通水漏点位掩码 / 权重和 ----
    size = 1 << k
    g_mask = [0] * size       # 子集 s 对应的 _Graph 关阀位掩码
    flowing = [0] * size      # 子集 s 下仍通水漏点的位掩码
    wsum = [0] * size         # 子集 s 下仍通水漏点权重之和
    for s in range(size):
        if s:
            low = s & -s
            g_mask[s] = g_mask[s ^ low] | plan_bits[low.bit_length() - 1]
        fed = g.reachable(g_mask[s], g.inlet_set)
        fm = 0
        for lid, li in leak_index.items():
            if (fed >> g.idx[lid]) & 1:
                fm |= 1 << li
        flowing[s] = fm
        ws = 0
        m = fm
        while m:
            low = m & -m
            ws += weight[leak_ids[low.bit_length() - 1]]
            m ^= low
        wsum[s] = ws

    # ---- 子集 DP: suffix[s] = 从已关闭集合 s 做到全部关完的最小暴露量 ----
    suffix: list[int | None] = [None] * size
    suffix[full] = 0
    for s in range(full - 1, -1, -1):  # ns = s∪{j} > s, 倒序递推
        best: int | None = None
        ws = wsum[s]
        for j in range(k):
            if (s >> j) & 1:
                continue
            val = dur[plan_valves[j]] * ws + suffix[s | (1 << j)]
            if best is None or val < best:
                best = val
        suffix[s] = best

    # ---- 从空集出发, 每步取能保持全局最优的最小编号阀门 => 字典序最小 ----
    order: list[int] = []
    s = 0
    while s != full:
        for j in range(k):  # plan_valves 已按编号升序
            if (s >> j) & 1:
                continue
            ns = s | (1 << j)
            if dur[plan_valves[j]] * wsum[s] + suffix[ns] == suffix[s]:
                order.append(j)
                s = ns
                break

    def leak_names(fm: int) -> list[str]:
        return [lid for lid in leak_ids if (fm >> leak_index[lid]) & 1]

    # ---- 逐步生成展示数据(起止时间/刚隔离/仍通水/累计暴露量) ----
    steps: list[dict[str, Any]] = []
    t = 0
    cum = 0
    s = 0
    for pos, j in enumerate(order):
        vid = plan_valves[j]
        d = dur[vid]
        exp = d * wsum[s]
        ns = s | (1 << j)
        newly = flowing[s] & ~flowing[ns]
        cum += exp
        steps.append({
            "order": pos + 1,
            "valve_id": vid,
            "segment_id": valve_by_id[vid]["segment_id"],
            "duration": d,
            "start": t,
            "end": t + d,
            "flowing_leaks_during": leak_names(flowing[s]),
            "flowing_weight_during": wsum[s],
            "exposure": exp,
            "newly_isolated_leaks": leak_names(newly),
            "flowing_leaks_after": leak_names(flowing[ns]),
            "flowing_weight_after": wsum[ns],
            "cumulative_exposure": cum,
        })
        t += d
        s = ns

    seq_names = [plan_valves[j] for j in order]
    if seq_names:
        message = (f"最优执行顺序: {' → '.join(seq_names)}; 总时长 {t} 分钟, "
                   f"累计暴露量 {cum}。")
    else:
        message = "该方案无需关闭任何阀门, 无操作时段, 累计暴露量 0。"
    return {
        "ok": True,
        "closed_valves": plan_valves,
        "durations": dur,
        "leak_weights": weight,
        "initial_flowing_leaks": leak_names(flowing[0]),
        "initial_flowing_weight": wsum[0],
        "final_flowing_leaks": leak_names(flowing[full]),
        "sequence": seq_names,
        "steps": steps,
        "total_duration": t,
        "total_exposure": cum,
        "message": message,
    }


# ---------------------------------------------------------------------------
# 临时供水跨接预览(只读计算, 针对已保存的可行方案)
# ---------------------------------------------------------------------------

def plan_jumpers(snapshot: dict[str, Any],
                 closed_valves: list[str],
                 raw_candidates: Any) -> dict[str, Any]:
    """已保存可行方案的临时供水跨接预览(只读计算, 不改方案与管网)。

    基于方案快照与已关阀管段(即方案执行后的管网), 评估至多 MAX_CANDIDATES
    条候选跨接: 每条含唯一编号、两个不同的现有节点与正整数铺设费, 跨接视为
    新增通水管段(无阀门, 铺设后始终通水)。枚举全部候选组合, 要求加入跨接后
    仍保持全部漏点与进水点断开、全部必保点有水; 在此前提下依次:
      1) 最大化由断水转为有水的普通节点数;
      2) 最小化铺设费合计;
      3) 跨接编号升序列表字典序最小。
    无法恢复任何普通节点时返回空方案(不铺设跨接, 费用 0)。
    """
    try:
        nodes, segments, valves = validate_network(snapshot)
    except NetworkValidationError as exc:
        raise NetworkValidationError(
            ["方案快照数据不合法: " + e for e in exc.errors]) from exc

    errors: list[str] = []

    # ---- 方案已关阀管段(计划阀门必须存在于快照管网中) ----
    valve_by_id = {vl["id"]: vl for vl in valves}
    closed = sorted(dict.fromkeys(_norm_id(v) for v in (closed_valves or [])))
    for vid in closed:
        if vid not in valve_by_id:
            errors.append(f"方案关闭的阀门 {vid} 不存在于方案快照的管网中")
    closed_segments = {valve_by_id[v]["segment_id"] for v in closed
                       if v in valve_by_id}

    # ---- 候选跨接录入校验: 数量 / 唯一编号 / 两个不同现有节点 / 正整数铺设费 ----
    if raw_candidates is None:
        raw_candidates = []
    if not isinstance(raw_candidates, list):
        raise NetworkValidationError(["candidates 必须是数组"])
    if len(raw_candidates) > MAX_CANDIDATES:
        errors.append(f"候选跨接数量为 {len(raw_candidates)}, "
                      f"超过上限 {MAX_CANDIDATES} 条")
    node_ids = {nd["id"] for nd in nodes}
    segment_ids = {sg["id"] for sg in segments}
    cands: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for i, cd in enumerate(raw_candidates):
        if not isinstance(cd, dict):
            errors.append(f"候选跨接 #{i + 1}: 必须是对象")
            continue
        jid = _norm_id(cd.get("id"))
        a, b = _norm_id(cd.get("endpoint_a")), _norm_id(cd.get("endpoint_b"))
        if not jid:
            errors.append(f"候选跨接 #{i + 1}: 缺少跨接编号")
        elif jid in seen_ids:
            errors.append(f"跨接编号重复: {jid}")
        elif jid in segment_ids:
            errors.append(f"跨接编号 {jid} 与现有管段编号重复")
        seen_ids.add(jid)
        label = jid or f"#{i + 1}"
        if not a or not b:
            errors.append(f"候选跨接 {label}: 必须选择两个不同的现有节点作为端点")
        else:
            if a not in node_ids:
                errors.append(
                    f"候选跨接 {label}: 端点 {a} 不存在于方案快照的节点中")
            if b not in node_ids:
                errors.append(
                    f"候选跨接 {label}: 端点 {b} 不存在于方案快照的节点中")
            if a == b and a in node_ids:
                errors.append(f"候选跨接 {label}: 两个端点不能相同({a})")
        cost = _positive_int(cd.get("cost"))
        if cost is None:
            errors.append(f"候选跨接 {label}: 铺设费必须是正整数, "
                          f"收到: {cd.get('cost')!r}")
        cands.append({"id": jid, "endpoint_a": a, "endpoint_b": b,
                      "cost": cost})
    if errors:
        raise NetworkValidationError(errors)

    # ---- 图: 方案执行后的管网(已关阀管段移除) + 候选跨接边 ----
    n = len(nodes)
    idx = {nd["id"]: i for i, nd in enumerate(nodes)}
    base_adj: list[list[int]] = [[] for _ in range(n)]
    for sg in segments:
        if sg["id"] in closed_segments:
            continue
        u, v = idx[sg["endpoint_a"]], idx[sg["endpoint_b"]]
        base_adj[u].append(v)
        base_adj[v].append(u)
    jumper_adj: list[list[tuple[int, int]]] = [[] for _ in range(n)]
    for j, cd in enumerate(cands):
        u, v = idx[cd["endpoint_a"]], idx[cd["endpoint_b"]]
        jumper_adj[u].append((v, 1 << j))
        jumper_adj[v].append((u, 1 << j))

    inlet_set = {i for i, nd in enumerate(nodes) if nd["role"] == "inlet"}
    leak_bits = sum(1 << i for i, nd in enumerate(nodes)
                    if nd["role"] == "leak")
    keep_bits = sum(1 << i for i, nd in enumerate(nodes)
                    if nd["role"] == "must_keep")
    normal_idx = [i for i, nd in enumerate(nodes) if nd["role"] == "normal"]

    def reachable(active: int) -> int:
        """从全部进水点出发, 经未关阀管段与已铺设跨接(active 位掩码)可达节点。"""
        seen = 0
        dq: deque[int] = deque()
        for s in inlet_set:
            if not (seen >> s) & 1:
                seen |= 1 << s
                dq.append(s)
        while dq:
            u = dq.popleft()
            for w in base_adj[u]:
                if not (seen >> w) & 1:
                    seen |= 1 << w
                    dq.append(w)
            for w, bit in jumper_adj[u]:
                if (active & bit) and not (seen >> w) & 1:
                    seen |= 1 << w
                    dq.append(w)
        return seen

    fed_base = reachable(0)
    disconnected_before = [nodes[i]["id"] for i in normal_idx
                           if not (fed_base >> i) & 1]

    # ---- 枚举候选组合: 始终保持 (A)(B), 优化 (恢复数, 铺设费, 编号列表) ----
    m = len(cands)
    best_key: tuple[int, int, tuple[str, ...]] | None = None
    best_active = 0
    best_fed = fed_base
    feasible_combinations = 0
    for active in range(1 << m):
        fed = reachable(active)
        if (fed & leak_bits) != 0 or (fed & keep_bits) != keep_bits:
            continue
        feasible_combinations += 1
        restored = sum(1 for i in normal_idx
                       if (fed >> i) & 1 and not (fed_base >> i) & 1)
        cost = sum(cands[j]["cost"] for j in range(m) if (active >> j) & 1)
        ids = tuple(sorted(cands[j]["id"] for j in range(m)
                           if (active >> j) & 1))
        key = (-restored, cost, ids)
        if best_key is None or key < best_key:
            best_key, best_active, best_fed = key, active, fed
    if best_key is None:
        # 方案本身已不满足 (A)(B)(数据不一致时兜底): 返回空方案
        best_active, best_fed = 0, fed_base

    selected = [cands[j] for j in range(m) if (best_active >> j) & 1]
    selected.sort(key=lambda c: c["id"])
    selected_ids = [c["id"] for c in selected]
    lay_total = sum(c["cost"] for c in selected)
    restored_nodes = [nodes[i]["id"] for i in normal_idx
                      if (best_fed >> i) & 1 and not (fed_base >> i) & 1]
    still_disconnected = [nodes[i]["id"] for i in normal_idx
                          if not (best_fed >> i) & 1]

    # ---- 铺设跨接后的节点/管段状态(复用状态构造, 跨接为新增通水管段) ----
    final_segments = segments + [
        {"id": c["id"], "endpoint_a": c["endpoint_a"],
         "endpoint_b": c["endpoint_b"], "valve_id": None}
        for c in selected
    ]
    g = _Graph(nodes, final_segments, valves)
    v_idx = {vl["id"]: b for b, vl in enumerate(g.valves_sorted)}
    mask = 0
    for vid in closed:
        mask |= 1 << v_idx[vid]
    statuses = _build_statuses(g, mask, feasible_combinations)
    jumper_set = set(selected_ids)
    for st in statuses["segment_status"]:
        if st["id"] in jumper_set:
            st["is_jumper"] = True

    if restored_nodes:
        message = (
            f"临时供水跨接预览(只读, 不修改管网与历史方案): 铺设 "
            f"{len(selected)} 条跨接({', '.join(selected_ids)}), 铺设费合计 "
            f"{lay_total}, 恢复供水普通节点 {len(restored_nodes)} 个"
            f"({', '.join(restored_nodes)}); 全部漏点仍与进水点断开、"
            f"全部必保点仍有供水。")
    elif not disconnected_before:
        message = ("临时供水跨接预览(只读, 不修改管网与历史方案): 方案执行后"
                   "没有断水的普通节点, 无需铺设跨接, 返回空方案(费用 0)。")
    else:
        message = (
            f"临时供水跨接预览(只读, 不修改管网与历史方案): 断水普通节点 "
            f"{', '.join(disconnected_before)} 无法经候选跨接恢复供水"
            f"(跨接不得使漏点复通进水点), 返回空方案(不铺设跨接, 费用 0)。")

    return {
        "ok": True,
        "closed_valves": statuses["closed_valves"],
        "candidate_count": m,
        "combination_count": 1 << m,
        "feasible_combination_count": feasible_combinations,
        "selected_jumpers": selected,
        "selected_ids": selected_ids,
        "lay_cost_total": lay_total,
        "restored_nodes": restored_nodes,
        "restored_count": len(restored_nodes),
        "disconnected_normal_before": disconnected_before,
        "still_disconnected_normal": still_disconnected,
        "node_status": statuses["node_status"],
        "segment_status": statuses["segment_status"],
        "message": message,
    }


# ---------------------------------------------------------------------------
# 关阀成本与断水影响权衡预览(只读计算, 针对当前编辑管网)
# ---------------------------------------------------------------------------

def solve_tradeoff(payload: dict[str, Any],
                   raw_weights: Any) -> dict[str, Any]:
    """关阀成本与断水影响权衡预览(只读计算, 不写管网、不入库方案)。

    为每个普通节点录入正整数用水权重(录入的键必须恰好是全部普通节点
    编号)。枚举全部关阀子集, 仅保留全部漏点与进水点断开且全部必保点
    仍有水的方案, 对每个方案计算双目标:
      1) 关阀代价合计 = 被关闭阀门的关闭代价之和;
      2) 断水影响 = 原本(不关阀时)有水、关阀后断水的普通节点用水权重
         之和(原本就断水的普通节点不计入)。
    同一对指标只保留关阀编号升序列表字典序最小的方案; 返回全部非支配
    方案(不存在另一可行方案代价与断水影响都不更大且至少一项严格更小),
    按 (关阀代价合计, 断水影响, 关阀编号升序列表) 升序排列。
    """
    nodes, segments, valves = validate_network(payload)
    g = _Graph(nodes, segments, valves)

    # ---- 用水权重录入校验: 键恰好是普通节点集合, 值为正整数 ----
    normal_ids = sorted(nd["id"] for nd in nodes if nd["role"] == "normal")
    normal_set = set(normal_ids)
    label_of = {nd["id"]: nd["label"] for nd in nodes}
    errors: list[str] = []
    raw_w = raw_weights if isinstance(raw_weights, dict) else {}
    weights: dict[str, int] = {}
    missing = [nid for nid in normal_ids if nid not in raw_w]
    extra = sorted(k for k in raw_w if k not in normal_set)
    if missing:
        errors.append("缺少普通节点的用水权重: " + ", ".join(missing))
    if extra:
        errors.append("提供了非普通节点的用水权重(多余编号): "
                      + ", ".join(extra))
    for nid in normal_ids:
        if nid in raw_w:
            val = _positive_int(raw_w[nid])
            if val is None:
                errors.append(f"普通节点 {nid} 的用水权重必须是正整数, "
                              f"收到: {raw_w[nid]!r}")
            else:
                weights[nid] = val
    if errors:
        raise NetworkValidationError(errors)

    # ---- 前置检查(与常规规划一致) ----
    if not g.inlet_set:
        return _infeasible("NO_INLET",
                           "管网中没有进水点, 任何方案都无法供水。",
                           solver="tradeoff")
    base_reach = g.reachable(0, g.inlet_set)
    already_off = g.keep_bits & ~base_reach
    if already_off:
        names = [g.nodes[i]["id"] for i in range(g.n)
                 if (already_off >> i) & 1]
        return _infeasible(
            "GUARANTEED_ALREADY_DISCONNECTED",
            "即使不关任何阀门, 以下必保点也无法连通任何进水点(关阀只会进一步"
            "减少连通性, 故无解): " + ", ".join(names),
            {"starved_guaranteed": names},
            solver="tradeoff")

    # 原本(不关阀时)有水的普通节点: 只有它们计入断水影响
    base_fed_normal = [nid for nid in normal_ids
                       if (base_reach >> g.idx[nid]) & 1]
    base_fed_set = set(base_fed_normal)

    # ---- 枚举全部关阀子集: 同一对(代价, 断水影响)只留字典序最小关阀清单 ----
    subset_cost = g.subset_costs()
    isolating_count = 0
    feasible_count = 0
    best_by_pair: dict[tuple[int, int], tuple[tuple[str, ...], int]] = {}
    for m in range(g.total_masks):
        fed = g.reachable(m, g.inlet_set)
        if (fed & g.leak_bits) != 0:
            continue
        isolating_count += 1
        if (fed & g.keep_bits) != g.keep_bits:
            continue
        feasible_count += 1
        impact = 0
        for nid in base_fed_normal:
            if not (fed >> g.idx[nid]) & 1:
                impact += weights[nid]
        closed = tuple(g.closed_names(m))
        key = (subset_cost[m], impact)
        cur = best_by_pair.get(key)
        if cur is None or closed < cur[0]:
            best_by_pair[key] = (closed, m)

    if not best_by_pair:
        result = _explain_infeasible(g, isolating_count)
        result["solver"] = "tradeoff"
        return result

    # ---- 非支配方案: 按代价升序扫描, 断水影响严格刷新最小值才入选 ----
    plans: list[dict[str, Any]] = []
    min_impact: int | None = None
    for (cost, impact), (closed, m) in sorted(best_by_pair.items()):
        if min_impact is not None and impact >= min_impact:
            continue  # 被此前某方案支配(代价不更高且断水影响更小)
        min_impact = impact
        fed = g.reachable(m, g.inlet_set)
        newly = [nid for nid in base_fed_normal
                 if not (fed >> g.idx[nid]) & 1]
        plans.append({
            "closed_valves": list(closed),
            "closed_count": len(closed),
            "total_cost": cost,
            "impact": impact,
            "newly_disconnected": newly,
            "newly_disconnected_details": [
                {"id": nid, "label": label_of[nid], "weight": weights[nid]}
                for nid in newly
            ],
        })

    # 结果按 (代价, 断水影响, 关阀编号升序列表) 排序(扫描顺序已满足, 显式排一次)
    plans.sort(key=lambda p: (p["total_cost"], p["impact"], p["closed_valves"]))

    return {
        "feasible": True,
        "solver": "tradeoff",
        "weights": weights,
        "normal_nodes": normal_ids,
        "baseline_fed_normal": base_fed_normal,
        "baseline_disconnected_normal": [nid for nid in normal_ids
                                         if nid not in base_fed_set],
        "subset_count": g.total_masks,
        "isolating_subset_count": isolating_count,
        "feasible_subset_count": feasible_count,
        "plan_count": len(plans),
        "plans": plans,
        "message": (
            f"权衡预览(只读, 不写入管网与历史方案): 枚举 {g.total_masks} 个"
            f"关阀组合, 其中 {feasible_count} 个满足漏点全隔离且必保点全有"
            f"水; 按(关阀代价合计, 断水影响)双目标求得非支配方案 "
            f"{len(plans)} 个, 已按代价、断水影响升序排列。"),
    }


# ---------------------------------------------------------------------------
# 失效监测点布设预览(只读计算, 针对已保存的可行方案)
# ---------------------------------------------------------------------------

def plan_monitors(snapshot: dict[str, Any],
                  closed_valves: list[str],
                  raw_candidates: Any) -> dict[str, Any]:
    """已保存可行方案的失效监测点布设预览(只读计算, 不改方案与管网)。

    从方案快照的**非进水节点**中录入至多 MAX_MONITOR_CANDIDATES 个候选
    监测点(编号不得重复), 每个候选有正整数布设费。模拟 1+k 种情形
    (k=计划关闭阀门数): 正常执行(全部计划阀门关闭)与每枚计划阀门单独
    关不上(该阀保持开启、其余照常关闭), 按多进水点 BFS 求各情形下有水
    的节点。监测点集可行当且仅当任意两种情形在该点集上的有水/无水读数
    向量不同; 优化次序:
      1) 布设费合计最小;
      2) 节点编号升序列表字典序最小。
    若全部候选点也无法区分某些情形对, 则无可行点集, 返回这些情形对。
    """
    try:
        nodes, segments, valves = validate_network(snapshot)
    except NetworkValidationError as exc:
        raise NetworkValidationError(
            ["方案快照数据不合法: " + e for e in exc.errors]) from exc

    errors: list[str] = []

    # ---- 计划关闭阀门必须存在于快照管网中 ----
    valve_by_id = {vl["id"]: vl for vl in valves}
    closed = sorted(dict.fromkeys(_norm_id(v) for v in (closed_valves or [])))
    for vid in closed:
        if vid not in valve_by_id:
            errors.append(f"方案关闭的阀门 {vid} 不存在于方案快照的管网中")

    # ---- 候选监测点录入校验: 数量 / 非进水节点 / 编号唯一 / 正整数布设费 ----
    if raw_candidates is None:
        raw_candidates = []
    if not isinstance(raw_candidates, list):
        raise NetworkValidationError(["candidates 必须是数组"])
    if len(raw_candidates) > MAX_MONITOR_CANDIDATES:
        errors.append(f"候选监测点数量为 {len(raw_candidates)}, "
                      f"超过上限 {MAX_MONITOR_CANDIDATES} 个")
    node_by_id = {nd["id"]: nd for nd in nodes}
    cands: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for i, cd in enumerate(raw_candidates):
        if not isinstance(cd, dict):
            errors.append(f"候选监测点 #{i + 1}: 必须是对象")
            continue
        nid = _norm_id(cd.get("node_id"))
        label = nid or f"#{i + 1}"
        if not nid:
            errors.append(f"候选监测点 #{i + 1}: 缺少节点编号")
        elif nid in seen_ids:
            errors.append(f"监测点编号重复: {nid}")
        elif nid not in node_by_id:
            errors.append(f"候选监测点 {nid} 不存在于方案快照的节点中")
        elif node_by_id[nid]["role"] == "inlet":
            errors.append(f"候选监测点 {nid} 是进水点, 只能在非进水节点布设")
        seen_ids.add(nid)
        cost = _positive_int(cd.get("cost"))
        if cost is None:
            errors.append(f"监测点 {label} 的布设费必须是正整数, "
                          f"收到: {cd.get('cost')!r}")
        cands.append({"node_id": nid, "cost": cost})
    if errors:
        raise NetworkValidationError(errors)

    # ---- 情形: 正常执行 + 每枚计划阀门单独关不上(该阀保持开启) ----
    g = _Graph(nodes, segments, valves)
    v_idx = {vl["id"]: b for b, vl in enumerate(g.valves_sorted)}
    base_mask = 0
    for vid in closed:
        base_mask |= 1 << v_idx[vid]
    scenarios: list[dict[str, Any]] = [{
        "scenario": "normal",
        "failed_valve": None,
        "label": "正常执行(全部按计划关闭)",
        "mask": base_mask,
    }]
    for vid in closed:
        scenarios.append({
            "scenario": "valve_failure",
            "failed_valve": vid,
            "label": f"阀门 {vid} 关不上(保持开启)",
            "mask": base_mask ^ (1 << v_idx[vid]),
        })
    s_count = len(scenarios)
    for sc in scenarios:
        sc["effective_closed_valves"] = g.closed_names(sc["mask"])
        sc["fed"] = g.reachable(sc["mask"], g.inlet_set)

    # ---- 每个候选点: 跨情形读数位掩码 -> 可区分的情形对位掩码 ----
    # pair_bit[(i,j)]: 情形对 (i,j) 的位; 候选点 p 的 dpat 含 (i,j) 位 <=>
    # p 在情形 i 与情形 j 的有水/无水读数不同。
    m = len(cands)
    pair_bit = {(i, j): 1 << (i * s_count + j)
                for i in range(s_count) for j in range(i + 1, s_count)}
    all_pairs_mask = 0
    for bit in pair_bit.values():
        all_pairs_mask |= bit
    pats: list[int] = []   # pats[j]: 候选点 j 在各情形有水的位掩码
    dpats: list[int] = []  # dpats[j]: 候选点 j 可区分的情形对位掩码
    for cd in cands:
        ni = g.idx[cd["node_id"]]
        p = 0
        for si, sc in enumerate(scenarios):
            if (sc["fed"] >> ni) & 1:
                p |= 1 << si
        pats.append(p)
        d = 0
        for (i, j), bit in pair_bit.items():
            if ((p >> i) ^ (p >> j)) & 1:
                d |= bit
        dpats.append(d)

    # ---- 子集并集(可区分情形对)与布设费合计: lowbit DP ----
    size = 1 << m
    union_d = [0] * size
    cost_sum = [0] * size
    for s in range(1, size):
        low = s & -s
        b = low.bit_length() - 1
        union_d[s] = union_d[s ^ low] | dpats[b]
        cost_sum[s] = cost_sum[s ^ low] + cands[b]["cost"]

    cand_sorted_idx = sorted(range(m), key=lambda j: cands[j]["node_id"])

    def _readings(si: int, idxs: list[int]) -> list[dict[str, Any]]:
        return [{"node_id": cands[j]["node_id"],
                 "supplied": bool((pats[j] >> si) & 1)} for j in idxs]

    def _scenario_out(si: int, idxs: list[int]) -> dict[str, Any]:
        sc = scenarios[si]
        return {
            "scenario": sc["scenario"],
            "failed_valve": sc["failed_valve"],
            "label": sc["label"],
            "effective_closed_valves": sc["effective_closed_valves"],
            "readings": _readings(si, idxs),
        }

    def _scenario_ref(si: int) -> dict[str, Any]:
        sc = scenarios[si]
        return {"scenario": sc["scenario"],
                "failed_valve": sc["failed_valve"],
                "label": sc["label"]}

    # ---- 全部候选点也无法区分的情形对 -> 无可行点集 ----
    missing = all_pairs_mask & ~union_d[size - 1]
    if missing:
        pairs = [{"a": _scenario_ref(i), "b": _scenario_ref(j)}
                 for (i, j), bit in pair_bit.items() if missing & bit]
        pair_text = "; ".join(
            f"{p['a']['label']} ↔ {p['b']['label']}" for p in pairs)
        return {
            "ok": False,
            "reason_code": "INDISTINGUISHABLE_SCENARIOS",
            "closed_valves": closed,
            "candidate_count": m,
            "scenario_count": s_count,
            "scenarios": [_scenario_out(si, cand_sorted_idx)
                          for si in range(s_count)],
            "indistinguishable_pairs": pairs,
            "message": (
                f"失效监测点布设预览(只读, 不修改管网与历史方案): 候选监测点"
                f"无法区分全部 {s_count} 种情形 — 以下 {len(pairs)} 对情形在"
                f"所有候选点上的有水/无水读数完全相同: {pair_text}。"
                f"请调整候选监测点。"),
        }

    # ---- 枚举候选子集: (布设费合计, 节点编号升序列表) 字典序最小 ----
    best_key: tuple[int, tuple[str, ...]] | None = None
    best_mask = 0
    distinguishing = 0
    for s in range(size):
        if union_d[s] != all_pairs_mask:
            continue
        distinguishing += 1
        ids = tuple(sorted(cands[j]["node_id"]
                           for j in range(m) if (s >> j) & 1))
        key = (cost_sum[s], ids)
        if best_key is None or key < best_key:
            best_key, best_mask = key, s

    sel_idx = sorted((j for j in range(m) if (best_mask >> j) & 1),
                     key=lambda j: cands[j]["node_id"])
    selected = [{"node_id": cands[j]["node_id"], "cost": cands[j]["cost"]}
                for j in sel_idx]
    sel_ids = [c["node_id"] for c in selected]
    total = cost_sum[best_mask]
    if sel_ids:
        message = (
            f"失效监测点布设预览(只读, 不修改管网与历史方案): 在 "
            f"{', '.join(sel_ids)} 布设 {len(sel_ids)} 个监测点, 布设费合计 "
            f"{total}; 任意两种情形(正常执行 + {s_count - 1} 种单阀关不上)"
            f"在所选点的有水/无水读数都不同。")
    else:
        message = ("失效监测点布设预览(只读, 不修改管网与历史方案): "
                   "该方案不关闭任何阀门, 仅正常执行一种情形, "
                   "无需布设监测点(空点集, 布设费合计 0)。")
    return {
        "ok": True,
        "closed_valves": closed,
        "candidate_count": m,
        "scenario_count": s_count,
        "scenarios": [_scenario_out(si, sel_idx) for si in range(s_count)],
        "selected_points": selected,
        "selected_node_ids": sel_ids,
        "total_cost": total,
        "subset_count": size,
        "distinguishing_subset_count": distinguishing,
        "message": message,
    }


# ---------------------------------------------------------------------------
# 应急送水分配预览(只读计算, 针对已保存的可行方案)
# ---------------------------------------------------------------------------

def _dinic_maxflow(caps: list[list[int]], src: int, sink: int) -> int:
    """整数容量有向图上的最大流(Dinic)。caps 为容量邻接矩阵, 不修改入参。"""
    n = len(caps)
    residual = [row[:] for row in caps]
    total = 0
    while True:
        level = [-1] * n
        level[src] = 0
        dq: deque[int] = deque([src])
        while dq:
            u = dq.popleft()
            for w in range(n):
                if residual[u][w] > 0 and level[w] < 0:
                    level[w] = level[u] + 1
                    dq.append(w)
        if level[sink] < 0:
            return total

        def dfs(u: int, pushed: int) -> int:
            if u == sink:
                return pushed
            for w in range(n):
                if residual[u][w] > 0 and level[w] == level[u] + 1:
                    f = dfs(w, min(pushed, residual[u][w]))
                    if f:
                        residual[u][w] -= f
                        residual[w][u] += f
                        return f
            return 0

        while True:
            f = dfs(src, 10 ** 30)
            if not f:
                break
            total += f


def plan_water_delivery(snapshot: dict[str, Any],
                        closed_valves: list[str],
                        raw_demands: Any,
                        raw_vehicles: Any) -> dict[str, Any]:
    """已保存可行方案的应急送水分配预览(只读计算, 不改方案与管网)。

    以方案快照中关阀(closed_valves)后断水的**普通节点**为需求点, 逐点
    录入正整数需水量; 录入至多 MAX_WATER_VEHICLES 辆候选送水车, 每辆含
    唯一编号、正整数出车费与载水量, 以及可服务的需求点列表。允许一个
    需求点由多车分担(整数水量)。枚举全部车辆组合, 用整数最大流判定组合
    能否满足全部需求(源->车容量=载水量, 车->可服务需求点容量=总需求,
    需求点->汇容量=需水量), 依次按:
      1) 出车费合计最低;
      2) 车辆编号升序列表字典序最小
    选取车辆组合。选中组合内各车向各点的配送量按(需求点编号, 车辆编号)
    双关键字贪心确定(逐单位用残余网络最大流校验), 结果唯一。全部候选车
    仍无法满足时, 给出最大可配送量(全部候选车最大流)与总缺口; 没有断水
    需求点时返回空调度。
    """
    try:
        nodes, segments, valves = validate_network(snapshot)
    except NetworkValidationError as exc:
        raise NetworkValidationError(
            ["方案快照数据不合法: " + e for e in exc.errors]) from exc

    errors: list[str] = []

    # ---- 计划关闭阀门必须存在于快照管网中 ----
    valve_by_id = {vl["id"]: vl for vl in valves}
    closed = sorted(dict.fromkeys(_norm_id(v) for v in (closed_valves or [])))
    for vid in closed:
        if vid not in valve_by_id:
            errors.append(f"方案关闭的阀门 {vid} 不存在于方案快照的管网中")

    # ---- 方案执行后的断水普通节点 = 需求点 ----
    g = _Graph(nodes, segments, valves)
    v_idx = {vl["id"]: b for b, vl in enumerate(g.valves_sorted)}
    mask = 0
    for vid in closed:
        if vid in v_idx:
            mask |= 1 << v_idx[vid]
    fed = g.reachable(mask, g.inlet_set)
    demand_ids = sorted(nd["id"] for nd in nodes
                        if nd["role"] == "normal"
                        and not (fed >> g.idx[nd["id"]]) & 1)
    label_of = {nd["id"]: nd["label"] for nd in nodes}
    demand_set = set(demand_ids)

    # ---- 需水量录入校验: 每个需求点必须有正整数需水量, 不允许多余编号 ----
    demands: dict[str, int] = {}
    if not isinstance(raw_demands, dict):
        errors.append("demands 必须是以需求点编号为键的对象")
        raw_d: dict[str, Any] = {}
    else:
        raw_d = raw_demands
        missing = [nid for nid in demand_ids if nid not in raw_d]
        extra = sorted(str(k) for k in raw_d if k not in demand_set)
        if missing:
            errors.append("缺少断水需求点的需水量: " + ", ".join(missing))
        if extra:
            errors.append("提供了非断水普通节点的需水量(多余编号): "
                          + ", ".join(extra))
        for nid in demand_ids:
            if nid in raw_d:
                val = _positive_int(raw_d[nid])
                if val is None:
                    errors.append(f"需求点 {nid} 的需水量必须是正整数, "
                                  f"收到: {raw_d[nid]!r}")
                else:
                    demands[nid] = val

    # ---- 候选车辆录入校验: 至多 6 辆 / 唯一编号 / 正整数出车费与载水量 /
    #        可服务点必须是本次断水需求点 ----
    if raw_vehicles is None:
        raw_vehicles = []
    if not isinstance(raw_vehicles, list):
        raise NetworkValidationError(["vehicles 必须是数组"])
    if len(raw_vehicles) > MAX_WATER_VEHICLES:
        errors.append(f"候选送水车数量为 {len(raw_vehicles)}, "
                      f"超过上限 {MAX_WATER_VEHICLES} 辆")
    vehicles: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for i, vh in enumerate(raw_vehicles):
        if not isinstance(vh, dict):
            errors.append(f"候选车辆 #{i + 1}: 必须是对象")
            continue
        vid = _norm_id(vh.get("id"))
        label = vid or f"#{i + 1}"
        if not vid:
            errors.append(f"候选车辆 #{i + 1}: 缺少车辆编号")
        elif vid in seen_ids:
            errors.append(f"车辆编号重复: {vid}")
        seen_ids.add(vid)
        cost = _positive_int(vh.get("cost"))
        if cost is None:
            errors.append(f"车辆 {label}: 出车费必须是正整数, "
                          f"收到: {vh.get('cost')!r}")
        capacity = _positive_int(vh.get("capacity"))
        if capacity is None:
            errors.append(f"车辆 {label}: 载水量必须是正整数, "
                          f"收到: {vh.get('capacity')!r}")
        serves: list[str] = []
        raw_serves = vh.get("serves", [])
        if not isinstance(raw_serves, list):
            errors.append(f"车辆 {label}: 可服务需求点必须是数组")
        else:
            seen_serves: set[str] = set()
            for s in raw_serves:
                sid = _norm_id(s)
                if not sid:
                    errors.append(f"车辆 {label}: 可服务需求点编号不能为空")
                elif sid not in demand_set:
                    errors.append(f"车辆 {label}: 可服务点 {sid} 不是本次关阀后"
                                  f"断水的普通节点(需求点)")
                elif sid not in seen_serves:
                    seen_serves.add(sid)
                    serves.append(sid)
        vehicles.append({"id": vid, "cost": cost, "capacity": capacity,
                         "serves": sorted(serves)})
    if errors:
        raise NetworkValidationError(errors)

    # ---- 没有断水需求点: 录入合法后返回空调度 ----
    if not demand_ids:
        return {
            "ok": True,
            "satisfied": True,
            "empty": True,
            "closed_valves": closed,
            "demand_nodes": [],
            "demands": {},
            "candidate_count": len(vehicles),
            "selected_vehicle_ids": [],
            "deliveries": {},
            "delivery_matrix": [],
            "node_summary": [],
            "delivered_total": 0,
            "total_demand": 0,
            "shortage_total": 0,
            "total_cost": 0,
            "combination_count": 1,
            "feasible_combination_count": 1,
            "message": ("应急送水分配预览(只读, 不修改管网与历史方案): "
                        "方案执行后没有断水的普通节点, 无需应急送水, "
                        "返回空调度。"),
        }

    # ---- 最大流模型 ----
    # 节点编号: 0=源; 1..m=车; 1+m..m+k=需求点; m+k+1=汇
    m = len(vehicles)
    k = len(demand_ids)
    sink = 1 + m + k
    total_demand = sum(demands[nid] for nid in demand_ids)
    for vh in vehicles:
        vh["serves_set"] = set(vh["serves"])

    def build_caps(active: list[int],
                   need: dict[str, int]) -> list[list[int]]:
        caps = [[0] * (sink + 1) for _ in range(sink + 1)]
        for j in active:
            vh = vehicles[j]
            caps[0][1 + j] = vh["capacity"]
            for t, nid in enumerate(demand_ids):
                if nid in vh["serves_set"]:
                    caps[1 + j][1 + m + t] = total_demand
        for t, nid in enumerate(demand_ids):
            caps[1 + m + t][sink] = need[nid]
        return caps

    def flow_of(active: list[int], need: dict[str, int]) -> int:
        return _dinic_maxflow(build_caps(active, need), 0, sink)

    # ---- 枚举全部车辆组合: 可行优先, 再比(出车费, 编号升序列表) ----
    best_key: tuple[int, int, tuple[str, ...]] | None = None
    best_active: list[int] = []
    feasible_combinations = 0
    for bits in range(1 << m):
        active = [j for j in range(m) if (bits >> j) & 1]
        satisfied = flow_of(active, demands) >= total_demand
        if satisfied:
            feasible_combinations += 1
        ids = tuple(sorted(vehicles[j]["id"] for j in active))
        key = (0 if satisfied else 1,
               sum(vehicles[j]["cost"] for j in active), ids)
        if best_key is None or key < best_key:
            best_key, best_active = key, active

    def greedy_allocate(active: list[int],
                        targets: dict[str, int]) -> dict[str, dict[str, int]]:
        """按(需求点编号, 车辆编号)双关键字贪心求整数配送量。

        每条 (需求点, 车辆) 边二分可占用的最大单位数: 占用后在残余容量
        网络上, 其余未锁定的需求仍能完成(最大流 >= 剩余目标之和)。已
        锁定容量直接从网络中扣除, 故越靠前的(点, 车)越优先被填满, 结果
        与流算法内部顺序无关、唯一确定。targets 为各点目标配送量(全满足
        时为需水量; 不足时为各点最大可配送量), 调用方须保证其可完成。
        """
        alloc: dict[str, dict[str, int]] = {
            nid: {vehicles[j]["id"]: 0 for j in active}
            for nid in demand_ids
        }
        caps = build_caps(active, targets)
        ordered = [(vehicles[j]["id"], j) for j in active]
        ordered.sort(key=lambda x: x[0])
        for t, nid in enumerate(demand_ids):
            node_v = 1 + m + t
            for vid, j in ordered:
                veh_v = 1 + j
                upper = min(caps[0][veh_v], caps[veh_v][node_v],
                            caps[node_v][sink])
                if upper <= 0:
                    continue
                remaining = sum(targets[n2] - sum(alloc[n2].values())
                                for n2 in demand_ids)
                lo, hi = 0, upper
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    trial = [row[:] for row in caps]
                    trial[0][veh_v] -= mid
                    trial[veh_v][node_v] -= mid
                    trial[node_v][sink] -= mid
                    if _dinic_maxflow(trial, 0, sink) >= remaining - mid:
                        lo = mid
                    else:
                        hi = mid - 1
                if lo:
                    caps[0][veh_v] -= lo
                    caps[veh_v][node_v] -= lo
                    caps[node_v][sink] -= lo
                    alloc[nid][vid] = lo
        return alloc

    def make_matrix(active: list[int],
                    alloc: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
        matrix = []
        for j in active:
            vid = vehicles[j]["id"]
            matrix.append({
                "vehicle_id": vid,
                "cost": vehicles[j]["cost"],
                "capacity": vehicles[j]["capacity"],
                "deliveries": [{"node_id": nid, "amount": alloc[nid][vid]}
                               for nid in demand_ids],
                "delivered_total": sum(alloc[nid][vid] for nid in demand_ids),
            })
        matrix.sort(key=lambda x: x["vehicle_id"])
        return matrix

    if feasible_combinations:
        # ---- 全部需求可满足: 最优组合的唯一整数配送量 ----
        alloc = greedy_allocate(best_active, demands)
        selected = [vehicles[j] for j in best_active]
        selected.sort(key=lambda v: v["id"])
        selected_ids = [v["id"] for v in selected]
        total_cost = sum(v["cost"] for v in selected)
        matrix = make_matrix(best_active, alloc)
        deliveries = {row["vehicle_id"]: {d["node_id"]: d["amount"]
                                          for d in row["deliveries"]}
                      for row in matrix}
        node_summary = [{
            "node_id": nid, "label": label_of[nid],
            "demand": demands[nid], "delivered": demands[nid], "shortage": 0,
            "by_vehicle": [{"vehicle_id": vid, "amount": alloc[nid][vid]}
                           for vid in selected_ids if alloc[nid][vid] > 0],
        } for nid in demand_ids]
        message = (
            f"应急送水分配预览(只读, 不修改管网与历史方案): 选派 "
            f"{len(selected_ids)} 辆车({', '.join(selected_ids) or '无'}), "
            f"出车费合计 {total_cost}, 全部 {k} 个断水需求点(共需水 "
            f"{total_demand})均满足; 允许同一需求点由多车分担, "
            f"整数水量分配结果唯一。")
        return {
            "ok": True,
            "satisfied": True,
            "empty": False,
            "closed_valves": closed,
            "demand_nodes": [{"id": nid, "label": label_of[nid],
                              "demand": demands[nid]} for nid in demand_ids],
            "demands": demands,
            "candidate_count": m,
            "combination_count": 1 << m,
            "feasible_combination_count": feasible_combinations,
            "selected_vehicles": [{
                "id": v["id"], "cost": v["cost"], "capacity": v["capacity"],
                "serves": v["serves"],
            } for v in selected],
            "selected_vehicle_ids": selected_ids,
            "deliveries": deliveries,
            "delivery_matrix": matrix,
            "node_summary": node_summary,
            "delivered_total": total_demand,
            "total_demand": total_demand,
            "shortage_total": 0,
            "total_cost": total_cost,
            "message": message,
        }

    # ---- 全部候选车仍无法满足: 全部车参与, 求各点最大可配送量 ----
    all_active = list(range(m))

    # 按需求点编号升序逐个锁定: 前序点配送量锁定后, 本点尽可能多配。
    # 测试本点上界时把后续点的汇边容量置 0(后续点只会与前序点争抢车辆,
    # 去掉它们不影响前序点的可完成性), 于是前序+本点目标全部可完成,
    # 当且仅当最大流恰好等于已锁定总量与本点上界之和。
    targets: dict[str, int] = {}
    for t, nid in enumerate(demand_ids):
        lo, hi = 0, demands[nid]
        while lo < hi:
            mid = (lo + hi + 1) // 2
            need = {n2: 0 for n2 in demand_ids}
            for n2, val in targets.items():
                need[n2] = val
            need[nid] = mid
            locked_sum = sum(targets.values()) + mid
            if flow_of(all_active, need) == locked_sum:
                lo = mid
            else:
                hi = mid - 1
        targets[nid] = lo

    max_delivered = sum(targets.values())
    alloc = greedy_allocate(all_active, targets)
    matrix = make_matrix(all_active, alloc)
    deliveries = {row["vehicle_id"]: {d["node_id"]: d["amount"]
                                      for d in row["deliveries"]}
                  for row in matrix}
    used_ids = [row["vehicle_id"] for row in matrix
                if row["delivered_total"] > 0]
    shortage_total = total_demand - max_delivered
    node_summary = [{
        "node_id": nid, "label": label_of[nid],
        "demand": demands[nid], "delivered": targets[nid],
        "shortage": demands[nid] - targets[nid],
        "by_vehicle": [{"vehicle_id": row["vehicle_id"],
                        "amount": alloc[nid][row["vehicle_id"]]}
                       for row in matrix if alloc[nid][row["vehicle_id"]] > 0],
    } for nid in demand_ids]
    message = (
        f"应急送水分配预览(只读, 不修改管网与历史方案): 全部 {m} 辆候选车"
        f"仍无法满足 {k} 个断水需求点(共需水 {total_demand}), 最大可配送量 "
        f"{max_delivered}, 总缺口 {shortage_total}; 已按需求点编号升序列出"
        f"各点缺口与分担车辆。")
    return {
        "ok": False,
        "reason_code": "INSUFFICIENT_CAPACITY",
        "satisfied": False,
        "empty": False,
        "closed_valves": closed,
        "demand_nodes": [{"id": nid, "label": label_of[nid],
                          "demand": demands[nid]} for nid in demand_ids],
        "demands": demands,
        "candidate_count": m,
        "combination_count": 1 << m,
        "feasible_combination_count": 0,
        "selected_vehicles": [],
        "selected_vehicle_ids": [],
        "used_vehicle_ids": used_ids,
        "deliveries": deliveries,
        "delivery_matrix": matrix,
        "node_summary": node_summary,
        "delivered_total": max_delivered,
        "total_demand": total_demand,
        "shortage_total": shortage_total,
        "total_cost": None,
        "message": message,
    }


# ---------------------------------------------------------------------------
# 关阀作业备件包采购预览(只读计算, 针对已保存的可行方案)
# ---------------------------------------------------------------------------

def plan_spare_parts(snapshot: dict[str, Any],
                     closed_valves: list[str],
                     raw_valve_demands: Any,
                     raw_packages: Any) -> dict[str, Any]:
    """已保存可行方案的关阀作业备件包采购预览(只读计算, 不改方案与管网)。

    为方案计划关闭的每枚阀门录入该阀所需备件: 备件种类 -> 正整数数量
    (无需备件的阀门录空表)。合并各阀需求得到各类总需求。录入至多
    MAX_SPARE_PACKAGES 个采购包, 每包含唯一编号、正整数价格, 以及
    contents: 按备件种类列出的非负整数件数(只能买一次)。枚举全部采购包
    组合(每类到货量为包内件数之和), 依次按:
      1) 能否覆盖全部需求(优先可行);
      2) 总价最低;
      3) 采购包编号升序列表字典序最小
    选取组合。全部采购包合起来仍不足以覆盖某类需求时, 返回逐类缺口
    (不产生采购方案, total_cost 为 null)。没有关阀备件需求时返回零费用
    空清单。
    """
    try:
        nodes, segments, valves = validate_network(snapshot)
    except NetworkValidationError as exc:
        raise NetworkValidationError(
            ["方案快照数据不合法: " + e for e in exc.errors]) from exc

    errors: list[str] = []

    # ---- 计划关闭阀门必须存在于快照管网中 ----
    valve_by_id = {vl["id"]: vl for vl in valves}
    closed = sorted(dict.fromkeys(_norm_id(v) for v in (closed_valves or [])))
    for vid in closed:
        if vid not in valve_by_id:
            errors.append(f"方案关闭的阀门 {vid} 不存在于方案快照的管网中")
    closed_set = set(closed)

    # ---- 逐阀备件需求录入校验: 每枚计划阀门一条, 数量为正整数 ----
    if raw_valve_demands is None:
        raw_valve_demands = {}
    if not isinstance(raw_valve_demands, dict):
        raise NetworkValidationError(["valve_demands 必须是以阀门编号为键的对象"])
    missing_v = [vid for vid in closed if vid not in raw_valve_demands]
    extra_v = sorted(_norm_id(k) for k in raw_valve_demands
                     if _norm_id(k) not in closed_set)
    if missing_v:
        errors.append("缺少计划关闭阀门的备件需求: " + ", ".join(missing_v))
    if extra_v:
        errors.append("提供了非计划关闭阀门的备件需求(多余编号): "
                      + ", ".join(v for v in extra_v if v))
    valve_demands: dict[str, dict[str, int]] = {}
    for vid in closed:
        raw_parts = raw_valve_demands.get(vid, {})
        parts: dict[str, int] = {}
        if not isinstance(raw_parts, dict):
            errors.append(f"阀门 {vid}: 备件需求必须是以备件种类为键的对象")
        else:
            for pkey, pval in raw_parts.items():
                pid = _norm_id(pkey)
                if not pid:
                    errors.append(f"阀门 {vid}: 备件种类名称不能为空")
                    continue
                val = _positive_int(pval)
                if val is None:
                    errors.append(f"阀门 {vid} 的备件 {pid} 数量必须是正整数, "
                                  f"收到: {pval!r}")
                else:
                    parts[pid] = parts.get(pid, 0) + val
        valve_demands[vid] = parts

    # ---- 采购包录入校验: 至多 12 个 / 唯一编号 / 正整数价格 /
    #        按备件种类的非负整数件数 ----
    if raw_packages is None:
        raw_packages = []
    if not isinstance(raw_packages, list):
        raise NetworkValidationError(["packages 必须是数组"])
    if len(raw_packages) > MAX_SPARE_PACKAGES:
        errors.append(f"采购包数量为 {len(raw_packages)}, "
                      f"超过上限 {MAX_SPARE_PACKAGES} 个")
    packages: list[dict[str, Any]] = []
    seen_pids: set[str] = set()
    for i, pk in enumerate(raw_packages):
        if not isinstance(pk, dict):
            errors.append(f"采购包 #{i + 1}: 必须是对象")
            continue
        pid = _norm_id(pk.get("id"))
        label = pid or f"#{i + 1}"
        if not pid:
            errors.append(f"采购包 #{i + 1}: 缺少采购包编号")
        elif pid in seen_pids:
            errors.append(f"采购包编号重复: {pid}")
        seen_pids.add(pid)
        price = _positive_int(pk.get("price"))
        if price is None:
            errors.append(f"采购包 {label}: 价格必须是正整数, "
                          f"收到: {pk.get('price')!r}")
        raw_contents = pk.get("contents", {})
        contents: dict[str, int] = {}
        if not isinstance(raw_contents, dict):
            errors.append(f"采购包 {label}: 备件件数必须是以备件种类为键的对象")
        elif not raw_contents:
            errors.append(f"采购包 {label}: 必须至少列出一种备件(件数为非负整数)")
        else:
            for ckey, cval in raw_contents.items():
                cid = _norm_id(ckey)
                if not cid:
                    errors.append(f"采购包 {label}: 备件种类名称不能为空")
                    continue
                val = _non_negative_int(cval)
                if val is None:
                    errors.append(f"采购包 {label} 的备件 {cid} 件数必须是"
                                  f"非负整数, 收到: {cval!r}")
                else:
                    contents[cid] = contents.get(cid, 0) + val
        packages.append({"id": pid, "price": price, "contents": contents})
    if errors:
        raise NetworkValidationError(errors)

    # ---- 合并各阀需求: 种类 -> 总需求 ----
    merged: dict[str, int] = {}
    for vid in closed:
        for pid, qty in valve_demands[vid].items():
            merged[pid] = merged.get(pid, 0) + qty
    part_ids = sorted(merged)
    total_demand = sum(merged.values())

    # 逐阀需求明细(编号升序, 各类数量按种类名升序)
    valve_demand_details = [{
        "valve_id": vid,
        "segment_id": valve_by_id[vid]["segment_id"],
        "parts": [{"part_id": pid, "quantity": valve_demands[vid][pid]}
                  for pid in sorted(valve_demands[vid])],
        "part_count": len(valve_demands[vid]),
        "quantity_total": sum(valve_demands[vid].values()),
    } for vid in closed]

    empty_message = ("关阀作业备件包采购预览(只读, 不修改管网与历史方案): "
                     "没有需要采购备件的关阀作业, 返回零费用空清单。")
    if not part_ids:
        return {
            "ok": True,
            "satisfied": True,
            "empty": True,
            "closed_valves": closed,
            "valve_demands": valve_demands,
            "valve_demand_details": valve_demand_details,
            "merged_demands": {},
            "part_ids": [],
            "candidate_count": len(packages),
            "combination_count": 1,
            "feasible_combination_count": 1,
            "selected_packages": [],
            "selected_package_ids": [],
            "total_cost": 0,
            "part_summary": [],
            "arrived_total": 0,
            "total_demand": 0,
            "surplus_total": 0,
            "shortage_total": 0,
            "message": empty_message,
        }

    # ---- 枚举全部采购包组合(每类件数求和): 可行优先, 再比(总价, 编号列表) ----
    m = len(packages)
    demand_vec = [merged[pid] for pid in part_ids]
    p_index = {pid: t for t, pid in enumerate(part_ids)}
    pkg_vec: list[list[int]] = []
    pkg_price: list[int] = []
    for pk in packages:
        vec = [0] * len(part_ids)
        for cid, qty in pk["contents"].items():
            t = p_index.get(cid)
            if t is not None:
                vec[t] += qty
        pkg_vec.append(vec)
        pkg_price.append(pk["price"])

    # 各子集件数合计与总价: lowbit DP(件数为逐类向量)
    size = 1 << m
    sums = [[0] * len(part_ids) for _ in range(size)]
    prices = [0] * size
    for bits in range(1, size):
        low = bits & -bits
        j = low.bit_length() - 1
        prev = sums[bits ^ low]
        vec = pkg_vec[j]
        sums[bits] = [prev[t] + vec[t] for t in range(len(part_ids))]
        prices[bits] = prices[bits ^ low] + pkg_price[j]

    def covers(arrived: list[int]) -> bool:
        return all(arrived[t] >= demand_vec[t]
                   for t in range(len(part_ids)))

    best_bits = 0
    best_key: tuple[int, int, tuple[str, ...]] | None = None
    feasible_combinations = 0
    for bits in range(size):
        if not covers(sums[bits]):
            continue
        feasible_combinations += 1
        ids = tuple(sorted(packages[j]["id"] for j in range(m)
                           if (bits >> j) & 1))
        key = (prices[bits], ids)
        if best_key is None or key < best_key:
            best_key, best_bits = key, bits

    # ---- 全部采购包合起来仍不足: 逐类缺口 ----
    if best_key is None:
        all_arrived = sums[size - 1] if m else [0] * len(part_ids)
        gap_total = 0
        part_summary = []
        gaps = []
        for t, pid in enumerate(part_ids):
            demand = merged[pid]
            arrived = all_arrived[t]
            gap = max(0, demand - arrived)
            gap_total += gap
            part_summary.append({"part_id": pid, "demand": demand,
                                 "arrived": arrived, "surplus": 0,
                                 "shortage": gap})
            if gap > 0:
                gaps.append({"part_id": pid, "demand": demand,
                             "available": arrived, "shortage": gap})
        message = (
            f"关阀作业备件包采购预览(只读, 不修改管网与历史方案): 全部 "
            f"{m} 个采购包合起来仍无法满足 {len(part_ids)} 类备件需求"
            f"(共需 {total_demand} 件), 总缺口 {gap_total} 件; "
            f"逐类缺口已列出, 不产生采购方案。")
        return {
            "ok": False,
            "reason_code": "INSUFFICIENT_PACKAGES",
            "satisfied": False,
            "empty": False,
            "closed_valves": closed,
            "valve_demands": valve_demands,
            "valve_demand_details": valve_demand_details,
            "merged_demands": merged,
            "part_ids": part_ids,
            "candidate_count": m,
            "combination_count": size,
            "feasible_combination_count": 0,
            "selected_packages": [],
            "selected_package_ids": [],
            "total_cost": None,
            "part_summary": part_summary,
            "arrived_total": sum(all_arrived),
            "total_demand": total_demand,
            "surplus_total": 0,
            "shortage_total": gap_total,
            "shortages": gaps,
            "message": message,
        }

    # ---- 覆盖全部需求: 采购清单 + 各类需求/到货/余量 ----
    sel_idx = sorted((j for j in range(m) if (best_bits >> j) & 1),
                     key=lambda j: packages[j]["id"])
    arrived_vec = sums[best_bits]
    selected_packages = [{
        "id": packages[j]["id"],
        "price": packages[j]["price"],
        "contents": [{"part_id": pid, "quantity": packages[j]["contents"][pid]}
                     for pid in sorted(packages[j]["contents"])],
    } for j in sel_idx]
    selected_ids = [packages[j]["id"] for j in sel_idx]
    total_cost = prices[best_bits]
    arrived_total = sum(arrived_vec)
    surplus_total = arrived_total - total_demand
    part_summary = [{
        "part_id": pid,
        "demand": merged[pid],
        "arrived": arrived_vec[t],
        "surplus": arrived_vec[t] - merged[pid],
        "shortage": 0,
    } for t, pid in enumerate(part_ids)]
    message = (
        f"关阀作业备件包采购预览(只读, 不修改管网与历史方案): 选买 "
        f"{len(selected_ids)} 个采购包({', '.join(selected_ids) or '无'}), "
        f"总价 {total_cost}, 全部 {len(part_ids)} 类备件需求(共 {total_demand} "
        f"件)均覆盖, 到货余量合计 {surplus_total} 件; 同价时按采购包编号"
        f"升序列表字典序决胜。")
    return {
        "ok": True,
        "satisfied": True,
        "empty": False,
        "closed_valves": closed,
        "valve_demands": valve_demands,
        "valve_demand_details": valve_demand_details,
        "merged_demands": merged,
        "part_ids": part_ids,
        "candidate_count": m,
        "combination_count": size,
        "feasible_combination_count": feasible_combinations,
        "selected_packages": selected_packages,
        "selected_package_ids": selected_ids,
        "total_cost": total_cost,
        "part_summary": part_summary,
        "arrived_total": arrived_total,
        "total_demand": total_demand,
        "surplus_total": surplus_total,
        "shortage_total": 0,
        "message": message,
    }


# ---------------------------------------------------------------------------
# 供水容量校核(只读计算, 针对已保存的可行方案)
# ---------------------------------------------------------------------------

def plan_capacity_check(snapshot: dict[str, Any],
                        closed_valves: list[str],
                        raw_capacities: Any,
                        raw_supplies: Any,
                        raw_demands: Any) -> dict[str, Any]:
    """已保存可行方案的供水容量校核(只读计算, 不改方案与管网)。

    以方案快照中**未关阀管段**(计划阀门未关闭的管段)构成无向输水网:
    每条管段录入正整数流量上限(管段净流量的绝对值受同一个上限约束,
    即无向边容量, 用两条容量相同的反向有向弧建模, 最大流值与无向容量
    一致), 每个进水点录入正整数供给上限, 每个必保供水点录入正整数需求。
    三类录入的编号集合都必须与方案快照**完整对应**(未关阀管段 / 进水点 /
    必保点, 不多不少)。用整数最大流(Dinic)求可送达必保点的最大总量:
    源->进水点容量=供给上限, 管段=无向容量边, 必保点->汇容量=需求。
    各必保点实际送达量按必保点编号升序逐个锁定: 前序点送达量锁定后,
    本点在残余网络上尽可能多送(二分 + 最大流校验), 结果唯一。返回需求
    总量、最大送达量、总缺口与各必保点实际送达量; 总送达量等于需求总量
    才判容量充足, 仅连通但容量不足时返回不足; 无必保点时返回充足及
    零需求。
    """
    try:
        nodes, segments, valves = validate_network(snapshot)
    except NetworkValidationError as exc:
        raise NetworkValidationError(
            ["方案快照数据不合法: " + e for e in exc.errors]) from exc

    errors: list[str] = []

    # ---- 计划关闭阀门必须存在于快照管网中 ----
    valve_by_id = {vl["id"]: vl for vl in valves}
    closed = sorted(dict.fromkeys(_norm_id(v) for v in (closed_valves or [])))
    for vid in closed:
        if vid not in valve_by_id:
            errors.append(f"方案关闭的阀门 {vid} 不存在于方案快照的管网中")
    closed_segments = {valve_by_id[v]["segment_id"] for v in closed
                       if v in valve_by_id}

    # ---- 未关阀管段构成无向输水网; 进水点供给 / 必保点需求 ----
    open_segments = [sg for sg in segments if sg["id"] not in closed_segments]
    open_seg_ids = [sg["id"] for sg in open_segments]
    open_seg_set = set(open_seg_ids)
    inlet_ids = sorted(nd["id"] for nd in nodes if nd["role"] == "inlet")
    inlet_set = set(inlet_ids)
    keep_ids = sorted(nd["id"] for nd in nodes if nd["role"] == "must_keep")
    keep_set = set(keep_ids)
    label_of = {nd["id"]: nd["label"] for nd in nodes}

    # ---- 管段流量上限: 键恰好是全部未关阀管段, 值为正整数 ----
    if not isinstance(raw_capacities, dict):
        errors.append("capacities 必须是以管段编号为键的对象")
        raw_cap: dict[str, Any] = {}
    else:
        raw_cap = raw_capacities
    capacities: dict[str, int] = {}
    missing_c = [sid for sid in open_seg_ids if sid not in raw_cap]
    extra_c = sorted(str(k) for k in raw_cap if k not in open_seg_set)
    if missing_c:
        errors.append("缺少未关阀管段的流量上限: " + ", ".join(missing_c))
    if extra_c:
        errors.append("提供了非未关阀管段的流量上限(多余编号): "
                      + ", ".join(extra_c))
    for sid in open_seg_ids:
        if sid in raw_cap:
            val = _positive_int(raw_cap[sid])
            if val is None:
                errors.append(f"管段 {sid} 的流量上限必须是正整数, "
                              f"收到: {raw_cap[sid]!r}")
            else:
                capacities[sid] = val

    # ---- 进水点供给上限: 键恰好是全部进水点, 值为正整数 ----
    if not isinstance(raw_supplies, dict):
        errors.append("supplies 必须是以进水点编号为键的对象")
        raw_sup: dict[str, Any] = {}
    else:
        raw_sup = raw_supplies
    supplies: dict[str, int] = {}
    missing_s = [iid for iid in inlet_ids if iid not in raw_sup]
    extra_s = sorted(str(k) for k in raw_sup if k not in inlet_set)
    if missing_s:
        errors.append("缺少进水点的供给上限: " + ", ".join(missing_s))
    if extra_s:
        errors.append("提供了非进水点的供给上限(多余编号): "
                      + ", ".join(extra_s))
    for iid in inlet_ids:
        if iid in raw_sup:
            val = _positive_int(raw_sup[iid])
            if val is None:
                errors.append(f"进水点 {iid} 的供给上限必须是正整数, "
                              f"收到: {raw_sup[iid]!r}")
            else:
                supplies[iid] = val

    # ---- 必保点需求: 键恰好是全部必保供水点, 值为正整数 ----
    if not isinstance(raw_demands, dict):
        errors.append("demands 必须是以必保供水点编号为键的对象")
        raw_dem: dict[str, Any] = {}
    else:
        raw_dem = raw_demands
    demands: dict[str, int] = {}
    missing_d = [kid for kid in keep_ids if kid not in raw_dem]
    extra_d = sorted(str(k) for k in raw_dem if k not in keep_set)
    if missing_d:
        errors.append("缺少必保供水点的需求: " + ", ".join(missing_d))
    if extra_d:
        errors.append("提供了非必保供水点的需求(多余编号): "
                      + ", ".join(extra_d))
    for kid in keep_ids:
        if kid in raw_dem:
            val = _positive_int(raw_dem[kid])
            if val is None:
                errors.append(f"必保点 {kid} 的需求必须是正整数, "
                              f"收到: {raw_dem[kid]!r}")
            else:
                demands[kid] = val

    if errors:
        raise NetworkValidationError(errors)

    open_segment_rows = [{
        "id": sg["id"], "endpoint_a": sg["endpoint_a"],
        "endpoint_b": sg["endpoint_b"], "capacity": capacities[sg["id"]],
    } for sg in open_segments]
    inlet_rows = [{"id": iid, "label": label_of[iid], "supply": supplies[iid]}
                  for iid in inlet_ids]

    # ---- 无必保点: 直接判充足, 零需求 ----
    if not keep_ids:
        return {
            "ok": True,
            "sufficient": True,
            "empty": True,
            "closed_valves": closed,
            "open_segments": open_segment_rows,
            "open_segment_ids": open_seg_ids,
            "capacities": capacities,
            "inlets": inlet_rows,
            "supplies": supplies,
            "keep_nodes": [],
            "demands": {},
            "node_summary": [],
            "total_demand": 0,
            "delivered_total": 0,
            "shortage_total": 0,
            "message": ("供水容量校核(只读, 不修改管网与历史方案): 方案快照"
                        "中没有必保供水点, 需求总量为 0, 直接判定容量充足。"),
        }

    # ---- 整数最大流: 源->进水点(供给上限), 管段=无向容量边(两条反向弧,
    #      净流量绝对值不超过同一上限), 必保点->汇(需求) ----
    n = len(nodes)
    idx = {nd["id"]: i + 1 for i, nd in enumerate(nodes)}
    sink = n + 1
    size = n + 2

    def build_caps(need: dict[str, int]) -> list[list[int]]:
        caps = [[0] * size for _ in range(size)]
        for iid in inlet_ids:
            caps[0][idx[iid]] = supplies[iid]
        for sg in open_segments:
            c = capacities[sg["id"]]
            u, v = idx[sg["endpoint_a"]], idx[sg["endpoint_b"]]
            caps[u][v] += c
            caps[v][u] += c
        for kid in keep_ids:
            caps[idx[kid]][sink] = need[kid]
        return caps

    total_demand = sum(demands[kid] for kid in keep_ids)
    delivered_total = _dinic_maxflow(build_caps(demands), 0, sink)

    # ---- 各必保点实际送达量: 编号升序逐个锁定, 前序点锁定后本点尽可能
    #      多送(测试本点上界时把后续点的汇边容量置 0, 前序+本点目标全部
    #      可完成当且仅当最大流恰好等于其和), 结果唯一 ----
    if delivered_total >= total_demand:
        targets = {kid: demands[kid] for kid in keep_ids}
    else:
        targets = {}
        for kid in keep_ids:
            lo, hi = 0, demands[kid]
            while lo < hi:
                mid = (lo + hi + 1) // 2
                need = {k2: 0 for k2 in keep_ids}
                need.update(targets)
                need[kid] = mid
                locked_sum = sum(targets.values()) + mid
                if _dinic_maxflow(build_caps(need), 0, sink) == locked_sum:
                    lo = mid
                else:
                    hi = mid - 1
            targets[kid] = lo

    shortage_total = total_demand - delivered_total
    sufficient = shortage_total == 0
    node_summary = [{
        "node_id": kid, "label": label_of[kid],
        "demand": demands[kid], "delivered": targets[kid],
        "shortage": demands[kid] - targets[kid],
    } for kid in keep_ids]
    keep_nodes = [{"id": kid, "label": label_of[kid], "demand": demands[kid]}
                  for kid in keep_ids]

    if sufficient:
        message = (
            f"供水容量校核(只读, 不修改管网与历史方案): 未关阀管段输水网"
            f"可送达必保点的最大总量 {delivered_total}, 等于需求总量 "
            f"{total_demand}, 全部 {len(keep_ids)} 个必保点需求均可满足, "
            f"容量充足。")
    else:
        message = (
            f"供水容量校核(只读, 不修改管网与历史方案): 必保点需求总量 "
            f"{total_demand}, 但未关阀管段输水网最大送达量仅 "
            f"{delivered_total}, 总缺口 {shortage_total}; 连通不代表容量"
            f"足够, 按容量校核判定为不足, 各必保点缺口已列出。")

    return {
        "ok": True,
        "sufficient": sufficient,
        "empty": False,
        "closed_valves": closed,
        "open_segments": open_segment_rows,
        "open_segment_ids": open_seg_ids,
        "capacities": capacities,
        "inlets": inlet_rows,
        "supplies": supplies,
        "keep_nodes": keep_nodes,
        "demands": demands,
        "node_summary": node_summary,
        "total_demand": total_demand,
        "delivered_total": delivered_total,
        "shortage_total": shortage_total,
        "message": message,
    }
