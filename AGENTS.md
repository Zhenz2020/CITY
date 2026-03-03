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
│   └── visualization/        # 可视化模块
│       └── renderer.py      # matplotlib渲染器
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
- [ ] 集成真实 RL 框架
- [ ] 支持 OpenStreetMap 数据导入
- [ ] 性能优化（支持大规模仿真）

---

## 参考文档

- `readme.md` - 系统设计详细文档
- 示例代码：`examples/` 目录

---

*最后更新: 2026-02-26*
