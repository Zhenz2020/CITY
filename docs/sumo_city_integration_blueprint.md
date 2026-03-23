# SUMO 与 CITY 融合实施蓝图

## 1. 文档目标

本文档用于明确 `SUMO` 微观交通机制与 `CITY` 多智能体交通仿真系统的融合方向、模块边界、实施步骤与测试方案。

目标不是将 `SUMO` 整体嵌入 `CITY`，而是借鉴其成熟的微观交通建模思想，在 `CITY` 内部构建一套可维护、可扩展、可被智能体与 LLM 调用的交通内核。

---

## 2. 融合总目标

将 `CITY` 升级为两层架构：

- 下层：确定性的微观交通内核，负责跟驰、变道、路口通行、车道连接、路网编辑、重路由
- 上层：多智能体与 LLM，负责策略、规划、调度、解释和高层决策

升级后的系统应满足以下目标：

- 车辆交互更加接近 `SUMO` 的微观仿真效果
- 路网支持结构化编辑，而非仅支持简单扩张
- `PlanningAgent`、`TrafficManager`、前端编辑器、LLM 共用统一的底层能力
- 交通行为逻辑与高层智能体逻辑解耦，降低后续维护成本

---

## 3. 当前系统现状

### 3.1 已有能力

当前 `CITY` 已具备以下基础：

- `Vehicle` 已有感知、决策、行动循环
- `RoadNetwork` 已有 `Node`、`Edge`、`Lane` 等基础结构
- 已支持基础的多车道、相邻车道感知和简单变道
- 已支持动态加点、加边
- 已有 `PlanningAgent` 等用于动态扩展路网的高层智能体

### 3.2 当前主要短板

当前系统主要存在以下结构性问题：

1. `Vehicle` 类过重  
   跟驰、变道、安全规则、LLM、死锁恢复、运动更新耦合在同一类中，难以扩展。

2. 变道逻辑较为粗糙  
   目前接近“目标车道局部空闲即可切入”，缺少战略性、协作性、收益性等变道动机。

3. 路网仍主要是边级抽象  
   缺少 `lane-to-lane connection`、冲突关系、目标车道约束等能力。

4. 路网编辑缺少统一事务层  
   动态建边建点已存在，但没有命令模式、校验、撤销重做、连接重建、受影响车辆重路由机制。

---

## 4. 融合原则

本次融合遵循以下原则：

### 4.1 借鉴机制，不直接移植系统

不将 `SUMO` 当作运行时依赖直接嵌入 `CITY`，而是借鉴其以下能力：

- 微观跟驰模型分层
- 变道动机分层
- 车道级连接建模
- 路口冲突与通行裁决
- 路网编辑事务机制
- 编辑后的网络修复与重路由流程

### 4.2 底层确定性，高层智能化

底层交通行为应保持确定性与可验证性：

- 跟驰
- 变道
- 路口是否可通过
- 网络编辑执行
- 重路由

高层智能体与 LLM 负责：

- 规划策略
- 驾驶风格参数
- 编辑方案选择
- 拥堵治理建议

### 4.3 分阶段推进

优先稳定微观车辆交互，再补全路口连接，再建设路网编辑系统，最后再将高层智能体全面接入。

---

## 5. 目标架构

建议新增核心包：

```text
city/
├── traffic_micro/
│   ├── __init__.py
│   ├── car_following.py
│   ├── lane_change.py
│   ├── junction.py
│   ├── routing.py
│   ├── network_editor.py
│   ├── edit_commands.py
│   ├── conflict.py
│   ├── occupancy.py
│   └── types.py
```

同时扩展现有模块：

- `city/agents/vehicle.py`
- `city/environment/road_network.py`
- `city/simulation/environment.py`
- `city/agents/planning_agent.py`
- `city/agents/traffic_manager.py`
- `city/agents/traffic_light_agent.py`

---

## 6. 模块设计

## 6.1 `car_following.py`

### 职责

负责车辆纵向运动控制，即加速、减速、跟车安全距离控制。

### 第一阶段建议实现

- `BaseCarFollowingModel`
- `IDMCarFollowingModel`

### 建议数据结构

```python
class CarFollowingContext:
    ego_speed: float
    ego_max_speed: float
    gap: float | None
    leader_speed: float | None
    speed_limit: float
    desired_speed: float
    reaction_time: float
    min_gap: float
```

