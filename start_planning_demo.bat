@echo off
chcp 65001 >nul
cd /d "d:\项目\CITY"

REM 检查依赖
echo 检查依赖...
python -c "import flask, flask_socketio" 2>nul
if errorlevel 1 (
    echo 安装依赖...
    pip install flask flask-cors flask-socketio -q
)

REM 启动后端
echo 启动城市规划仿真服务...
echo 访问 http://localhost:5001
echo.
python -m backend.app
