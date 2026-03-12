import requests
import time

API_BASE = 'http://localhost:5000'

print('Starting...')
res = requests.post(f'{API_BASE}/api/planning/control', json={'action': 'start'})
print('Response:', res.json())

for i in range(30):
    time.sleep(1)
    try:
        res = requests.get(f'{API_BASE}/api/planning/state', timeout=5)
        data = res.json()
        t = data.get('time', 0)
        running = data.get('is_running', False)
        print(f'{i+1}s: time={t:.1f}s, running={running}')
    except Exception as e:
        print(f'{i+1}s: Error - {type(e).__name__}')

print('Pausing...')
res = requests.post(f'{API_BASE}/api/planning/control', json={'action': 'pause'})
print('Response:', res.json())
