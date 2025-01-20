import asyncio
from typing import Any, List

class BroadcastChannel:
    def __init__(self, max_size: int = 10):
        self._queues: List[asyncio.Queue] = []
        self._max_size = max_size

    async def broadcast(self, value: Any):
        """Send a new value to all subscribers."""
        for queue in self._queues:
            # If the queue is full, remove the oldest item to make room for the new one
            if queue.full():
                _ = await queue.get()
            await queue.put(value)

    def subscribe(self) -> asyncio.Queue:
        """Subscribe a new receiver to the channel."""
        queue = asyncio.Queue(maxsize=self._max_size)
        self._queues.append(queue)
        return queue