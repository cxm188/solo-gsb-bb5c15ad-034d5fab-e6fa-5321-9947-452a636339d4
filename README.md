# 管网漏点隔离规划台

在无向供水管网上录入**管段、进水点、漏点、必保供水点**以及**绑定管段的阀门**
（最多 14 个，关闭代价为正整数），系统提供十种规划：

1. **常规规划**：计算使全部漏点与全部进水点断开、同时每个必保供水点仍连通
   至少一个进水点的**最低代价关阀组合**。
2. **单阀失效备援规划**：计划关闭的**任意一枚阀门都可能关不上、保持开启**。
   要求方案在正常执行时、以及每一种单阀失效情形（该阀绑定管段保持通水）下，
   全部漏点均与进水点断开、全部必保点仍连通至少一个进水点；在此前提下最小化
   计划关闭阀门的代价总和。
3. **现场执行顺序规划**：对**已保存的可行方案**（常规或备援均可），按方案
   快照为每枚计划阀门录入**正整数操作时长（分钟）**、为每个漏点录入
   **正整数漏水权重**。操作期间该阀仍开启，每步完成后按多进水点连通性更新
   仍通水漏点；求使各操作时段
   **「时长 × 仍通水漏点权重之和」累计暴露量**最小的执行顺序，所有计划
   阀门都要执行，同暴露量取阀门编号序列字典序最小的唯一顺序。入口在
   **历史方案详情**（也可在刚求解出的可行结果下方直接使用），计算只读、
   不修改原方案。
4. **新增阀门选址预览**：对**当前编辑中的管网**，从**尚无阀门的管段**中
   选择至多 **6 个候选位置**，为每个候选录入**唯一新阀编号、正整数安装费、
   正整数关阀代价**（原阀与候选合计仍不超过 14 个）。系统在「原阀 + 全部
   候选」上寻找能使全部漏点断开进水点且全部必保点仍有水的**增设及关阀
   方案**：**只为实际关闭的候选阀计安装费**，依次最小化
   **安装费合计 → 本次关阀代价**，仍并列时按**新增管段编号列表、关阀编号
   列表**字典序决胜。返回新增位置、费用、关阀清单与供水状态；无解时说明
   **候选范围内不可修复**。本规划为**只读预览**：不修改当前管网，也不写入
   历史方案。
5. **临时供水跨接预览**：对**已保存的可行方案**（常规或备援均可），基于
   方案快照与已关阀管段（即方案执行后的管网），录入至多 **6 条候选跨接**，
   每条含**唯一编号、两个不同的现有节点、正整数铺设费**，跨接视为
   **新增通水管段**。枚举候选组合，始终保持全部漏点与进水点断开、全部
   必保点有水；**先最大化由断水转为有水的普通节点数，再最小化铺设费合计**，
   并列时按**跨接编号升序列表**字典序选取。返回选中跨接、费用、恢复供水
   节点及各节点状态；**无法恢复普通节点时返回空方案**。入口在
   **历史方案详情**（也可在刚求解出的可行结果下方直接使用），预览**只读**，
   不修改管网与历史方案。
6. **关阀成本与断水影响权衡预览**：对**当前编辑中的管网**，为**每个普通
   节点**录入**正整数用水权重**。枚举全部关阀组合，**仅保留全部漏点与进水
   点断开且必保点仍有水的方案**，以 **（关阀代价合计, 原本有水而关阀后断水
   的普通节点权重和）** 为双目标，返回**全部非支配方案**；**同一对指标只
   保留关阀编号升序列表字典序最小者**，结果按**代价、断水影响、编号**升序
   排列，并展示各方案的**关阀清单**与**新增断水节点**。本规划为**只读
   预览**：不修改当前管网，也不写入历史方案。
7. **应急送水分配预览**：对**已保存的可行方案**（常规或备援均可），以方案
   快照中**关阀后断水的普通节点**为需求点，逐点录入**正整数需水量**；录入
   至多 **6 辆候选送水车**，每辆含**唯一编号、正整数出车费与载水量、可服务
   的需求点**。允许一个需求点由多车分担（整数水量），枚举全部车辆组合并用
   **整数最大流**判定能否满足全部需求，选出**出车费合计最低**的组合，同费按
   **车辆编号升序列表**字典序决胜，返回各车向各点的配送量与总费用；**全部
   候选车仍无法满足时返回最大可配送量与总缺口**；**无断水需求时返回空调度**。
   入口在**历史方案详情**（也可在刚求解出的可行结果下方直接使用），预览
   **只读**，不修改管网与历史方案。
8. **失效监测点布设预览**：对**已保存的可行方案**（常规或备援均可），从
   方案快照的**非进水节点**中录入至多 **12 个候选监测点**（编号不得重复）
   及各自**正整数布设费**。分别模拟**正常执行**与**每枚计划关闭阀门单独
   关不上**时的供水连通状态；选出**布设费总和最低**、同费按**节点编号升序
   列表**字典序最小的点集，使**任意两种情形在所选点的有水/无水读数不同**。
   返回选中点、总费用与各情形读数；**候选点无法区分某些情形时列出这些
   情形对**。入口在**历史方案详情**（也可在刚求解出的可行结果下方直接
   使用），预览**只读**，不修改管网与历史方案。
9. **关阀作业备件包采购预览**：对**已保存的可行方案**（常规或备援均可），
   为**每枚计划关闭的阀门**录入所需**备件种类及正整数数量**（无需备件的
   阀门录空表），**合并各阀需求**后录入至多 **12 个采购包**：每包有
   **唯一编号、正整数价格**，并**按备件种类列出非负整数件数**，**每包只能
   买一次**。枚举全部采购包组合（每类到货量为包内件数之和），选出
   **覆盖全部需求的最低总价组合**，同价按**采购包编号升序列表**字典序
   决胜，返回**采购清单**与各类**需求/到货/余量**；**全部包合起来仍不足时
   返回逐类缺口**（不产生采购方案）；**无关阀备件需求时返回零费用空清单**。
   入口在**历史方案详情**（也可在刚求解出的可行结果下方直接使用），预览
   **只读**，不修改管网与历史方案。
10. **供水容量校核**：对**已保存的可行方案**（常规或备援均可），以方案
    快照中**未关阀管段**构成无向输水网，录入**每条管段正整数流量上限**
    （管段净流量的绝对值受同一个上限约束）、**每个进水点正整数供给上限**、
    **每个必保供水点正整数需求**，三类编号须与方案快照**完整对应**。通过
    **整数最大流**求可送达必保点的最大总量，返回**需求总量、最大送达量、
    总缺口与各必保点实际送达量**；**总送达量等于总需求才标记容量充足**，
    仅连通但容量不足时显示不足与各点缺口；**无必保点时返回充足及零需求**。
    入口在**历史方案详情**（也可在刚求解出的可行结果下方直接使用），校核
    **只读**，不修改管网与历史方案。

> 前两种规划同代价时，均取“关闭阀门编号按升序排列后的列表”字典序最小的方案。
> 备援规划无解时会区分：**原本就没有常规可行方案**（`no_base_plan`）与
> **仅缺少备援方案**（`no_failover_plan`，常规方案存在但都扛不住单阀失效）。

- 常规规划无解时给出明确原因（不存在进水点 / 必保点本来就断水 / 漏点有切不断的
  无阀通路 / 任何隔离方案都会饿死某个必保点）。选址预览无解时复用同一套原因
  分析（在候选扩展后的管网上），并注明候选范围内不可修复。

## 技术栈

Python 3.11 · FastAPI · SQLite（标准库 `sqlite3`）· 原生 HTML/CSS/JavaScript
（无前端构建、无框架）。求解方式：枚举全部阀门子集（≤2¹⁴=16384），对每个
子集做 BFS 连通性判定，保证全局最优。备援规划在此基础上预计算每个子集的
常规可行性，方案 `M` 备援可行当且仅当 `M` 与每个 `M\{j}`（阀门 j 关不上）
均常规可行。执行顺序规划对方案的计划阀门做**子集 DP**（
`suffix[S] = min(d_v·W(S) + suffix[S∪{v}])`，`W(S)` 为关闭集合 S 后仍通水
漏点权重之和，由多进水点 BFS 求出），再正向取字典序最小的最优排列。
选址预览把候选新阀并入管网（原阀 + 候选 ≤ 14），复用同一套图校验与
连通性判定枚举全部「原阀 + 候选」关阀子集，按
`（安装费合计, 本次关阀代价, 新增管段编号列表, 关阀编号列表）` 的
字典序取最优；安装但未关闭的候选阀不影响连通性也不计费，最优解不会
包含它，故关阀子集即方案。跨接预览在方案执行后的管网（快照去掉已关阀
管段）上枚举全部候选跨接子集（≤2⁶=64），对每个子集做多进水点 BFS，
仅保留漏点仍全隔离且必保点全有水的组合，按
`（恢复供水普通节点数降序, 铺设费合计, 跨接编号升序列表）` 取最优。
权衡预览枚举全部关阀子集（≤2¹⁴），仅保留漏点全隔离且必保点全有水的
方案，计算双目标 `（关阀代价合计, 原本有水而关阀后断水的普通节点权重和）`，
同一对指标只保留关阀编号升序列表字典序最小者，再按代价升序扫描、断水
影响严格刷新最小值，得到全部非支配方案。监测点布设预览在方案快照上模拟
1+k 种情形（k=计划阀门数≤14）：正常执行与每枚计划阀门单独关不上，各做
一次多进水点 BFS；把每个候选点的跨情形有水/无水读数编成位掩码，再换算成
「情形对可区分」位掩码，枚举全部候选子集（≤2¹²=4096）用 lowbit DP 求
并集，选出能区分全部情形对且 `（布设费合计, 节点编号升序列表）` 字典序
最小的点集；全部候选的并集缺哪些情形对，即为无法区分的情形对。备件包
采购预览先逐阀汇总备件需求，再枚举全部采购包子集（≤2¹²=4096），各子
集的逐类件数合计与总价用 lowbit DP 递推，按
`（可行优先, 总价, 采购包编号升序列表）` 字典序取最优；全部子集都无法
覆盖某类需求时，按全部采购包的逐类件数合计给出缺口。供水容量校核在方案
快照去掉已关阀管段后的无向输水网上构造整数最大流（源→进水点容量为供给
上限，无向管段以两条容量相同的反向有向弧建模，净流量绝对值不超过该管段
流量上限，必保点→汇容量为需求），用 Dinic 求可送达必保点的最大总量；
不足时各必保点实际送达量按必保点编号升序逐个锁定（二分 + 残余网络最大流
校验），结果唯一。

