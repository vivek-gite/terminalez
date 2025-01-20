# import asyncio
# from typing import Any
#
#
# class Watch:
#     def __init__(self, initial_value):
#         self._value = initial_value
#         self._condition = asyncio.Condition()
#
#     class Sender:
#         def __init__(self, watch):
#             self._watch = watch
#
#         async def send(self, value) -> None:
#             async with self._watch._condition:
#                 self._watch._value = value
#                 self._watch._condition.notify_all()
#
#     class Receiver:
#         def __init__(self, watch):
#             self._watch = watch
#             self._last_seen_value = watch._value  # Initialize with the current value
#
#         async def recv(self) -> Any:
#             async with self._watch._condition:
#                 # If the last seen value is already updated, return it immediately
#                 """
#                 In case if sender sends the value but receiver is not ready to receive the value,
#                 then the value will be stored in the last_seen_value and it will be returned
#                 when the receiver is ready to receive the value.
#                 """
#                 if self._last_seen_value != self._watch._value:
#                     self._last_seen_value = self._watch._value
#                     return self._last_seen_value
#
#                 # Otherwise, wait for the next update
#                 await self._watch._condition.wait()
#                 self._last_seen_value = self._watch._value
#                 return self._last_seen_value
#
#         def get_latest(self):
#             return self._watch._value
#
#     def sender(self) -> Sender:
#         return Watch.Sender(self)
#
#     def receiver(self) -> Receiver:
#         return Watch.Receiver(self)
#
#
# # Example usage
# async def main():
#     watch = Watch(0)
#     sender = watch.sender()
#     receiver1 = watch.receiver()
#     receiver2 = watch.receiver()
#     receiver3 = watch.receiver()
#
#     async def producer():
#         for i in range(1, 6):
#             print(f"Producer sending: {i}")
#             await sender.send(i)
#             print("Hey I am here")
#
#
#     async def consumer(name, receiver):
#         while True:
#             value = await receiver.recv()
#             print(f"{name} received: {value}")
#
#     await asyncio.gather(
#         producer(),
#         consumer("Receiver1", receiver1),
#         consumer("Receiver2", receiver2),
#         consumer("Receiver3", receiver3),
#     )
#     # asyncio.create_task(producer())
#     # asyncio.create_task(consumer("Receiver1", receiver1))
#     # asyncio.create_task(consumer("Receiver2", receiver2))
#     # asyncio.create_task(consumer("Receiver3", receiver3))
#
#
# asyncio.run(main())