### 建议接口

```python
class BaseCarFollowingModel:
    def compute_acceleration(self, ctx: CarFollowingContext) -> float:
        ...
```

### 说明

- 第一版仅实现 `IDM`
- 不建议一开始引入 `EIDM` 或过多高级参数
- 模型输出统一为“期望加速度”，由运动积分器执行

---

## 6.2 `lane_change.py`

### 职责

负责车辆横向决策，即是否变道、向哪一侧变道、是否安全可变。

### 建议分层

1. 变道动机计算
2. 变道安全性检查
3. 变道执行裁决

### 建议实现的变道动机

- `strategic`：为后续转向、出口、目标边提前换道
- `speed_gain`：为获得更高通行速度而换道
- `cooperative`：为其他车辆让行
- `keep_right`：保持靠右通行偏好

### 建议数据结构

```python
class LaneChangeDesire:
    strategic: float
    speed_gain: float
    cooperative: float
    keep_right: float
    total: float
    target_side: str | None

class LaneChangeDecision:
    should_change: bool
    target_lane_id: str | None
    reason: str
    urgency: float
```

### 第一阶段约束

- 先做离散车道切换
- 暂不实现 `sublane` 连续横向偏移

---

## 6.3 `junction.py`

### 职责

负责路口通行与车道连接关系管理。

### 建议新增核心概念

- `Connection`
- `TurnDirection`
- `JunctionPolicy`
- `ConflictMatrix`

### 建议数据结构

```python
class Connection:
    from_lane_id: str
    to_lane_id: str
    turn_direction: str
    priority: int
    conflict_ids: set[str]
```

### 功能目标

- 定义当前车道可以连接到哪些下游车道
- 决定车辆是否具备合法转向路径
- 在路口前进行冲突判断和通行裁决
- 为信号灯控制提供连接级控制基础

### 重要性

该模块是整个融合方案的关键，没有 `lane-to-lane connection`，车辆行为无法真正接近 `SUMO`。

---

## 6.4 `routing.py`

### 职责

负责路径规划与目标车道推荐。

### 路径层次

- `node path`
- `edge path`
- `lane recommendation`

### 建议数据结构

```python
class RoutePlan:
    nodes: list[str]
    edges: list[str]
    desired_lanes_by_edge: dict[str, list[str]]
```

### 第一阶段目标

- 从节点最短路升级到边级路径
- 根据后续转向需求为车辆推荐目标车道

### 第二阶段目标

- 支持路网编辑后的局部重路由
- 支持基于拥堵状态的动态重路由

---

## 6.5 `occupancy.py`

### 职责

负责维护车道上的车辆占用快照，提升邻车查询效率。

### 建议数据结构

```python
class LaneOccupancy:
    lane_id: str
    ordered_vehicle_ids: list[str]

class NeighborVehicles:
    leader: str | None
    follower: str | None
    left_leader: str | None
    left_follower: str | None
    right_leader: str | None
    right_follower: str | None
```

### 设计要求

- 每个仿真步建立稳定快照
- 车道上的车辆按位置排序
- 车辆感知尽量基于快照查询，避免频繁全量扫描

---

## 6.6 `network_editor.py` 与 `edit_commands.py`

### 职责

负责路网编辑事务执行、网络合法性维护、重建连接关系、触发重路由。

### 建议命令对象

```python
class EditCommand: ...
class AddNodeCommand(EditCommand): ...
class AddEdgeCommand(EditCommand): ...
class RemoveEdgeCommand(EditCommand): ...
class AddLaneCommand(EditCommand): ...
class RemoveLaneCommand(EditCommand): ...
class SplitEdgeCommand(EditCommand): ...
class ChangeSpeedLimitCommand(EditCommand): ...
class ChangeLanePermissionCommand(EditCommand): ...
```

### 建议事务对象

```python
class EditTransaction:
    commands: list[EditCommand]
    description: str
```

### 执行流程

1. 预校验
2. 执行编辑命令
3. 重建 `connection`
4. 标记受影响车辆
5. 执行局部重路由
6. 写入编辑历史
7. 支持撤销与重做

---

## 7. 现有模块改造方案

## 7.1 `Vehicle` 改造方向

### 当前问题