## 一键启动

```bash
docker compose up --build -d
```

启动后访问：

| 用途 | 地址 |
| --- | --- |
| 规划台页面（含常规/备援求解、选址预览与权衡预览入口；执行顺序规划、临时供水跨接预览、失效监测点布设预览、应急送水分配预览、关阀作业备件包采购预览与供水容量校核入口在历史方案详情内） | http://localhost:8000/ |
| API 健康检查 | http://localhost:8000/api/health |
| 新增阀门选址预览 API | http://localhost:8000/api/plan-siting |
| 关阀成本与断水影响权衡预览 API | http://localhost:8000/api/plan-tradeoff |
| 执行顺序规划 API（`{id}` 替换为历史可行方案编号） | http://localhost:8000/api/plans/{id}/sequence |
| 临时供水跨接预览 API（`{id}` 替换为历史可行方案编号） | http://localhost:8000/api/plans/{id}/jumpers |
| 失效监测点布设预览 API（`{id}` 替换为历史可行方案编号） | http://localhost:8000/api/plans/{id}/monitors |
| 应急送水分配预览 API（`{id}` 替换为历史可行方案编号） | http://localhost:8000/api/plans/{id}/water-delivery |
| 关阀作业备件包采购预览 API（`{id}` 替换为历史可行方案编号） | http://localhost:8000/api/plans/{id}/spare-parts |
| 供水容量校核 API（`{id}` 替换为历史可行方案编号） | http://localhost:8000/api/plans/{id}/capacity-check |
| OpenAPI 文档 | http://localhost:8000/docs |

服务端口固定为宿主机 **8000**（compose 端口映射 `8000:8000`，容器内监听
8000）。容器**首次启动自动建表**，并在空库中写入一份示例管网（页面上点
「载入示例管网」可随时恢复）。停止：`docker compose down`；连同数据一起
删除：`docker compose down -v`。

## 配置

| 配置项 | 方式 | 默认值 | 说明 |
| --- | --- | --- | --- |
| 服务端口 | compose 的 `ports`，如 `"8080:8000"` | `8000:8000` | 宿主机端口可改，容器内固定 8000 |
| SQLite 文件 | 环境变量 `DB_PATH`（Dockerfile 已设） | `/data/pipeline.db` | `/data` 已挂载为命名卷 `pipeline-data` |

## 本地（无 Docker）运行

```bash
pip install -r requirements.txt
DB_PATH=./pipeline.db uvicorn main:app --host 0.0.0.0 --port 8000 --app-dir app
```
首次运行同样会自动初始化数据库并写入示例数据。

## 页面用法

1. **管网输入**：三张表分别维护节点（选角色：进水点/漏点/必保供水点/普通点）、
   无向管段（选两个端点）、阀门（选一条绑定管段并填正整数代价，≤14 个）。
   下方 Canvas 自动绘制力导向管网示意，红色虚线方块表示被关闭的阀门。
2. 点 **求解最优关阀方案**（常规）：依次展示
   - 关阀清单（编号升序、各阀代价、总代价、枚举统计）；
   - 各节点隔离后的供水状态（含每个节点仍连通的进水点）；
   - 各管段状态：`通水 / 已关阀 / 停水`。
3. 点 **求解单阀失效备援方案**：从当前编辑的管网直接发起备援求解，展示
   - **备援关阀清单与总代价**（编号升序、各阀绑定管段与代价）；
   - **逐阀失效校验表**：正常执行 + 计划清单中每一枚阀门“关不上、保持开启”
     两种情形下，全部漏点是否与进水点断开、全部必保点是否仍有供水；任一情形
     不通过会列出仍通水的漏点 / 断水的必保点；
   - 正常执行时的节点供水状态与管段状态。
   - 无解时横幅明确区分 **无备援方案（存在常规可行方案）** 与
     **常规规划本身无解**，并展示最低代价常规方案逐阀失效的校验明细。
4. **历史方案**：两种求解都会自动入库，历史表“类型”列区分 `常规 / 单阀备援`，
   可回看任一方案及其管网快照（备援方案含全部逐阀失效校验结果）。
5. **现场执行顺序规划**：在第 4 步打开的**方案详情**底部（或刚求解出的可行
   方案结果下方）出现规划卡片：为每枚计划阀门填正整数操作时长（分钟）、为
   每个漏点填正整数漏水权重，点「计算最优执行顺序」后展示
   - 最优阀门顺序、总时长、**累计暴露量**与执行前/完成后的仍通水漏点；
   - 每一步的**起止时间（分钟）**、操作期间仍通水漏点（该阀仍开启，暴露量
     据此计算）、**本步暴露量、刚隔离的漏点、完成后仍通水漏点**与
     **累计暴露量**；
   - 不可行方案不显示入口；录入时遗漏/多余编号或填非正整数会逐条报错，
     计算过程**只读**，原方案与管网快照均不改变。
6. **临时供水跨接预览**：在执行顺序规划卡片下方的预览卡片中「＋ 添加候选
   跨接」（至多 6 行），每行填**跨接编号**、下拉选择**两个不同的现有节点**
   （端点 A/B）、填正整数**铺设费**。点「跨接预览求解」后展示只读预览：
   - **选中跨接**（编号、端点、铺设费）与**铺设费合计**；
   - **恢复供水节点**（由断水转为有水的普通节点）、方案执行后断水的普通
     节点与铺设后仍断水的节点；
   - 铺设跨接后的各节点供水状态与各管段状态（跨接管段标注「跨接」）；
   - 无法恢复任何普通节点时给出**空方案**（不铺设跨接，费用 0）并说明原因。
   预览**不修改管网、不写入历史方案**，可反复调整候选重新求解。
7. **失效监测点布设预览**：在跨接预览卡片下方的预览卡片中「＋ 添加候选
   监测点」（至多 12 行），每行下拉选择**非进水节点**、填正整数**布设费**
   （编号不得重复）。点「监测点预览求解」后展示只读预览：
   - **选中监测点**（节点编号、布设费）与**布设费合计**；
   - **各情形读数矩阵**：正常执行 + 每枚计划阀门单独关不上，逐情形展示
     各选中点的有水/无水读数，任意两种情形的读数行都不同；
   - 候选点无法区分某些情形时，列出**无法区分的情形对**及全部候选点上
     的各情形读数矩阵，便于调整候选。
   预览**不修改管网、不写入历史方案**，可反复调整候选重新求解。
8. **应急送水分配预览**：在监测点预览卡片下方的预览卡片中，表格自动列出
   方案快照里**关阀后断水的普通节点**作为需求点，逐点填**正整数需水量**；
   「＋ 添加候选车辆」（至多 6 行），每行填**唯一车辆编号**、正整数
   **出车费**与**载水量**，勾选该车**可服务的需求点**。点「送水分配预览
   求解」后展示只读预览：
   - **满足全部需求**：横幅给出**选派车辆**与**出车费合计**；配送矩阵按
     车辆逐行列出向各需求点的整数配送量与本车合计（同一需求点可由多车
     分担），并附各需求点「需水量/已配送/缺口/分担车辆」汇总；
   - **运力不足**：横幅给出**最大可配送量**与**总缺口**，矩阵与汇总展示
     全部候选车参与时各车向各点的配送量及逐点缺口（按需求点编号升序优先
     保障），不产生出车费方案；
   - **无断水需求**：卡片直接提示空调度（总费用 0），无需录入。
   预览**不修改管网、不写入历史方案**，可反复调整需水量与候选重新求解。
9. **关阀作业备件包采购预览**：在送水分配预览卡片下方的预览卡片中，
   表格自动列出方案中**每枚计划关闭的阀门**（含绑定管段），用
   「＋ 为 V# 添加备件」逐行录入**备件种类**与**正整数数量**（无需备件的
   阀门不加行即可）；「＋ 添加采购包」（至多 12 个），每包填**唯一编号**、
   正整数**价格**，并用包内小表逐行填**备件种类**与**非负整数件数**（件数
   允许为 0，每包至少列一种备件）。点「备件采购预览求解」后展示只读预览：
   - **覆盖全部需求**：横幅给出**采购清单（包编号）**与**总价**；列出各阀
     备件需求（合并前）以及各类的**总需求/到货/余量**（含枚举统计）；
   - **全部包仍不足**：横幅给出**总缺口**，并列出**逐类缺口**（总需求、
     全部包可提供量、缺口），不产生采购方案（总价为空）；
   - **无关阀备件需求**：卡片/横幅提示零费用空清单（总价 0），无需采购。
   预览**不修改管网、不写入历史方案**，可反复调整需求与采购包重新求解。
