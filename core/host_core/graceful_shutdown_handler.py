import asyncio
import functools
import signal
import sys
import threading


class GracefulExitHandler:
    def __init__(self, client):
        self.client = client
        self.shutdown_initiated = False
        self.exit_event = asyncio.Event()  # Create exit event for both platforms
        self._setup_handlers()

    def _setup_handlers(self):
        # Register for both Windows and Unix
        if sys.platform == 'win32':
            # For Windows, we need to use a different approach
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
            # For Unix, use a more robust approach
            def unix_signal_handler(sig, frame):
                if not self.shutdown_initiated:
                    self.shutdown_initiated = True
                    # Create a task to handle shutdown in the event loop
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(self._trigger_exit_event())
                    except RuntimeError:
                        # If no event loop is running, use thread-safe call
                        threading.Thread(target=self._sync_shutdown, args=(sig,), daemon=True).start()

            # Register signal handlers
            signal.signal(signal.SIGINT, unix_signal_handler)
            signal.signal(signal.SIGTERM, unix_signal_handler)
            
            # Also try to register with the event loop if available
            try:
                loop = asyncio.get_running_loop()
                for sig in (signal.SIGINT, signal.SIGTERM):
                    loop.add_signal_handler(
                        sig,
                        functools.partial(self._async_shutdown, sig)
                    )
            except RuntimeError:
                # Event loop not running yet, signal handlers will handle it
                pass

    async def _trigger_exit_event(self):
        self.exit_event.set()
        await self.shutdown_coro("Signal")

    def _async_shutdown(self, sig):
        """Async shutdown entry point for Unix signal handlers"""
        if not self.shutdown_initiated:
            self.shutdown_initiated = True
            asyncio.create_task(self.shutdown_coro(sig))

    def _sync_shutdown(self, sig):
        """Synchronous shutdown fallback"""
        if not self.shutdown_initiated:
            self.shutdown_initiated = True
            print(f"\nReceived exit signal {sig}, shutting down gracefully...")
            try:
                # Try to close client synchronously
                if hasattr(self.client, 'close') and not asyncio.iscoroutinefunction(self.client.close):
                    self.client.close()
                    print("Client closed successfully")
            except Exception as e:
                print(f"Error closing client: {e}")
            finally:
                # Force exit if needed
                sys.exit(0)

    def shutdown(self, sig):
        """Synchronous shutdown entry point (deprecated, kept for compatibility)"""
        self._async_shutdown(sig)

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

        # Step 3: Set exit event and handle proper shutdown
        self.exit_event.set()
        
        # Step 4: Stop the event loop gracefully
        try:
            loop = asyncio.get_running_loop()
            # Schedule the loop to stop after current tasks complete
            loop.call_soon_threadsafe(loop.stop)
        except RuntimeError:
            # Fallback to direct exit
            sys.exit(0)

async def monitor_exit_event(exit_event):
    """Monitor the exit event and exit when it's set (compatible with both Windows and Unix)"""
    await exit_event.wait()
    # Once the event is set, we just end this monitoring task
    print("Exit event triggered, monitoring task completed")