from typing import Dict
import zstandard

from core.comms_core.proto.identifiers import libs
from core.comms_core.proto.identifiers.libs import Sid, Uid
from core.comms_core.proto.terminalez import terminalez_pb2
from core.server_core.state_manager.session import Session, Metadata, State
from core.server_core.web.proto.ws_protocol import web_protocol_pb2

# Persist at most this many bytes of output in storage, per shell.
SHELL_CHECKPOINT_BYTES = 1 << 15

# Maximum size of a checkpoint, in bytes.
MAX_CHECKPOINT_SIZE = 1 << 22 # 4 MiB

compressor = zstandard.ZstdCompressor(level=3)
decompressor = zstandard.ZstdDecompressor(max_window_size=MAX_CHECKPOINT_SIZE)

def compress_data(data: bytes) -> bytes:
    """
    Compresses the given data using the zstandard compression algorithm.

    Args:
        data (bytes): The data to be compressed.

    Returns:
        bytes: The compressed data.
    """
    return compressor.compress(data)


def decompress_data(data: bytes) -> bytes:
    """
    Decompresses the given data using the zstandard compression algorithm.

    Args:
        data (bytes): The data to be decompressed.

    Returns:
        bytes: The decompressed data.
    """
    return decompressor.decompress(data)


async def checkpoint_capture(session: Session):
    """
    Capture the current state of a session and serialize it into a compressed format.

    This function captures the state of all active shells within a session, including their sequence numbers,
    data, chunk offsets, byte offsets, and window sizes. It then serializes this information into a protobuf
    message and returns the serialized data.

    Args:
        session (Session): The session object containing the state to be captured.

    Returns:
        bytes: The serialized and compressed session state data.

    Raises:
        ValueError: If a shell's window size is not found in the session's source.
    """
    sid: Sid = await session.counter.get_sid()
    uid: Uid = await session.counter.get_uid()
    shell_list: web_protocol_pb2.WsServer.Shells = session.source.get_latest()

    # Convert the list to a dictionary
    win_sizes: Dict[libs.Sid, web_protocol_pb2.WsWinsize] = {sid: winsize for sid, winsize in shell_list.shells.items()}

    encrypted_session_data: terminalez_pb2.EncryptedSessionData = terminalez_pb2.EncryptedSessionData()

    for shell_id, session_state in (await session.shells.read()).items():
        chunk_offset: int = session_state.chunk_offset
        byte_offset: int = session_state.byte_offset

        offset: int = 0
        stored_bytes: int = session_state.seq_num - session_state.byte_offset
        while offset < len(session_state.data) and stored_bytes > SHELL_CHECKPOINT_BYTES:
            chunk_size = len(session_state.data[offset])
            stored_bytes -= chunk_size
            chunk_offset += 1
            byte_offset += chunk_size
            offset += 1

        win_size: web_protocol_pb2.WsWinsize = win_sizes.get(shell_id, None)
        if win_size is None:
            continue
        encrypted_shell_data: terminalez_pb2.EncryptedShellData = terminalez_pb2.EncryptedShellData()
        encrypted_shell_data.seq_num = session_state.seq_num
        # Assignment not allowed for `repeated` fields in protocol message objects
        encrypted_shell_data.data.extend(session_state.data[offset:])
        encrypted_shell_data.chunk_offset = chunk_offset
        encrypted_shell_data.byte_offset = byte_offset
        encrypted_shell_data.closed = session_state.closed
        encrypted_shell_data.winsize_x = win_size.x
        encrypted_shell_data.winsize_y = win_size.y
        encrypted_shell_data.winsize_rows = win_size.rows
        encrypted_shell_data.winsize_cols = win_size.cols

        encrypted_session_data.shells[shell_id.value] = encrypted_shell_data

    encrypted_session_data.next_sid = sid.value
    encrypted_session_data.next_uid = uid.value
    encrypted_session_data.name = session.metadata.name

    serialized_data: bytes = encrypted_session_data.SerializeToString()
    return serialized_data


async def checkpoint_restore(data: bytes, session: Session):
    # Decompress the serialized protobuf message
    data = decompress_data(data)

    # Parse the protobuf message from the decompressed data
    encrypted_session_data: terminalez_pb2.EncryptedSessionData = terminalez_pb2.EncryptedSessionData()
    encrypted_session_data.ParseFromString(data)

    session.metadata = Metadata(name=encrypted_session_data.name)

    shells: Dict[libs.Sid, State] = await session.shells.read_mut()
    await session.shells.acquire_write()

    source_winsizes: web_protocol_pb2.WsServer.Shells = web_protocol_pb2.WsServer.Shells()

    for shell_id, encrypted_shell_data in encrypted_session_data.shells.items():
        shell_state = State()
        shell_state.seq_num = encrypted_shell_data.seq_num
        shell_state.data.extend(encrypted_shell_data.data)
        shell_state.chunk_offset = encrypted_shell_data.chunk_offset
        shell_state.byte_offset = encrypted_shell_data.byte_offset
        shell_state.closed = encrypted_shell_data.closed

        ws_win_size: web_protocol_pb2.WsWinsize = web_protocol_pb2.WsWinsize(
            x=encrypted_shell_data.winsize_x,
            y=encrypted_shell_data.winsize_y,
            rows=encrypted_shell_data.winsize_rows,
            cols=encrypted_shell_data.winsize_cols)
        source_winsizes.shells[shell_id].CopyFrom(ws_win_size)

        shells[Sid(value=shell_id)] = shell_state

    await session.shells.release_write()
    await session.shells.write(shells)

    await session.source.send(source_winsizes)

    await session.counter.set_sid(Sid(value=encrypted_session_data.next_sid))
    await session.counter.set_uid(Uid(value=encrypted_session_data.next_uid))

