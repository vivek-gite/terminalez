"""
Common shell data types used for communication with terminal processes.
These classes are used by both UnixPTyTerminal and ConPTyTerminal.
"""

from dataclasses import dataclass


class ShellData:
    """Base class for internal messages routed to shell runners."""
    pass


@dataclass(frozen=True)
class Data(ShellData):
    """Sequence of input bytes from the server."""
    data: bytes


@dataclass(frozen=True)
class Sync(ShellData):
    """Information about the server's current sequence number."""
    seq: int


@dataclass(frozen=True)
class Resize(ShellData):
    """Resize the shell to a different number of rows and columns."""
    rows: int
    cols: int
