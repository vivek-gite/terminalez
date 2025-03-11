import asyncio

class ReadWriteLock[T]:

    def __init__(self, initial_value=None):
        self._read_ready: asyncio.Condition = asyncio.Condition()
        self._readers: int = 0
        self._writers_waiting: int = 0
        self._writer_active: bool = False
        self._value: T = initial_value  # Shared resource

    async def acquire_read(self):
        async with self._read_ready:
            while self._writer_active or self._writers_waiting > 0:
                await self._read_ready.wait()
            self._readers += 1

    async def release_read(self):
        async with self._read_ready:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()

    async def acquire_write(self):
        async with self._read_ready:
            self._writers_waiting += 1
            while self._writer_active or self._readers > 0:
                await self._read_ready.wait()
            self._writers_waiting -= 1
            self._writer_active = True

    async def release_write(self):
        async with self._read_ready:
            self._writer_active = False
            self._read_ready.notify_all()

    async def write(self, new_value: T):
        """Safely write a new value."""
        await self.acquire_write()
        try:
            self._value = new_value
        finally:
            await self.release_write()

    async def read(self) -> T:
        """ Gives the reference of the value which can be mutated."""
        await self.acquire_read()
        try:
            value: T = self._value
        finally:
            await self.release_read()
        return value
