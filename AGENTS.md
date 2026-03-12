# AGENTS.md - 综合交通仿真系统

> 本文档面向 AI 编程助手，旨在帮助快速理解本项目背景、架构及开发规范。

---

## 项目概述

本项目是一个**多智能体交通仿真系统**，目标是通过模拟多元化的交通环境（包括传统交通实体和管理实体），结合机器学习和优化算法，提供基于数据驱动的实时交通管理和规划决策支持。

**当前状态**: 已实现核心模块（基础仿真功能可用）

**项目语言**: 中文（所有文档和注释使用中文）

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    综合交通仿真系统                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  交通代理    │  │  管理实体    │  │   数据分析与推荐     │  │
│  │  - 车辆     │  │  - 交通管理者 │  │   - 实时监控        │  │
│  │  - 行人     │  │  - 交通规划者 │  │   - 路径推荐        │  │
│  │             │  │  - 工程师    │  │   - 预测分析        │  │
│  │             │  │  - 规划师    │  │                     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                      仿真引擎层                              │
│         (交通流模拟 / 强化学习决策 / 优化算法)                 │
├─────────────────────────────────────────────────────────────┤
│                      基础设施层                              │
│              (道路网络 / 交通信号 / 环境状态)                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 项目结构

```
CITY/
├── city/                      # 主代码包
│   ├── __init__.py
│   ├── agents/               # 智能体模块
│   │   ├── base.py          # 智能体基类
│   │   ├── vehicle.py       # 车辆代理
│   │   ├── pedestrian.py    # 行人代理
│   │   ├── traffic_manager.py   # 交通管理者
│   │   └── traffic_planner.py   # 交通规划者
│   ├── environment/          # 环境模块
│   │   └── road_network.py  # 道路网络
│   ├── simulation/           # 仿真引擎
│   │   └── environment.py   # 仿真环境
│   ├── decision/             # 决策系统
│   │   └── rl_controller.py # RL控制器
│   ├── llm/                  # 大语言模型接口
│   │   ├── llm_client.py    # LLM客户端
│   │   └── agent_llm_interface.py  # 智能体LLM接口
│   ├── utils/                # 工具模块
│   │   └── vector.py        # 2D向量工具
│   ├── visualization/        # 可视化模块
│   │   ├── renderer.py      # matplotlib渲染器
│   │   └── zoning_visualizer.py  # 城市规划可视化
│   └── urban_planning/       # 城市规划模块
│       ├── __init__.py
│       ├── zone.py          # 功能区域类
│       └── zoning_agent.py  # 城市规划智能体
├── tests/                    # 测试模块
├── examples/                 # 示例脚本
├── config/                   # 配置文件
│   └── llm_config.json      # LLM配置
├── main.py                   # 主入口
├── requirements.txt          # 依赖文件
├── readme.md                 # 设计文档
└── AGENTS.md                 # 本文件
```

---

## 核心模块

### 1. 道路网络 (`city/environment/road_network.py`)

**核心类**:
- `Node`: 道路节点（交叉口）
- `Edge`: 路段（连接两个节点）
- `Lane`: 车道
- `TrafficLight`: 交通信号灯
- `RoadNetwork`: 道路网络管理器

**关键功能**:
- 使用 Dijkstra 算法的最短路径规划
- 交通信号灯状态管理
- 支持多车道道路

### 2. 智能体 (`city/agents/`)

#### 基类 (`base.py`)
- `BaseAgent`: 所有智能体的抽象基类
- 定义 `perceive() -> decide() -> act()` 循环

#### 车辆代理 (`vehicle.py`)
- `Vehicle`: 模拟各类车辆
- 支持类型：CAR, BUS, TRUCK, EMERGENCY, MOTORCYCLE, BICYCLE
- 行为：加速、减速、变道、停车

#### 行人代理 (`pedestrian.py`)
- `Pedestrian`: 模拟行人行为
- 状态：行走、等待、过马路

#### 交通管理者 (`traffic_manager.py`)
- `TrafficManager`: 实时交通协调和监控
- 功能：信号灯控制、事件响应、交通监控

