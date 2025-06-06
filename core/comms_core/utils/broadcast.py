import asyncio
from typing import Any, List
import logging

logger = logging.getLogger(__name__)

class BroadcastChannel:
    def __init__(self, max_size: int = 10):
        self._queues: List[asyncio.Queue] = []
        self._max_size: int = max_size

    async def broadcast(self, value: Any):
        """Send a new value to all subscribers."""
        # Clean up closed/orphaned queues during broadcast
        active_queues = []
        for queue in self._queues:
            try:
                # If the queue is full, remove the oldest item to make room for the new one
                if queue.full():
                    try:
                        _ = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                
                await queue.put(value)
                active_queues.append(queue)
            except Exception as e:
                # Queue might be closed or invalid, skip it
                logger.debug(f"Removing inactive queue from broadcast channel: {e}")
                continue
        
        # Update the active queues list
        self._queues = active_queues

    def subscribe(self) -> asyncio.Queue:
        """Subscribe a new receiver to the channel."""
        queue = asyncio.Queue(maxsize=self._max_size)
        self._queues.append(queue)
        return queue
    
    def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe a receiver from the channel."""
        try:
            self._queues.remove(queue)
        except ValueError:
            # Queue was already removed
            pass
    
    def get_subscriber_count(self) -> int:
        """Get the current number of active subscribers."""
        return len(self._queues)
    
    def cleanup_inactive_subscribers(self):
        """Remove queues that are no longer reachable."""
        active_queues = []
        for queue in self._queues:
            # Check if queue is still valid and not closed
            if not queue._closed if hasattr(queue, '_closed') else True:
                active_queues.append(queue)
        self._queues = active_queues