10. **供水容量校核**：在备件包采购预览卡片下方的校核卡片中，系统自动列出
    方案快照里**全部未关阀管段**（逐条填**正整数流量上限**）、**全部进水点**
    （**正整数供给上限**）与**全部必保供水点**（**正整数需求**），三类编号
    与方案快照完整对应。点「供水容量校核」后展示只读结果：
    - **容量充足**：绿色横幅给出**需求总量 = 最大送达量**，各必保点实际
      送达量等于需求、缺口均为 0；
    - **容量不足**：红色横幅给出**需求总量、最大送达量与总缺口**，并逐点
      列出实际送达量与缺口（按必保点编号升序逐个最大化，结果唯一）；
      **仅连通但容量不足**同样判为不足；
    - **无必保供水点**：卡片直接提示需求总量为 0、容量充足，无需录入。
    校核**不修改管网、不写入历史方案**，可反复调整上限与需求重新校核。
11. **新增阀门选址预览**：在①管网输入下方的候选卡片中「＋ 添加候选位置」
    （至多 6 行），每行填**新阀编号**、下拉选择**尚无阀门的管段**、填正整数
    **安装费**与**关阀代价**（卡片实时提示「原阀 + 候选 ≤ 14」）。点
    **选址预览求解**后在③区展示只读预览：
   - **新增位置**（新阀编号、安装管段、安装费、关阀代价）；
   - **费用**：安装费合计（仅实际关闭的候选阀）与本次关阀代价合计；
   - **关阀清单**（编号升序，标注每个阀门为「新增」或「原有」）；
   - 方案执行后的各节点供水状态与各管段状态；
   - 无解时横幅明确「候选范围内不可修复」并给出原因（附证据通路等明细）。
   预览**不写入管网、不保存历史方案**，可反复调整候选重新求解。
12. **关阀成本与断水影响权衡预览**：在①管网输入下方的权重卡片中为**每个
    普通节点**填**正整数用水权重**（表格随节点表自动增删行，默认 1）。点
    **权衡预览求解**后在④区展示只读预览：
    - 枚举与可行组合统计、普通节点总数与**原本有水/原本断水**节点清单；
    - **双目标非支配方案表**：每行一个方案，含**关阀清单**（编号升序）、
      关阀数、**关阀代价合计**、**断水影响（权重和）**与**新增断水节点**
      （标注各自权重），按代价、断水影响升序排列；
    - 同一对（代价, 断水影响）只保留关阀编号升序列表字典序最小的方案；
    - 无可行方案时横幅给出原因代码与明细（复用常规规划的无解原因分析）。
    预览**不写入管网、不保存历史方案**，可反复调整权重重新求解。
13. **保存输入**把当前编辑内容落库（求解时也会随方案保存快照，无需先保存）。

> 示例管网中漏点 L 的两条通路各只有一枚阀门（V2、V4），常规方案为
> `V2+V4`（代价 7），但任一枚关不上 L 都会复通，故备援求解返回
> `NO_FAILOVER_PLAN`，可直接在页面上看到逐阀失效校验。

## API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/network` | 读取当前管网输入 |
| PUT | `/api/network` | 校验并整体覆盖管网输入 |
| POST | `/api/plan` | 常规求解并保存方案；请求体可空（用已保存管网），也可直接提交管网 |
| POST | `/api/plan-failover` | **单阀失效备援求解**（独立 API）；请求体规则同 `/api/plan`，复用同一套管网结构与输入校验 |
| POST | `/api/plan-siting` | **新增阀门选址预览**（独立 API，只读：不写管网、不入库方案）；提交当前管网 + 至多 6 个候选新阀 |
| POST | `/api/plan-tradeoff` | **关阀成本与断水影响权衡预览**（独立 API，只读：不写管网、不入库方案）；提交当前管网 + 每个普通节点的正整数用水权重，返回双目标非支配方案 |
| GET | `/api/plans?limit=20` | 最近方案列表（含 `solver`：`base`/`failover`） |
| GET | `/api/plans/{id}` | 方案详情（含节点/管段状态与管网快照） |
| POST | `/api/plans/{id}/sequence` | **现场执行顺序规划**（只读计算，不改原方案）：按快照录入计划阀门时长与漏点权重 |
| POST | `/api/plans/{id}/jumpers` | **临时供水跨接预览**（只读计算，不改管网与方案）：按快照与已关阀管段录入至多 6 条候选跨接 |
| POST | `/api/plans/{id}/monitors` | **失效监测点布设预览**（只读计算，不改管网与方案）：按快照从非进水节点录入至多 12 个候选点及布设费 |
| POST | `/api/plans/{id}/water-delivery` | **应急送水分配预览**（只读计算，不改管网与方案）：以快照中关阀后断水的普通节点为需求点录入正整数需水量，配至多 6 辆候选送水车（出车费/载水量/可服务点） |
| POST | `/api/plans/{id}/spare-parts` | **关阀作业备件包采购预览**（只读计算，不改管网与方案）：为每枚计划关闭阀门录入备件种类及正整数数量，配至多 12 个采购包（唯一编号/正整数价格/各类非负整数件数），返回最低总价采购清单与各类需求/到货/余量 |
| POST | `/api/plans/{id}/capacity-check` | **供水容量校核**（只读计算，不改管网与方案）：以快照中未关阀管段构成无向输水网，录入每条管段正整数流量上限、每个进水点正整数供给上限、每个必保点正整数需求（编号与快照完整对应），整数最大流求最大送达量，返回需求总量/最大送达量/总缺口/各必保点实际送达量 |
| POST | `/api/demo` | 恢复内置示例管网 |
| POST | `/api/clear` | 清空管网输入 |

### 请求示例

```bash
curl -X POST http://localhost:8000/api/plan \
  -H 'Content-Type: application/json' \
  -d '{
    "nodes": [
      {"id":"S","role":"inlet"},
      {"id":"L","role":"leak"},
      {"id":"H","role":"must_keep"},
      {"id":"A","role":"normal"}
    ],
    "segments": [
      {"id":"p1","endpoint_a":"S","endpoint_b":"A"},
      {"id":"p2","endpoint_a":"A","endpoint_b":"L"},
      {"id":"p3","endpoint_a":"A","endpoint_b":"H"}
    ],
    "valves": [
      {"id":"V1","segment_id":"p2","cost":2}
    ]
  }'
```

### 可行响应（节选）

```json
{
  "feasible": true,
  "total_cost": 2,
  "closed_valves": ["V1"],
  "subset_count": 2,
  "isolating_subset_count": 1,
  "node_status": [
    {"id":"S","role":"inlet","supplied":true,"status":"inlet_supply","connected_inlets":["S"]},
    {"id":"H","role":"must_keep","supplied":true,"status":"supplied","connected_inlets":["S"]},
    {"id":"L","role":"leak","supplied":false,"status":"isolated","connected_inlets":[]}
  ],
  "segment_status": [
    {"id":"p2","status":"closed","flowing":false}
  ]
}
```

### 无解响应

`feasible:false`，`reason_code` 取值：

| reason_code | 含义 |
| --- | --- |
| `NO_INLET` | 管网没有进水点 |
| `GUARANTEED_ALREADY_DISCONNECTED` | 一个阀门都不关，已有必保点不通任何进水点 |
| `UNCUTTABLE_LEAK_PATH` | 漏点经**不含任何阀门**的管段连到进水点，无法切断（附一条证据通路） |
| `GUARANTEED_CONFLICT` | 每个能隔离漏点的组合都会使某个必保点失去全部进水点（附在所有方案中都断水的必保点及示例组合） |

`/api/plan` 只可能返回以上四种代码。`/api/plan-failover` 除复用以上代码外，
还可能返回下表代码，并用 `solver:"failover"` 与 `infeasible_kind` 区分两类无解：

| reason_code | infeasible_kind | 含义 |
| --- | --- | --- |
| `NO_INLET` / `GUARANTEED_ALREADY_DISCONNECTED` / `UNCUTTABLE_LEAK_PATH` / `GUARANTEED_CONFLICT` | `no_base_plan` | **原本就没有常规可行方案**（与常规规划同因） |
| `NO_FAILOVER_PLAN` | `no_failover_plan` | **仅缺少备援方案**：存在常规可行方案，但没有任何方案能承受任意单阀关不上 |

### 备援求解请求示例

请求体格式与 `/api/plan` 完全一致。例如漏点唯一通路上有两枚串联阀（任一失效，
另一枚仍可切断漏点）：

```bash
curl -X POST http://localhost:8000/api/plan-failover \
  -H 'Content-Type: application/json' \
  -d '{
    "nodes": [
      {"id":"S","role":"inlet"},
      {"id":"M","role":"normal"},
      {"id":"L","role":"leak"},
      {"id":"H","role":"must_keep"}
    ],
    "segments": [
      {"id":"a","endpoint_a":"S","endpoint_b":"M"},
      {"id":"b","endpoint_a":"M","endpoint_b":"L"},
      {"id":"h","endpoint_a":"S","endpoint_b":"H"}
    ],
    "valves": [
      {"id":"V1","segment_id":"a","cost":1},
      {"id":"V2","segment_id":"b","cost":2}
    ]
  }'
```

