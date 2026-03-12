import socketio
import time

sio = socketio.Client(reconnection=True, reconnection_attempts=5)
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
    print('Disconnected!')

@sio.on('connect_error')
def on_error(e):
    print(f'Connection error: {e}')

print('Connecting...')
try:
    sio.connect('http://localhost:5000')
    print('Waiting 30s...')
    time.sleep(30)
    print(f'Total updates: {updates}')
    sio.disconnect()
except Exception as e:
    print(f'Error: {e}')
