"""
Platform-agnostic terminal factory for creating appropriate PTY terminals
based on the operating system.
"""
import asyncio
import platform
import logging
from typing import Union

from UnixPTyTerminal import UnixPTyTerminal

# Conditionally import ConPTy only on Windows
if platform.system().lower() == "windows":
    try:
        from ConPTyTerminal import ConPTyTerminal
        PTyTerminal = Union[ConPTyTerminal, UnixPTyTerminal]
    except ImportError:
        ConPTyTerminal = None
        PTyTerminal = UnixPTyTerminal
else:
    ConPTyTerminal = None
    PTyTerminal = UnixPTyTerminal

logger = logging.getLogger(__name__)


class TerminalFactory:
    """Factory class for creating platform-appropriate terminal instances."""
    
    @staticmethod
    def create_terminal(command: str, write_queue, read_queue):
        """
        Create a terminal instance appropriate for the current platform.
        
        Args:
            command: The shell command to execute
            write_queue: Queue for input data to the terminal
            read_queue: Queue for output data from the terminal
            
        Returns:
            A platform-appropriate terminal instance
            
        Raises:
            RuntimeError: If the current platform is not supported
        """
        system = platform.system().lower()
        
        if system == "windows":
            if ConPTyTerminal is not None:
                logger.info("Creating ConPTy terminal for Windows")
                return ConPTyTerminal(command, write_queue, read_queue)
            else:
                logger.info("ConPTy not available on Windows, falling back to Unix PTY")
                return UnixPTyTerminal(command, write_queue, read_queue)
        elif system in ["linux", "darwin", "freebsd", "openbsd", "netbsd"]:
            logger.info(f"Creating Unix PTY terminal for {system}")
            return UnixPTyTerminal(command, write_queue, read_queue)
        else:
            raise RuntimeError(f"Unsupported platform: {system}")
    
    @staticmethod
    def get_default_shell() -> str:
        """Get the default shell for the current platform."""
        system = platform.system().lower()
        
        if system == "windows":
            # Try PowerShell first, fallback to cmd
            try:
                import shutil
                if shutil.which("pwsh"):
                    return "pwsh"
                elif shutil.which("powershell"):
                    return "powershell"
                else:
                    return "cmd"
            except:
                return "cmd"
        else:
            # Unix-like systems
            import os
            shell = os.environ.get("SHELL", "/bin/sh")
            return shell
    
    @staticmethod
    def is_windows() -> bool:
        """Check if running on Windows."""
        return platform.system().lower() == "windows"
    
    @staticmethod
    def is_unix() -> bool:
        """Check if running on a Unix-like system."""
        return platform.system().lower() in ["linux", "darwin", "freebsd", "openbsd", "netbsd"]


# Convenience function for creating terminals
def create_terminal(command: str = None, write_queue = None, read_queue = None):
    """
    Convenience function to create a terminal with default parameters.
    
    Args:
        command: Shell command to execute (defaults to system default shell)
        write_queue: Input queue (creates new if None)
        read_queue: Output queue (creates new if None)
        
    Returns:
        A platform-appropriate terminal instance
    """
    if command is None:
        command = TerminalFactory.get_default_shell()
    
    if write_queue is None:
        write_queue = asyncio.Queue()
    
    if read_queue is None:
        read_queue = asyncio.Queue()
    
    return TerminalFactory.create_terminal(command, write_queue, read_queue)