#### 交通规划者 (`traffic_planner.py`)
- `TrafficPlanner`: 长期交通规划
- 功能：瓶颈识别、规划提案、历史数据分析

### 3. 仿真环境 (`city/simulation/environment.py`)

**核心类**:
- `SimulationEnvironment`: 管理整个仿真系统
- `SimulationConfig`: 仿真配置

**功能**:
- 智能体生命周期管理
- 仿真时间推进
- 统计数据收集

### 4. 决策系统 (`city/decision/`)

- `TrafficSignalRLController`: 信号灯强化学习控制器
- 基于 Q-learning 的信号灯优化

### 5. 可视化模块 (`city/visualization/`)

- `TrafficVisualizer`: 交通仿真可视化器
  - 实时渲染道路网络、车辆、行人
  - 显示交通信号灯状态（红/黄/绿）
  - 显示仿真统计信息
- `SimulationVisualizer`: 集成可视化包装器

### 6. 大语言模型模块 (`city/llm/`)

- `LLMClient`: LLM API客户端
  - 支持 OpenAI、Azure 等提供商
  - 自动从环境变量读取API密钥
- `AgentLLMInterface`: 智能体LLM接口
  - 为不同类型智能体提供LLM决策支持
  - 车辆、行人、交通管理者、规划者
- `MockLLMClient`: 模拟LLM客户端（用于测试）

---

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行示例

```bash
# 运行简单交叉口仿真（无可视化）
python main.py --example simple

# 运行网格城市仿真（无可视化）
python main.py --example grid

# 运行可视化仿真
python main.py --visual simple
python main.py --visual grid

# 运行测试
python main.py --test
```

### 使用可视化

```python
from city.simulation.environment import SimulationEnvironment
from city.visualization.renderer import SimulationVisualizer

# 创建环境
env = SimulationEnvironment(network)

# 创建可视化器
visualizer = SimulationVisualizer(env, figsize=(12, 10))

# 运行可视化仿真
visualizer.run()

# 或逐步运行
while env.is_running:
    visualizer.step()

# 保存截图
visualizer.save_screenshot("screenshot.png")
```

### 使用大语言模型

#### 方式1: 使用配置文件（推荐）

**1. 编辑配置文件**

打开 `config/siliconflow_config.json`，填入你的 API Key：

```json
{
  "provider": "SILICONFLOW",
  "api_key": "sk-XXXXXXXXXXXXXXXXXXXXXXXX",  
  "base_url": "https://api.siliconflow.cn/v1",
  "model": "Qwen/Qwen3-14B",
  "temperature": 0.7,
  "max_tokens": 500
}
```

**2. 代码中使用**

```python
from city.llm.llm_client import load_siliconflow_config, load_llm_from_config
from city.llm.agent_llm_interface import set_global_llm_client
from city.agents.vehicle import Vehicle, VehicleType

# 自动查找并加载 config/siliconflow_config.json
llm_client = load_siliconflow_config()

# 或指定配置文件路径
# llm_client = load_llm_from_config("config/siliconflow_config.json")

# 设置全局客户端
set_global_llm_client(llm_client)

# 创建启用LLM的智能体
vehicle = Vehicle(
    vehicle_type=VehicleType.CAR,
    use_llm=True
)

# 获取LLM决策
perception = vehicle.perceive()
decision = vehicle.llm_decide(perception)
print(decision)
```

**3. 运行演示**

```bash
# 确保 config/siliconflow_config.json 已配置好
$env:PYTHONPATH="d:\项目\CITY"; python examples/use_config.py
```

---

#### 方式2: 使用环境变量

```powershell
# Windows PowerShell
$env:SILICONFLOW_API_KEY="your-api-key"
$env:SILICONFLOW_BASE_URL="https://api.siliconflow.cn/v1"
$env:SILICONFLOW_MODEL="Qwen/Qwen3-14B"
```

---

#### 方式3: 代码中直接配置

```python
from city.llm.llm_client import LLMClient, LLMConfig, LLMProvider

config = LLMConfig(
    provider=LLMProvider.SILICONFLOW,
    api_key="sk-xxxxxxxx",
    base_url="https://api.siliconflow.cn/v1",
    model="Qwen/Qwen3-14B",
    temperature=0.7,
    max_tokens=500
)

llm_client = LLMClient(config)
```