`Vehicle` 同时承担感知、规则决策、LLM、安全检查、跟驰、变道、死锁恢复、运动推进等多项职责。

### 目标改造

将 `Vehicle` 改为“宿主对象”，保留状态与生命周期，策略逻辑交给独立模型：

```python
class Vehicle(BaseAgent):
    car_follow_model: BaseCarFollowingModel
    lane_change_model: BaseLaneChangeModel
    route_plan: RoutePlan | None
```

### `Vehicle` 保留职责

- 车辆基础属性
- 当前车道、路段、位置、速度状态
- 感知数据采集
- 调用微观交通模型
- 运动积分
- 生命周期管理

### 从 `Vehicle` 中拆出的职责

- 跟驰模型公式
- 变道判据
- 路口连接与冲突裁决
- 路网编辑后的重路由处理

---

## 7.2 `RoadNetwork` 改造方向

### 新增能力

建议在现有 `RoadNetwork` 基础上增加：

- `Lane.edge`
- `Lane.index`
- `Lane.permissions`
- `Edge.max_speed`
- `RoadNetwork.connections`
- 连接级查询接口

### 建议新增方法

- `build_connections()`
- `get_lane_by_id()`
- `get_outgoing_connections(lane)`
- `add_lane_to_edge(edge_id)`
- `remove_lane_from_edge(edge_id, lane_index)`
- `split_edge(edge_id, position_ratio)`
- `validate_network()`

### 改造目标

从“边级网络图”升级为“具备车道连接关系的可通行网络”。

---

## 7.3 `SimulationEnvironment` 改造方向

### 当前问题

目前每个智能体大多独立完成决策和推进，横向交互协调能力不足。

### 目标更新流水线

建议每个仿真步采用以下统一流程：

1. 更新信号灯
2. 构建车道占用快照
3. 为每辆车计算纵向控制
4. 为每辆车计算横向意图
5. 统一裁决冲突变道
6. 统一推进车辆位置
7. 处理过边、过路口、重路由
8. 清理完成车辆

### 目标

将“单车独立推进”转为“统一调度推进”，从而提升稳定性与一致性。

---

## 7.4 `PlanningAgent` 改造方向

### 当前问题

当前路网规划智能体倾向于直接操作网络结构。

### 目标改造

将其输出从“直接建边建点”改为“编辑事务请求”：

1. 生成编辑计划
2. 调用 `NetworkEditor.apply(transaction)`
3. 由编辑器负责校验、连接重建、重路由和历史记录

### 好处

- 人工编辑与智能体编辑走统一路径
- 网络合法性校验集中管理
- 编辑行为可追溯、可撤销

---

## 8. LLM 与微观交通内核的分工

### 8.1 LLM 负责的内容

- 驾驶风格参数选择
- 拥堵后的管理策略
- 编辑方案建议
- 规划优先级判断
- 高层解释与说明

### 8.2 微观交通内核负责的内容

- 跟驰
- 变道
- 路口冲突判断
- 通行许可裁决
- 路网编辑执行
- 车辆重路由

### 8.3 明确边界

不建议让 LLM 直接控制“本帧是否左变道”。

建议让 LLM 输出的是高层策略变量，例如：

- `risk_preference=0.7`
- `reroute_on_congestion=true`
- `preferred_edit=add_lane(edge_12)`

---

## 9. 分阶段实施计划

## 9.1 第一期：微观车辆交互升级

### 目标

先让车辆纵向与横向行为更接近真实微观仿真。

### 范围

- 引入 `IDM` 跟驰模型
- 引入四类变道动机
- 增加 `LaneOccupancy` 快照
- 路由从 `node path` 升级到 `edge path`
- 初步支持目标车道推荐

### 需要新增或改造的文件

- `city/traffic_micro/car_following.py`
- `city/traffic_micro/lane_change.py`
- `city/traffic_micro/occupancy.py`
- `city/traffic_micro/routing.py`
- `city/agents/vehicle.py`
- `city/environment/road_network.py`
- `city/simulation/environment.py`

### 验收标准

- 跟车行为更平滑
- 变道不再是“有空就切”
- 车辆会为了后续路线提前选道
- 明显的穿车、抢道现象显著减少

### 第一阶段细化任务清单

以下任务建议按顺序执行，每项都应以“接口稳定、行为可测、尽量少改外围模块”为原则推进。

