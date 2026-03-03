# 车辆感知与决策优化总结

## 问题分析

车辆出现锁死或不动的情况主要由以下原因导致：

1. **感知范围不足** - 只检测同一车道前车，缺少周边车辆信息
2. **决策逻辑简单** - 缺乏智能跟车、死锁恢复等机制
3. **停止后无法恢复** - 停车后缺乏重新启动的逻辑
4. **LLM集成不充分** - 感知数据不够丰富，无法支撑智能决策

---

## 优化内容

### 1. 增强感知系统 (`vehicle.py`)

#### 新增感知维度：
- **前车详细信息**：距离、速度、相对速度、碰撞时间(TTC)、是否停止
- **后车检测**：距离、接近速度
- **相邻车道车辆**：左/右车道车辆位置和状态
- **路口排队检测**：排队车辆数、是否被堵住
- **周边环境概览**：100米范围内所有车辆

#### 感知数据结构：
```python
{
    'self': {...},              # 自身状态
    'route': {...},             # 路线进度
    'front_vehicle': {...},     # 前车详细信息
    'rear_vehicle': {...},      # 后车信息
    'left_lane_vehicle': {...}, # 左邻车道
    'right_lane_vehicle': {...},# 右邻车道
    'traffic_light': {...},     # 信号灯状态+距离
    'intersection_queue': {...},# 路口排队
    'surroundings': [...],      # 周边所有车辆
    'road_conditions': 'normal',# 道路条件
    'is_deadlocked': False,     # 死锁标记
}
```

---

### 2. 智能决策系统 (`vehicle.py`)

#### 新增决策特性：

**A. 紧急制动逻辑**
- 当 TTC < 2秒 时触发紧急制动
- 减速度加倍，确保安全

**B. 智能跟车 (IDM简化版)**
- 计算安全距离：`min_gap + velocity * reaction_time`
- 根据距离动态调整速度
- 前车停止时自动跟随停止

**C. 交通信号灯优化**
- 红灯时计算能否安全停车
- 黄灯时判断是否能通过
- 距离路口<10米时强制停车

**D. 路口排队处理**
- 检测路口是否被堵住
- 提前减速避免堵在路口中央

**E. 变道逻辑框架**
- 检查目标车道空间
- 预留完整变道实现接口

---

### 3. 死锁检测与恢复 (`vehicle.py`)

#### 死锁检测机制：
```python
def _check_deadlock(self) -> bool:
    # 1. 速度<0.5 m/s 持续5秒以上
    # 2. 记录位置历史(30帧)
    # 3. 检查最后10个位置是否基本不变(<1米)
```

#### 死锁恢复策略：
1. **第一辆车**：给一个微小速度(0.5 m/s)缓慢前进
2. **尝试变道**：检查左/右车道是否空闲
3. **等待恢复**：如果无法移动，等待前车

---

### 4. 增强LLM接口 (`agent_llm_interface.py`)

#### 改进点：

**A. 丰富的上下文提示**
```
=== 车辆驾驶决策请求 ===

【自身状态】
- ID, 类型, 速度, 状态, 位置, 路线进度

【前方车辆 - 关键信息】  
- 距离, 前车速度, 相对速度, TTC, 是否停止
⚠️ 警告：碰撞风险高！

【交通信号灯】
- 状态, 距离路口, 预计到达时间
🔴 红灯即将到达，需要准备停车

【相邻车道】
- 左车道: 空闲/有车辆
- 右车道: 空闲/有车辆

【周边环境】
- 周边X辆车在100米范围内

【上次决策】
- 动作, 理由

=== 决策要求 ===
特别注意事项...
请以JSON格式回复
```

**B. 结构化决策输出**
```python
{
    "action": "动作类型",
    "reason": "决策理由",
    "reasoning_chain": ["推理步骤1", ...],  # 新增
    "confidence": 0.95,  # 置信度
    "parameters": {...}
}
```

**C. 决策历史跟踪**
- 记录最近10次决策
- 包含感知摘要和决策结果
- 支持决策解释生成

**D. 增强的Fallback决策**
- 基于感知信息的规则决策
- 紧急情况优先处理
- 死锁自动恢复

---

### 5. 状态跟踪与可视化 (`vehicle.py`)

#### 新增车辆状态：
```python
class VehicleState(Enum):
    CRUISING = auto()       # 巡航
    FOLLOWING = auto()      # 跟车
    STOPPED = auto()        # 已停止
    ACCELERATING = auto()   # 加速中
    DECELERATING = auto()   # 减速中
    WAITING_LIGHT = auto()  # 等红灯
    QUEUED = auto()         # 排队中
    DEADLOCKED = auto()     # 死锁
```

#### 新增车辆属性：
- `vehicle_state`: 当前行驶状态
- `current_action`: 当前执行动作
- `front_vehicle_distance`: 前车距离
- `is_emergency`: 是否紧急状态
- `stop_timer`: 停止计时器
- `position_history`: 位置历史（用于死锁检测）

---

### 6. 后端数据增强 (`backend/app.py`)

#### 新增传输字段：
- `vehicle_state`: 车辆状态
- `current_action`: 当前动作
- `front_vehicle_distance`: 前车距离
- `is_emergency`: 紧急状态
- `stop_timer`: 停止时间
- `use_llm`: 是否启用LLM

#### 信号灯数据增强：
- `timer`: 当前相位剩余时间
- `cycle_time`: 周期时间
- `green_duration`: 绿灯时长
- `yellow_duration`: 黄灯时长

---

## 测试结果

```
Perception keys: ['self', 'route', 'front_vehicle', 'rear_vehicle', 
                  'left_lane_vehicle', 'right_lane_vehicle', 
                  'traffic_light', 'intersection_queue', 
                  'surroundings', 'road_conditions', 'is_deadlocked']

Front vehicle: True
Distance: 25.5
Traffic light: {'state': 'RED', 'distance': 100.0, ...}
Surroundings: 1
OK - Test passed
```

---

## 使用建议

### 1. 启用LLM决策
```python
vehicle = env.spawn_vehicle(start, end, VehicleType.CAR)
vehicle.use_llm = True  # 启用智能决策
```

### 2. 配置Mock LLM（测试用）
```python
from city.llm.llm_client import MockLLMClient
from city.llm.agent_llm_interface import set_global_llm_client

mock_llm = MockLLMClient({
    "拥堵": '{"action": "decelerate", "reason": "前方拥堵"}',
    "红灯": '{"action": "stop", "reason": "红灯停车"}',
})
set_global_llm_client(mock_llm)
```

### 3. 配置真实LLM
```python
from city.llm.llm_client import load_siliconflow_config
from city.llm.agent_llm_interface import set_global_llm_client

llm_client = load_siliconflow_config()
set_global_llm_client(llm_client)
```

---

## 效果预期

1. **减少车辆锁死** - 死锁检测+恢复机制，5秒内自动恢复
2. **更智能的跟车** - IDM风格跟车，平滑加减速
3. **更好的信号灯处理** - 提前判断，避免急刹
4. **更丰富的前端展示** - 车辆状态、动作、决策推理链可视化
