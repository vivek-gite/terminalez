import asyncio

from core.comms_core.utils.rw_lock import ReadWriteLock


class Notify:
    def __init__(self):
        self.__permit = ReadWriteLock(False)
        self._condition = asyncio.Condition()

    async def notify_n(self, n):
        async with self._condition:
            await self.__permit.write(True)
            self._condition.notify(n)

    async def wait(self):
        async with self._condition:
            while not self.__permit.read():
                await self._condition.wait()
            await self.__permit.write(False)

    async def notify_all(self):
        async with self._condition:
            await self.__permit.write(True)
            self._condition.notify_all()