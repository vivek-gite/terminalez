import asyncio
from typing import Callable
from dataclasses import dataclass
from typing import List, Dict, Tuple

from core.comms_core.proto.identifiers import libs
from core.comms_core.utils.shutdown import Shutdown
from core.server_core.web import protocol
from core.comms_core.utils.watch import WatchChannel
from core.comms_core.utils.broadcast import BroadcastChannel
from core.comms_core.utils.rw_lock import ReadWriteLock
from core.comms_core.utils.notify import Notify

from core.comms_core.proto.terminalez import terminalez_pb2
from core.server_core.web.protocol import WsWinsize, WsUser, WsServer

# maximum number of bytes of terminal output to store for each shell
SHELL_STORED_BYTES = 1 << 21  # 2 MiB


@dataclass
class Metadata:
    """Static metadata for this session."""
    name: str


class State:
    """ Internal State of a single shell within a session."""

    def __int__(self):
        self.seq_num: int = 0  # Sequence number, indicating how many bytes have been received.
        self.data: List[bytes] = []  # Accumulated data from the shell.
        self.chunk_offset: int = 0  # Number of pruned data chunks before `data[0]`
        self.byte_offset: int = 0  # Number of bytes in pruned data chunks.`
        self.closed: bool = False  # Whether the shell has been closed.
        self.notify: Notify = Notify()  # Condition variable for notifying when data is available.
        self.state_lock: asyncio.Condition = asyncio.Condition()  # Condition variable for notifying when the state has changed.



