import socketio
import time

sio = socketio.Client()

@sio.on('connect')
def on_connect():
    print('Connected to server')
    sio.emit('planning_connect')

@sio.on('planning_connected')
def on_connected(data):
    print('Planning mode connected:', data)

@sio.on('planning_update')
def on_update(data):
    t = data.get('time', 0)
    print(f'Update: time={t:.1f}s')

@sio.on('disconnect')
def on_disconnect():
    print('Disconnected')

print('Connecting to server...')
sio.connect('http://localhost:5000')

print('Waiting for updates (10s)...')
time.sleep(10)

sio.disconnect()
print('Done')
