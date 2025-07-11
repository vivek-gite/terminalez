import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Callable, AsyncGenerator
from dataclasses import dataclass
from typing import List, Dict, Tuple

from core.comms_core.proto.identifiers import libs
from core.comms_core.utils.shutdown import Shutdown
from core.comms_core.utils.watch import WatchChannel
from core.comms_core.utils.broadcast import BroadcastChannel
from core.comms_core.utils.rw_lock import ReadWriteLock
from core.comms_core.utils.notify import Notify
from core.comms_core.utils.task_registry import task_registry

from core.comms_core.proto.terminalez import terminalez_pb2
from core.server_core.web.proto.ws_protocol import web_protocol_pb2

# maximum number of bytes of terminal output to store for each shell
SHELL_STORED_BYTES = 1 << 21  # 2 MiB

logger = logging.getLogger(__name__)

@dataclass
class Metadata:
    """Static metadata for this session."""
    name: str # The name of the host computer running the session. Format: "username@hostname"
    available_shells: List[str] # The available shells on the host computer.

    def __str__(self):
        return f"Metadata(name={self.name}, available_shells={'\n'.join(self.available_shells)})"

class State:
    """ Internal State of a single shell within a session."""

    def __init__(self):
        self.seq_num: int = 0  # Sequence number, indicating how many bytes have been received.
        self.data: List[bytes] = []  # Accumulated data from the shell.
        self.chunk_offset: int = 0  # Number of pruned data chunks before `data[0]`
        self.byte_offset: int = 0  # Number of bytes in pruned data chunks.`
        self.closed: bool = False  # Whether the shell has been closed.
        self.notify: Notify = Notify()  # Condition variable for notifying when data is available.
        self.state_lock: asyncio.Condition = asyncio.Condition()  # Condition variable for notifying when the state has changed.

