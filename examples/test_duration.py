import requests
import time

API_BASE = 'http://localhost:5000'

# First, restart simulation
print('Restarting simulation...')
requests.post(f'{API_BASE}/api/planning/control', json={'action': 'reset'})
time.sleep(0.5)
requests.post(f'{API_BASE}/api/planning/control', json={'action': 'start'})
print('Started')

# Monitor for 45 seconds
print('Monitoring for 45 seconds...')
for i in range(45):
    time.sleep(1)
    try:
        res = requests.get(f'{API_BASE}/api/planning/state', timeout=5)
        data = res.json()
        t = data.get('time', 0)
        running = data.get('is_running', False)
        vehicles = len(data.get('agents', {}).get('vehicles', []))
        print(f'{i+1}s: time={t:.1f}s, running={running}, vehicles={vehicles}')
    except Exception as e:
        print(f'{i+1}s: ERROR - {type(e).__name__}')

print('Test complete')
