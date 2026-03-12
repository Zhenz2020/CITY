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
    print(f'Update #{updates}: time={t:.1f}s')

@sio.on('connect')
def on_connect():
    print('Connected')
    sio.emit('planning_connect')

@sio.on('disconnect')
def on_disconnect():
    print('Disconnected')

print('Connecting WebSocket...')
sio.connect('http://localhost:5000')

print('Waiting 20s...')
time.sleep(20)

print(f'Total updates: {updates}')
sio.disconnect()
