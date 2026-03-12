import requests
import socketio
import time

API_BASE = 'http://localhost:5000'

# Start simulation
print('Starting...')
requests.post(f'{API_BASE}/api/planning/control', json={'action': 'reset'})
time.sleep(0.5)
requests.post(f'{API_BASE}/api/planning/control', json={'action': 'start'})

# Connect WebSocket
sio = socketio.Client()
updates = 0
last_time = 0

@sio.on('planning_update')
def on_update(data):
    global updates, last_time
    updates += 1
    t = data.get('time', 0)
    last_time = t
    v = len(data.get('agents', {}).get('vehicles', []))
    print(f'#{updates}: time={t:.1f}s, vehicles={v}')

@sio.on('connect')
def on_connect():
    sio.emit('planning_connect')

sio.connect('http://localhost:5000')

print('Running 60s...')
for i in range(60):
    time.sleep(1)
    if i % 10 == 9:
        print(f'  {i+1}s elapsed, last update at {last_time:.1f}s')

print(f'Total updates: {updates}')
sio.disconnect()