---

#### Mock LLM 测试（无需API密钥）

```python
from city.llm.llm_client import MockLLMClient
from city.llm.agent_llm_interface import set_global_llm_client

mock_llm = MockLLMClient({
    "拥堵": '{"action": "decelerate"}',
    "畅通": '{"action": "accelerate"}'
})
set_global_llm_client(mock_llm)
```

### 直接使用代码

```python
from city.environment.road_network import RoadNetwork, Node
from city.simulation.environment import SimulationEnvironment
from city.utils.vector import Vector2D

# 创建道路网络
network = RoadNetwork("my_network")
n1 = Node(position=Vector2D(0, 0), name="start")
n2 = Node(position=Vector2D(100, 0), name="end")
network.add_node(n1)
network.add_node(n2)
network.create_edge(n1, n2)

# 创建仿真环境
env = SimulationEnvironment(network)

# 生成车辆
vehicle = env.spawn_vehicle(n1, n2)

# 运行仿真
env.run(num_steps=1000)
```

---

## 技术栈

| 模块 | 技术 |
|------|------|
| 编程语言 | Python 3.10+ |
| 数学计算 | NumPy, Pandas |
| 可视化 | Matplotlib (TkAgg后端) |
| 大语言模型 | OpenAI API / Azure OpenAI |
| 强化学习 | 预留接口，可集成 Stable-Baselines3 |
| 测试 | pytest |

**依赖安装：**
```bash
# 可视化
pip install matplotlib

# 大语言模型
pip install openai
```

---

## 开发规范

### 代码风格
- 代码注释使用**中文**
- 遵循 PEP 8
- 使用类型注解

### 命名规范
- 类名：大驼峰（如 `TrafficManager`）
- 函数/变量：小写下划线（如 `spawn_vehicle`）
- 常量：大写下划线（如 `DEFAULT_MAX_SPEED`）

### 文档规范
- 类和方法使用 docstring
- 复杂逻辑添加注释

---

## 扩展指南

### 添加新的车辆类型

```python
class VehicleType(Enum):
    # 在原有类型后添加
    ELECTRIC_CAR = auto()

Vehicle.TYPE_PARAMS[VehicleType.ELECTRIC_CAR] = {
    'max_speed': 27.78,
    'acceleration': 3.0,
    # ...
}
```

### 添加新的智能体类型

继承 `BaseAgent` 并实现以下方法：
- `perceive()`: 感知环境
- `decide()`: 做出决策
- `act(action)`: 执行动作
- `update(dt)`: 更新状态

---

## 城市规划智能体 (Urban Planning Agent)

**文件**: `city/urban_planning/zoning_agent.py`

### 功能概述

城市规划智能体是一个基于LLM的城市功能区域规划系统，专门负责规划和管理城市中的各类功能区域，如住宅区、商业区、医院、学校、公园等。它能够分析城市人口需求，自动决策何时/何地规划何种类型的区域。

### 区域类型 (ZoneType)

```python
from city.urban_planning.zone import ZoneType

# 支持的区域类型
ZoneType.RESIDENTIAL    # 住宅区 - 浅蓝色
ZoneType.COMMERCIAL     # 商业区 - 浅橙色
ZoneType.INDUSTRIAL     # 工业区 - 灰蓝色
ZoneType.HOSPITAL       # 医院 - 浅红色
ZoneType.SCHOOL         # 学校 - 浅绿色
ZoneType.PARK           # 公园/绿地 - 薄荷绿
ZoneType.OFFICE         # 办公区 - 浅紫色
ZoneType.MIXED_USE      # 混合用途 - 粉色
ZoneType.GOVERNMENT     # 政府机构 - 青绿色
ZoneType.SHOPPING       # 购物中心 - 浅黄色
```

### 核心组件

#### 1. Zone - 功能区域类

```python
from city.urban_planning.zone import Zone, ZoneType
from city.utils.vector import Vector2D

# 创建住宅区
residential_zone = Zone(
    zone_type=ZoneType.RESIDENTIAL,
    center=Vector2D(100, 200),
    width=120,      # 米
    height=100,     # 米
    name="住宅区_A"
)

# 区域属性
print(residential_zone.area)           # 面积 (m²)
print(residential_zone.max_population) # 最大人口容量
print(residential_zone.bounds)         # 边界 (min_x, min_y, max_x, max_y)
```

