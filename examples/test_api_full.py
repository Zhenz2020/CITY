"""Test backend API full flow"""
import requests
import time

API_BASE = 'http://localhost:5000'

print('1. Starting planning simulation...')
res = requests.post(f'{API_BASE}/api/planning/control', json={'action': 'start'})
print(f'   Response: {res.json()}')

print('2. Checking state after 1s...')
time.sleep(1)
res = requests.get(f'{API_BASE}/api/planning/state', timeout=5)
print(f'   Status: {res.status_code}')
data = res.json()
print(f'   Time: {data.get("time", 0):.1f}s')
print(f'   Running: {data.get("is_running")}')
print(f'   Vehicles: {len(data.get("agents", {}).get("vehicles", []))}')

print('3. Waiting 10 seconds...')
for i in range(10):
    time.sleep(1)
    try:
        res = requests.get(f'{API_BASE}/api/planning/state', timeout=5)
        data = res.json()
        t = data.get("time", 0)
        vehicles = len(data.get("agents", {}).get("vehicles", []))
        print(f'   {i+1}s: time={t:.1f}s, vehicles={vehicles}')
    except Exception as e:
        print(f'   {i+1}s: Error - {e}')

print('4. Pausing...')
res = requests.post(f'{API_BASE}/api/planning/control', json={'action': 'pause'})
print(f'   Response: {res.json()}')

print('Done!')
