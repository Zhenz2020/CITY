import requests
import time

API_BASE = 'http://localhost:5000'

# Check current state
try:
    res = requests.get(f'{API_BASE}/api/planning/state', timeout=5)
    data = res.json()
    print(f'Time: {data.get("time", 0):.1f}s')
    print(f'Running: {data.get("is_running")}')
    print(f'Vehicles: {len(data.get("agents", {}).get("vehicles", []))}')
    print(f'Nodes: {len(data.get("network", {}).get("nodes", []))}')
except Exception as e:
    print(f'Error: {e}')
