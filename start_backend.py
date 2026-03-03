#!/usr/bin/env python3
"""Start backend server in background."""
import subprocess
import sys
import os

# Change to project directory
os.chdir(r'd:\项目\CITY')

# Start backend
process = subprocess.Popen(
    [sys.executable, 'backend/app.py'],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NEW_CONSOLE
)

print(f"Backend started with PID: {process.pid}")
