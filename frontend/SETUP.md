# 前端安装与运行指南

## 系统要求

- Node.js 18+ 
- Python 3.10+
- npm 或 yarn

## 安装步骤

### 1. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
cd ..
```

### 2. 安装前端依赖

```bash
cd frontend/city-frontend
npm install
cd ../..
```

如果 npm install 很慢，可以使用淘宝镜像：
```bash
npm config set registry https://registry.npmmirror.com
npm install
```

### 3. 启动系统

**方式1: 一键启动（推荐）**
```bash
python start_all.py
```

**方式2: 分别启动**

终端1 - 启动后端:
```bash
python backend/app.py
```

终端2 - 启动前端:
```bash
cd frontend/city-frontend
npm start
```

### 4. 访问系统

打开浏览器访问: http://localhost:3000

## 项目结构

```
frontend/city-frontend/
├── public/                 # 静态资源
│   └── index.html
├── src/
│   ├── components/         # React组件
│   │   ├── SimulationCanvas.tsx    # 可视化画布
│   │   ├── AgentDetailPanel.tsx    # 实体详情面板
│   │   ├── ControlPanel.tsx        # 控制面板
│   │   └── DecisionLog.tsx         # 决策日志
│   ├── hooks/              # 自定义Hooks
│   │   └── useSocket.ts    # WebSocket连接
│   ├── types/              # TypeScript类型
│   │   └── index.ts
│   ├── App.tsx             # 主应用组件
│   └── index.tsx           # 入口文件
├── package.json            # 项目依赖
└── tsconfig.json           # TypeScript配置
```

## 功能说明

### 可视化画布
- 实时显示道路网络（节点和路段）
- 车辆移动动画（不同颜色代表不同类型）
- 行人显示（橙色圆点）
- 交通信号灯状态（红黄绿）
- 点击智能体可选中并查看详情

### 控制面板
- 开始/暂停/重置仿真
- 生成车辆（可选择类型）
- 实时统计显示

### 实体详情面板
- 显示选中实体的详细信息
- 位置、速度、状态等
- 显示LLM决策过程和结果
- 刷新决策按钮

### 决策日志
- 滚动显示所有实体的决策历史
- 包含时间戳、感知信息、决策结果

## 技术栈

- **前端框架**: React 18 + TypeScript
- **UI组件库**: Ant Design
- **可视化**: PixiJS (2D渲染)
- **实时通信**: Socket.IO
- **构建工具**: Create React App

## 常见问题

### Q: npm install 失败？
A: 尝试使用淘宝镜像:
```bash
npm config set registry https://registry.npmmirror.com
npm install
```

### Q: 前端无法连接到后端？
A: 确保后端服务已启动 (http://localhost:5000)，并检查package.json中的proxy配置。

### Q: 画布显示空白？
A: 检查浏览器控制台是否有错误信息，确保网络数据已正确加载。
