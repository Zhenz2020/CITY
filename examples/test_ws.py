import socketio
import time

sio = socketio.Client()
updates = 0

@sio.on('planning_update')
def on_update(data):
    global updates
    updates += 1
    t = data.get('time', 0)
    vehicles = len(data.get('agents', {}).get('vehicles', []))
    print(f'Update #{updates}: time={t:.1f}s, vehicles={vehicles}')

@sio.on('connect')
def on_connect():
    print('Connected')
    sio.emit('planning_connect')

print('Connecting...')
sio.connect('http://localhost:5000')

print('Waiting 20s...')
time.sleep(20)

print(f'Total updates: {updates}')
sio.disconnect()
