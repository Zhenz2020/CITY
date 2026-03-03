# 🚀 快速启动步骤（按顺序执行）

## 步骤 1：停止所有服务

如果之前启动了后端或前端，先停止它们：
- 后端终端：按 `Ctrl+C`
- 前端终端：按 `Ctrl+C`

## 步骤 2：启动后端（终端 1）

```bash
python backend/app.py
```

你会看到：
```
仿真环境已初始化
 * Running on http://localhost:5000
```

**保持这个终端运行，不要关闭！**

## 步骤 3：启动前端（终端 2）

打开**新的终端窗口**，执行：

```bash
cd frontend/city-frontend
npm start
```

等待看到：
```
Compiled successfully!

You can now view city-frontend in the browser.

  Local: http://localhost:3000
```

**保持这个终端运行，不要关闭！**

## 步骤 4：打开浏览器

浏览器会自动打开，或手动访问：
```
http://localhost:3000
```

## 步骤 5：查看决策

### 方式 A：自动查看（推荐）
1. 点击【开始】按钮
2. 看右下角的"决策日志"面板
3. 应该会自动显示决策记录

### 方式 B：手动查看
1. 点击画布上的任意车辆
2. 看右侧中间的"AI 决策输出"面板
3. 显示决策结果

---

## ❓ 如果看不到决策

### 检查 1：看后端终端
应该有输出：
```
[决策] vehicle_1: {'action': 'accelerate', 'reason': '...'}
```

### 检查 2：按 F12 看浏览器控制台
应该有输出：
```
[Socket] 收到决策: {...}
```

### 检查 3：运行测试脚本
```bash
python test_decision_api.py
```

---

## 🛑 停止系统

关闭两个终端窗口，或按 `Ctrl+C`。
