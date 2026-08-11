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
    """Get the local IP address."""
    sock = None
    try:
        # This does not send network traffic; it asks the OS which local interface
        # would be used for an outbound connection.
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError as e:
        logger.warning(f"Failed to determine local IP address: {e}")
        return "127.0.0.1"
    finally:
        if sock is not None:
            sock.close()

async def big_start():
    user_name = get_username_by_whoami() or get_username_by_env()
    ip = get_local_ip_address()

    name = f"{user_name}@{ip}"
    logger.info(f"Initializing connection with name: {name}")

    grpc_address = os.getenv("TERMLY_GRPC_ADDRESS", "127.0.0.1:50051")
    web_url = os.getenv("TERMLY_WEB_URL", "http://127.0.0.1:5173").rstrip("/")
    client = GrpcClient(grpc_address)

    # Set up the exit handler
    exit_handler = GracefulExitHandler(client)

    # Monitor the exit event for all platforms (Windows and Unix)
    asyncio.create_task(monitor_exit_event(exit_handler.exit_event))

    try:
        await client.connect()
        session_id, url = await client.initiate_connection(name)
        print(
            f"✅ Connected successfully!\n\n"
            f"Please access the terminal from this URL:\n{web_url}{url}")
        await client.run()

    except Exception as e:
        logger.exception(f"Connection failed: {e}")


if __name__ == "__main__":
    asyncio.run(big_start())