#### 2. ZoneManager - 区域管理器

```python
from city.urban_planning.zone import ZoneManager

manager = ZoneManager()

# 添加区域
manager.add_zone(residential_zone)

# 查询区域
zones = manager.get_zones_by_type(ZoneType.RESIDENTIAL)
nearest = manager.find_nearest_zone(Vector2D(0, 0))
overlapping = manager.check_overlap(new_zone)

# 获取统计
stats = manager.get_statistics()
```

#### 3. ZoningAgent - 城市规划智能体

```python
from city.urban_planning.zoning_agent import ZoningAgent

zoning_agent = ZoningAgent(
    environment=env,
    use_llm=True,               # 使用LLM进行决策
    planning_interval=20.0,     # 规划间隔（秒）
    max_zones=30,               # 最大区域数
    min_zone_size=50.0,         # 最小区域尺寸
    max_zone_size=200.0,        # 最大区域尺寸
    buffer_distance=20.0        # 区域间缓冲距离
)

env.add_agent(zoning_agent)
```

### 工作流程

1. **需求分析**: 根据人口数量和现有区域分布，分析城市服务需求
2. **类型决策**: 确定下一个需要规划的区域类型（优先满足学校、医院等基础设施需求）
3. **位置规划**: 使用LLM或规则选择最佳位置
   - 住宅区：分散布置
   - 商业区：靠近中心或主干道
   - 医院/学校：服务覆盖最大化
   - 工业区：远离住宅区，靠近边缘
   - 公园：靠近住宅区
4. **冲突检测**: 确保新区域不与现有区域重叠
5. **执行规划**: 创建区域并连接到道路网络

### 规划策略

```python
# LLM规划示例提示
"""
你是一位城市规划专家。请为城市规划一个新的功能区域。

规划目标: 学校
当前城市状态:
  - 总区域数: 5
  - 网络范围: X[0, 800], Y[0, 800]
  - 现有住宅区: 3个

规划约束:
1. 位置应靠近住宅区，方便学生上学
2. 大小: 宽度 60-150米, 高度 60-150米
3. 不应与现有区域重叠

输出JSON格式决策:
{
    "center_x": 整数,
    "center_y": 整数,
    "width": 宽度,
    "height": 高度,
    "name": "区域名称",
    "reasoning": "规划理由"
}
"""
```

### 可视化

#### 区域可视化器

```python
from city.visualization.zoning_visualizer import ZoningVisualizer

visualizer = ZoningVisualizer(
    environment=env,
    zoning_agent=zoning_agent,
    figsize=(14, 12),
    zone_alpha=0.6    # 区域透明度
)

# 运行仿真时更新可视化
while env.is_running:
    env.step()
    visualizer.render()

# 保存截图
visualizer.save_frame("city_zoning.png")
```

#### 集成可视化器

```python
from city.visualization.zoning_visualizer import IntegratedCityVisualizer

# 同时显示功能区域和交通仿真
visualizer = IntegratedCityVisualizer(
    env,
    zoning_agent=zoning_agent,
    figsize=(16, 10),
    enable_zones=True,
    enable_traffic=True
)

visualizer.render()
```

### 区域颜色映射

| 区域类型 | 颜色 | 用途 |
|---------|------|------|
| 住宅区 | 浅蓝色 #E3F2FD | 居住 |
| 商业区 | 浅橙色 #FFE0B2 | 商业活动 |
| 工业区 | 灰蓝色 #CFD8DC | 工业生产 |
| 医院 | 浅红色 #FFCDD2 | 医疗服务 |
| 学校 | 浅绿色 #C8E6C9 | 教育 |
| 公园 | 薄荷绿 #B9F6CA | 休闲绿地 |
| 办公区 | 浅紫色 #D1C4E9 | 办公 |
| 混合区 | 粉色 #F8BBD9 | 多功能 |

### 运行演示

