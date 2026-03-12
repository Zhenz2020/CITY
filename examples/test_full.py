import requests
import socketio
import time

API_BASE = 'http://localhost:5000'

# Start simulation first
print('Starting simulation...')
requests.post(f'{API_BASE}/api/planning/control', json={'action': 'reset'})
time.sleep(0.5)
requests.post(f'{API_BASE}/api/planning/control', json={'action': 'start'})
print('Started')

# Connect WebSocket
sio = socketio.Client()
updates = 0

@sio.on('planning_update')
def on_update(data):
    global updates
    updates += 1
    t = data.get('time', 0)
    v = len(data.get('agents', {}).get('vehicles', []))
    print(f'Update #{updates}: time={t:.1f}s, vehicles={v}')

@sio.on('connect')
def on_connect():
    print('WebSocket connected')
    sio.emit('planning_connect')

print('Connecting WebSocket...')
sio.connect('http://localhost:5000')

print('Waiting 15s...')
time.sleep(15)

print(f'Total updates: {updates}')
sio.disconnect()
print('Done')
