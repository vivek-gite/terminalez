import asyncio
import logging
import os
import platform
import shutil
from typing import Optional, Dict, List, Any

from core.comms_core.proto.terminalez import terminalez_pb2
from core.comms_core.utils.shell_data import ShellData

logger = logging.getLogger(__name__)


class PlatformTerminalRunner:
    """
    Platform-agnostic terminal runner that works on both Windows and Unix systems.

    This class provides functionality to:
    1. List available terminals on the current platform
    2. Create and spawn new terminal processes
    3. Handle communication with terminal processes via read/write pipes
    """

    def __init__(self):
        self.write_pipe: asyncio.Queue[ShellData] = asyncio.Queue()
        self.read_pipe: asyncio.Queue[terminalez_pb2.ClientUpdate] = asyncio.Queue()
        self.active_terminal: Optional[Any] = None  # Using Any to avoid type issues
        self.platform = platform.system().lower()

    @staticmethod
    def list_available_terminals() -> Dict[str, str]:
        """Lists available terminals for the current platform."""
        system = platform.system().lower()
        
        if system == "windows":
            return PlatformTerminalRunner._list_windows_terminals()
        else:
            return PlatformTerminalRunner._list_unix_terminals()

    @staticmethod
    def _list_windows_terminals() -> Dict[str, str]:
        """Lists common terminals available on Windows with their paths."""
        terminals = {}

        # Common terminal executables and their locations
        common_terminals = {
            "Command Prompt": os.path.join(os.environ.get("WINDIR", ""), "System32", "cmd.exe"),
            "PowerShell": os.path.join(os.environ.get("WINDIR", ""), "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
            "PowerShell Core": shutil.which("pwsh") or "",
            "Git Bash": "C:\\Program Files\\Git\\bin\\bash.exe"  # Default location for Git Bash
        }

        # Check for common executables
        for name, path in common_terminals.items():
            if path and os.path.exists(path):
                terminals[name] = path

        return terminals

    @staticmethod
    def _list_unix_terminals() -> Dict[str, str]:
        """Lists common shells and terminals available on Unix systems."""
        terminals = {}
        
        # Common shells
        common_shells = {
            "Bash": "/bin/bash",
            "Zsh": "/bin/zsh", 
            "Fish": "/usr/bin/fish",
            "Tcsh": "/bin/tcsh",
            "Ksh": "/bin/ksh",
            "Dash": "/bin/dash",
            "Sh": "/bin/sh"
        }
        
        # Check which shells exist
        for name, path in common_shells.items():
            if os.path.exists(path):
                terminals[name] = path
        
        # Check for shells in PATH
        path_shells = ["bash", "zsh", "fish", "tcsh", "ksh", "dash", "sh"]
        for shell in path_shells:
            which_result = shutil.which(shell)
            if which_result and shell.title() not in terminals:
                terminals[shell.title()] = which_result
        
        # Add current shell from environment
        current_shell = os.environ.get("SHELL")
        if current_shell and os.path.exists(current_shell):
            shell_name = os.path.basename(current_shell).title()
            if shell_name not in terminals:
                terminals[f"Current ({shell_name})"] = current_shell
        
        return terminals

    @staticmethod
    def available_terminals_list() -> List[str]:
        """
        Returns a list of available terminals in 'name;path' format

        Returns:
            list: List of strings in 'name;path' format
        """
        terminals = PlatformTerminalRunner.list_available_terminals()
        return [f"{name};{path}" for name, path in terminals.items()]

    async def create_terminal(self, terminal_path: str = "") -> None:
        """
        Creates a new terminal process with the specified command.

        Args:
            terminal_path (str): Path to the terminal executable. If empty, uses default terminal.
        """
        # Import here to avoid circular imports
        from core.host_core.TerminalFactory import TerminalFactory
        
        if not terminal_path:
            terminal_path = TerminalFactory.get_default_shell()

        # Create platform-appropriate terminal
        self.active_terminal = TerminalFactory.create_terminal(
            command=terminal_path, 
            write_queue=self.write_pipe, 
            read_queue=self.read_pipe
        )

        await self.active_terminal.start()
        logger.info(f"Created {type(self.active_terminal).__name__} with command: {terminal_path}")

    async def run_command(self, command: ShellData) -> bool:
        """
        Runs a command in the selected terminal.

        Args:
            command (ShellData): The command to run

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
        if self.active_terminal:
            if hasattr(self.active_terminal, 'is_alive'):
                return self.active_terminal.is_alive()
            elif hasattr(self.active_terminal, 'process') and self.active_terminal.process:
                if hasattr(self.active_terminal.process, 'is_alive'):
                    return self.active_terminal.process.is_alive()
                elif hasattr(self.active_terminal.process, 'poll'):
                    return self.active_terminal.process.poll() is None
        return False

    async def stop(self):
        """Stop the active terminal and clean up resources."""
        if self.active_terminal:
            await self.active_terminal.stop()
            self.active_terminal = None

    async def get_terminal_info(self) -> Dict[str, any]:
        """Get information about the current terminal."""
        if not self.active_terminal:
            return {"status": "no_terminal", "platform": self.platform}
        
        is_terminal_alive = await self.is_alive()
        info = {
            "status": "active" if is_terminal_alive else "inactive",
            "platform": self.platform,
            "terminal_type": type(self.active_terminal).__name__,
        }
        
        if hasattr(self.active_terminal, 'get_pid'):
            info["pid"] = self.active_terminal.get_pid()
        elif hasattr(self.active_terminal, 'pid'):
            info["pid"] = self.active_terminal.pid
            
        if hasattr(self.active_terminal, 'get_winsize'):
            info["winsize"] = self.active_terminal.get_winsize()
            
        return info


# Backwards compatibility alias
ConPTyRunner = PlatformTerminalRunner
