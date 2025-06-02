import asyncio
import logging
import os
from typing import Optional

from core.host_core.ConPTyTerminal import ShellData, ConPTyTerminal
from core.comms_core.proto.terminalez import terminalez_pb2

logger = logging.getLogger(__name__)


class ConPTyRunner:
    """
    Manages terminal processes using WinPTY.

    This class provides functionality to:
    1. List available terminals on Windows
    2. Create and spawn new terminal processes
    3. Handle communication with terminal processes via read/write pipes
    """

    def __init__(self):
        self.write_pipe: asyncio.Queue[ShellData] = asyncio.Queue()
        self.read_pipe: asyncio.Queue[terminalez_pb2.ClientUpdate] = asyncio.Queue()
        self.active_terminal: Optional[ConPTyTerminal] = None


    @staticmethod
    def list_available_terminals() -> dict:
        """Lists common terminals available on Windows with their paths."""
        terminals = {}

        # Common terminal executables and their locations
        common_terminals = {
            "Command Prompt": os.path.join(os.environ["WINDIR"], "System32", "cmd.exe"),
            "PowerShell": os.path.join(os.environ["WINDIR"], "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
            "Windows Terminal": os.path.join(os.getenv("LOCALAPPDATA"), "Microsoft", "WindowsApps", "wt.exe"),
            # Location for Windows Terminal
            "Git Bash": "C:\\Program Files\\Git\\bin\\bash.exe"  # Default location for Git Bash
        }

        # Check for common executables
        for name, path in common_terminals.items():
            if os.path.exists(path):
                terminals[name] = path

        return terminals

    @staticmethod
    def available_terminals_list():
        """
        Returns a list of available terminals in 'name;path' format

        Returns:
            list: List of strings in 'name;path' format
        """
        terminals = ConPTyRunner.list_available_terminals()
        return [f"{name};{path}" for name, path in terminals.items()]

    async def create_terminal(self, terminal_path: str = "") -> None:
        """
        Creates a new terminal process with the specified command.

        Args:
            terminal_path (str): Path to the terminal executable. If empty, uses default terminal.
        """
        if not terminal_path:
            terminal_path = os.path.join(os.environ["WINDIR"], "System32", "cmd.exe")

        self.active_terminal = ConPTyTerminal(command=terminal_path, write_queue=self.write_pipe, read_queue=self.read_pipe)

        await self.active_terminal.start()

    async def run_command(self, command: ShellData) -> bool:
        """
        Runs a command in the selected terminal.

        Args:
            command (str): The command to run

        Returns:
            bool: True if command was queued, False otherwise
        """
        try:
            await self.write_pipe.put(command)
            return True
        except Exception as e:
            logger.error(f"Error queueing command: {e}")
            return False

    def get_read_pipe(self) -> asyncio.Queue[terminalez_pb2.ClientUpdate]:
        """Returns the read pipe queue"""
        return self.read_pipe

    def get_write_pipe(self) -> asyncio.Queue[ShellData]:
        """Returns the write pipe queue"""
        return self.write_pipe

    async def is_alive(self) -> bool:
        """
        Checks if the active terminal process is still running.

        Returns:
            bool: True if the terminal is alive, False otherwise
        """
        if self.active_terminal and self.active_terminal.process:
            return self.active_terminal.process.is_alive()
        return False


