from dataclasses import dataclass
from pydantic import BaseModel
from typing import Optional, Tuple, List
from core.comms_core.proto.identifiers import libs


class WsWinsize(BaseModel):
    """ Real-time window size update. """
    x: int = 0                            # The top-left x-coordinate of the shell window, offset from the origin
    y: int = 0                            # The top-left y-coordinate of the shell window, offset from the origin
    rows: int = 24                        # The number of rows in the shell window
    cols: int = 80                        # The number of columns in the shell window

class WsUser(BaseModel):
    """Real-time message providing information about a user."""
    name: str
    cursor: Optional[Tuple[int, int]] = None
    focus: Optional[libs.Sid] = None                # Unique identifier for a shell within the session.


class WsServer(BaseModel):
    """A real-time message sent from the server over WebSocket."""


    class Hello(BaseModel):
        """Initial server message, with the user's ID and session metadata."""
        user_id: libs.Uid                           # Unique identifier for a user within the session.
        metadata: str

    class Users(BaseModel):
        """A snapshot of all current users in the session."""
        users: List[Tuple[libs.Uid, WsUser]]        # Unique identifier for a user within the session.

    class UserDiff(BaseModel):
        """Info about a single user in the session: joined, left, or changed."""
        user_id: libs.Uid                           # Unique identifier for a user within the session.
        user: WsUser

    class Shells(BaseModel):
        """Notification when the set of open shells has changed."""
        shells: List[Tuple[libs.Sid, WsWinsize]]

    class Chunks(BaseModel):
        """Subscription results, in the form of terminal data chunks."""
        sid: libs.Sid                           # Unique identifier for a shell within the session.
        index: int
        chunks: List[bytes]

    class ShellLatency(BaseModel):
        """Forward a latency measurement between the server and backend shell."""
        latency: int

    class Pong(BaseModel):
        """Echo back a timestamp, for the client's own latency measurement"""
        timestamp: int

    class Error(BaseModel):
        """Alert the client of an application error."""
        message: str


class WsClient(BaseModel):
    class SetName(BaseModel):
        """Set the name of the current user."""
        name: str

    class SetCursor(BaseModel):
        """Send real-time information about the user's cursor"""
        cursor: Optional[Tuple[int, int]]

    class SetFocus(BaseModel):
        """Set the currently focused shell."""
        focus: Optional[libs.Sid]                       # Unique identifier for a shell within the session.

    class Create(BaseModel):
        """Create a new shell."""
        x: int
        y: int


    class Close(BaseModel):
        """Close a specific shell."""
        shell: libs.Sid                                 # Unique identifier for a shell within the session.

    class Move(BaseModel):
        """Move a shell window to a new position and focus it."""
        shell: libs.Sid                                 # Unique identifier for a shell within the session.
        size: Optional[WsWinsize]

    class Data(BaseModel):
        """Add user data to a given shell"""
        shell: libs.Sid                                 # Unique identifier for a shell within the session.
        data: bytes
        offset: int

    class Subscribe(BaseModel):
        """Subscribe to a shell, starting at a given chunk index."""
        shell: libs.Sid                                 # Unique identifier for a shell within the session.
        chunk_num: int

    class Ping(BaseModel):
        """Send a ping to the server, for latency measurement."""
        timestamp: int

    class ServerResHello(BaseModel):
        """Response from server message, after sending the initial hello message."""
        user_id: libs.Uid                           # Unique identifier for a user within the session.
