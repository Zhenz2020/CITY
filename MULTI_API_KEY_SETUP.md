# 多API Key配置指南 - 全LLM模式

本系统支持使用多个API Key实现高并发LLM决策，适用于所有智能体（车辆、红绿灯）同时调用LLM的场景。

## 配置方法

### 方法1: 配置文件（推荐）

编辑 `config/siliconflow_config.json`：

```json
{
  "provider": "SILICONFLOW",
  "api_key": [
    "sk-your-first-api-key",
    "sk-your-second-api-key",
    "sk-your-third-api-key"
  ],
  "base_url": "https://api.siliconflow.cn/v1",
  "model": "Qwen/Qwen3-14B",
  "temperature": 0.7,
  "max_tokens": 500,
  "timeout": 30.0
}
```

### 方法2: 环境变量

```bash
# Windows PowerShell
$env:SILICONFLOW_API_KEY="sk-your-first-api-key"
$env:SILICONFLOW_API_KEY_1="sk-your-second-api-key"
$env:SILICONFLOW_API_KEY_2="sk-your-third-api-key"
```

### 方法3: 混合配置

配置文件 + 环境变量补充：
- 配置文件中的api_key可以是字符串或数组
- 环境变量会作为补充

## 工作原理

### LLMClientPool（客户端池）

```
┌─────────────────────────────────────────────────────────────┐
│                    LLMClientPool                            │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Client #1  │  │  Client #2  │  │  Client #3  │  ...     │
│  │  API Key 1  │  │  API Key 2  │  │  API Key 3  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
         ↑            ↑            ↑
         └────────────┴────────────┘
              轮询分配算法
```

### 智能体分配策略

1. **一致性哈希**: 同一智能体总是使用相同的API Key
   - 便于追踪和限流
   - 有利于缓存优化

2. **轮询**: 新请求按顺序分配给不同的Client

## 全LLM模式特性

### 车辆智能体
- 所有车辆都启用LLM决策
- 异步并行处理，不阻塞仿真
- 规则决策作为fallback

### 红绿灯智能体
- 检测到车辆时自动使用LLM
- 无车辆时使用固定周期
- 实时流量分析和配时优化

## API Key获取

### SiliconFlow（推荐）
1. 访问 https://siliconflow.cn
2. 注册账号
3. 创建多个API Key（每个账号可创建多个）

### 其他平台
- OpenAI: https://platform.openai.com
- Azure OpenAI: https://azure.microsoft.com

## 性能优化建议

1. **API Key数量**: 建议5-10个Key用于高并发
2. **模型选择**: Qwen3-14B性价比高
3. **超时设置**: 30秒足够应对大多数情况
4. **并发控制**: LLMManager默认5个worker线程

## 监控和调试

启动时会在控制台显示：
```
[LLM] 客户端池就绪: X 个API Key可用
[Vehicle X] 提交LLM决策请求
[Vehicle X] LLM决策(缓存): accelerate
[红绿灯 X] LLM决策: switch_phase (车辆Y辆)
```

前端显示：
- 顶部状态栏显示"🤖 全LLM模式"
- AI Chain View显示决策推理过程
- Analytics View显示统计数据

## 故障排除

### API Key无效
```
[LLM] API Key #1 初始化失败
```
检查Key是否正确，是否已过期。

### 请求超时
```
[LLMManager] vehicle_X 决策失败: timeout
```
增加timeout配置或减少并发请求数。

### 额度不足
```
[LLM] HTTP 429: Too Many Requests
```
添加更多API Key或降低请求频率。
