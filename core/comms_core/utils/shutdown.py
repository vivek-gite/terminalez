import asyncio

from core.comms_core.utils.rw_lock import ReadWriteLock


class Shutdown:
    def __init__(self):
        self._shutdown: ReadWriteLock[bool] = ReadWriteLock(False)
        self.notify: asyncio.Condition = asyncio.Condition()

    async def shutdown(self) -> None:
        print("Shutting down...")
        await self._shutdown.write(True)
        async with self.notify:
            self.notify.notify_all()

    async def is_terminated(self) -> bool:
        val = await self._shutdown.read()
        return val


    async def wait(self) -> None:
        val = await self._shutdown.read()
        if not val:
            async with self.notify:
                await self.notify.wait()
        print(f"Waiting for shutdown... val: {val}")