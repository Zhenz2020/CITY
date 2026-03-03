#!/usr/bin/env python3
"""
简化的启动脚本 - 更可靠的方式。

这个脚本只启动后端，然后提示用户手动启动前端。
"""

import subprocess
import os
import time
import sys

def main():
    """主函数。"""
    print("=" * 70)
    print("CITY 交通仿真系统 - 简化启动")
    print("=" * 70)
    
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(backend_dir, "frontend", "city-frontend")
    
    # 检查前端是否已安装
    if not os.path.exists(os.path.join(frontend_dir, "node_modules")):
        print("\n错误: 前端依赖未安装!")
        print(f"\n请先安装前端依赖:")
        print(f"  cd frontend/city-frontend")
        print(f"  npm install")
        input("\n按回车键退出...")
        return
    
    # 启动后端（在新窗口）
    print("\n[步骤 1/3] 启动后端服务...")
    print("  正在打开新窗口运行后端...")
    
    if sys.platform == 'win32':
        os.system(f'start cmd /k "cd /d {backend_dir} && python backend/app.py"')
    else:
        subprocess.Popen(
            [sys.executable, 'backend/app.py'],
            cwd=backend_dir
        )
    
    print("  后端启动中，请等待...")
    time.sleep(3)
    
    # 启动前端（在新窗口）
    print("\n[步骤 2/3] 启动前端服务...")
    print("  正在打开新窗口运行前端...")
    
    if sys.platform == 'win32':
        os.system(f'start cmd /k "cd /d {frontend_dir} && npm start"')
    else:
        subprocess.Popen(
            ["npm", "start"],
            cwd=frontend_dir
        )
    
    print("  前端启动中，请等待...")
    time.sleep(2)
    
    # 完成
    print("\n[步骤 3/3] 启动完成!")
    print("\n" + "=" * 70)
    print("服务已启动:")
    print("  - 后端 API: http://localhost:5000")
    print("  - 前端界面: http://localhost:3000")
    print("=" * 70)
    print("\n注意:")
    print("  - 后端和前端分别在独立的命令行窗口中运行")
    print("  - 如果浏览器没有自动打开，请手动访问 http://localhost:3000")
    print("  - 关闭相应的命令行窗口即可停止服务")
    
    input("\n按回车键退出此脚本（服务会继续运行）...")

if __name__ == "__main__":
    main()
