import asyncio
import os
import subprocess
import socket
import sys

from core.host_core.Controller import GrpcClient
from core.host_core.graceful_shutdown_handler import GracefulExitHandler, monitor_exit_event

from core.comms_core.utils.logger import logger

logger.name = __name__

def get_username_by_whoami():
    result = subprocess.run(['whoami'], capture_output=True, text=True)
    return result.stdout.strip()

def get_username_by_env():
    return os.getlogin()

def get_local_ip_address():
    hostname = socket.gethostname()
    return socket.gethostbyname(hostname)

async def big_start():
    user_name = get_username_by_whoami() or get_username_by_env()
    ip = get_local_ip_address()

    name = f"{user_name}@{ip}"
    logger.info(f"Initializing connection with name: {name}")

    client = GrpcClient("localhost:50051")

    # Set up the exit handler
    exit_handler = GracefulExitHandler(client)

    # For Windows, we need to monitor the exit event
    if sys.platform == 'win32':
        asyncio.create_task(monitor_exit_event(exit_handler.exit_event))

    try:
        await client.connect()
        session_id, url = await client.initiate_connection(name)
        logger.info(f"Connected successfully - Session ID: {session_id}, URL: {url}")
        await client.run()

    except Exception as e:
        logger.exception(f"Connection failed: {e}")


if __name__ == "__main__":
    asyncio.run(big_start())