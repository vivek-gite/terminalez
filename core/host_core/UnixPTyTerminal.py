import asyncio
import logging
import os
import pty
import subprocess
from typing import Tuple, List, Optional

from core.comms_core.proto.terminalez import terminalez_pb2
from core.comms_core.utils.shell_data import *

logger = logging.getLogger(__name__)

CONTENT_CHUNK_SIZE = 1 << 16    # ~64KB chunks
CONTENT_ROLLING_BYTES = 8 << 20  # Keep ~8MB content
CONTENT_PRUNE_BYTES = 12 << 20  # Prune when exceeding ~12MB


def prev_char_boundary(s_bytes: bytes, i: int) -> int:
    """
    Finds the largest byte index less than or equal to `i` within string `s`
    that is a valid character boundary in its UTF-8 representation.

    Equivalent to Rust's str::prev_char_boundary. Iterates backward from `i`.

    Args:
        s_bytes: The content in bytes.
        i: The byte index to search backwards from (inclusive).
           Must be 0 <= i <= len(s.encode('utf-8')).

    Returns:
        The found character boundary byte index.

    Raises:
        ValueError: If i is outside the valid byte index range [0, len(s.encode('utf-8'))].
        (This matches the implicit guarantee in Rust where 0 <= i <= s.len())
    """

    s_bytes_len = len(s_bytes)

    # Check if the input index i is within the valid range [0, length of bytes]
    if not (0 <= i <= s_bytes_len):
        # This check makes the Python function more robust for invalid inputs,
        # even if the Rust version expects valid 'i'.
        raise ValueError(f"Index {i} is out of bounds for bytes of length {s_bytes_len}")

    for j in range(i, -1, -1):
        is_boundary = False
        if j == 0 or j == s_bytes_len:
            is_boundary = True
        elif j > 0 and j < s_bytes_len:
            # Check if the byte at index j is NOT a continuation byte
            if not (0x80 <= s_bytes[j] <= 0xBF):
                is_boundary = True

        # Rust: .find(|&j| is_boundary) -> Return the first j that satisfies the condition
        if is_boundary:
            return j  # Found the largest boundary <= i

    return 0


