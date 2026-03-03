#!/usr/bin/env python3
"""
测试决策 API 是否正常工作
"""

import requests
import json
import time

def test_full_flow():
    """测试完整流程"""
    print("=" * 70)
    print("决策功能测试")
    print("=" * 70)
    
    # 1. 重置仿真
    print("\n1. 重置仿真...")
    r = requests.post('http://localhost:5000/api/control', 
                     json={'action': 'reset'})
    print(f"   结果: {r.json()}")
    time.sleep(1)
    
    # 2. 启动仿真
    print("\n2. 启动仿真...")
    r = requests.post('http://localhost:5000/api/control', 
                     json={'action': 'start'})
    print(f"   结果: {r.json()}")
    time.sleep(2)
    
    # 3. 获取车辆列表
    print("\n3. 获取车辆列表...")
    r = requests.get('http://localhost:5000/api/state')
    data = r.json()
    vehicles = data.get('agents', {}).get('vehicles', [])
    print(f"   车辆数: {len(vehicles)}")
    
    if not vehicles:
        print("\n   没有车辆，生成一辆...")
        r = requests.post('http://localhost:5000/api/control',
                         json={'action': 'spawn_vehicle'})
        print(f"   结果: {r.json()}")
        time.sleep(1)
        
        # 重新获取
        r = requests.get('http://localhost:5000/api/state')
        data = r.json()
        vehicles = data.get('agents', {}).get('vehicles', [])
    
    if vehicles:
        vehicle_id = vehicles[0]['id']
        print(f"\n4. 测试车辆 {vehicle_id} 的决策 API...")
        
        # 4. 测试 REST API 获取决策
        print("\n   调用 /api/agent/{id}/decision...")
        r = requests.post(f'http://localhost:5000/api/agent/{vehicle_id}/decision')
        print(f"   状态码: {r.status_code}")
        
        if r.status_code == 200:
            decision_data = r.json()
            print(f"\n   ✓ 决策获取成功!")
            print(f"\n   决策数据:")
            print(json.dumps(decision_data, indent=2, ensure_ascii=False))
        else:
            print(f"\n   ✗ 失败: {r.text}")
    else:
        print("\n   ✗ 没有车辆可供测试")
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)
    print("\n现在请刷新浏览器页面，点击车辆，然后点击'获取决策'按钮")

if __name__ == "__main__":
    test_full_flow()
