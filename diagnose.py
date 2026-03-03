#!/usr/bin/env python3
"""
诊断脚本 - 检查系统状态
"""

import requests
import json
import sys

def check_backend():
    """检查后端服务状态"""
    print("=" * 60)
    print("检查后端服务")
    print("=" * 60)
    
    try:
        # 检查根路径
        response = requests.get('http://localhost:5000/', timeout=5)
        print(f"✓ 后端服务正在运行 (状态码: {response.status_code})")
        return True
    except requests.exceptions.ConnectionError:
        print("✗ 无法连接到后端服务")
        print("  请确保后端已启动: python backend/app.py")
        return False
    except Exception as e:
        print(f"✗ 检查失败: {e}")
        return False

def check_network_api():
    """检查网络数据 API"""
    print("\n检查网络数据 API...")
    try:
        response = requests.get('http://localhost:5000/api/network', timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 网络数据正常")
            print(f"  节点数: {len(data.get('nodes', []))}")
            print(f"  路段数: {len(data.get('edges', []))}")
            return True
        else:
            print(f"✗ API 返回错误: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 请求失败: {e}")
        return False

def check_control_api():
    """检查控制 API"""
    print("\n检查控制 API...")
    try:
        # 尝试启动仿真
        response = requests.post(
            'http://localhost:5000/api/control',
            json={'action': 'start'},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 控制 API 正常")
            print(f"  响应: {data}")
            return True
        else:
            print(f"✗ 控制 API 返回错误: {response.status_code}")
            print(f"  响应: {response.text}")
            return False
    except Exception as e:
        print(f"✗ 请求失败: {e}")
        return False

def check_state_api():
    """检查状态 API"""
    print("\n检查状态 API...")
    try:
        response = requests.get('http://localhost:5000/api/state', timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 状态 API 正常")
            print(f"  仿真时间: {data.get('time', 0):.2f}s")
            print(f"  运行状态: {'运行中' if data.get('is_running') else '已停止'}")
            print(f"  车辆数: {len(data.get('agents', {}).get('vehicles', []))}")
            return True
        else:
            print(f"✗ API 返回错误: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 请求失败: {e}")
        return False

def main():
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "CITY 系统诊断工具" + " " * 26 + "║")
    print("╚" + "=" * 58 + "╝")
    
    results = []
    
    # 检查后端
    results.append(("后端服务", check_backend()))
    
    # 如果后端正常，继续检查 API
    if results[-1][1]:
        results.append(("网络数据 API", check_network_api()))
        results.append(("控制 API", check_control_api()))
        results.append(("状态 API", check_state_api()))
    
    # 总结
    print("\n" + "=" * 60)
    print("诊断结果")
    print("=" * 60)
    
    for name, status in results:
        icon = "✓" if status else "✗"
        print(f"{icon} {name}")
    
    all_ok = all(status for _, status in results)
    
    if all_ok:
        print("\n✓ 所有检查通过！系统运行正常。")
        print("\n如果前端仍有问题，请检查:")
        print("  1. 浏览器控制台是否有错误 (按 F12)")
        print("  2. 是否启用了广告拦截插件")
        print("  3. 尝试刷新页面 (F5)")
    else:
        print("\n✗ 发现一些问题，请根据上面的提示修复。")
        print("\n常见解决方案:")
        print("  1. 确保后端已启动: python backend/app.py")
        print("  2. 检查端口 5000 是否被占用")
        print("  3. 重启后端服务")
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
