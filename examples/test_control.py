import requests
import time

API_BASE = 'http://localhost:5000'

print('=== Testing Control API ===')

# Reset
print('1. Reset...')
res = requests.post(f'{API_BASE}/api/planning/control', json={'action': 'reset'})
print(f'   Status: {res.status_code}')
print(f'   Response: {res.json()}')
time.sleep(1)

# Check state
print('2. Check state...')
res = requests.get(f'{API_BASE}/api/planning/state', timeout=3)
data = res.json()
t = data.get('time', 0)
print(f'   Time: {t}s')
print(f'   Running: {data.get("is_running")}')

# Start
print('3. Start...')
res = requests.post(f'{API_BASE}/api/planning/control', json={'action': 'start'})
print(f'   Status: {res.status_code}')
print(f'   Response: {res.json()}')
time.sleep(1)

# Check state again
print('4. Check state after start...')
res = requests.get(f'{API_BASE}/api/planning/state', timeout=3)
data = res.json()
t = data.get('time', 0)
print(f'   Time: {t}s')
print(f'   Running: {data.get("is_running")}')

print('=== Done ===')
