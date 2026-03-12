"""详细测试启动过程"""
import requests
import time

API_BASE = 'http://localhost:5000'

print("=" * 60)
print("详细测试后端日志")
print("=" * 60)

# 1. 重置
print("\n[1] 发送 RESET...")
res = requests.post(f'{API_BASE}/api/planning/control', json={'action': 'reset'})
print(f"    响应: {res.json()}")
time.sleep(1)

# 2. 开始
print("\n[2] 发送 START...")
res = requests.post(f'{API_BASE}/api/planning/control', json={'action': 'start'})
print(f"    响应: {res.json()}")
print("    注意：此时后端终端应该打印 [Planning Control] 日志！")

# 3. 监控5秒
print("\n[3] 监控仿真运行...")
for i in range(5):
    time.sleep(1)
    res = requests.get(f'{API_BASE}/api/planning/state', timeout=3)
    data = res.json()
    t = data.get('time', 0)
    running = data.get('is_running', False)
    print(f"    {i+1}s: time={t:.1f}s, running={running}")
    print(f"        注意：此时后端终端应该打印 [仿真步] 或 [状态] 日志！")

print("\n" + "=" * 60)
print("测试完成，请检查后端终端是否有上述日志输出")
print("=" * 60)
