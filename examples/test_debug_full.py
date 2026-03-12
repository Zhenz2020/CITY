import requests
import time

API_BASE = 'http://localhost:5000'

print('=== Debug Test ===')

# Restart
requests.post(f'{API_BASE}/api/planning/control', json={'action': 'reset'})
time.sleep(0.5)
requests.post(f'{API_BASE}/api/planning/control', json={'action': 'start'})

print('Monitoring API and stats...')
for i in range(30):
    time.sleep(1)
    try:
        res = requests.get(f'{API_BASE}/api/planning/state', timeout=5)
        data = res.json()
        t = data.get('time', 0)
        running = data.get('is_running', False)
        stats = data.get('statistics', {})
        vehicles = stats.get('active_vehicles', 0)
        
        # Get planning agent info
        pa = data.get('planning_agent', {})
        city_stats = pa.get('city_stats', {})
        density = city_stats.get('density', 0)
        capacity = city_stats.get('max_capacity', 0)
        
        print(f'{i+1}s: time={t:.1f}s, vehicles={vehicles}, density={density:.2f}, capacity={capacity}, running={running}')
    except Exception as e:
        print(f'{i+1}s: Error - {type(e).__name__}')

print('=== Done ===')