### 备援可行响应（节选）

```json
{
  "feasible": true,
  "solver": "failover",
  "total_cost": 3,
  "closed_valves": ["V1", "V2"],
  "subset_count": 4,
  "isolating_subset_count": 3,
  "base_feasible_subset_count": 3,
  "failover_candidate_count": 1,
  "normal_check": {
    "scenario": "normal",
    "failed_valve": null,
    "effective_closed_valves": ["V1", "V2"],
    "leaks_isolated": true, "leaks_reachable": [],
    "keeps_supplied": true, "keeps_starved": [],
    "ok": true
  },
  "failure_checks": [
    {
      "scenario": "valve_failure",
      "failed_valve": "V1",
      "segment_id": "a",
      "cost": 1,
      "effective_closed_valves": ["V2"],
      "leaks_isolated": true, "leaks_reachable": [],
      "keeps_supplied": true, "keeps_starved": [],
      "ok": true
    },
    {
      "scenario": "valve_failure",
      "failed_valve": "V2",
      "segment_id": "b",
      "cost": 2,
      "effective_closed_valves": ["V1"],
      "leaks_isolated": true, "leaks_reachable": [],
      "keeps_supplied": true, "keeps_starved": [],
      "ok": true
    }
  ],
  "node_status": ["…同常规规划（正常执行视角）…"],
  "segment_status": ["…同常规规划（正常执行视角）…"]
}
```

`failure_checks` 对计划清单中的**每一枚阀门**给出一行：该阀关不上、其绑定管段
保持通水时的实际关阀集合、仍可达进水点的漏点（`leaks_reachable`）、断水的
必保点（`keeps_starved`）以及本行是否通过（`ok`）。

### 备援无解响应（仅缺少备援方案）

`feasible:false`、`reason_code:"NO_FAILOVER_PLAN"`、
`infeasible_kind:"no_failover_plan"`；`reason_detail.best_base_plan` 给出最低代价
常规方案（编号升序、总代价）及其逐阀失效校验：

```json
{
  "feasible": false,
  "solver": "failover",
  "reason_code": "NO_FAILOVER_PLAN",
  "infeasible_kind": "no_failover_plan",
  "reason_detail": {
    "base_feasible_subset_count": 1,
    "best_base_plan": {
      "closed_valves": ["V2", "V4"],
      "total_cost": 7,
      "failure_checks": ["…每个计划阀门一行, 结构同上…"]
    }
  }
}
```

### 选址预览请求示例

`POST /api/plan-siting` 的请求体为 `{"network": …, "candidates": …}`：
`network` 为当前编辑中的管网（结构同 `/api/plan`，**可省略**，省略时使用
已保存管网）；`candidates` 为至多 6 个候选新阀，每个包含唯一新阀编号
`id`、一条**尚无阀门**的管段 `segment_id`、正整数 `install_cost`（安装费）
与正整数 `close_cost`（关阀代价）。**只读**：不修改管网、不写入历史方案。

```bash
curl -X POST http://localhost:8000/api/plan-siting \
  -H 'Content-Type: application/json' \
  -d '{
    "network": {
      "nodes": [
        {"id":"S","role":"inlet"},
        {"id":"M","role":"normal"},
        {"id":"L","role":"leak"},
        {"id":"H","role":"must_keep"}
      ],
      "segments": [
        {"id":"p1","endpoint_a":"S","endpoint_b":"M"},
        {"id":"p2","endpoint_a":"M","endpoint_b":"L"},
        {"id":"p3","endpoint_a":"S","endpoint_b":"H"}
      ],
      "valves": []
    },
    "candidates": [
      {"id":"NV1","segment_id":"p2","install_cost":5,"close_cost":2},
      {"id":"NV2","segment_id":"p1","install_cost":9,"close_cost":1}
    ]
  }'
```

### 选址预览可行响应（节选）

```json
{
  "feasible": true,
  "solver": "siting",
  "new_valves": [
    {"id":"NV1","segment_id":"p2","install_cost":5,"close_cost":2}
  ],
  "new_segment_ids": ["p2"],
  "install_cost_total": 5,
  "close_cost_total": 2,
  "closed_valves": ["NV1"],
  "closed_valve_details": [
    {"id":"NV1","segment_id":"p2","close_cost":2,"is_new":true,"install_cost":5}
  ],
  "candidate_count": 2,
  "subset_count": 4,
  "isolating_subset_count": 3,
  "node_status": ["…同常规规划（方案执行后视角）…"],
  "segment_status": ["…未增设的候选阀不会出现在管段 valve_id 上…"]
}
```

- 优化次序：`install_cost_total`（只为实际关闭的候选阀计安装费）最小 →
  `close_cost_total`（本次关阀代价 = 被关闭原阀的关闭代价 + 新阀关阀代价
  之和）最小 → 新增管段编号升序列表 `new_segment_ids` 字典序 → 关阀编号
  升序列表 `closed_valves` 字典序。
- 上例中 NV2（安装费 9）单独也能隔离漏点，但 NV1（安装费 5）安装费更低，
  故选 NV1；未被增设的候选阀不计费，也不会出现在 `new_valves` 与管段
  状态中。

### 选址预览无解响应

`feasible:false`、`solver:"siting"`，`message` 以「候选范围内不可修复」
开头；`reason_code` 复用常规规划的四种（`NO_INLET` /
`GUARANTEED_ALREADY_DISCONNECTED` / `UNCUTTABLE_LEAK_PATH` /
`GUARANTEED_CONFLICT`），在「原阀 + 全部候选」扩展管网上判定，即
**把全部候选新阀都装上也无法修复**。

### 选址预览错误响应（422，`detail.errors` 逐条列出）

| 场景 | 示例错误 |
| --- | --- |
| 候选超过 6 个 | `候选位置数量为 7, 超过上限 6 个` |
| 新阀编号与原阀/其他候选重复 | `阀门编号重复: V1` |
| 候选管段已有阀门 / 两候选共用管段 | `管段 p1 同时绑定了阀门 V1 和 NV1(每条管段最多 1 个阀门)` |
| 候选管段不存在 | `阀门 NV1: 绑定的管段 pX 不存在` |
| 缺少新阀编号 / 未选管段 | `候选 #1: 缺少新阀编号`、`候选阀门 NV1: 必须选择安装管段` |
| 安装费非正整数 | `候选阀门 NV1: 安装费必须是正整数, 收到: 0` |
| 关阀代价非正整数 | `阀门 NV1: 关闭代价必须是正整数` |
| 原阀 + 候选合计超过 14 个 | `阀门数量为 15, 超过上限 14 个` |

### 权衡预览请求示例

`POST /api/plan-tradeoff` 的请求体为 `{"network": …, "weights": …}`：
`network` 为当前编辑中的管网（结构同 `/api/plan`，**可省略**，省略时使用
已保存管网）；`weights` 的键必须**恰好**是全部普通节点编号，值为**正整数
用水权重**。**只读**：不修改管网、不写入历史方案。下例中漏点 L1、L2 各有
一条通路，每条通路可选「便宜但会使普通节点断水」或「贵但不断水」的阀门：

```bash
curl -X POST http://localhost:8000/api/plan-tradeoff \
  -H 'Content-Type: application/json' \
  -d '{
    "network": {
      "nodes": [
        {"id":"S","role":"inlet"},
        {"id":"A","role":"normal"},
        {"id":"B","role":"normal"},
        {"id":"L1","role":"leak"},
        {"id":"L2","role":"leak"}
      ],
      "segments": [
        {"id":"p1","endpoint_a":"S","endpoint_b":"A"},
        {"id":"p2","endpoint_a":"A","endpoint_b":"L1"},
        {"id":"p3","endpoint_a":"S","endpoint_b":"B"},
        {"id":"p4","endpoint_a":"B","endpoint_b":"L2"}
      ],
      "valves": [
        {"id":"V1","segment_id":"p1","cost":2},
        {"id":"V2","segment_id":"p2","cost":5},
        {"id":"V3","segment_id":"p3","cost":2},
        {"id":"V4","segment_id":"p4","cost":5}
      ]
    },
    "weights": {"A":3,"B":3}
  }'
```

### 权衡预览可行响应（节选）

```json
{
  "feasible": true,
  "solver": "tradeoff",
  "weights": {"A": 3, "B": 3},
  "normal_nodes": ["A", "B"],
  "baseline_fed_normal": ["A", "B"],
  "baseline_disconnected_normal": [],
  "subset_count": 16,
  "isolating_subset_count": 9,
  "feasible_subset_count": 9,
  "plan_count": 3,
  "plans": [
    {"closed_valves": ["V1", "V3"], "closed_count": 2,
     "total_cost": 4, "impact": 6,
     "newly_disconnected": ["A", "B"],
     "newly_disconnected_details": [
       {"id": "A", "label": "A", "weight": 3},
       {"id": "B", "label": "B", "weight": 3}
     ]},
    {"closed_valves": ["V1", "V4"], "closed_count": 2,
     "total_cost": 7, "impact": 3,
     "newly_disconnected": ["A"],
     "newly_disconnected_details": [
       {"id": "A", "label": "A", "weight": 3}
     ]},
    {"closed_valves": ["V2", "V4"], "closed_count": 2,
     "total_cost": 10, "impact": 0,
     "newly_disconnected": [],
     "newly_disconnected_details": []}
  ]
}
```

