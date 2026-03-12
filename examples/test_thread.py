"""Test if simulation thread is running"""
import requests
import time

API_BASE = 'http://localhost:5000'

# Start simulation
print('Starting...')
res = requests.post(f'{API_BASE}/api/planning/control', json={'action': 'start'})
print('Start response:', res.json())

# Check state multiple times
print('Checking state...')
for i in range(20):
    time.sleep(1)
    res = requests.get(f'{API_BASE}/api/planning/state', timeout=5)
    data = res.json()
    t = data.get('time', 0)
    running = data.get('is_running', False)
    vehicles = len(data.get('agents', {}).get('vehicles', []))
    print(f'{i+1}s: time={t:5.1f}s, running={running}, vehicles={vehicles}')

print('Done!')
