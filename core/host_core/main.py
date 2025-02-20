import os
import subprocess
import socket

def get_username_by_whoami():
    result = subprocess.run(['whoami'], capture_output=True, text=True)
    return result.stdout.strip()

def get_username_by_env():
    return os.getlogin()

def get_local_ip_address():
    hostname = socket.gethostname()
    return socket.gethostbyname(hostname)