- 双目标：`total_cost`（关阀代价合计）与 `impact`（原本有水、关阀后断水的
  普通节点用水权重之和；`baseline_disconnected_normal` 中原本就断水的普通
  节点不计入）。`plans` 为全部**非支配方案**，按
  `（代价, 断水影响, 关阀编号升序列表）` 升序排列。
- **同一对指标只保留字典序最小者**：上例中 `{V2,V3}` 与 `{V1,V4}` 同为
  `（代价 7, 断水影响 3）`，只保留编号升序列表字典序更小的 `["V1","V4"]`。
- 每个方案给出**关阀清单**（`closed_valves`，编号升序）与**新增断水节点**
  （`newly_disconnected` 及带名称/权重的 `newly_disconnected_details`）。
- 无可行方案时返回 `feasible:false`、`solver:"tradeoff"`，`reason_code`
  复用常规规划的四种（`NO_INLET` / `GUARANTEED_ALREADY_DISCONNECTED` /
  `UNCUTTABLE_LEAK_PATH` / `GUARANTEED_CONFLICT`）。

### 权衡预览错误响应（422，`detail.errors` 逐条列出）

| 场景 | 示例错误 |
| --- | --- |
| 缺少普通节点的用水权重 | `缺少普通节点的用水权重: A, B` |
| 多余编号（非普通节点或不存在） | `提供了非普通节点的用水权重(多余编号): S` |
| 权重非正整数（0、负数、小数、字符串、布尔、null） | `普通节点 A 的用水权重必须是正整数, 收到: 0` |
| 管网本身非法 | 复用管网校验错误（如 `管段 p1: 端点 S 不存在`） |

### 现场执行顺序规划请求示例

对已保存的**可行方案** `id=1` 调用（只读，不入库、不改方案）。`durations`
的键必须**恰好**是方案 `closed_valves` 中的全部计划阀门，`leak_weights` 的键
必须**恰好**是方案快照中的全部漏点，值均为正整数：

```bash
curl -X POST http://localhost:8000/api/plans/1/sequence \
  -H 'Content-Type: application/json' \
  -d '{"durations":{"V2":10,"V4":20},"leak_weights":{"L":5}}'
```

### 执行顺序可行响应（节选）

```json
{
  "ok": true,
  "plan_id": 1,
  "solver": "base",
  "closed_valves": ["V2", "V4"],
  "durations": {"V2": 10, "V4": 20},
  "leak_weights": {"L": 5},
  "initial_flowing_leaks": ["L"],
  "initial_flowing_weight": 5,
  "final_flowing_leaks": [],
  "sequence": ["V2", "V4"],
  "total_duration": 30,
  "total_exposure": 150,
  "steps": [
    {
      "order": 1,
      "valve_id": "V2",
      "segment_id": "s5",
      "duration": 10,
      "start": 0,
      "end": 10,
      "flowing_leaks_during": ["L"],
      "flowing_weight_during": 5,
      "exposure": 50,
      "newly_isolated_leaks": [],
      "flowing_leaks_after": ["L"],
      "flowing_weight_after": 5,
      "cumulative_exposure": 50
    },
    {
      "order": 2,
      "valve_id": "V4",
      "segment_id": "s6",
      "duration": 20,
      "start": 10,
      "end": 30,
      "flowing_leaks_during": ["L"],
      "flowing_weight_during": 5,
      "exposure": 100,
      "newly_isolated_leaks": ["L"],
      "flowing_leaks_after": [],
      "flowing_weight_after": 0,
      "cumulative_exposure": 150
    }
  ]
}
```

- 第 k 步的暴露量 = 该阀时长 × **操作期间**（该阀仍开启，已关闭的只有前
  k-1 枚）仍通水漏点权重之和；`start/end` 为累计分钟时刻，从 0 起算。
- `newly_isolated_leaks` 为本步完成后由通水变隔离的漏点，
  `flowing_leaks_after` 为本步完成后仍通水的漏点；`cumulative_exposure`
  为截至本步的累计暴露量。
- 顺序**唯一**：达到最小累计暴露量的多个排列中，取阀门编号序列字典序
  （按编号字符串比较，如 `V10 < V2`）最小者。
- 方案不关闭任何阀门时返回空 `steps`、`total_exposure: 0`。

### 执行顺序错误响应

| 场景 | HTTP 状态 | 返回内容 |
| --- | --- | --- |
| 方案编号不存在 | 404 | `方案不存在` |
| 目标方案不可行（无解方案） | 422 | `detail.errors` 指明方案不可行及 `reason_code`，不可规划 |
| 遗漏计划阀门时长 / 漏点权重 | 422 | 如 `缺少计划阀门的操作时长: V4`、`缺少漏点的漏水权重: L` |
| 多余编号（非计划阀门 / 非漏点） | 422 | 如 `提供了非计划阀门的操作时长(多余编号): V1`、`提供了非漏点的漏水权重(多余编号): X` |
| 时长或权重不是正整数（0、负数、小数、字符串、布尔、null） | 422 | 如 `阀门 V2 的操作时长必须是正整数(分钟), 收到: 0`、`漏点 L 的漏水权重必须是正整数, 收到: 1.5` |

### 临时供水跨接预览请求示例

对已保存的**可行方案** `id=1` 调用（只读，不入库、不改方案与管网）。
`candidates` 为至多 6 条候选跨接，每条含唯一编号 `id`、两个不同的现有
节点 `endpoint_a` / `endpoint_b`（须为方案快照中的节点）与正整数铺设费
`cost`；跨接视为新增通水管段。下例方案来自备援求解（计划关闭 V1+V2，
冗余关阀使普通节点 M、X 断水且与漏点 L 分离）：

```bash
curl -X POST http://localhost:8000/api/plans/1/jumpers \
  -H 'Content-Type: application/json' \
  -d '{
    "candidates": [
      {"id":"J1","endpoint_a":"S","endpoint_b":"M","cost":6},
      {"id":"J2","endpoint_a":"H","endpoint_b":"X","cost":4},
      {"id":"J3","endpoint_a":"S","endpoint_b":"L","cost":1}
    ]
  }'
```

### 跨接预览响应（节选）

```json
{
  "ok": true,
  "plan_id": 1,
  "solver": "failover",
  "closed_valves": ["V1", "V2"],
  "candidate_count": 3,
  "combination_count": 8,
  "feasible_combination_count": 4,
  "selected_jumpers": [
    {"id":"J2","endpoint_a":"H","endpoint_b":"X","cost":4}
  ],
  "selected_ids": ["J2"],
  "lay_cost_total": 4,
  "restored_nodes": ["M", "X"],
  "restored_count": 2,
  "disconnected_normal_before": ["M", "X"],
  "still_disconnected_normal": [],
  "node_status": ["…铺设跨接后视角, 结构同常规规划…"],
  "segment_status": ["…含新增跨接管段 J2(带 is_jumper 标记)…"],
  "message": "临时供水跨接预览(只读, 不修改管网与历史方案): 铺设 1 条跨接(J2), …"
}
```

- 候选 J3（S—L）会把漏点 L 重新接通进水点，凡含 J3 的组合均被约束排除
  （8 个组合中仅 4 个保持漏点隔离与必保供水）；J1、J2 都能恢复 M、X，
  选取铺设费更低的 J2。
- 优化次序：**恢复供水普通节点数**（由断水转为有水）最大 →
  **铺设费合计**最小 → **跨接编号升序列表**字典序最小。
- `disconnected_normal_before` 为方案执行后（未铺设跨接）断水的普通节点；
  `still_disconnected_normal` 为铺设选中跨接后仍断水的普通节点。
- **空方案**：无法恢复任何普通节点时（没有断水普通节点，或候选跨接够不到/
  会复通漏点），返回 `selected_jumpers: []`、`lay_cost_total: 0`、
  `restored_nodes: []`，`message` 说明原因。

### 跨接预览错误响应

| 场景 | HTTP 状态 | 示例错误（`detail.errors` 逐条列出） |
| --- | --- | --- |
| 方案编号不存在 | 404 | `方案不存在` |
| 目标方案不可行（无解方案） | 422 | `方案 #3 为不可行方案(reason_code: …), 没有已关阀管段可作为跨接预览的基础, 不能规划临时供水跨接` |
| 候选超过 6 条 | 422 | `候选跨接数量为 7, 超过上限 6 条` |
| 跨接编号重复 / 与现有管段编号重复 | 422 | `跨接编号重复: J1`、`跨接编号 p1 与现有管段编号重复` |
| 缺少跨接编号 / 未选端点 | 422 | `候选跨接 #1: 缺少跨接编号`、`候选跨接 J1: 必须选择两个不同的现有节点作为端点` |
| 端点不是快照中的现有节点 | 422 | `候选跨接 J1: 端点 ZZ 不存在于方案快照的节点中` |
| 两个端点相同 | 422 | `候选跨接 J1: 两个端点不能相同(S)` |
| 铺设费非正整数（0、负数、小数、字符串、布尔、null） | 422 | `候选跨接 J1: 铺设费必须是正整数, 收到: 0` |

### 失效监测点布设预览请求示例

对已保存的**可行方案** `id=1` 调用（只读，不入库、不改方案与管网）。
`candidates` 为至多 12 个候选监测点，每个含方案快照中**非进水节点**的
编号 `node_id`（不得重复）与正整数布设费 `cost`。下例方案来自常规求解
（计划关闭 V1+V2，分别隔离两条支路上的漏点 L1、L2）：