class Session:
    """In-memory state of a single terminalez session."""

    def __init__(self, metadata: Metadata):
        self.metadata: Metadata = metadata  # metadata of this session
        self.users: ReadWriteLock(Dict[libs.Uid, protocol.WsUser]) = ReadWriteLock(
            {})  # Metadata for currently connected users
        self.counter = libs.IdCounter()  # Counter for generating unique identifiers
        self.source = WatchChannel(
            [])  # Watch channel source for the ordered list of open shells and sizes which is of type `List[Tuple[libs.Sid, protocol.WsWinsize]]`
        self.broadcaster = BroadcastChannel(
            max_size=64)  # Broadcast channel for sending messages to all connected clients
        self.shells: ReadWriteLock(Dict[libs.Sid, State]) = ReadWriteLock(
            {})  # In-memory state of the session with Read-write lock for accessing the session state
        self.sync_notify: Notify = Notify()  # Condition variable for notifying when the session state has changed, Triggered from metadata events when an immediate snapshot is needed.
        self.shutdown: Shutdown = Shutdown()  # Shutdown object for managing session termination, set when this session has been closed and removed
        self.buffer_message: asyncio.Queue = asyncio.Queue()  # Access the sender of the client message channel for this session

    async def sequence_numbers(self) -> terminalez_pb2.SequenceNumbers:
        shells: Dict[libs.Sid, State] = await self.shells.read()
        sequence_numbers = terminalez_pb2.SequenceNumbers()

        for key, value in shells.items():
            if not value.closed:
                sequence_numbers.map[key.value] = value.seq_num

        return sequence_numbers

    def subscribe_broadcast(self) -> asyncio.Queue:
        """Receive a notification on broadcast message events."""
        return self.broadcaster.subscribe()

    def subscribe_shells(self) -> WatchChannel.WatchReceiver:
        """Receive a notification every time the set of shells is changed."""
        return self.source.subscribe()

    async def notification_wait(self, condition):
        async with condition:
            await condition.wait()

    async def subscribe_chunks(self, sid: libs.Sid, chunk_num: int):
        """
        Subscribe to chunks of data for a given shell ID (sid) starting from a specific chunk number (chunk_num).

        This coroutine continuously yields chunks of data as they become available or until the shell is closed or the session is terminated.

        Args:
            sid (libs.Sid): The unique identifier of the shell.
            chunk_num (int): The starting chunk number to subscribe from.

        Yields:
            Tuple[int, List[bytes]]: A tuple containing the sequence number and a list of data chunks.
        """

        while True:
            shells: Dict[libs.Sid, State] = await self.shells.read()
            match shells.get(sid):
                case None:
                    return
                case state:
                    if state.closed:
                        return
                    shell: State = state

            seq_num = shell.byte_offset
            chunks = []
            current_chunks = shell.chunk_offset + len(shell.data)
            if chunk_num < current_chunks:
                start = max(0, chunk_num - shell.chunk_offset)
                seq_num += sum(len(x) for x in shell.data[:start])
                chunks = shell.data[start:]
                chunk_num = current_chunks

            if len(chunks) > 0:
                yield seq_num, chunks

            done, pending = await asyncio.wait([
                asyncio.create_task(self.notification_wait(shell.notify)),
                asyncio.create_task(self.terminated())],
                return_when=asyncio.FIRST_COMPLETED)

            if done.pop().result() == "terminated":
                return

    async def add_shell(self, sid: libs.Sid, location: (int, int)):
        """Add a new shell to the session."""
        shells: Dict[libs.Sid, State] = await self.shells.read_mut()
        if sid in shells:
            raise ValueError(f"Shell already exists with id={sid}")
        await self.shells.acquire_write()
        shells[sid] = State()
        await self.shells.release_write()

        shell_list: List[Tuple[libs.Sid, WsWinsize]] = self.source.get_latest()
        shell_list.append((sid, WsWinsize(x=location[0], y=location[1])))
        await self.source.send(shell_list)

        await self.sync_now()

    async def close_shell(self, sid: libs.Sid):
        """ Close a shell in the session."""
        shells: Dict[libs.Sid, State] = await self.shells.read_mut()
        match shells.get(sid):
            case None:
                raise KeyError(f"cannot close shell with id={sid}, does not exist")
            case state if not state.closed:
                async with state.state_lock:
                    state.closed = True

                state.notify.notify_all()

        source = list(filter(lambda t: t[0] != sid, self.source.get_latest()))
        await self.source.send(source)

        await self.sync_now()

    async def add_data(self, sid: libs.Sid, data: bytes, seq: int):
        shells: Dict[libs.Sid, State] = await self.shells.read_mut()
        shell: State = shells.get(sid)

        async with shell.state_lock:
            if seq <= shell.seq_num and (seq + len(data) > shell.seq_num):
                start = shell.seq_num - seq
                segment = data[start:]
                shell.seq_num += len(segment)
                shell.data.append(segment)

                stored_bytes = shell.seq_num - shell.byte_offset
                if stored_bytes > SHELL_STORED_BYTES:
                    offset = 0
                    while offset < len(shell.data) and stored_bytes > SHELL_STORED_BYTES:
                        chunk_size = len(shell.data[offset])
                        stored_bytes -= chunk_size
                        shell.chunk_offset += 1
                        shell.byte_offset += chunk_size
                        offset += 1

                    del shell.data[:offset]

                # Notify any waiting consumers that new data is available
                await shell.notify.notify_all()

    async def list_users(self) -> List[Tuple[libs.Uid, WsUser]]:
        """List all users in the session."""
        users: Dict[libs.Uid, WsUser] = await self.users.read_mut()
        return list(users.items())

    async def update_users(self, uid: libs.Uid, callback: Callable[[WsUser], None]):
        """ Update a user in the session by ID, applying a callback to the user object and broadcasting the change."""
        users: Dict[libs.Uid, WsUser] = await self.users.read_mut()
        await self.users.acquire_write()

        if uid in users:
            user = users[uid]
            callback(user)

            await self.broadcaster.broadcast(WsServer.UserDiff(user_id=uid, user=user))
            await self.users.release_write()
        else:
            raise KeyError(f"cannot update user with id={uid}, does not exist")

    async def user_scope(self, uid: libs.Uid) -> None:
        """
        Ensure a user with the given UID exists in the session. If the user does not exist, create a new user and broadcast the change.

        Args:
            uid (libs.Uid): The unique identifier of the user.

        Raises:
            ValueError: If a user with the given UID already exists.
        """
        users: Dict[libs.Uid, WsUser] = await self.users.read_mut()
        match users.get(uid):
            case None:
                await self.users.acquire_write()
                new_user = WsUser(
                    name=f"User {uid}",
                    cursor=None,
                    focus=None
                )
                users[uid] = new_user
                await self.users.release_write()
                await self.broadcaster.broadcast(WsServer.UserDiff(user_id=uid, user=new_user))

            case _:
                raise ValueError(f"cannot add user with id={uid}, already exists")

    async def remove_user(self, uid: libs.Uid):
        users: Dict[libs.Uid, WsUser] = await self.users.read_mut()

        match users.get(uid):
            case None:
                print(f"Invariant violation: removed user with id={uid} does not exist")
            case user:
                await self.users.acquire_write()
                try:
                    del users[uid]
                    await self.broadcaster.broadcast(WsServer.UserDiff(user_id=uid, user=user))
                finally:
                    await self.users.release_write()



    async def move_shell(self, sid: libs.Sid, winsize: WsWinsize):
        """
        Change the size of a terminal, notifying clients if necessary

        Args:
            sid (libs.Sid): The unique identifier of the shell to move.
            winsize (WsWinsize): The new window size for the shell.

        Raises:
            ValueError: If the shell with the given ID does not exist.
        """

        shells: Dict[libs.Sid, State] = await self.shells.read_mut()
        if sid not in shells:
            raise ValueError(f"Shell does not exists with id={sid}")
        await self.shells.acquire_write()
        sources = self.source.get_latest()
        idx = -1
        for source in range(len(sources)):
            if sources[source][0] == sid:
                idx = source
                break
        if idx != -1:
            sources[idx] = (sid, winsize)
            await self.source.send(sources)
        await self.shells.release_write()


    async def sync_now(self):
        """
        Mark the session as requiring an immediate storage sync into the redis server.

        This is needed for consistency when creating new shells, removing old
        shells, or updating the ID counter. If these operations are lost in a
        server restart, then the snapshot that contains them would be invalid
        compared to the current backend client state.

        Note that it is not necessary to do this all the time though, since that
        would put too much pressure on the database. Lost terminal data is
        already re-synchronized periodically.
        """
        await self.sync_notify.notify_n(n=1)

    async def sync_now_wait(self):
        """ Resolves when the session has been marked for an immediate sync. """
        await self.sync_notify.wait()

    async def terminated(self):
        """Wait until the session is terminated."""
        await self.shutdown.wait()
        return "terminated"

    async def shutdown_session(self):
        """Send a termination signal to exit this session."""
        await self.shutdown.shutdown()
