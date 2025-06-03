# Controller.py Integration Recommendations

This document provides recommended changes to Controller.py to properly integrate with the optimized ConsoleHandler.

## 1. Improve spawn_shell_task Method

The current implementation in Controller.py directly awaits the shell_task, which blocks further processing:

```python
async def spawn_shell_task(self, sid: int, x: int, y: int, shell_info: str="") -> None:
    create_shell = terminalez_pb2.NewShell(shell_id=sid, x=x, y=y, shell_info=shell_info)
    client_update = terminalez_pb2.ClientUpdate(created_shell=create_shell)

    await self.console_handler.output_pipe.put(client_update)

    terminal_path = shell_info.strip().split(";")[1]

    shell_task = asyncio.create_task(self.console_handler.shell_task(sid=sid, terminal_path=terminal_path))
    await shell_task  # This blocks until the task completes

    close_shell = terminalez_pb2.ClientUpdate(closed_shell=sid)
    await self.console_handler.output_pipe.put(close_shell)
```

### Recommended Change:

```python
async def spawn_shell_task(self, sid: int, x: int, y: int, shell_info: str="") -> None:
    create_shell = terminalez_pb2.NewShell(shell_id=sid, x=x, y=y, shell_info=shell_info)
    client_update = terminalez_pb2.ClientUpdate(created_shell=create_shell)

    # Notify about shell creation
    await self.console_handler.output_pipe.put(client_update)

    # Extract terminal path
    terminal_path = shell_info.strip().split(";")[1] if ";" in shell_info.strip() else ""

    # Create the task without awaiting it directly
    shell_task = asyncio.create_task(
        self._run_shell_task(sid=sid, terminal_path=terminal_path)
    )
    # Store task reference if needed
    self._active_shell_tasks[sid] = shell_task
    
    # Optional: Add done callback to handle task completion
    shell_task.add_done_callback(
        lambda t, s=sid: asyncio.create_task(self._handle_shell_task_done(s, t))
    )
    
    return sid  # Return the sid to the caller

async def _run_shell_task(self, sid: int, terminal_path: str = "") -> None:
    """Run the shell task and handle completion"""
    try:
        await self.console_handler.shell_task(sid=sid, terminal_path=terminal_path)
    except Exception as e:
        logger.error(f"Error in shell task for sid {sid}: {e}")
    finally:
        # Clean up task reference
        if sid in self._active_shell_tasks:
            del self._active_shell_tasks[sid]

async def _handle_shell_task_done(self, sid: int, task: asyncio.Task) -> None:
    """Handle shell task completion and notify clients"""
    # Notify about shell closure
    close_shell = terminalez_pb2.ClientUpdate(closed_shell=sid)
    await self.console_handler.output_pipe.put(close_shell)
    
    # Handle any exceptions
    if not task.cancelled():
        try:
            # This will re-raise any exception that occurred in the task
            task.result()
        except Exception as e:
            logger.error(f"Shell task for sid {sid} failed with error: {e}")
```

## 2. Add Graceful Shutdown Support

Add a method to properly shut down the ConsoleHandler:

```python
async def shutdown(self) -> None:
    """Gracefully shut down the client and all terminals"""
    logger.info("Shutting down GrpcClient")
    
    # First shutdown console handler and all terminals
    if hasattr(self, 'console_handler'):
        await self.console_handler.shutdown()
    
    # Then close the gRPC channel
    await self.close()
    
    logger.info("GrpcClient shutdown complete")
```

## 3. Improve Constructor to Initialize Task Tracking

```python
def __init__(self, server_address: str):
    self.server_address = server_address
    self.channel: Optional[grpc.aio.Channel] = None
    self.stub: Optional[terminalez_pb2_grpc.TerminalEzStub] = None
    self.name: str = ""
    self.shells_output_queue: asyncio.Queue[terminalez_pb2.ClientUpdate] = asyncio.Queue(maxsize=1000)
    self.console_handler: ConsoleHandler = ConsoleHandler(self.shells_output_queue)
    
    # Track active shell tasks for management
    self._active_shell_tasks: Dict[int, asyncio.Task] = {}
```

## 4. Add Resource Management to Error Handling

Modify the run method's error handling to better manage resources:

```python
async def run(self):
    last_retry: float = datetime.now(timezone.utc).timestamp()
    retries: int = 0
    try:
        while True:
            try:
                await self.try_channel()
            except asyncio.CancelledError:
                logger.info("Run task was cancelled, shutting down")
                break
            except Exception as e:
                logger.exception(f"Error in gRPC connection: {e}")
                current_time: float = datetime.now(timezone.utc).timestamp()
                if last_retry - current_time > 10:
                    retries = 0
                logger.error(f"Disconnected, retrying in {2 ** retries} seconds...")
                await asyncio.sleep(2 ** retries)
                retries += 1
            last_retry = datetime.now(timezone.utc).timestamp()
    finally:
        # Ensure clean shutdown
        await self.shutdown()
```

## 5. Add Terminal Resize Support

Add a method to handle terminal resize events:

```python
async def resize_terminal(self, sid: int, rows: int, cols: int) -> bool:
    """
    Resize a terminal window.
    
    Args:
        sid: Shell ID of the terminal to resize
        rows: New number of rows
        cols: New number of columns
        
    Returns:
        bool: True if resize command was sent successfully
    """
    if not self.console_handler:
        logger.error("Cannot resize: console handler not initialized")
        return False
        
    resize_data = Resize(rows=rows, cols=cols)
    return await self.console_handler.send_input_to_terminal(sid, resize_data)
```
