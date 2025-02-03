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





# # Example usage
# async def main():
#     channel = WatchChannel(initial_value=0)
#
#     # Subscribe two receivers
#     receiver1 = channel.subscribe()
#     receiver2 = channel.subscribe()
#
#     async def producer(rec_channel):
#         for i in range(1, 6):
#             print(f"Producer sending: {i}")
#             await rec_channel.send(i)
#         await rec_channel.send(None)
#
#     async def receiver_task(name: str, receiver):
#         while True:
#             value = await receiver.recv()
#             if value is None:
#                 break
#             print(f"{name} received: {value}")
#
#     await asyncio.gather(
#         asyncio.create_task(receiver_task("Receiver 1", receiver1)),
#         asyncio.create_task(receiver_task("Receiver 2", receiver2)),
#         asyncio.create_task(producer(channel))
#     )
#
#     print("Producer done")
#     await asyncio.sleep(1)
#
#     await channel.send(10)
#     receiver3 = channel.subscribe()
#     asyncio.create_task(receiver_task("Receiver 3", receiver3))
#     print("Receiver 3 done")
#     await asyncio.sleep(1)
#
# asyncio.run(main())
