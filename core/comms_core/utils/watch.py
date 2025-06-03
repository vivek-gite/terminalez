import asyncio
from typing import Any, List


class WatchChannel:
    def __init__(self, initial_value: Any):
        self._value = initial_value
        self._receivers: List[asyncio.Queue] = []

    async def send(self, value: Any):
        """Send a new value to all receivers."""
        self._value = value
        for queue in self._receivers:
            await queue.put(value)

    def subscribe(self) -> 'WatchReceiver':
        """Subscribe a new receiver to the channel."""
        queue = asyncio.Queue(maxsize=1)
        self._receivers.append(queue)
        return WatchChannel.WatchReceiver(queue, self._value)

    def get_latest(self):
        return self._value


    class WatchReceiver:
        def __init__(self, queue: asyncio.Queue, initial_value: Any):
            self._queue = queue
            self._initial_value = initial_value
            self._first_value = True

        async def recv(self) -> Any:
            """Receive the next value. Returns the current value on the first call."""
            if self._first_value:
                self._first_value = False
                return self._initial_value
            val = await self._queue.get()
            self._queue.task_done()
            return val
