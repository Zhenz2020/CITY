"""测试并显示详细日志"""
import requests
import time
import sys

API_BASE = 'http://localhost:5000'

def log(msg):
    print(f"[TEST] {msg}", flush=True)

def main():
    log("=== 开始测试 ===")
    
    # 1. 重置
    log("1. 发送 RESET 请求...")
    try:
        res = requests.post(f'{API_BASE}/api/planning/control', json={'action': 'reset'}, timeout=5)
        log(f"   状态: {res.status_code}")
        log(f"   响应: {res.json()}")
    except Exception as e:
        log(f"   错误: {e}")
        return
    
    time.sleep(1)
    
    # 2. 检查状态
    log("2. 检查初始状态...")
    try:
        res = requests.get(f'{API_BASE}/api/planning/state', timeout=5)
        data = res.json()
        log(f"   时间: {data.get('time')}s")
        log(f"   运行中: {data.get('is_running')}")
    except Exception as e:
        log(f"   错误: {e}")
    
    # 3. 开始仿真
    log("3. 发送 START 请求...")
    try:
        res = requests.post(f'{API_BASE}/api/planning/control', json={'action': 'start'}, timeout=5)
        log(f"   状态: {res.status_code}")
        log(f"   响应: {res.json()}")
    except Exception as e:
        log(f"   错误: {e}")
        return
    
    # 4. 监控10秒
    log("4. 监控仿真运行10秒...")
    for i in range(10):
        time.sleep(1)
        try:
            res = requests.get(f'{API_BASE}/api/planning/state', timeout=3)
            data = res.json()
            t = data.get('time', 0)
            running = data.get('is_running', False)
            vehicles = len(data.get('agents', {}).get('vehicles', []))
            log(f"   {i+1}s: 仿真时间={t:.1f}s, 运行中={running}, 车辆={vehicles}")
        except Exception as e:
            log(f"   {i+1}s: 请求失败 - {type(e).__name__}")
    
    # 5. 暂停
    log("5. 发送 PAUSE 请求...")
    try:
        res = requests.post(f'{API_BASE}/api/planning/control', json={'action': 'pause'}, timeout=5)
        log(f"   状态: {res.status_code}")
    except Exception as e:
        log(f"   错误: {e}")
    
    log("=== 测试完成 ===")

if __name__ == '__main__':
    main()
