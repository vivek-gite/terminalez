import asyncio
import functools
import signal
import sys


class GracefulExitHandler:
    def __init__(self, client):
        self.client = client
        self.shutdown_initiated = False
        self._setup_handlers()

    def _setup_handlers(self):
        # Register for both Windows and Unix
        if sys.platform == 'win32':
            # For Windows, we need to use a different approach
            # Using asyncio.Event as a signal mechanism
            self.exit_event = asyncio.Event()

            # Create a handler for CTRL+C events
            def win_handler(sig, frame):
                if not self.shutdown_initiated:
                    self.shutdown_initiated = True
                    # Set the event to trigger cleanup
                    asyncio.create_task(self._trigger_exit_event())

            # Register the handler
            signal.signal(signal.SIGINT, win_handler)
            signal.signal(signal.SIGTERM, win_handler)
        else:
            # For Unix, we can use add_signal_handler
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(
                    sig,
                    functools.partial(self.shutdown, sig)
                )

    async def _trigger_exit_event(self):
        self.exit_event.set()
        await self.shutdown_coro("CTRL+C")

    def shutdown(self, sig):
        """Synchronous shutdown entry point"""
        if not self.shutdown_initiated:
            self.shutdown_initiated = True
            # Schedule the coroutine in the event loop
            asyncio.create_task(self.shutdown_coro(sig))

    async def shutdown_coro(self, sig):
        """Coroutine that performs actual shutdown operations"""
        print(f"\nReceived exit signal {sig}, shutting down gracefully...")

        # Step 1: Close the client
        try:
            if hasattr(self.client, 'close'):
                if asyncio.iscoroutinefunction(self.client.close):
                    await self.client.close()
                else:
                    self.client.close()
            print("Client closed successfully")
        except Exception as e:
            print(f"Error closing client: {e}")

        # # Step 2: Cancel all tasks
        # if self.tasks:
        #     print(f"Cancelling {len(self.tasks)} running tasks...")
        #     for task in self.tasks:
        #         if not task.done():
        #             task.cancel()
        #
        #     # Wait for all tasks to complete their cancellation
        #     await asyncio.gather(*self.tasks, return_exceptions=True)
        #     print("All tasks cancelled successfully")

        # Step 3: Stop the event loop and exit
        loop = asyncio.get_event_loop()
        loop.stop()

async def monitor_exit_event(exit_event):
    """For Windows: Monitor the exit event and exit when it's set"""
    await exit_event.wait()
    # Once the event is set, we just end this monitoring task