import asyncio
import logging

from core.comms_core.utils.shutdown import Shutdown

from core.server_core.state_manager.server_state import ServerState

logger = logging.getLogger(__name__)

class Server:
    def __init__(self):
        from core.server_core.listen import init_server_state

        self.state = ServerState()
        self.shutdown = Shutdown()
        init_server_state(self.state)

    async def _run_background_task(self):
        await asyncio.gather(
            self.state.process_transfer(),
            self.state.close_expired_sessions()
        )

    async def start_background_workers(self):
        await asyncio.wait([
            asyncio.create_task(self._run_background_task()),
            asyncio.create_task(self.shutdown.wait())],
            return_when=asyncio.FIRST_COMPLETED
        )

    async def listen(self):
        from core.server_core.listen import start_servers

        try:
            asyncio.create_task(self.start_background_workers())
            await start_servers()
        except Exception as e:
            logger.exception(f"Servers shutting down due to {e}")
            await self.graceful_shutdown()

    async def graceful_shutdown(self):
        # Stop receiving new connections
        await self.shutdown.shutdown()
        # Terminate each of the existing connections
        await self.state.shutdown_all_sessions()


