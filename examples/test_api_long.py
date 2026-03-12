"""Test backend API for longer duration"""
import requests
import time

API_BASE = 'http://localhost:5000'

print('Starting and running for 30 seconds...')
res = requests.post(f'{API_BASE}/api/planning/control', json={'action': 'start'})
print(f'Start response: {res.json()}')

time.sleep(2)

for i in range(30):
    time.sleep(1)
    try:
        res = requests.get(f'{API_BASE}/api/planning/state', timeout=5)
        data = res.json()
        t = data.get("time", 0)
        running = data.get("is_running", False)
        vehicles = len(data.get("agents", {}).get("vehicles", []))
        nodes = len(data.get("network", {}).get("nodes", []))
        print(f'{i+1}s: time={t:5.1f}s, running={running}, vehicles={vehicles}, nodes={nodes}')
        
        if not running:
            print('WARNING: Simulation stopped!')
            break
    except Exception as e:
        print(f'{i+1}s: Error - {e}')

res = requests.post(f'{API_BASE}/api/planning/control', json={'action': 'pause'})
print(f'Pause response: {res.json()}')
print('Test complete!')
