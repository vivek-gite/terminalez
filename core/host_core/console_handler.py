import asyncio
import logging
from typing import Dict, Optional

from core.comms_core.proto.terminalez import terminalez_pb2
from core.host_core.ConPTyRunner import ConPTyRunner
from core.host_core.ConPTyTerminal import ShellData

logger = logging.getLogger(__name__)


class ConsoleHandler:
    """
    Manages multiple terminal sessions and their I/O operations.
    
    This handler provides:
    - Terminal lifecycle management
    - Async I/O between terminals and the output pipeline
    - Resource cleanup and error handling
    - Terminal session tracking
    """
    
    def __init__(self, shells_output_queue: asyncio.Queue[terminalez_pb2.ClientUpdate]):
        # Active terminal tracking
        self.active_terminals: Dict[int, ConPTyRunner] = {}
        self.terminal_writes: Dict[int, asyncio.Queue[ShellData]] = {}
        self.terminal_reads: Dict[int, asyncio.Queue[terminalez_pb2.ClientUpdate]] = {}
        
        # Output pipeline with bounded queue to prevent memory issues
        self.output_pipe: asyncio.Queue[terminalez_pb2.ClientUpdate] = shells_output_queue
        
        # Task tracking for proper cleanup
        self.active_tasks: Dict[int, asyncio.Task] = {}
        
        # Shutdown coordination
        self._shutdown_event = asyncio.Event()
        
        # Statistics
        self._terminal_count = 0
        
    @property
    def number_of_terminals(self) -> int:
        """Get the current number of active terminals."""
        return len(self.active_terminals)

    async def add_terminal(self, sid: int, terminal_path: str = "") -> bool:
        """
        Create a new terminal session.
        
        Args:
            sid: Session ID for the terminal
            terminal_path: Path to the terminal executable
            
        Returns:
            bool: True if terminal was created successfully, False otherwise
        """
        if sid in self.active_terminals:
            logger.warning(f"Terminal with sid {sid} already exists")
            return False
            
        try:
            # Create terminal with timeout to prevent hanging
            con_pty_runner = ConPTyRunner()
            create_task = asyncio.create_task(con_pty_runner.create_terminal(terminal_path=terminal_path))
            await asyncio.wait_for(create_task, timeout=30.0)
            
            # Store terminal and its pipes
            self.active_terminals[sid] = con_pty_runner
            self.terminal_writes[sid] = con_pty_runner.get_write_pipe()
            self.terminal_reads[sid] = con_pty_runner.get_read_pipe()
            
            self._terminal_count += 1
            logger.info(f"Terminal created with id: {sid}, total terminals: {self.number_of_terminals}")
            return True
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout creating terminal {sid}")
            await self._cleanup_terminal(sid)
            return False
            
        except Exception as e:
            logger.error(f"Failed to create terminal {sid}: {e}")
            await self._cleanup_terminal(sid)
            return False

    async def shell_task(self, sid: int, terminal_path: str = "") -> None:
        """
        Main task for handling terminal I/O operations.
        
        Args:
            sid: Session ID for the terminal
            terminal_path: Path to the terminal executable
        """
        # Register this task in active_tasks for proper management
        current_task = asyncio.current_task()
        if current_task:
            self.active_tasks[sid] = current_task
            
        try:
            # Create terminal with proper error handling
            if not await self.add_terminal(sid=sid, terminal_path=terminal_path):
                logger.error(f"Failed to create terminal {sid}")
                return

            logger.info(f"Starting shell task for terminal {sid}")
            
            # Main I/O loop with improved error handling
            while not self._shutdown_event.is_set() and sid in self.terminal_reads:
                try:
                    # Get the queue reference once to avoid race conditions
                    result_queue = self.terminal_reads.get(sid)
                    if result_queue is None:
                        logger.warning(f"Terminal queue for sid {sid} no longer exists")
                        break
                        
                    # Check if terminal is still alive
                    terminal = self.active_terminals.get(sid)
                    if terminal and not await terminal.is_alive():
                        logger.info(f"Terminal {sid} process has died")
                        break
                    
                    try:
                        # Wait for data with reasonable timeout
                        result = await asyncio.wait_for(result_queue.get(), timeout=30.0)
                        
                        # Validate and set shell_id
                        if hasattr(result, 'data') and hasattr(result.data, 'shell_id'):
                            result.data.shell_id = sid
                        
                        logger.debug(f"Shell task {sid} received data: {type(result)}")
                        
                        # Send to output pipeline with timeout to prevent deadlocks
                        try:
                            await asyncio.wait_for(self.output_pipe.put(result), timeout=5.0)
                        except asyncio.TimeoutError:
                            logger.error(f"Timeout putting data to output pipe for shell {sid} - potential consumer deadlock")
                            # Consider if we should drop data or take other action
                            continue
                        except Exception as e:
                            logger.error(f"Error putting data to output pipe for shell {sid}: {e}")
                            continue
                            
                    except asyncio.TimeoutError:
                        # No data received within timeout, check if terminal is still active
                        if sid not in self.terminal_reads or self.terminal_reads.get(sid) is None:
                            logger.info(f"Terminal {sid} no longer active, stopping shell task")
                            break
                        # Continue the loop for periodic checks
                        continue
                        
                    except asyncio.CancelledError:
                        logger.info(f"Shell task for terminal {sid} was cancelled")
                        break
                        
                except Exception as e:
                    logger.error(f"Error processing terminal data for sid {sid}: {e}")
                    # Short pause before retrying to avoid CPU spinning
                    await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info(f"Shell task for terminal {sid} was cancelled")
        except Exception as e:
            logger.error(f"Shell task failed for terminal {sid}: {e}")
        finally:
            # Ensure cleanup always happens
            await self._cleanup_terminal(sid)
            # Remove task from active tasks
            if sid in self.active_tasks:
                del self.active_tasks[sid]
            logger.info(f"Shell task for terminal {sid} completed")

    async def _cleanup_terminal(self, sid: int) -> None:
        """
        Clean up terminal resources when shell task ends.
        
        Args:
            sid: Session ID of the terminal to clean up
        """
        try:
            # Stop the terminal if it exists
            terminal = self.active_terminals.get(sid)
            if terminal and terminal.active_terminal:
                try:
                    await terminal.active_terminal.stop()
                except Exception as e:
                    logger.warning(f"Error stopping terminal {sid}: {e}")
            
            # Clean up tracking dictionaries
            if sid in self.active_terminals:
                del self.active_terminals[sid]
            if sid in self.terminal_writes:
                del self.terminal_writes[sid]
            if sid in self.terminal_reads:
                del self.terminal_reads[sid]
            if sid in self.active_tasks:
                task = self.active_tasks[sid]
                if not task.done():
                    task.cancel()
                del self.active_tasks[sid]
                
            logger.info(f"Terminal {sid} resources cleaned up, remaining terminals: {self.number_of_terminals}")
            
        except Exception as e:
            logger.error(f"Error during cleanup of terminal {sid}: {e}")

    async def send_input_to_terminal(self, sid: int, data: ShellData) -> bool:
        """
        Send input data to a specific terminal.
        
        Args:
            sid: Session ID of the terminal
            data: Data to send to the terminal
            
        Returns:
            bool: True if data was sent successfully, False otherwise
        """
        if sid not in self.terminal_writes:
            logger.warning(f"Terminal {sid} not found for input")
            return False
            
        try:
            write_queue = self.terminal_writes[sid]
            await asyncio.wait_for(write_queue.put(data), timeout=5.0)
            return True
        except asyncio.TimeoutError:
            logger.error(f"Timeout sending input to terminal {sid}")
            return False
        except Exception as e:
            logger.error(f"Error sending input to terminal {sid}: {e}")
            return False

    async def shutdown(self) -> None:
        """
        Gracefully shutdown all terminals and cleanup resources.
        """
        logger.info("Shutting down ConsoleHandler")
        self._shutdown_event.set()
        
        # Cancel all active tasks
        for sid, task in list(self.active_tasks.items()):
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete with timeout
        if self.active_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.active_tasks.values(), return_exceptions=True),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.warning("Some tasks did not complete within shutdown timeout")
        
        # Clean up all terminals
        for sid in list(self.active_terminals.keys()):
            await self._cleanup_terminal(sid)
            
        logger.info("ConsoleHandler shutdown complete")

    def get_terminal_stats(self) -> Dict[str, int]:
        """
        Get statistics about terminal usage.
        
        Returns:
            Dict containing terminal statistics
        """
        return {
            "active_terminals": len(self.active_terminals),
            "active_tasks": len(self.active_tasks),
            "total_created": self._terminal_count
        }
