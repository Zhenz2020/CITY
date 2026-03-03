# CITY 交通仿真系统 - 快速参考

## 项目结构

```
CITY/
├── city/                   # Python 仿真核心
│   ├── agents/            # 智能体（车辆、行人、管理者）
│   ├── environment/       # 道路网络
│   ├── simulation/        # 仿真引擎
│   ├── llm/              # 大语言模型接口
│   └── visualization/    # Matplotlib可视化
├── backend/               # Web API 后端
│   ├── app.py            # Flask + SocketIO 服务
│   └── requirements.txt
├── frontend/              # React 前端
│   └── city-frontend/    # Node.js + React + PixiJS
├── config/               # 配置文件
├── examples/             # 示例脚本
└── tests/                # 测试
```

## 三种使用方式

### 方式1: Python 脚本（快速测试）

```bash
# 运行简单仿真
$env:PYTHONPATH="d:\项目\CITY"; python examples/simple_intersection.py

# 运行可视化仿真
$env:PYTHONPATH="d:\项目\CITY"; python examples/visual_simple.py
```

### 方式2: 配置 LLM（智能决策）

```bash
# 1. 编辑配置文件
# config/siliconflow_config.json
{
  "api_key": "sk-your-key",
  "model": "Qwen/Qwen3-14B"
}

# 2. 运行 LLM 演示
$env:PYTHONPATH="d:\项目\CITY"; python examples/use_config.py
```

### 方式3: Web 界面（推荐，可交互）

```bash
# 一键启动前后端
python start_all.py

# 然后访问 http://localhost:3000
```

## 核心命令

| 命令 | 说明 |
|------|------|
| `python start_all.py` | 一键启动完整系统 |
| `python backend/app.py` | 只启动后端 API |
| `npm start` (frontend目录) | 只启动前端 |
| `pip install -r backend/requirements.txt` | 安装后端依赖 |
| `npm install` (frontend目录) | 安装前端依赖 |

## 端口

| 服务 | 端口 | 访问地址 |
|------|------|----------|
| 前端 | 3000 | http://localhost:3000 |
| 后端 API | 5000 | http://localhost:5000 |

## 配置 LLM（三种方式）

### 方式1: 配置文件（推荐）
编辑 `config/siliconflow_config.json`

### 方式2: 环境变量
```powershell
$env:SILICONFLOW_API_KEY="sk-xxxx"
$env:SILICONFLOW_MODEL="Qwen/Qwen3-14B"
```

### 方式3: 代码中
```python
from city.llm.llm_client import LLMClient, LLMConfig, LLMProvider

config = LLMConfig(
    provider=LLMProvider.SILICONFLOW,
    api_key="sk-xxxx",
    model="Qwen/Qwen3-14B"
)
client = LLMClient(config)
```

## 前端功能

- 🎮 **实时可视化** - PixiJS 渲染车辆和道路
- 🖱️ **交互操作** - 点击车辆查看详情
- 🧠 **决策展示** - 显示 LLM 决策过程
- 📊 **统计面板** - 实时仿真数据
- 📝 **决策日志** - 历史决策记录

## 技术栈

| 层级 | 技术 |
|------|------|
| 仿真引擎 | Python 3.10+ |
| 后端 API | Flask + SocketIO |
| 前端框架 | React 18 + TypeScript |
| UI 组件 | Ant Design |
| 可视化 | PixiJS |
| 通信 | Socket.IO |
| 大模型 | OpenAI API / SiliconFlow |
