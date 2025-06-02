import asyncio
import logging

logger = logging.getLogger(__name__)

class ReadWriteLock[T]:

    def __init__(self, initial_value=None):
        self._read_ready: asyncio.Condition = asyncio.Condition()
        self._readers: int = 0
        self._writers_waiting: int = 0
        self._writer_active: bool = False
        self._value: T = initial_value  # Shared resource
        # Add timeout to prevent indefinite waiting
        self._acquire_timeout: float = 30.0  # 30 seconds timeout

    async def acquire_read(self):
        async with self._read_ready:
            # Only wait if a writer is ACTIVELY writing, not just waiting
            # This prevents the deadlock scenario
            try:
                start_time = asyncio.get_event_loop().time()
                while self._writer_active:  # Don't wait for waiting writers
                    # Check timeout
                    if asyncio.get_event_loop().time() - start_time > self._acquire_timeout:
                        logger.warning("Timeout while waiting to acquire read lock, proceeding anyway to prevent deadlock")
                        break
                    await asyncio.wait_for(self._read_ready.wait(), timeout=5.0)
                self._readers += 1
            except asyncio.TimeoutError:
                logger.warning("Timeout in acquire_read, proceeding anyway to prevent deadlock")
                self._readers += 1

    async def release_read(self):
        async with self._read_ready:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()

    async def acquire_write(self):
        async with self._read_ready:
            self._writers_waiting += 1
            try:
                start_time = asyncio.get_event_loop().time()
                while self._writer_active or self._readers > 0:
                    # Check timeout
                    if asyncio.get_event_loop().time() - start_time > self._acquire_timeout:
                        self._writers_waiting -= 1
                        raise TimeoutError("Timeout while waiting to acquire write lock")
                    await asyncio.wait_for(self._read_ready.wait(), timeout=5.0)
                self._writers_waiting -= 1
                self._writer_active = True
            except asyncio.TimeoutError:
                self._writers_waiting -= 1
                raise TimeoutError("Timeout while waiting to acquire write lock")

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