#### 任务 1：建立 `traffic_micro` 基础骨架

**目标**

先把微观交通内核的目录和基础类型搭出来，避免后续继续把逻辑堆进 `Vehicle`。

**新增文件**

- `city/traffic_micro/__init__.py`
- `city/traffic_micro/types.py`
- `city/traffic_micro/car_following.py`
- `city/traffic_micro/lane_change.py`
- `city/traffic_micro/occupancy.py`
- `city/traffic_micro/routing.py`

**建议内容**

- 在 `types.py` 中放公共 dataclass
- 在 `car_following.py` 中定义跟驰上下文与抽象基类
- 在 `lane_change.py` 中定义变道上下文、动机结构、决策结构
- 在 `occupancy.py` 中定义车道占用快照结构
- 在 `routing.py` 中定义 `RoutePlan`

**完成标准**

- 新包结构可被现有系统导入
- 不改动现有仿真行为，仅建立骨架和接口

---

#### 任务 2：抽离 `IDM` 跟驰模型

**目标**

把当前 `Vehicle` 中混杂的纵向安全逻辑抽为独立模型，统一输出纵向加速度。

**涉及文件**

- `city/traffic_micro/car_following.py`
- `city/agents/vehicle.py`

**建议实现**

- 新增 `CarFollowingContext`
- 新增 `BaseCarFollowingModel`
- 新增 `IDMCarFollowingModel`
- 在 `Vehicle.__init__` 中挂载 `self.car_follow_model`
- 在 `Vehicle` 内部新增一层适配逻辑，将当前感知结果转换为 `CarFollowingContext`

**建议拆法**

将当前代码中与以下逻辑相关的部分逐步替换：

- 前车距离计算结果
- 安全距离计算
- 基于前车状态的加减速决策

**完成标准**

- 车辆纵向速度控制主要由 `IDMCarFollowingModel` 驱动
- `Vehicle` 不再直接写主要跟驰公式
- 基础直线路段跟车行为比当前更平滑

---

#### 任务 3：建立车道占用快照机制

**目标**

降低邻车查询成本，并为后续变道模型提供稳定输入。

**涉及文件**

- `city/traffic_micro/occupancy.py`
- `city/simulation/environment.py`
- `city/agents/vehicle.py`
- `city/environment/road_network.py`

**建议实现**

- 在每个仿真步开始时，按车道构建车辆顺序快照
- 每条 `Lane` 上的车辆按 `distance_on_edge` 排序
- 提供以下查询：
  - 当前车道前车
  - 当前车道后车
  - 左侧目标车道前后车
  - 右侧目标车道前后车

**建议新增接口**

```python
occupancy_snapshot.get_leader(vehicle)
occupancy_snapshot.get_follower(vehicle)
occupancy_snapshot.get_adjacent_neighbors(vehicle, side="left")
```

**完成标准**

- `Vehicle` 不再通过遍历整条车道和相邻车道手工查找邻车
- 变道与跟驰可共用同一套邻车查询接口

---

#### 任务 4：抽离规则化变道模型

**目标**

让变道从“空就切”升级为“有动机、有约束、有收益判断”的规则模型。

**涉及文件**

- `city/traffic_micro/lane_change.py`
- `city/agents/vehicle.py`
- `city/environment/road_network.py`

**建议实现**

- 新增 `LaneChangeContext`
- 新增 `LaneChangeDesire`
- 新增 `LaneChangeDecision`
- 新增 `RuleBasedLaneChangeModel`

**第一版至少实现 3 类动机**

- `strategic`
- `speed_gain`
- `keep_right`

`cooperative` 可以先保留接口，第二轮补强。

**建议安全约束**

- 目标车道前向间隙必须满足最小安全距离
- 目标车道后车接近速度不能过高
- 变道决策应设置冷却时间，避免左右横跳

**完成标准**

- 车辆变道前先计算动机和安全性
- `Vehicle._attempt_lane_change()` 只负责执行，不再负责完整决策
- 连续多车道道路中，车辆会出现更合理的超车与提前并道行为

---

#### 任务 5：把路径从 `node path` 升级为 `edge path`

**目标**

为后续目标车道推荐和战略性变道提供必要的路径信息。

**涉及文件**

- `city/traffic_micro/routing.py`
- `city/environment/road_network.py`
- `city/agents/vehicle.py`
- `city/simulation/environment.py`