```bash
curl -X POST http://localhost:8000/api/plans/1/monitors \
  -H 'Content-Type: application/json' \
  -d '{
    "candidates": [
      {"node_id":"A","cost":1},
      {"node_id":"B","cost":1},
      {"node_id":"L1","cost":1},
      {"node_id":"L2","cost":5},
      {"node_id":"H","cost":9}
    ]
  }'
```

### 监测点预览响应（节选）

```json
{
  "ok": true,
  "plan_id": 1,
  "solver": "base",
  "closed_valves": ["V1", "V2"],
  "candidate_count": 5,
  "scenario_count": 3,
  "selected_points": [
    {"node_id": "A", "cost": 1},
    {"node_id": "B", "cost": 1}
  ],
  "selected_node_ids": ["A", "B"],
  "total_cost": 2,
  "subset_count": 32,
  "distinguishing_subset_count": 18,
  "scenarios": [
    {
      "scenario": "normal",
      "failed_valve": null,
      "label": "正常执行(全部按计划关闭)",
      "effective_closed_valves": ["V1", "V2"],
      "readings": [
        {"node_id": "A", "supplied": false},
        {"node_id": "B", "supplied": false}
      ]
    },
    {
      "scenario": "valve_failure",
      "failed_valve": "V1",
      "label": "阀门 V1 关不上(保持开启)",
      "effective_closed_valves": ["V2"],
      "readings": [
        {"node_id": "A", "supplied": true},
        {"node_id": "B", "supplied": false}
      ]
    },
    {
      "scenario": "valve_failure",
      "failed_valve": "V2",
      "label": "阀门 V2 关不上(保持开启)",
      "effective_closed_valves": ["V1"],
      "readings": [
        {"node_id": "A", "supplied": false},
        {"node_id": "B", "supplied": true}
      ]
    }
  ],
  "message": "失效监测点布设预览(只读, 不修改管网与历史方案): …"
}
```

- 情形 = **正常执行**（全部计划阀门关闭）+ **每枚计划关闭阀门单独关不上**
  （该阀保持开启、其余照常关闭），共 `scenario_count = 1 + 计划阀门数` 种；
  `readings` 为该情形在各**选中点**的有水/无水读数，任意两种情形的读数
  行都不同。
- 优化次序：**布设费合计**最小 → **节点编号升序列表**字典序最小。
  上例中 `{A,B}` 与 `{L1,B}` 同为布设费 2，取编号升序列表字典序更小的
  `["A","B"]`。
- `subset_count` 为枚举的候选子集数（2^候选数），
  `distinguishing_subset_count` 为其中能区分全部情形的子集数。
- 方案不关闭任何阀门时仅有正常执行一种情形，返回空点集
  （`selected_points: []`、`total_cost: 0`）。

### 监测点预览无法区分情形响应

候选点无法区分某些情形时返回 `ok:false`、
`reason_code:"INDISTINGUISHABLE_SCENARIOS"`，并列出**无法区分的情形对**；
`scenarios` 中给出各情形在**全部候选点**上的读数（便于调整候选）：

```json
{
  "ok": false,
  "reason_code": "INDISTINGUISHABLE_SCENARIOS",
  "closed_valves": ["V1", "V2"],
  "candidate_count": 3,
  "scenario_count": 3,
  "indistinguishable_pairs": [
    {
      "a": {"scenario": "normal", "failed_valve": null,
            "label": "正常执行(全部按计划关闭)"},
      "b": {"scenario": "valve_failure", "failed_valve": "V2",
            "label": "阀门 V2 关不上(保持开启)"}
    }
  ],
  "scenarios": ["…各情形在全部候选点上的读数…"],
  "message": "…以下 1 对情形在所有候选点上的有水/无水读数完全相同: …"
}
```

### 监测点预览错误响应

| 场景 | HTTP 状态 | 示例错误（`detail.errors` 逐条列出） |
| --- | --- | --- |
| 方案编号不存在 | 404 | `方案不存在` |
| 目标方案不可行（无解方案） | 422 | `方案 #3 为不可行方案(reason_code: …), 没有可监测的关阀方案, 不能规划失效监测点布设` |
| 候选超过 12 个 | 422 | `候选监测点数量为 13, 超过上限 12 个` |
| 监测点编号重复 | 422 | `监测点编号重复: A` |
| 缺少节点编号 | 422 | `候选监测点 #1: 缺少节点编号` |
| 节点不是快照中的现有节点 | 422 | `候选监测点 ZZ 不存在于方案快照的节点中` |
| 节点选择进水点 | 422 | `候选监测点 S 是进水点, 只能在非进水节点布设` |
| 布设费非正整数（0、负数、小数、字符串、布尔、null） | 422 | `监测点 A 的布设费必须是正整数, 收到: 0` |

### 应急送水分配预览请求示例

在**历史可行方案详情**页（或刚求解出的可行方案下方）的「应急送水分配预览」
卡片中，系统以方案快照里**关阀后断水的普通节点**为需求点（无需手填需求点
清单），逐点录入**正整数需水量**，并录入至多 **6 辆**候选送水车：每辆含
唯一编号、正整数**出车费**与**载水量**，以及可服务的需求点。允许一个需求点
由多车分担（整数水量）。

```bash
curl -X POST http://localhost:8000/api/plans/1/water-delivery \
  -H 'Content-Type: application/json' \
  -d '{
    "demands": {"M": 10, "X": 7},
    "vehicles": [
      {"id": "T1", "cost": 5, "capacity": 8, "serves": ["M"]},
      {"id": "T2", "cost": 3, "capacity": 8, "serves": ["M", "X"]},
      {"id": "T3", "cost": 4, "capacity": 7, "serves": ["X"]}
    ]
  }'
```

系统枚举全部 2^车辆数 个组合，用**整数最大流**判定该组合能否满足全部需求
（源→车容量为载水量，车→可服务需求点容量不限，需求点→汇容量为需水量），
选出**出车费合计最低**的组合；同费按**车辆编号升序列表**字典序决胜。
选中组合内各车向各点的配送量按「需求点编号、车辆编号」双关键字贪心确定
（逐单位用残余网络最大流校验），结果唯一。

### 送水分配预览满足响应（节选）

```json
{
  "ok": true,
  "satisfied": true,
  "empty": false,
  "plan_id": 1,
  "solver": "failover",
  "closed_valves": ["V1", "V2"],
  "demand_nodes": [
    {"id": "M", "label": "M", "demand": 10},
    {"id": "X", "label": "X", "demand": 7}
  ],
  "demands": {"M": 10, "X": 7},
  "candidate_count": 3,
  "combination_count": 8,
  "feasible_combination_count": 1,
  "selected_vehicle_ids": ["T1", "T2", "T3"],
  "selected_vehicles": [
    {"id": "T1", "cost": 5, "capacity": 8, "serves": ["M"]}
  ],
  "deliveries": {
    "T1": {"M": 8, "X": 0},
    "T2": {"M": 2, "X": 6},
    "T3": {"M": 0, "X": 1}
  },
  "delivery_matrix": [
    {"vehicle_id": "T1", "cost": 5, "capacity": 8,
     "deliveries": [{"node_id": "M", "amount": 8},
                    {"node_id": "X", "amount": 0}],
     "delivered_total": 8}
  ],
  "node_summary": [
    {"node_id": "M", "label": "M", "demand": 10, "delivered": 10,
     "shortage": 0,
     "by_vehicle": [{"vehicle_id": "T1", "amount": 8},
                    {"vehicle_id": "T2", "amount": 2}]}
  ],
  "total_demand": 17,
  "delivered_total": 17,
  "shortage_total": 0,
  "total_cost": 12,
  "message": "应急送水分配预览(只读, 不修改管网与历史方案): 选派 3 辆车…"
}
```

### 送水分配预览运力不足响应

全部候选车仍无法满足时返回 `ok:false`、
`reason_code:"INSUFFICIENT_CAPACITY"`，`total_cost` 为 `null`（不产生出车费
方案），并给出**最大可配送量** `delivered_total` 与**总缺口**
`shortage_total`；`delivery_matrix`/`node_summary` 仍给出全部候选车参与时
各车向各点的整数配送量与逐点缺口（按需求点编号升序优先保障）：

```json
{
  "ok": false,
  "reason_code": "INSUFFICIENT_CAPACITY",
  "satisfied": false,
  "total_demand": 17,
  "delivered_total": 8,
  "shortage_total": 9,
  "total_cost": null,
  "selected_vehicle_ids": [],
  "used_vehicle_ids": ["T1"],
  "deliveries": {"T1": {"M": 8, "X": 0}},
  "node_summary": [
    {"node_id": "M", "demand": 10, "delivered": 8, "shortage": 2,
     "by_vehicle": [{"vehicle_id": "T1", "amount": 8}]},
    {"node_id": "X", "demand": 7, "delivered": 0, "shortage": 7,
     "by_vehicle": []}
  ],
  "message": "应急送水分配预览(只读, 不修改管网与历史方案): …最大可配送量 8, 总缺口 9…"
}
```

方案执行后**没有断水普通节点**时，无需任何录入即可返回空调度：
`ok:true`、`empty:true`、`selected_vehicle_ids:[]`、`deliveries:{}`、
`total_cost:0`。

### 送水分配预览错误响应

