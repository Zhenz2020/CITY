#!/usr/bin/env python3
"""
环境检查脚本。

检查运行 CITY 系统所需的所有依赖。
"""

import subprocess
import sys
import os


def check_command(command, name):
    """检查命令是否可用。"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        if result.returncode == 0:
            version = result.stdout.strip().split('\n')[0]
            print(f"  [OK] {name}: {version}")
            return True
        else:
            print(f"  [FAIL] {name}: 命令执行失败")
            return False
    except FileNotFoundError:
        print(f"  [MISSING] {name}: 未安装或未添加到 PATH")
        return False
    except Exception as e:
        print(f"  [ERROR] {name}: {e}")
        return False


def check_python_packages():
    """检查 Python 包。"""
    packages = ['flask', 'flask_socketio', 'flask_cors']
    print("\nPython 包检查:")
    
    for package in packages:
        try:
            __import__(package)
            print(f"  [OK] {package}")
        except ImportError:
            print(f"  [MISSING] {package}: 未安装")


def check_directories():
    """检查项目目录结构。"""
    print("\n目录结构检查:")
    
    dirs = [
        ('backend', 'backend'),
        ('frontend', 'frontend'),
        ('frontend/city-frontend', '前端代码'),
        ('config', '配置文件'),
    ]
    
    for dir_path, name in dirs:
        if os.path.exists(dir_path):
            print(f"  [OK] {name}: {dir_path}")
        else:
            print(f"  [MISSING] {name}: {dir_path} 不存在")


def check_npm_modules():
    """检查 npm 模块。"""
    print("\nnpm 模块检查:")
    
    node_modules = "frontend/city-frontend/node_modules"
    if os.path.exists(node_modules):
        print(f"  [OK] node_modules 已安装")
    else:
        print(f"  [MISSING] node_modules: 未安装")
        print(f"       请运行: cd frontend/city-frontend && npm install")


def main():
    """主函数。"""
    print("=" * 70)
    print("CITY 交通仿真系统 - 环境检查")
    print("=" * 70)
    
    # 检查 Python
    print("\nPython 检查:")
    print(f"  Python 版本: {sys.version.split()[0]}")
    print(f"  Python 路径: {sys.executable}")
    
    # 检查 Node.js 和 npm
    print("\nNode.js 检查:")
    has_node = check_command("node --version", "Node.js")
    has_npm = check_command("npm --version", "npm")
    
    # 检查 Python 包
    check_python_packages()
    
    # 检查目录
    check_directories()
    
    # 检查 npm 模块
    if has_npm:
        check_npm_modules()
    
    # 总结
    print("\n" + "=" * 70)
    print("检查完成")
    print("=" * 70)
    
    if not has_node or not has_npm:
        print("\n[错误] 未检测到 Node.js 或 npm")
        print("\n请安装 Node.js:")
        print("  1. 访问 https://nodejs.org/")
        print("  2. 下载并安装 LTS 版本")
        print("  3. 重启终端并再次运行此检查")
        print("\n或者使用分别启动的方式（仅启动后端）:")
        print("  python backend/app.py")
        return 1
    
    print("\n[OK] 环境检查通过！")
    print("\n你可以使用以下命令启动系统:")
    print("  一键启动: python start_all.py")
    print("  分别启动: python backend/app.py")
    print("           cd frontend/city-frontend && npm start")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
