#!/usr/bin/env python3
"""
一键启动前端开发服务器。

自动安装依赖并启动 React 开发服务器。
"""

import subprocess
import sys
import os

def run_command(command, cwd=None):
    """运行命令并实时输出。"""
    print(f"\n>>> 执行: {command}")
    process = subprocess.Popen(
        command,
        shell=True,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8'
    )
    
    for line in process.stdout:
        print(line, end='')
    
    process.wait()
    return process.returncode

def main():
    """主函数。"""
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend", "city-frontend")
    
    if not os.path.exists(frontend_dir):
        print(f"错误: 找不到前端目录 {frontend_dir}")
        sys.exit(1)
    
    print("=" * 70)
    print("CITY 前端启动脚本")
    print("=" * 70)
    
    # 检查 node_modules
    node_modules = os.path.join(frontend_dir, "node_modules")
    if not os.path.exists(node_modules):
        print("\n首次运行，正在安装依赖...")
        print("这可能需要几分钟时间...")
        
        # 安装依赖
        if run_command("npm install", cwd=frontend_dir) != 0:
            print("错误: 依赖安装失败")
            sys.exit(1)
    
    print("\n启动前端开发服务器...")
    print("启动后请访问: http://localhost:3000")
    print("按 Ctrl+C 停止服务器")
    print("=" * 70)
    
    # 启动开发服务器
    try:
        run_command("npm start", cwd=frontend_dir)
    except KeyboardInterrupt:
        print("\n\n已停止服务器")

if __name__ == "__main__":
    main()