class Session:
    """In-memory state of a single terminalez session."""

    def __init__(self, metadata: Metadata = None):
        self.metadata: Metadata = metadata  # metadata of this session
        self.users: ReadWriteLock[web_protocol_pb2.WsServer.Users] = ReadWriteLock(
            web_protocol_pb2.WsServer.Users())  # Metadata for currently connected users
        self.counter = libs.IdCounter()  # Counter for generating unique identifiers
        self.source = WatchChannel(
            web_protocol_pb2.WsServer.Shells())  # Watch channel source for the ordered list of open shells and sizes which is of type `List[Tuple[libs.Sid, protocol.WsWinsize]]`
        self.broadcaster = BroadcastChannel(
            max_size=64)  # Broadcast channel for sending messages to all connected clients
        self.shells: ReadWriteLock[Dict[libs.Sid, State]] = ReadWriteLock(
            {})  # In-memory state of the session with Read-write lock for accessing the session state
        self.sync_notify: Notify = Notify()  # Condition variable for notifying when the session state has changed, Triggered from metadata events when an immediate snapshot is needed.
        self.shutdown: Shutdown = Shutdown()  # Shutdown object for managing session termination, set when this session has been closed and removed
        self.buffer_message: asyncio.Queue = asyncio.Queue()  # Access the sender of the client message channel for this session
        self._last_access_time = time.time()  # The last time this session was accessed
        # Add storage for background tasks that need to be tracked and canceled during shutdown
        self.background_tasks: List[asyncio.Task] = []


    async def send_latency_measurement(self, latency: int):
        """Send a latency measurement of the data from the host machine."""
        shell_latency: web_protocol_pb2.WsServer.ShellLatency = web_protocol_pb2.WsServer.ShellLatency(latency=latency)
        await self.broadcaster.broadcast(web_protocol_pb2.WsServer(shell_latency=shell_latency))


    def last_accessed(self):
        """Return the last time this session was accessed."""
        return self._last_access_time

    def update_access_time(self) -> float:
        """Update the last time this session was accessed."""
        self._last_access_time = time.time()
        return self._last_access_time


    async def sequence_numbers(self) -> terminalez_pb2.SequenceNumbers:
        """
        Retrieve the sequence numbers for all active shells in the session.

        This method reads the current state of all shells in the session and constructs
        a `SequenceNumbers` protobuf message containing the sequence numbers of all shells
        that are not closed.

        The `seq_num` represents the sequence number, indicating how many bytes have been received
        for a particular shell.

        Returns:
            terminalez_pb2.SequenceNumbers: A protobuf message containing the sequence numbers
            of all active shells.
        """
        shells: Dict[libs.Sid, State] = await self.shells.read()
        sequence_numbers = terminalez_pb2.SequenceNumbers()

        for key, value in shells.items():
            if not value.closed:
                sequence_numbers.map[key.value] = value.seq_num

        return sequence_numbers

    def subscribe_broadcast(self) -> asyncio.Queue[web_protocol_pb2.WsServer]:
        """Receive a notification on broadcast message events."""
        return self.broadcaster.subscribe()

    def subscribe_shells(self) -> WatchChannel.WatchReceiver:
        """Receive a notification every time the set of shells is changed."""
        return self.source.subscribe()

    @staticmethod
    async def notification_wait(notify: Notify):
        await notify.wait()

    async def subscribe_chunks(self, sid: libs.Sid, chunk_num: int) -> AsyncGenerator[Tuple[int, List[bytes]], None]:
        """
        Subscribe to chunks of data for a given shell ID (sid) starting from a specific chunk number (chunk_num).

        This coroutine continuously yields chunks of data as they become available or until the shell is closed or the session is terminated.

        Args:
            sid (libs.Sid): The unique identifier of the shell.
            chunk_num (int): The starting chunk number to subscribe from.

        Yields:
            Tuple[int, List[bytes]]: A tuple containing the sequence number and a list of data chunks.
        """
        # Create a context for any tasks created by this subscription
        shell_context = f"shell_{sid.value}_chunks"
        
        try:
            while True:
                shells: Dict[libs.Sid, State] = await self.shells.read()
                shell_state = shells.get(sid)
                
                if shell_state is None or shell_state.closed:
                    logger.debug(f"Shell {sid.value} not found or closed, ending chunk subscription")
                    return

                logger.debug(f"Subscribing to shell {sid.value}")

                seq_num = shell_state.byte_offset
                chunks = []
                current_chunks = shell_state.chunk_offset + len(shell_state.data)
                
                if chunk_num < current_chunks:
                    start = max(0, chunk_num - shell_state.chunk_offset)
                    seq_num += sum(len(x) for x in shell_state.data[:start])
                    chunks = shell_state.data[start:]
                    chunk_num = current_chunks

                if chunks:
                    yield seq_num, chunks

                try:
                    # Create tasks with proper tracking
                    notify_task = task_registry.create_task(
                        self.notification_wait(shell_state.notify),
                        name=f"notify_wait_{sid.value}",
                        context=shell_context
                    )

                    terminate_task = task_registry.create_task(
                        self.terminated(),
                        name=f"termination_wait_{sid.value}",
                        context=shell_context
                    )

                    done, pending = await asyncio.wait(
                        [notify_task, terminate_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    # Cancel pending tasks immediately
                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

                    # Process completed task
                    completed_task = done.pop()
                    logger.debug(f"subscribe_chunks completed task: {completed_task.get_name()}")

                    # Check if we need to terminate
                    if completed_task.get_name().startswith("termination"):
                        if completed_task.result() == "terminated":
                            logger.debug(f"Session terminated, ending chunk subscription for shell {sid.value}")
                            return

                except asyncio.CancelledError:
                    logger.info(f"Shell chunk subscription for {sid.value} was cancelled")
                    return
                except Exception as e:
                    logger.exception(f"Error in subscribe_chunks for shell {sid.value}: {e}")
                    # Continue the loop unless it's a critical error
                    if "critical" in str(e).lower():
                        return
        finally:
            # Clean up any tasks created for this shell's chunk subscription
            try:
                await task_registry.cancel_context_tasks(shell_context)
            except Exception as e:
                logger.warning(f"Error cleaning up context tasks for shell {sid.value}: {e}")

    async def add_shell(self, sid: libs.Sid, location: Tuple[int, int]):
        """Add a new shell to the session."""
        shells: Dict[libs.Sid, State] = await self.shells.read()
        if sid in shells:
            raise ValueError(f"Shell already exists with id={sid}")
        await self.shells.acquire_write()
        shells[sid] = State()
        await self.shells.release_write()

        shell_list: web_protocol_pb2.WsServer.Shells = self.source.get_latest()

        # TODO: Once have a better understanding of the shell_list, update the below code
        # As in the sshx->session.rs->add_shell-> we are only sending the notification of the new shell not the whole shell_list
        shell_list.shells[sid.value].CopyFrom(web_protocol_pb2.WsWinsize(x=location[0], y=location[1], rows=24, cols=80))

        await self.source.send(shell_list)

        await self.sync_now()

    async def close_shell(self, sid: libs.Sid):
        """ Close a shell in the session."""
        shells: Dict[libs.Sid, State] = await self.shells.read()
        shell = shells.get(sid)
        
        if shell is None:
            logger.info(f"Cannot close shell with id={sid}, does not exist")
            return
            
        if shell.closed:
            logger.debug(f"Shell {sid.value} is already closed")
            return

        # Mark shell as closed and notify waiting consumers
        async with shell.state_lock:
            shell.closed = True
        await shell.notify.notify_all()

        try:
            shells = await self.shells.read()  # Get fresh reference

            # Remove shell from tracking
            await self.shells.acquire_write()

            if sid in shells:
                del shells[sid]
        finally:
            await self.shells.release_write()

        # Update shells list for clients
        updated_shells: web_protocol_pb2.WsServer.Shells = self.source.get_latest()
        await self.source.flush_receivers()

        if sid.value in updated_shells.shells:
            del updated_shells.shells[sid.value]

        await self.source.send(updated_shells)
        await self.sync_now()

    async def add_data(self, sid: libs.Sid, data: bytes, seq: int):
        """
        Add data to a shell with optimized sequence number handling.

        This method efficiently handles different sequence number scenarios:
        1. Future packets with sequence numbers ahead of current state
        2. Overlapping packets that contain some new data
        3. Old data that can be safely ignored

        Args:
            sid (libs.Sid): The shell ID to add data to
            data (bytes): The data to add
            seq (int): The sequence number of the data
        """
        shells: Dict[libs.Sid, State] = await self.shells.read()
        shell: State = shells.get(sid)

        if not shell:
            logger.warning(f"Attempted to add data to non-existent shell {sid.value}")
            return

        data_len = len(data)
        if data_len == 0:
            return  # No data to process

        logger.debug(f"Adding data to shell {sid.value}, seq={seq}, shell.seq_num={shell.seq_num}, len(data)={data_len}")

        async with shell.state_lock:
            data_end = seq + data_len

            # Case 1: Completely old data - ignore
            if data_end <= shell.seq_num:
                logger.debug(f"Ignoring old data: seq={seq}, len={data_len}, current seq_num={shell.seq_num}")
                return

            # Case 2: Future packet or partially overlapping data
            if seq > shell.seq_num:
                # Future packet - accept as-is (gap handling)
                logger.debug(f"Sequence gap detected: received seq={seq}, current seq_num={shell.seq_num}. Accepting new data.")
                shell.data.append(data)
                shell.seq_num = data_end
            else:
                # Partially overlapping data - extract new portion
                start_offset = shell.seq_num - seq
                if start_offset < data_len:
                    new_data = data[start_offset:]
                    shell.data.append(new_data)
                    shell.seq_num += len(new_data)
                else:
                    # No new data
                    return

            # Manage storage limits efficiently
            self._manage_shell_storage(shell)

            # Notify waiting consumers
            await shell.notify.notify_all()

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Completed add_data for shell {sid.value}, new seq_num={shell.seq_num}")

    @staticmethod
    def _manage_shell_storage(shell: State):
        """Efficiently manage shell storage by pruning old data chunks."""
        stored_bytes = shell.seq_num - shell.byte_offset
        if stored_bytes <= SHELL_STORED_BYTES:
            return

        offset = 0
        bytes_to_remove = stored_bytes - SHELL_STORED_BYTES

        # Calculate how many chunks to remove
        while offset < len(shell.data) and bytes_to_remove > 0:
            chunk_size = len(shell.data[offset])
            if chunk_size <= bytes_to_remove:
                bytes_to_remove -= chunk_size
                shell.chunk_offset += 1
                shell.byte_offset += chunk_size
                offset += 1
            else:
                break
        # Remove pruned chunks in batch
        if offset > 0:
            del shell.data[:offset]

    async def list_users(self) -> web_protocol_pb2.WsServer.Users:
        """List all users in the session."""
        users_data: web_protocol_pb2.WsServer.Users = await self.users.read()
        return users_data

    async def update_users(self, uid: libs.Uid, callback: Callable[[web_protocol_pb2.WsUser], None]):
        """ Update a user in the session by ID, applying a callback to the user object and broadcasting the change."""
        users_data: web_protocol_pb2.WsServer.Users = await self.users.read()
        
        # Check if user exists before acquiring write lock
        if uid.value not in users_data.users:
            raise KeyError(f"cannot update user with id={uid}, does not exist")

        try:
            # Re-check after acquiring lock in case of concurrent modifications
            users_data = await self.users.read()
            if uid.value not in users_data.users:
                raise KeyError(f"cannot update user with id={uid}, does not exist")
            
            await self.users.acquire_write()

            ws_user: web_protocol_pb2.WsUser = users_data.users.get(uid.value)
            callback(ws_user)
            users_data.users[uid.value].CopyFrom(ws_user)

            # Broadcast the details of the updated user to all clients
            user_diff = web_protocol_pb2.WsServer.UserDiff(
                    user_id=uid.value,
                    user=ws_user,
                    action=web_protocol_pb2.WsServer.UserDiff.ActionType.CHANGED)
            await self.broadcaster.broadcast(web_protocol_pb2.WsServer(user_diff=user_diff))
        finally:
            await self.users.release_write()

    async def send_chat_message(self, uid: libs.Uid, message: str):
        """
        Send a chat message from a user to all clients in the session.

        Args:
            uid (libs.Uid): The unique identifier of the user sending the message.
            message (str): The chat message to send.

        Raises:
            KeyError: If the user with the given UID does not exist.
        """
        users_data: web_protocol_pb2.WsServer.Users = await self.users.read()
        if uid.value not in users_data.users:
            raise KeyError(f"cannot send message from user with id={uid}, does not exist")

        now = datetime.now(timezone.utc)
        timestamp = int(now.timestamp())

        chat_message = web_protocol_pb2.WsServer.ChatBroadcast(
            user_id=uid.value,
            message=message,
            user_name=users_data.users[uid.value].name,
            sent_at=timestamp
        )
        await self.broadcaster.broadcast(web_protocol_pb2.WsServer(chat_broadcast=chat_message))


    async def user_scope(self, uid: libs.Uid) -> None:
        """
        Ensure a user with the given UID exists in the session. If the user does not exist, create a new user and broadcast the change.

        Args:
            uid (libs.Uid): The unique identifier of the user.

        Raises:
            ValueError: If a user with the given UID already exists.
        """
        users_data: web_protocol_pb2.WsServer.Users = await self.users.read()
        match users_data.users.get(uid.value):
            case None:
                await self.users.acquire_write()
                new_user = web_protocol_pb2.WsUser(
                    name=f"User {uid.value}"
                )
                users_data.users[uid.value].CopyFrom(new_user)

                await self.users.release_write()

                user_diff = web_protocol_pb2.WsServer.UserDiff(
                        user_id=uid.value,
                        user=new_user,
                        action=web_protocol_pb2.WsServer.UserDiff.ActionType.JOINED)

                await self.broadcaster.broadcast(web_protocol_pb2.WsServer(user_diff=user_diff))
            case _:
                raise ValueError(f"cannot add user with id={uid}, already exists")


    async def remove_user(self, uid: libs.Uid):
        users_data: web_protocol_pb2.WsServer.Users = await self.users.read()

        match users_data.users.get(uid.value):
            case None:
                logger.info(f"Invariant violation: removed user with id={uid} does not exist")
            case user:
                await self.users.acquire_write()
                try:
                    del users_data.users[uid.value]

                    user_diff = web_protocol_pb2.WsServer.UserDiff(user_id=uid.value,
                                                           user=user,
                                                           action=web_protocol_pb2.WsServer.UserDiff.ActionType.LEFT)
                    await self.broadcaster.broadcast(web_protocol_pb2.WsServer(user_diff=user_diff))
                finally:
                    await self.users.release_write()



    async def move_shell(self, sid: libs.Sid, winsize: web_protocol_pb2.WsWinsize):
        """
        Change the size of a terminal, notifying clients if necessary

        Args:
            sid (libs.Sid): The unique identifier of the shell to move.
            winsize (web_protocol_pb2.WsWinsize): The new window size for the shell.

        Raises:
            ValueError: If the shell with the given ID does not exist.
        """

        shells: Dict[libs.Sid, State] = await self.shells.read()
        # if sid not in shells:
        #     raise ValueError(f"Shell does not exists with id={sid}")
        await self.shells.acquire_write()
        sources: web_protocol_pb2.WsServer.Shells = self.source.get_latest()

        if sid in shells:
            # Update the existing shell's window size
            sources.shells[sid.value].CopyFrom(winsize)

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
        session_id = getattr(self.metadata, 'name', 'unknown')
        logger.info(f"Shutting down session: {session_id}")

        # First, use task_registry to cancel any tasks associated with this session
        try:
            # Find all contexts that might be related to this session
            contexts_to_clean = []
            for context in task_registry.get_all_contexts():
                # If the context name includes the session ID or starts with "shell_"
                if (session_id != 'unknown' and session_id in context) or context.startswith("shell_"):
                    contexts_to_clean.append(context)
            
            # Cancel tasks in each relevant context
            for context in contexts_to_clean:
                task_count = await task_registry.cancel_context_tasks(context)
                if task_count > 0:
                    logger.info(f"Cancelled {task_count} tasks in context {context}")
        except Exception as e:
            logger.error(f"Error cancelling tasks during session shutdown: {e}")
        
        # Also cancel any legacy tracked tasks
        if hasattr(self, 'background_tasks') and self.background_tasks:
            logger.info(f"Cancelling {len(self.background_tasks)} legacy background tasks for session")
            for task in self.background_tasks:
                if not task.done() and not task.cancelled():
                    task.cancel()
            
            # Wait for all tasks to complete their cancellation with a timeout
            try:
                await asyncio.wait(self.background_tasks, timeout=5.0)
            except Exception as e:
                logger.warning(f"Error waiting for legacy tasks to cancel: {e}")

        # Finally, shut down the session
        await self.shutdown.shutdown()
