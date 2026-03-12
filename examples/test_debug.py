import requests
import time

API_BASE = 'http://localhost:5000'

print('=== Test Start ===')

# 1. Check current state
print('1. Checking current state...')
try:
    res = requests.get(f'{API_BASE}/api/planning/state', timeout=5)
    data = res.json()
    print(f'   Current time: {data.get("time", 0):.1f}s')
    print(f'   Running: {data.get("is_running")}')
    print(f'   Nodes: {len(data.get("network", {}).get("nodes", []))}')
except Exception as e:
    print(f'   Error: {e}')

# 2. Reset
print('2. Resetting simulation...')
try:
    res = requests.post(f'{API_BASE}/api/planning/control', json={'action': 'reset'})
    print(f'   Response: {res.json()}')
    time.sleep(1)
except Exception as e:
    print(f'   Error: {e}')

# 3. Start
print('3. Starting simulation...')
try:
    res = requests.post(f'{API_BASE}/api/planning/control', json={'action': 'start'})
    print(f'   Response: {res.json()}')
except Exception as e:
    print(f'   Error: {e}')

# 4. Check state for 5 seconds
print('4. Checking running state...')
for i in range(5):
    time.sleep(1)
    try:
        res = requests.get(f'{API_BASE}/api/planning/state', timeout=5)
        data = res.json()
        t = data.get('time', 0)
        running = data.get('is_running', False)
        vehicles = len(data.get('agents', {}).get('vehicles', []))
        print(f'   {i+1}s: time={t:.1f}s, running={running}, vehicles={vehicles}')
    except Exception as e:
        print(f'   {i+1}s: Error - {e}')

print('=== Test Complete ===')
