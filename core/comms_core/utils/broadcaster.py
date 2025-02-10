import asyncio

class Broadcast:
    def __init__(self):
        self._condition = asyncio.Condition()
        self._subscribers = []
        self._last_message = None  # Store the last message

    async def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue()
        async with self._condition:
            if self._last_message is not None:
                # Immediately send the last message to the new subscriber
                await queue.put(self._last_message)
            self._subscribers.append(queue)
        return queue

    async def broadcast(self, message) -> None:
        async with self._condition:
            self._last_message = message  # Update the last message
            for subscriber in self._subscribers:
                await subscriber.put(message)
            self._condition.notify_all()

# # Example usage
# async def main():
#     broadcaster = Broadcast()
#
#     async def producer():
#         for i in range(1, 6):
#             print(f"Producer sending: {i}")
#             await broadcaster.broadcast(i)
#             await asyncio.sleep(1)
#
#     async def consumer(name):
#         queue = await broadcaster.subscribe()
#         while True:
#             message = await queue.get()
#             print(f"{name} received: {message}")
#
#     await asyncio.gather(
#         producer(),
#         consumer("Receiver1"),
#         consumer("Receiver2"),
#     )
#
# asyncio.run(main())
