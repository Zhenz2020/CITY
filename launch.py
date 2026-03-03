#!/usr/bin/env python3
"""整合启动脚本 - 同时启动前后端。"""

import subprocess
import sys
import os
import time
import webbrowser

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(base_dir, "backend")
    frontend_dir = os.path.join(base_dir, "frontend", "city-frontend")
    
    print("=" * 60)
    print("CITY 交通仿真系统启动")
    print("=" * 60)
    
    # 启动后端
    print("\n[1/3] 启动后端服务...")
    backend_proc = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=backend_dir,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    time.sleep(4)
    
    # 启动前端
    print("[2/3] 启动前端服务...")
    frontend_proc = subprocess.Popen(
        ["npm", "start"],
        cwd=frontend_dir,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    time.sleep(5)
    
    # 打开浏览器
    print("[3/3] 打开浏览器...")
    webbrowser.open("http://localhost:3000")
    
    print("\n" + "=" * 60)
    print("服务已启动:")
    print("  - 后端: http://localhost:5000")
    print("  - 前端: http://localhost:3000")
    print("=" * 60)
    print("\n关闭命令行窗口即可停止服务")
    
    try:
        while True:
            time.sleep(1)
            # 检查进程是否还在运行
            if backend_proc.poll() is not None:
                print("\n后端服务已停止")
                break
    except KeyboardInterrupt:
        print("\n正在停止服务...")
        backend_proc.terminate()
        frontend_proc.terminate()

if __name__ == "__main__":
    main()
