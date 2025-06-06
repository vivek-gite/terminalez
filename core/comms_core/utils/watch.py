import asyncio
from typing import Any, List
import logging

logger = logging.getLogger(__name__)


class WatchChannel:
    def __init__(self, initial_value: Any):
        self._value = initial_value
        self._receivers: List[asyncio.Queue] = []

    async def send(self, value: Any):
        """Send a new value to all receivers."""
        self._value = value

        # Clean up inactive receivers during send
        active_receivers = []
        for queue in self._receivers:
            try:
                await queue.put(value)
                active_receivers.append(queue)
            except Exception as e:
                # Queue might be closed or invalid, skip it
                logger.debug(f"Removing inactive receiver from watch channel: {e}")
                continue

        # Update the active receivers list
        self._receivers = active_receivers

    def subscribe(self) -> 'WatchReceiver':
        """Subscribe a new receiver to the channel."""
        queue = asyncio.Queue(maxsize=1)
        self._receivers.append(queue)
        return WatchChannel.WatchReceiver(queue, self._value, self)

    def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe a receiver from the channel."""
        try:
            self._receivers.remove(queue)
        except ValueError:
            # Queue was already removed
            pass

    def get_latest(self):
        return self._value

    async def flush_receivers(self):
        """
        Remove all pending items from each receiver queue.

        This method iterates through all registered receiver queues and
        empties them by retrieving and marking each item as done. It is
        useful for clearing out any unprocessed messages.
        """
        logger.debug("Flushing all receivers...")
        active_receivers = []

        for queue in self._receivers:
            try:
                while not queue.empty():
                    try:
                        queue.get_nowait()
                        queue.task_done()
                    except asyncio.QueueEmpty:
                        break
                active_receivers.append(queue)
            except Exception as e:
                # Queue might be closed or invalid, skip it
                logger.debug(f"Removing invalid queue during flush: {e}")
                continue

        # Update the active receivers list
        self._receivers = active_receivers

    def cleanup_inactive_receivers(self):
        """Remove receivers that are no longer reachable."""
        active_receivers = []
        for queue in self._receivers:
            # Check if queue is still valid and not closed
            if not queue._closed if hasattr(queue, '_closed') else True:
                active_receivers.append(queue)
        self._receivers = active_receivers

    class WatchReceiver:
        def __init__(self, queue: asyncio.Queue, initial_value: Any, channel: 'WatchChannel'):
            self._queue = queue
            self._initial_value = initial_value
            self._first_value = True
            self._channel = channel

        async def recv(self) -> Any:
            """Receive the next value. Returns the current value on the first call."""
            if self._first_value:
                self._first_value = False
                return self._initial_value
            val = await self._queue.get()
            self._queue.task_done()
            return val

        def close(self):
            """Close this receiver and remove it from the channel."""
            if self._channel:
                self._channel.unsubscribe(self._queue)
                self._channel = None