**建议实现**

- 在现有最短路基础上生成 `RoutePlan`
- `RoutePlan` 中同时保存：
  - 节点序列
  - 边序列
  - 每条边的候选目标车道信息

**建议新增接口**

```python
routing_engine.plan_route(start_node, end_node) -> RoutePlan
```

**完成标准**

- `Vehicle` 内部主路由不再只保留节点列表
- 车辆可以知道自己当前边之后要接入哪条边
- 后续战略性变道有基础输入

---

#### 任务 6：改造 `Vehicle` 为模型调度器

**目标**

将 `Vehicle` 从“大而全逻辑体”改为“状态宿主 + 模型调度器”。

**涉及文件**

- `city/agents/vehicle.py`

**建议改造点**

- 在 `__init__` 中初始化：
  - `car_follow_model`
  - `lane_change_model`
  - `route_plan`
- 把 `decide()` 中的纵向和横向逻辑拆分为独立步骤
- 保留：
  - 生命周期管理
  - 当前状态记录
  - 位置更新
  - 动作执行

**建议的内部流程**

```python
perception -> context build -> 
car_follow_model -> lane_change_model -> 
safety override -> act -> update position
```

**完成标准**

- `Vehicle` 中与交通行为模型强耦合的大段规则被显著缩减
- 后续替换更复杂模型时只需替换模型类，而不是重写 `Vehicle`

---

#### 任务 7：调整仿真主循环，加入占用快照阶段

**目标**

让仿真从“每辆车各自扫环境”过渡到“环境统一准备交通上下文”。

**涉及文件**

- `city/simulation/environment.py`

**建议改造**

在 `step()` 中加入：

1. 更新信号灯
2. 构建车道占用快照
3. 让车辆基于快照决策
4. 统一执行车辆动作
5. 统一推进位置

第一期无需把所有裁决都做成集中式，只要先把快照和决策上下文统一起来即可。

**完成标准**

- 仿真主循环中显式出现“构建交通上下文”的阶段
- `Vehicle` 可从环境拿到本步快照

---

#### 任务 8：补齐基础测试

**目标**

用测试锁住第一期接口与行为，避免后续二期三期改动时回归。

**新增测试文件**

- `tests/test_car_following.py`
- `tests/test_lane_change.py`
- `tests/test_routing_edge_plan.py`
- `tests/test_occupancy_snapshot.py`

**最低测试覆盖点**

- `IDM` 在自由行驶和跟车状态下的输出差异
- 目标车道前后有车时是否禁止变道
- 路径规划是否能产出 `edge path`
- 车道快照是否能正确找到 leader / follower

**完成标准**

- 新增模块均有最基本单测
- 第一阶段核心接口具备回归保护

---

#### 任务 9：增加第一期演示脚本

**目标**

提供一个简单、可重复运行的场景，用于人工观察第一期效果。

**建议新增文件**

- `examples/test_micro_phase1.py`

**建议场景**

- 双车道直线路段
- 多辆车同向行驶
- 前车低速、后车高速接近
- 观察跟驰平滑性和超车变道表现

**完成标准**

- 能快速运行并肉眼观察第一期行为改进
- 作为后续优化前后的对比基准

---

#### 任务 10：控制第一期边界

**目标**

确保第一期不失控，不把第二期、第三期内容提前混入。

**第一期明确不做**

- `sublane` 连续横向偏移
- 完整路口冲突矩阵
- 编辑事务系统
- 撤销与重做
- 智能体直接调用编辑器
- 基于拥堵的动态重路由

**原因**

第一期的目标是先稳定车辆微观交互，不是一次性完成整套交通内核。

---

#### 第一阶段建议里程碑

可按以下里程碑推进：

1. `traffic_micro` 骨架 + `IDM` 模型完成
2. 占用快照 + 规则变道模型完成
3. `edge path` 路由 + `Vehicle` 解耦完成
4. 测试与演示脚本完成

当以上四个里程碑完成后，再进入第二期的 `Connection` 与路口系统建设。

---

## 9.2 第二期：路口连接与冲突系统

### 目标

让路口从几何连接点升级为具备通行规则的控制单元。

### 范围

