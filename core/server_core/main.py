import asyncio

from dotenv import load_dotenv
load_dotenv()

from core.comms_core.utils.logger import logger, listener

logger.name = __name__

from core.server_core.server_lib import Server

async def start():
    server = Server()
    logger.info(f"In {__name__} starting server")
    await server.listen()

if __name__ == "__main__":
    asyncio.run(start())
    listener.stop()