# 道路规划Agent功能设计

## 功能概述
创建一个智能规划Agent，能够：
1. 监控全网车辆OD（起点-终点）需求
2. 根据交通流量动态扩展路网（从2x2开始）
3. 使用LLM决策路网扩展策略

## 系统架构

### 1. 后端组件
```
backend/
├── agents/
│   └── planning_agent.py      # 规划Agent核心
├── environment/
│   └── dynamic_network.py     # 动态路网管理
└── routes/
    └── planning_routes.py     # 规划相关API
```

### 2. 前端组件
```
frontend/
└── components/
    └── views/
        └── PlanningView.tsx   # 规划功能页面
```

### 3. 数据流
```
车辆OD需求 → PlanningAgent感知 → LLM决策 → 动态添加路段/节点 → 更新路网
```

## 核心功能模块

### 1. PlanningAgent
- **感知**: 收集所有车辆的OD对
- **决策**: 根据OD密度决定扩展策略
- **执行**: 调用DynamicNetwork添加道路

### 2. 动态路网 (DynamicNetwork)
- 初始: 2x2网格 (4个节点, 4条边)
- 扩展策略:
  - OD对过多 → 添加新节点和连接
  - 某方向拥堵 → 添加平行路段
  - 长距离OD → 添加捷径

### 3. 前端界面
- 路网编辑器视图
- OD需求热力图
- 规划决策日志
- 路网扩展历史

## API设计

### 后端API
```python
# 获取当前OD统计
GET /api/planning/od-stats

# 获取规划Agent状态
GET /api/planning/agent-status

# 手动触发路网扩展
POST /api/planning/expand-network

# 获取路网扩展历史
GET /api/planning/expansion-history

# 重置为初始2x2网格
POST /api/planning/reset-network
```

### WebSocket事件
```javascript
// 实时OD更新
'od_update': { od_pairs: [...], densities: [...] }

// 路网扩展事件
'network_expanded': { new_nodes: [...], new_edges: [...] }

// 规划决策
'planning_decision': { decision: 'expand', reason: '...' }
```

## 实现步骤
1. 创建PlanningAgent类
2. 实现DynamicNetwork管理器
3. 添加后端API路由
4. 创建前端PlanningView
5. 集成LLM决策接口
