#!/usr/bin/env python3
"""
一键启动完整系统（后端 + 前端）。

使用说明:
    python start_all.py
"""

import subprocess
import sys
import os
import time
import signal

def start_backend():
    """启动后端服务。"""
    print("启动后端服务...")
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 使用 subprocess.Popen 启动后端
    if sys.platform == 'win32':
        # Windows: 使用 CREATE_NEW_CONSOLE 创建新窗口
        return subprocess.Popen(
            [sys.executable, 'backend/app.py'],
            cwd=backend_dir,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
    else:
        return subprocess.Popen(
            [sys.executable, 'backend/app.py'],
            cwd=backend_dir
        )

def start_frontend():
    """启动前端服务。"""
    print("启动前端服务...")
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "city-frontend")
    
    if not os.path.exists(frontend_dir):
        print(f"错误: 找不到前端目录 {frontend_dir}")
        return None
    
    # 检查 node_modules
    node_modules = os.path.join(frontend_dir, "node_modules")
    if not os.path.exists(node_modules):
        print("警告: 未找到 node_modules，请先运行 npm install")
        print(f"  cd frontend/city-frontend")
        print(f"  npm install")
        return None
    
    # 启动前端
    if sys.platform == 'win32':
        # Windows: 使用 shell=True 来确保能找到 npm
        return subprocess.Popen(
            "npm start",
            cwd=frontend_dir,
            shell=True,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
    else:
        return subprocess.Popen(
            ["npm", "start"],
            cwd=frontend_dir
        )

def main():
    """主函数。"""
    print("=" * 70)
    print("CITY 交通仿真系统 - 一键启动")
    print("=" * 70)
    
    backend_proc = None
    frontend_proc = None
    
    try:
        # 启动后端
        backend_proc = start_backend()
        if backend_proc:
            print(f"后端进程 PID: {backend_proc.pid}")
        print("等待后端启动...")
        time.sleep(3)
        
        # 启动前端
        frontend_proc = start_frontend()
        if frontend_proc:
            print(f"前端进程 PID: {frontend_proc.pid}")
        
        print("\n" + "=" * 70)
        print("系统启动完成!")
        print("- 后端 API: http://localhost:5000")
        print("- 前端界面: http://localhost:3000")
        print("=" * 70)
        print("\n提示:")
        print("  - 浏览器会自动打开 http://localhost:3000")
        print("  - 如果没有自动打开，请手动访问")
        print("  - 后端和前端分别在独立的窗口中运行")
        print("  - 按 Ctrl+C 可以停止这个脚本，但不会关闭后端和前端")
        print("  - 要完全停止系统，请关闭后端和前端的窗口")
        print("\n按 Ctrl+C 退出此脚本...")
        
        # 保持脚本运行
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n正在停止...")
        print("注意: 后端和前端仍在运行，请手动关闭它们的窗口")
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        
    print("\n脚本已退出")

if __name__ == "__main__":
    main()
