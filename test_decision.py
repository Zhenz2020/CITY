#!/usr/bin/env python3
"""
测试决策功能是否正常
"""

import requests
import json

def test_decision():
    # 1. 启动仿真
    print("1. 启动仿真...")
    r = requests.post('http://localhost:5000/api/control', 
                     json={'action': 'start'})
    print(f"   结果: {r.json()}")
    
    # 2. 获取当前车辆列表
    print("\n2. 获取车辆列表...")
    r = requests.get('http://localhost:5000/api/state')
    data = r.json()
    vehicles = data.get('agents', {}).get('vehicles', [])
    print(f"   车辆数: {len(vehicles)}")
    
    if vehicles:
        vehicle_id = vehicles[0]['id']
        print(f"\n3. 测试车辆 {vehicle_id} 的决策...")
        
        # 3. 获取车辆详情
        r = requests.get(f'http://localhost:5000/api/agent/{vehicle_id}')
        print(f"   详情: {r.json()}")
        
        print("\n请在前端界面中:")
        print(f"  1. 点击车辆 {vehicle_id}")
        print(f"  2. 点击'获取决策'按钮")
        print(f"  3. 观察右侧面板显示的决策输出")
    else:
        print("\n没有车辆，生成一辆...")
        r = requests.post('http://localhost:5000/api/control',
                         json={'action': 'spawn_vehicle'})
        print(f"   结果: {r.json()}")

if __name__ == "__main__":
    test_decision()
