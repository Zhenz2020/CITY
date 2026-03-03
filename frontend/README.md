# CITY 交通仿真可视化前端

## 技术栈

- **后端**: Python Flask + WebSocket
- **前端**: Node.js + React + TypeScript
- **可视化**: HTML5 Canvas + Pixi.js（2D渲染）
- **通信**: Socket.IO（实时双向通信）
- **UI组件**: Ant Design

## 快速开始

### 1. 安装依赖

```bash
# 后端依赖
pip install flask flask-socketio flask-cors

# 前端依赖
cd frontend
cd city-frontend
npm install
```

### 2. 启动服务

```bash
# 启动后端API
python backend/app.py

# 启动前端（新终端）
cd frontend/city-frontend
npm start
```

### 3. 访问

打开浏览器访问: http://localhost:3000