| 场景 | HTTP 状态 | 示例错误（`detail.errors` 逐条列出） |
| --- | --- | --- |
| 方案编号不存在 | 404 | `方案不存在` |
| 目标方案不可行（无解方案） | 422 | `方案 #3 为不可行方案(reason_code: …), 没有关阀后供水状态快照, 不能规划应急送水分配` |
| 缺少需求点需水量 | 422 | `缺少断水需求点的需水量: X` |
| 为非断水普通点提供需水量 | 422 | `提供了非断水普通节点的需水量(多余编号): H` |
| 需水量非正整数（0、负数、小数、字符串、布尔、null） | 422 | `需求点 M 的需水量必须是正整数, 收到: 0` |
| 候选车辆超过 6 辆 | 422 | `候选送水车数量为 7, 超过上限 6 辆` |
| 缺少/重复车辆编号 | 422 | `候选车辆 #1: 缺少车辆编号` / `车辆编号重复: A` |
| 出车费或载水量非正整数 | 422 | `车辆 A: 出车费必须是正整数, 收到: 0` / `车辆 A: 载水量必须是正整数, 收到: -2` |
| 可服务点不是本次断水需求点 | 422 | `车辆 A: 可服务点 L 不是本次关阀后断水的普通节点(需求点)` |

### 关阀作业备件包采购预览请求示例

在**历史可行方案详情**页（或刚求解出的可行方案下方）的「关阀作业备件包
采购预览」卡片中，为**每枚计划关闭的阀门**录入所需备件种类及正整数数量
（`valve_demands` 的键必须恰好是全部计划关闭阀门编号，无需备件的阀门给
空对象 `{}`），并录入至多 **12 个**采购包：每包含唯一编号 `id`、正整数
`price`，以及 `contents`（备件种类 → **非负整数**件数，至少一种备件）。
每包只能买一次。

```bash
curl -X POST http://localhost:8000/api/plans/1/spare-parts \
  -H 'Content-Type: application/json' \
  -d '{
    "valve_demands": {
      "V2": {"密封圈": 2, "螺栓": 4},
      "V4": {"密封圈": 1}
    },
    "packages": [
      {"id": "P1", "price": 10, "contents": {"密封圈": 2, "螺栓": 2}},
      {"id": "P2", "price": 8,  "contents": {"密封圈": 1, "螺栓": 2}},
      {"id": "P3", "price": 6,  "contents": {"密封圈": 1, "螺栓": 2, "螺母": 5}}
    ]
  }'
```

系统合并各阀需求（本例：密封圈 3、螺栓 4），枚举全部 2^采购包数 个组合
（每类到货量为包内件数之和），先只保留能覆盖全部需求的组合，再取
**总价最低**者；同价按**采购包编号升序列表**字典序决胜。本例唯一可行的
最低总价组合为 `P1+P3`（总价 16；`P1+P2` 与 `P2+P3` 各缺一类件数）。

### 备件采购预览覆盖响应（节选）

```json
{
  "ok": true,
  "satisfied": true,
  "empty": false,
  "plan_id": 1,
  "solver": "base",
  "closed_valves": ["V2", "V4"],
  "valve_demands": {"V2": {"密封圈": 2, "螺栓": 4}, "V4": {"密封圈": 1}},
  "valve_demand_details": [
    {"valve_id": "V2", "segment_id": "p2",
     "parts": [{"part_id": "密封圈", "quantity": 2},
               {"part_id": "螺栓", "quantity": 4}],
     "part_count": 2, "quantity_total": 6},
    {"valve_id": "V4", "segment_id": "p4",
     "parts": [{"part_id": "密封圈", "quantity": 1}],
     "part_count": 1, "quantity_total": 1}
  ],
  "merged_demands": {"密封圈": 3, "螺栓": 4},
  "part_ids": ["密封圈", "螺栓"],
  "candidate_count": 3,
  "combination_count": 8,
  "feasible_combination_count": 3,
  "selected_package_ids": ["P1", "P3"],
  "selected_packages": [
    {"id": "P1", "price": 10,
     "contents": [{"part_id": "密封圈", "quantity": 2},
                  {"part_id": "螺栓", "quantity": 2}]},
    {"id": "P3", "price": 6,
     "contents": [{"part_id": "密封圈", "quantity": 1},
                  {"part_id": "螺栓", "quantity": 2},
                  {"part_id": "螺母", "quantity": 5}]}
  ],
  "part_summary": [
    {"part_id": "密封圈", "demand": 3, "arrived": 3, "surplus": 0, "shortage": 0},
    {"part_id": "螺栓", "demand": 4, "arrived": 4, "surplus": 0, "shortage": 0}
  ],
  "total_demand": 7,
  "arrived_total": 7,
  "surplus_total": 0,
  "shortage_total": 0,
  "total_cost": 16,
  "message": "关阀作业备件包采购预览(只读, 不修改管网与历史方案): 选买 2 个采购包(P1, P3), 总价 16…"
}
```

> `part_summary` 只列出**有需求的备件种类**的需求/到货/余量；采购包中
> 不属于任何需求的种类（如上例 `螺母`）仍在 `selected_packages[].contents`
> 中回显，但不计入需求与余量合计。

### 备件采购预览全部包不足响应

全部采购包合起来仍无法覆盖某类需求时返回 `ok:false`、
`reason_code:"INSUFFICIENT_PACKAGES"`，`total_cost` 为 `null`（不产生采购
方案）、`selected_package_ids:[]`，并给出**逐类缺口** `shortages`（仅列
仍有缺口的种类）；`part_summary` 仍列出全部需求种类的需求/可到货/缺口：

```json
{
  "ok": false,
  "reason_code": "INSUFFICIENT_PACKAGES",
  "satisfied": false,
  "empty": false,
  "merged_demands": {"x": 5, "y": 2},
  "candidate_count": 1,
  "combination_count": 2,
  "feasible_combination_count": 0,
  "selected_package_ids": [],
  "part_summary": [
    {"part_id": "x", "demand": 5, "arrived": 4, "surplus": 0, "shortage": 1},
    {"part_id": "y", "demand": 2, "arrived": 0, "surplus": 0, "shortage": 2}
  ],
  "shortages": [
    {"part_id": "x", "demand": 5, "available": 4, "shortage": 1},
    {"part_id": "y", "demand": 2, "available": 0, "shortage": 2}
  ],
  "total_demand": 7,
  "arrived_total": 4,
  "shortage_total": 3,
  "total_cost": null,
  "message": "关阀作业备件包采购预览(只读, 不修改管网与历史方案): …总缺口 3 件…"
}
```

方案**没有任何关阀备件需求**时（含方案不关闭阀门），无需采购包即可返回
零费用空清单：`ok:true`、`empty:true`、`selected_package_ids:[]`、
`part_summary:[]`、`total_cost:0`。

### 备件采购预览错误响应

| 场景 | HTTP 状态 | 示例错误（`detail.errors` 逐条列出） |
| --- | --- | --- |
| 方案编号不存在 | 404 | `方案不存在` |
| 目标方案不可行（无解方案） | 422 | `方案 #3 为不可行方案(reason_code: …), 没有计划关闭的阀门, 不能规划关阀作业备件采购` |
| 缺少计划阀门的备件录入 | 422 | `缺少计划关闭阀门的备件需求: V4` |
| 为非计划关闭阀门提供录入 | 422 | `提供了非计划关闭阀门的备件需求(多余编号): V9` |
| 阀门备件数量非正整数（0、负数、小数、字符串、布尔、null） | 422 | `阀门 V2 的备件 密封圈 数量必须是正整数, 收到: 0` |
| 备件种类名称为空 | 422 | `阀门 V2: 备件种类名称不能为空` |
| 采购包超过 12 个 | 422 | `采购包数量为 13, 超过上限 12 个` |
| 缺少/重复采购包编号 | 422 | `采购包 #1: 缺少采购包编号` / `采购包编号重复: A` |
| 价格非正整数 | 422 | `采购包 A: 价格必须是正整数, 收到: 0` |
| 件数为负数/小数/字符串/布尔/null | 422 | `采购包 A 的备件 x 件数必须是非负整数, 收到: -1`（件数 `0` 合法） |
| 采购包未列任何备件 | 422 | `采购包 A: 必须至少列出一种备件(件数为非负整数)` |

### 供水容量校核请求示例

在**历史可行方案详情**页（或刚求解出的可行方案下方）的「供水容量校核」
卡片中，系统以方案快照里**未关阀管段**构成无向输水网：`capacities` 的键
必须**恰好**是全部未关阀管段编号（已关阀管段不属于输水网），`supplies`
的键必须**恰好**是全部进水点编号，`demands` 的键必须**恰好**是全部必保
供水点编号，值均为**正整数**。下例为示例管网常规方案（关闭 V2+V4，未关阀
管段 s1–s4，进水点 S，必保点 H1/H2）：

```bash
curl -X POST http://localhost:8000/api/plans/1/capacity-check \
  -H 'Content-Type: application/json' \
  -d '{
    "capacities": {"s1": 10, "s2": 3, "s3": 10, "s4": 4},
    "supplies": {"S": 100},
    "demands": {"H1": 3, "H2": 4}
  }'
```

管段净流量的**绝对值**受同一个流量上限约束（无向边容量，用两条容量相同
的反向有向弧建模）；系统用**整数最大流**求可送达必保点的最大总量。

### 容量校核充足响应（节选）