class UnixPTyTerminal:
    def __init__(self, command: str, write_queue: asyncio.Queue[ShellData], read_queue: asyncio.Queue[terminalez_pb2.ClientUpdate]):
        self.command = command
        self.read_queue: asyncio.Queue[terminalez_pb2.ClientUpdate] = read_queue
        self.write_queue: asyncio.Queue[ShellData] | None = write_queue
        self._winsize: Tuple[int, int] | None = None # Current size of the PTY console (cols, rows)
        self.seq: int = 0  # Our current sequence number
        self.seq_outdated = 0  # Number of times seq has been outdated
        self.content_offset = 0  # bytes which got pruned before the first character of `content`
        self.content: bytes = b""  # The content of the PTY

        # Unix PTY specific attributes
        self.master_fd: Optional[int] = None
        self.slave_fd: Optional[int] = None
        self.process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None

        # Event for clean shutdown
        self.shutdown_event = asyncio.Event()

        self.buffer_size = 16384 # Default buffer size for PTY

        # Tasks
        self.tasks: List[asyncio.Task] = []

    async def start(self):
        """Initialize the terminal process and start async tasks"""
        try:
            # Create a pseudo-terminal pair
            self.master_fd, self.slave_fd = pty.openpty()
            
            # Set initial window size
            self._set_winsize(80, 24)
            
            # Parse command (handle shell commands with arguments)
            if isinstance(self.command, str):
                # Split command string into command and arguments
                cmd_parts = self.command.split()
                if not cmd_parts:
                    raise ValueError("Empty command provided")
                command = cmd_parts[0]
                args = cmd_parts[1:] if len(cmd_parts) > 1 else []
            else:
                command = self.command
                args = []

            # Setup environment for proper terminal behavior
            env = os.environ.copy()
            
            # Set terminal-specific environment variables
            env['TERM'] = 'xterm-256color'  # Ensure 256 color support
            env['COLORTERM'] = 'truecolor'  # Enable true color support
                
            # Force color output for various tools
            env['FORCE_COLOR'] = '1'
            env['CLICOLOR'] = '1'
            env['CLICOLOR_FORCE'] = '1'

            # Start the process with the slave end of the PTY as stdin/stdout/stderr
            self.process = subprocess.Popen(
                [command] + args,
                stdin=self.slave_fd,
                stdout=self.slave_fd,
                stderr=self.slave_fd,
                env=env,  # Pass the enhanced environment
                preexec_fn=os.setsid,  # Start new session to handle signals properly
                close_fds=True
            )
            
            self.pid = self.process.pid
            
            # Close the slave fd in the parent process (only child needs it)
            os.close(self.slave_fd)
            self.slave_fd = None
            
            # Make master fd non-blocking
            import fcntl
            flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            # Start reading and writing tasks
            self.tasks.append(asyncio.create_task(self.read_output()))
            self.tasks.append(asyncio.create_task(self.write_input()))

            logger.info(f"Started Unix PTY process {self.pid} with command: {self.command}")

        except Exception as e:
            logger.exception(f"Failed to start Unix PTY process: {e}")
            await self._cleanup()
            raise

    def _set_winsize(self, cols: int, rows: int):
        """Set the window size of the PTY"""
        if self.master_fd is not None:
            import struct
            import fcntl
            import termios
            
            # Pack window size into the format expected by TIOCSWINSZ
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
            self._winsize = (cols, rows)

    def is_alive(self) -> bool:
        """Check if the process is still alive"""
        if self.process is None:
            return False
        return self.process.poll() is None

    async def read_output(self):
        """Background task to continuously read output from the PTY process."""
        while (not self.shutdown_event.is_set()) and self.is_alive() and self.master_fd is not None:
            try:
                # Use run_in_executor to make the blocking read non-blocking
                data = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._read_from_master
                )

                if data:
                    print("Unix PTY data: \n", repr(data))

                if data and len(data) > 0:
                    self.content += data

                    # send data if the server has fallen behind
                    if self.content_offset + len(self.content) > self.seq:
                        start = prev_char_boundary(self.content, self.seq - self.content_offset)
                        end_pos = min(start + CONTENT_CHUNK_SIZE, len(self.content))
                        end = prev_char_boundary(self.content, end_pos)

                        content_slice = self.content[start:end]

                        data_msg = terminalez_pb2.TerminalOutput(
                            seq_num=self.content_offset + start,
                            data=content_slice
                        )

                        self.seq = self.content_offset + end
                        self.seq_outdated = 0
                        await self.read_queue.put(terminalez_pb2.ClientUpdate(data=data_msg))

                    # Prune old content to prevent memory bloat
                    if (len(self.content) > CONTENT_PRUNE_BYTES) and (
                            self.seq - CONTENT_ROLLING_BYTES > self.content_offset):
                        pruned = (self.seq - CONTENT_ROLLING_BYTES) - self.content_offset
                        pruned = prev_char_boundary(self.content, pruned)
                        self.content_offset += pruned
                        self.content = self.content[pruned:]

            except Exception as e:
                logger.exception(f"Error reading from Unix PTY: {e}")
                try:
                    self.read_queue.shutdown()
                except:
                    pass
                break

            await asyncio.sleep(0.001)  # Yield control to event loop

    def _read_from_master(self) -> bytes:
        """Read data from master fd with timeout"""
        if self.master_fd is None:
            return b""
            
        try:
            import select
            # Use select with a short timeout for responsiveness
            ready, _, _ = select.select([self.master_fd], [], [], 0.01)  # 10ms timeout
            
            if ready:
                return os.read(self.master_fd, self.buffer_size)
            else:
                return b""
                
        except (OSError, BlockingIOError):
            # No data available or fd closed
            return b""

    async def write_input(self):
        """Background task to continuously write input to the PTY process."""
        while (not self.shutdown_event.is_set()) and self.is_alive() and self.master_fd is not None:
            try:
                if not self.write_queue.empty():
                    # Wait for commands to write
                    command = await self.write_queue.get()
                    self.write_queue.task_done()

                    if command is None:
                        logger.info("Received shutdown signal for Unix PTY")
                        self.shutdown_event.set()
                        return

                    shell_data: ShellData = command
                    logger.info(f"Writing to Unix PTY: {shell_data!r}")
                    logger.info(f"Is instance: {isinstance(shell_data, Data)}")

                    if isinstance(shell_data, Data):
                        data = shell_data.data
                        logger.info(f"Writing to Unix PTY: {data!r}")
                        await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: self._write_to_master(data)
                        )
                    elif isinstance(shell_data, Sync):
                        if shell_data.seq < self.seq:
                            self.seq_outdated += 1
                            if self.seq_outdated >= 3:
                                self.seq = shell_data.seq
                    elif isinstance(shell_data, Resize):
                        # Resize the PTY console
                        self._set_winsize(shell_data.cols, shell_data.rows)
                else:
                    # Queue is empty, yield control to other tasks briefly
                    await asyncio.sleep(0.01)  # Small sleep to prevent busy waiting

            except Exception as e:
                logger.exception(f"Error writing to Unix PTY: {e}")
                return

            await asyncio.sleep(0.001)  # Yield control to event loop

    def _write_to_master(self, data: bytes):
        """Write data to master fd"""
        if self.master_fd is not None:
            try:
                os.write(self.master_fd, data)
            except (OSError, BrokenPipeError) as e:
                logger.error(f"Failed to write to Unix PTY master: {e}")

    async def stop(self):
        """Stop all tasks and terminate the process"""
        logger.info("Stopping Unix PTY terminal")
        self.shutdown_event.set()

        # Send shutdown signal to write worker
        if self.write_queue:
            try:
                await self.write_queue.put(None)
            except:
                pass

        # Try to terminate the process gracefully
        if self.process and self.is_alive():
            try:
                # Try to send exit command first
                if self.master_fd is not None:
                    try:
                        os.write(self.master_fd, b"exit\r\n")
                        await asyncio.sleep(0.2)  # Give it time to exit gracefully
                    except:
                        pass
                
                # If still alive, send SIGTERM
                if self.is_alive():
                    self.process.terminate()
                    await asyncio.sleep(0.5)
                
                # If still alive, send SIGKILL
                if self.is_alive():
                    self.process.kill()
                    
            except Exception as e:
                logger.warning(f"Error during process termination: {e}")

        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to complete
        if self.tasks:
            try:
                await asyncio.gather(*self.tasks, return_exceptions=True)
            except:
                pass

        # Clean up file descriptors
        await self._cleanup()

    async def _cleanup(self):
        """Clean up file descriptors and resources"""
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except:
                pass
            self.master_fd = None
            
        if self.slave_fd is not None:
            try:
                os.close(self.slave_fd)
            except:
                pass
            self.slave_fd = None

    def get_winsize(self) -> Tuple[int, int] | None:
        """Get the size of the PTY."""
        if not self.is_alive():
            logger.error("Unix PTY not initialized/closed. Cannot get window size.")
            return None
        return self._winsize

    def get_pid(self) -> Optional[int]:
        """Get the process ID of the PTY process"""
        return self.pid