```bash
# 城市规划演示（带可视化）
python examples/zoning_demo.py --visual

# 不使用LLM（仅规则规划）
python examples/zoning_demo.py --visual --no-llm

# 集成路网规划 + 城市规划
python examples/integrated_city_planning.py --visual
```

---

## 路网规划智能体 (Road Planning Agent)

**文件**: `city/agents/planning_agent.py`

### 功能概述

路网规划智能体是一个基于LLM的智能系统，能够动态分析交通需求并自主扩展道路网络。它从2×2网格开始，通过监测车辆OD（起点-终点）模式来识别交通瓶颈，并使用LLM决策何时/何地添加新道路或节点。

### 核心组件

#### 1. ODAnalyzer - OD需求分析器

```python
analyzer = ODAnalyzer(window_size=100)

# 记录车辆OD
analyzer.record_vehicle_od(vehicle)

# 分析需求模式
patterns = analyzer.analyze_demand_patterns()
# 返回: {
#   'patterns': [...],     # 高频OD对
#   'hotspots': [...],     # 热点节点
#   'total_records': 100,
#   'unique_od_pairs': 20
# }
```

#### 2. PlanningAgent - 规划智能体

```python
from city.agents.planning_agent import PlanningAgent

planning_agent = PlanningAgent(
    environment=env,
    use_llm=True,
    expansion_cooldown=60.0,    # 扩展冷却时间（秒）
    max_nodes=16,               # 最大节点数限制
    min_edge_length=150.0,      # 最小边长度
    max_edge_length=400.0       # 最大边长度
)

env.add_agent(planning_agent)
```

### 工作流程

1. **数据收集**: 监测仿真中所有车辆的OD模式
2. **需求分析**: 识别高频OD对和拥堵路段
3. **候选生成**: 基于以下策略生成扩展候选：
   - 连接高需求但无直接连接的OD对
   - 为拥堵路段添加绕行路线
4. **LLM决策**: 使用LLM评估候选并选择最佳扩展方案
5. **执行扩展**: 动态添加节点或边到路网

### 扩展类型

```python
# 类型1: 添加边（连接现有节点）
{
    "should_expand": True,
    "action": "add_edge",
    "from_node": "node_1",
    "to_node": "node_2",
    "num_lanes": 2,
    "reason": "High demand OD pair without direct connection"
}

# 类型2: 添加节点和边
{
    "should_expand": True,
    "action": "add_node_and_edge",
    "new_node_position": {"x": 450, "y": 300},
    "num_lanes": 2,
    "reason": "Creating new intersection for better connectivity"
}
```

### 前端路网规划模式

**访问路径**: 前端界面第四个Tab "路网规划"

**功能特点**:
- 可视化显示2×2初始网格和动态扩展的路网
- 绿色高亮显示新添加的节点和边
- 实时显示规划智能体状态（扩展次数、OD记录数）
- 扩展历史时间线
- 支持缩放、平移操作

### API端点

```
GET  /api/planning/network       # 获取路网数据
GET  /api/planning/state         # 获取完整状态
POST /api/planning/control       # 控制仿真 (start/pause/reset)
POST /api/planning/spawn         # 生成车辆
GET  /api/planning/expansion     # 获取扩展历史
```

WebSocket事件:
- `planning_connect` - 连接路网规划模式
- `planning_update` - 仿真状态更新
- `planning_vehicle_spawned` - 车辆生成确认

---

## 待办事项

- [x] 搭建项目基础结构
- [x] 实现道路网络基础设施
- [x] 实现智能体基类
- [x] 实现车辆代理
- [x] 实现行人代理
- [x] 实现交通管理者
- [x] 实现交通规划者
- [x] 实现仿真环境
- [x] 添加可视化模块
- [x] **集成大语言模型API**
- [x] **路网规划智能体** - 基于OD分析动态扩展路网
- [x] **城市规划智能体** - 基于LLM的功能区域规划
- [ ] 集成真实 RL 框架
- [ ] 支持 OpenStreetMap 数据导入
- [ ] 性能优化（支持大规模仿真）

---

## 参考文档

- `readme.md` - 系统设计详细文档
- 示例代码：`examples/` 目录

---

*最后更新: 2026-03-09*
