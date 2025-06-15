import asyncio
import logging
import platform
from typing import Tuple, List, Any, Optional

# Conditionally import conpty on Windows
if platform.system().lower() == "windows":
    try:
        import conpty
    except ImportError:
        conpty = None
else:
    conpty = None

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

class ConPTyTerminal:
    def __init__(self, command: str, write_queue: asyncio.Queue[ShellData], read_queue: asyncio.Queue[terminalez_pb2.ClientUpdate]):
        self.command = command
        self.read_queue: asyncio.Queue[terminalez_pb2.ClientUpdate] = read_queue
        self.write_queue: asyncio.Queue[ShellData] | None = write_queue
        self._winsize: Tuple[int, int] | None = None # Current size of the PTY console (cols, rows)
        self.seq: int = 0  # Our current sequence number
        self.seq_outdated = 0  # Number of times seq has been outdated
        self.content_offset = 0  # bytes which got pruned before the first character of `content`
        self.content: bytes = b""  # The content of the PTY
        self.process: Optional[Any] = None  # ConPTy process instance of type conpty.RealtimeConPtyProcess
        self.use_realtime = False

        # Event for clean shutdown
        self.shutdown_event = asyncio.Event()

        self.buffer_size = 16384 # Default buffer size for PTY
        self.pid: Optional[int] = None  # Process ID of the PTY process        # Tasks
        self.tasks: List[asyncio.Task] = []

    async def start(self):
        """Initialize the terminal process and start async tasks"""
        # Check if conpty is available
        if conpty is None:
            raise RuntimeError("ConPTy module is not available. Please install the 'conpty' package for Windows terminal support.")
        
        try:
            self.process = conpty.spawn_realtime(
                self.command,
                console_size=(80, 24),
                buffer_size=self.buffer_size)

            self.process.start_realtime_streaming()

            self.pid = self.process.pid()

            # Start reading and writing tasks
            self.tasks.append(asyncio.create_task(self.read_output()))
            self.tasks.append(asyncio.create_task(self.write_input()))

        except Exception as e:
            logger.exception(f"Failed to start ConPTY process {e}")
            raise

    async def read_output(self):
        """Background task to continuously read output from the PTY process."""
        while (not self.shutdown_event.is_set()) and self.process and self.process.is_alive():
            try:
                # Read with short timeout for responsiveness
                data = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.process.read_realtime(
                        size=4096,
                        timeout_microseconds=10000  # 10ms timeout
                    )
                )

                if data:
                    print("Tempo data: \n", repr(data))

                if data and len(data) > 0:
                    self.content+=data

                    # send data if the server has fallen behind
                    if self.content_offset + len(self.content) > self.seq:
                        start = prev_char_boundary(self.content, self.seq - self.content_offset)
                        end_pos = min(start + CONTENT_CHUNK_SIZE, len(self.content))
                        end = prev_char_boundary(self.content, end_pos)

                        content_slice = self.content[start:end]

                        data = terminalez_pb2.TerminalOutput(
                            seq_num=self.content_offset + start,
                            data=content_slice
                        )

                        self.seq = self.content_offset + end
                        self.seq_outdated = 0
                        await self.read_queue.put(terminalez_pb2.ClientUpdate(data=data))

                    if (len(self.content) > CONTENT_PRUNE_BYTES) and (
                            self.seq - CONTENT_ROLLING_BYTES > self.content_offset):
                        pruned = (self.seq - CONTENT_ROLLING_BYTES) - self.content_offset
                        pruned = prev_char_boundary(self.content, pruned)
                        self.content_offset += pruned
                        self.content = self.content[pruned:]

            except Exception as e:
                logger.exception(f"Error reading from PTY: {e}")
                self.read_queue.shutdown()
                break

            await asyncio.sleep(0.001)  # Yield control to event loop


    async def write_input(self):
        """Background task to continuously write input to the PTY process."""
        while (not self.shutdown_event.is_set()) and self.process and self.process.is_alive():
            try:
                if not self.write_queue.empty():
                    # Wait for commands to write
                    command = await self.write_queue.get()
                    self.write_queue.task_done()

                    if command is None:
                        logger.error("PTY not initialized. Cannot write input.")
                        self.shutdown_event.set()
                        return


                    shell_data: ShellData = command

                    if isinstance(shell_data, Data):
                        data = shell_data.data
                        logger.debug(f"Writing to PTY: {data!r}")
                        await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: self.process.write_realtime(data)
                        )
                    elif isinstance(shell_data, Sync):
                        if shell_data.seq < self.seq:
                            self.seq_outdated += 1
                            if self.seq_outdated >= 3:
                                self.seq = shell_data.seq
                    elif isinstance(shell_data, Resize):
                        # Resize the PTY console
                        self.process.resize(shell_data.cols, shell_data.rows)
                        self._winsize = (shell_data.cols, shell_data.rows)
                else:
                    # Queue is empty, yield control to other tasks briefly
                    await asyncio.sleep(0.01)  # Small sleep to prevent busy waiting

            except Exception as e:
                logger.exception(f"Error writing to PTY: {e}")
                return

            await asyncio.sleep(0.001)  # Yield control to event loop

    async def stop(self):
        """Stop all tasks and terminate the process"""
        self.shutdown_event.set()

        # Send shutdown signal to write worker
        await self.write_queue.put(None)

        # Terminate process
        if self.process and self.process.is_alive():
            try:
                if self.use_realtime:
                    await asyncio.get_event_loop().run_in_executor(
                        None, lambda: self.process.write_realtime(b"exit\r\n")
                    )
                await asyncio.sleep(0.2)
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.process.terminate(0)
                )
            except:
                pass

        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

    def get_winsize(self) -> Tuple[int, int] | None:
        """Get the size of the PTY."""
        if self.process.is_alive():
            logger.error("ConPTY not initialized/closed. Cannot get window size.")
            return None
        return self._winsize