```json
{
  "ok": true,
  "sufficient": true,
  "empty": false,
  "plan_id": 1,
  "solver": "base",
  "closed_valves": ["V2", "V4"],
  "open_segment_ids": ["s1", "s2", "s3", "s4"],
  "capacities": {"s1": 10, "s2": 3, "s3": 10, "s4": 4},
  "supplies": {"S": 100},
  "demands": {"H1": 3, "H2": 4},
  "total_demand": 7,
  "delivered_total": 7,
  "shortage_total": 0,
  "node_summary": [
    {"node_id": "H1", "label": "必保点H1", "demand": 3, "delivered": 3, "shortage": 0},
    {"node_id": "H2", "label": "必保点H2", "demand": 4, "delivered": 4, "shortage": 0}
  ],
  "message": "供水容量校核(只读, 不修改管网与历史方案): …容量充足。"
}
```

### 容量校核不足响应

**总送达量等于总需求才标记容量充足**；仅连通但容量不足时返回
`sufficient:false`，并给出**最大送达量** `delivered_total`、**总缺口**
`shortage_total` 与各必保点实际送达量（按必保点编号升序逐个最大化：
前序点送达量锁定后，本点在残余网络上尽可能多送，结果唯一）。上例把干管
`s1` 的流量上限改为 5：

```json
{
  "ok": true,
  "sufficient": false,
  "total_demand": 7,
  "delivered_total": 5,
  "shortage_total": 2,
  "node_summary": [
    {"node_id": "H1", "demand": 3, "delivered": 3, "shortage": 0},
    {"node_id": "H2", "demand": 4, "delivered": 2, "shortage": 2}
  ],
  "message": "…最大送达量仅 5, 总缺口 2; 连通不代表容量足够…"
}
```

方案快照中**没有必保供水点**时返回充足及零需求：`sufficient:true`、
`empty:true`、`total_demand:0`、`delivered_total:0`、`shortage_total:0`、
`node_summary:[]`（`demands` 必须为空对象，否则按多余编号报 422）。

### 容量校核错误响应

| 场景 | HTTP 状态 | 示例错误（`detail.errors` 逐条列出） |
| --- | --- | --- |
| 方案编号不存在 | 404 | `方案不存在` |
| 目标方案不可行（无解方案） | 422 | `方案 #3 为不可行方案(reason_code: …), 没有可行的关阀后输水网, 不能进行供水容量校核` |
| 缺少未关阀管段的流量上限 | 422 | `缺少未关阀管段的流量上限: s4` |
| 为已关阀/不存在的管段提供上限 | 422 | `提供了非未关阀管段的流量上限(多余编号): s5` |
| 流量上限非正整数（0、负数、小数、字符串、布尔、null） | 422 | `管段 s1 的流量上限必须是正整数, 收到: 0` |
| 缺少/多余进水点供给上限 | 422 | `缺少进水点的供给上限: S` / `提供了非进水点的供给上限(多余编号): A` |
| 供给上限非正整数 | 422 | `进水点 S 的供给上限必须是正整数, 收到: -2` |
| 缺少/多余必保点需求 | 422 | `缺少必保供水点的需求: H2` / `提供了非必保供水点的需求(多余编号): A` |
| 需求非正整数 | 422 | `必保点 H2 的需求必须是正整数, 收到: 1.5` |

## 建模约定

- 管段为无向边；每条管段最多绑定 1 个阀门，关阀等价于从图中删除该管段。
- 节点四种角色互斥；漏点本身隔离后为“已隔离”，与漏点处于同一无水分量的
  普通点显示为“断水”。
- 多个漏点必须**全部**与所有进水点断开才算隔离成功。
- **单阀失效备援**：计划关阀集合 M 中每一枚阀门都可能“关不上、保持开启”，
  失效时实际关阀集合为 M 去掉该阀（其余阀门照常关闭）。备援可行要求 M 本身
  及每个 M\\{j} 都满足“漏点全隔离 + 必保点全有水”。失效的仅是“关闭动作”，
  因此计划清单之外的阀门不受影响；不关闭任何阀门的方案天然备援可行。
- 备援规划与常规规划**目标一致**：仅在可行解集合上不同，优化目标仍是计划
  关闭阀门的代价总和最小，同代价按编号升序列表的字典序取最小。
- **现场执行顺序**：计划阀门逐枚操作，操作阀门 v 的时段内 v 仍开启，故该
  时段生效的关阀集合是此前已完成的阀门；暴露量 = v 的正整数时长 × 此时段
  仍通水漏点（与至少一个进水点连通）的正整数权重之和。所有计划阀门都必须
  执行，全部完成后可行方案的漏点必全部隔离。仍通水漏点集合只取决于已关闭
  阀门集合，与顺序无关，因此用 2^k（k=计划阀门数≤14）个子集的子集 DP 求
  最小累计暴露量，并正向构造阀门编号序列字典序最小的唯一最优排列；该计算
  完全只读，不修改原方案与管网快照。
- **新增阀门选址预览**：候选位置只能选在**尚无阀门的管段**上，至多 6 个，
  每个候选有唯一新阀编号（不得与原阀或其他候选重复）、正整数安装费与正整数
  关阀代价，且原阀与候选合计不超过 14 个。方案 = 在「原阀 + 候选」中选择
  要关闭的阀门子集：被关闭的候选阀即**增设位置**，**只为实际关闭的候选阀
  计安装费**（安装但不关闭的候选阀不影响连通性也不计费，最优解不会包含
  它）。优化次序：安装费合计最小 → 本次关阀代价（被关闭原阀的关闭代价 +
  新阀关阀代价之和）最小 → 新增管段编号升序列表字典序 → 关阀编号升序
  列表字典序。求解复用常规规划的图校验与 BFS 连通性判定（在候选扩展后的
  管网上枚举，≤2¹⁴ 个子集）；无解原因同样复用常规分析并注明**候选范围内
  不可修复**。整个规划为只读预览：不修改当前管网，也不写入历史方案。
- **临时供水跨接预览**：针对已保存的**可行方案**，基于方案快照与已关阀
  管段（方案执行后的管网）。候选跨接至多 6 条，每条有唯一编号（候选之间
  不重复、不与现有管段编号重复）、两个不同的**现有节点**（方案快照中的
  节点）与正整数铺设费；跨接视为**新增通水管段**（无阀门，铺设后始终
  通水）。枚举全部候选组合（≤2⁶=64），只保留加入跨接后仍满足「全部漏点
  与进水点断开、全部必保点有水」的组合——跨接不得把漏点重新接通进水点。
  优化次序：**由断水转为有水的普通节点数**最大 → **铺设费合计**最小 →
  **跨接编号升序列表**字典序最小。漏点必须保持隔离、必保点本就全部有水，
  故只有普通节点可能被恢复；无法恢复任何普通节点时返回**空方案**（不铺设
  跨接，费用 0）。整个预览为只读计算：不修改管网与历史方案。
- **关阀成本与断水影响权衡预览**：针对**当前编辑中的管网**，为每个普通
  节点录入正整数用水权重（录入的键必须恰好是全部普通节点编号）。枚举全部
  关阀子集（≤2¹⁴），仅保留全部漏点与进水点断开且全部必保点仍有水的方案，
  对每个方案计算双目标：**关阀代价合计**与**断水影响**（原本——即不关阀
  时——有水、关阀后断水的普通节点用水权重之和；原本就断水的普通节点不计入）。
  方案 A **支配**方案 B 当且仅当 A 的代价与断水影响都不大于 B 且至少一项
  严格更小；返回全部**非支配方案**。同一对（代价, 断水影响）只保留关阀编号
  升序列表字典序最小的方案，结果按（代价, 断水影响, 关阀编号升序列表）升序
  排列。无可行方案时复用常规规划的无解原因分析。整个预览为只读计算：不修改
  当前管网，也不写入历史方案。
- **失效监测点布设预览**：针对已保存的**可行方案**，从方案快照的**非进水
  节点**中录入至多 12 个候选监测点（编号不得重复），每个候选有正整数
  布设费。情形 = 正常执行（全部计划阀门关闭）+ 每枚计划关闭阀门单独关
  不上（该阀保持开启、其余照常关闭），共 1+k 种（k=计划阀门数≤14）；
  每种情形按多进水点 BFS 求各节点有水/无水。监测点集可行当且仅当任意
  两种情形在该点集上的读数向量不同；优化次序：**布设费合计**最小 →
  **节点编号升序列表**字典序最小。若全部候选点的读数都无法区分某些
  情形对，则无可行点集，返回这些情形对及各情形在全部候选点上的读数。
  整个预览为只读计算：不修改管网与历史方案。
- **供水容量校核**：针对已保存的**可行方案**，以方案快照中**未关阀管段**
  （计划阀门未关闭的管段）构成无向输水网。每条管段录入正整数流量上限，
  管段净流量的**绝对值**受同一个上限约束（无向边容量，用两条容量相同的
  反向有向弧建模，最大流值与无向容量一致）；每个进水点录入正整数供给
  上限，每个必保供水点录入正整数需求；三类录入的编号集合都必须与方案
  快照**完整对应**（未关阀管段 / 进水点 / 必保点，不多不少）。用整数
  最大流（Dinic）求可送达必保点的最大总量：源→进水点容量为供给上限，
  必保点→汇容量为需求。**总送达量等于需求总量才判容量充足**——可行方案
  只保证连通，不保证容量足够，仅连通但容量不足时返回不足；各必保点实际
  送达量按必保点编号升序逐个锁定（前序点锁定后本点尽可能多送，二分 +
  残余网络最大流校验），结果唯一。无必保点时直接返回充足及零需求。整个
  校核为只读计算：不修改管网与历史方案。