- 引入 `Connection`
- 自动构建 `lane-to-lane connection`
- 引入基础冲突矩阵
- 让信号灯控制与连接关系绑定
- 根据连接关系限定车辆可达车道

### 需要新增或改造的文件

- `city/traffic_micro/junction.py`
- `city/traffic_micro/conflict.py`
- `city/environment/road_network.py`
- `city/agents/traffic_light_agent.py`
- `city/agents/vehicle.py`

### 验收标准

- 车辆在路口转向时可选择合法目标车道
- 路口通过过程更稳定
- 信号控制能细化到连接级影响

---

## 9.3 第三期：路网编辑系统

### 目标

将当前“动态扩张”升级为真正可编辑、可修复、可回滚的路网编辑系统。

### 范围

- 增加编辑命令体系
- 支持加边、删边、加车道、删车道、拆边
- 编辑后自动重建连接关系
- 编辑后受影响车辆自动重路由
- 支持编辑历史、撤销与重做

### 需要新增或改造的文件

- `city/traffic_micro/network_editor.py`
- `city/traffic_micro/edit_commands.py`
- `city/environment/road_network.py`
- `city/simulation/environment.py`
- `city/agents/planning_agent.py`

### 验收标准

- 路网编辑后仿真不中断
- 网络结构保持合法
- 车辆在编辑后仍能继续运行
- 智能体与人工编辑共用同一编辑接口

---

## 10. 建议的数据结构

建议在 `types.py` 中集中定义部分公共类型。

### 建议类型

```python
@dataclass
class LanePermission:
    allow_vehicle_types: set[str]
    disallow_vehicle_types: set[str]

@dataclass
class VehicleKinematics:
    speed: float
    acceleration: float
    position_on_lane: float

@dataclass
class RoutePlan:
    nodes: list[str]
    edges: list[str]
    desired_lanes_by_edge: dict[str, list[str]]
```

### 设计要求

- 公共类型集中定义，避免模块之间重复声明
- 命名稳定，便于未来 API 和前端对接
- 后续支持序列化，方便日志、回放和前端展示

---

## 11. 测试方案

建议增加以下测试文件：

```text
tests/
├── test_car_following.py
├── test_lane_change.py
├── test_junction_connections.py
├── test_network_editor.py
├── test_rerouting_after_edit.py
└── test_planning_agent_edits.py
```

### 核心测试点

- `IDM` 在不同跟车距离下的加速度输出是否合理
- 变道前后的前后安全间隙是否满足要求
- 路口连接关系是否正确建立
- 删除边后车辆是否能自动重路由
- 新增车道后连接关系是否自动修复
- `PlanningAgent` 输出编辑事务后能否正确生效

---

## 12. 建议的最小可行接口

建议尽早稳定以下核心接口：

```python
route = routing_engine.plan_route(vehicle, start_node, end_node)

acc = vehicle.car_follow_model.compute_acceleration(ctx)
lane_decision = vehicle.lane_change_model.decide(ctx)

editor.apply(
    EditTransaction(
        description="新增绕行道路",
        commands=[
            AddNodeCommand(...),
            AddEdgeCommand(...),
            AddLaneCommand(...),
        ],
    )
)
```

这些接口一旦稳定，后续扩展成本会显著下降。

---

## 13. 推荐开发顺序

建议按以下顺序推进：

1. 抽离 `IDMCarFollowingModel`
2. 抽离 `RuleBasedLaneChangeModel`
3. 增加 `LaneOccupancy` 快照
4. 让 `Vehicle` 改为调用模型对象
5. 引入 `Connection`
6. 实现 `NetworkEditor`
7. 改造 `PlanningAgent` 对接事务式编辑

### 顺序理由

先稳定车辆行为，再提升网络复杂度。  
如果先做编辑系统，再处理微观行为，调试难度会显著增加。

---

## 14. 最终结论

本次融合的正确方向不是“把 `SUMO` 软件接入 `CITY`”，而是：

- 借鉴 `SUMO` 的微观交通模型分层
- 借鉴 `SUMO` 的车道级网络与连接思维
- 借鉴 `SUMO netedit` 的编辑事务机制
- 在 `CITY` 内部重建一套可被多智能体和 LLM 共同调用的交通内核

这样既能保留 `CITY` 在多智能体与 LLM 方面的优势，也能显著提升交通仿真的真实性、可扩展性与工程稳定性。
