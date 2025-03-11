from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class InitialConnectionRequest(_message.Message):
    __slots__ = ("m_name", "available_shells")
    M_NAME_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_SHELLS_FIELD_NUMBER: _ClassVar[int]
    m_name: str
    available_shells: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, m_name: _Optional[str] = ..., available_shells: _Optional[_Iterable[str]] = ...) -> None: ...

class InitialConnectionResponse(_message.Message):
    __slots__ = ("session_id", "url")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    URL_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    url: str
    def __init__(self, session_id: _Optional[str] = ..., url: _Optional[str] = ...) -> None: ...

class NewShell(_message.Message):
    __slots__ = ("shell_id", "x", "y", "shell_info")
    SHELL_ID_FIELD_NUMBER: _ClassVar[int]
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    SHELL_INFO_FIELD_NUMBER: _ClassVar[int]
    shell_id: int
    x: int
    y: int
    shell_info: str
    def __init__(self, shell_id: _Optional[int] = ..., x: _Optional[int] = ..., y: _Optional[int] = ..., shell_info: _Optional[str] = ...) -> None: ...

class TerminalInput(_message.Message):
    __slots__ = ("shell_id", "data", "offset")
    SHELL_ID_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    shell_id: int
    data: bytes
    offset: int
    def __init__(self, shell_id: _Optional[int] = ..., data: _Optional[bytes] = ..., offset: _Optional[int] = ...) -> None: ...

class TerminalOutput(_message.Message):
    __slots__ = ("shell_id", "data", "seq_num")
    SHELL_ID_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    SEQ_NUM_FIELD_NUMBER: _ClassVar[int]
    shell_id: int
    data: bytes
    seq_num: int
    def __init__(self, shell_id: _Optional[int] = ..., data: _Optional[bytes] = ..., seq_num: _Optional[int] = ...) -> None: ...

class SequenceNumbers(_message.Message):
    __slots__ = ("map",)
    class MapEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: int
        def __init__(self, key: _Optional[int] = ..., value: _Optional[int] = ...) -> None: ...
    MAP_FIELD_NUMBER: _ClassVar[int]
    map: _containers.ScalarMap[int, int]
    def __init__(self, map: _Optional[_Mapping[int, int]] = ...) -> None: ...

class ClientUpdate(_message.Message):
    __slots__ = ("session_id", "data", "created_shell", "closed_shell", "pong", "error")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    CREATED_SHELL_FIELD_NUMBER: _ClassVar[int]
    CLOSED_SHELL_FIELD_NUMBER: _ClassVar[int]
    PONG_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    data: TerminalOutput
    created_shell: NewShell
    closed_shell: int
    pong: int
    error: str
    def __init__(self, session_id: _Optional[str] = ..., data: _Optional[_Union[TerminalOutput, _Mapping]] = ..., created_shell: _Optional[_Union[NewShell, _Mapping]] = ..., closed_shell: _Optional[int] = ..., pong: _Optional[int] = ..., error: _Optional[str] = ...) -> None: ...

class ServerUpdate(_message.Message):
    __slots__ = ("terminal_input", "create_shell", "close_shell", "sync", "resize", "ping", "error")
    TERMINAL_INPUT_FIELD_NUMBER: _ClassVar[int]
    CREATE_SHELL_FIELD_NUMBER: _ClassVar[int]
    CLOSE_SHELL_FIELD_NUMBER: _ClassVar[int]
    SYNC_FIELD_NUMBER: _ClassVar[int]
    RESIZE_FIELD_NUMBER: _ClassVar[int]
    PING_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    terminal_input: TerminalInput
    create_shell: NewShell
    close_shell: int
    sync: SequenceNumbers
    resize: TerminalSize
    ping: int
    error: str
    def __init__(self, terminal_input: _Optional[_Union[TerminalInput, _Mapping]] = ..., create_shell: _Optional[_Union[NewShell, _Mapping]] = ..., close_shell: _Optional[int] = ..., sync: _Optional[_Union[SequenceNumbers, _Mapping]] = ..., resize: _Optional[_Union[TerminalSize, _Mapping]] = ..., ping: _Optional[int] = ..., error: _Optional[str] = ...) -> None: ...

class TerminalSize(_message.Message):
    __slots__ = ("shell_id", "rows", "cols")
    SHELL_ID_FIELD_NUMBER: _ClassVar[int]
    ROWS_FIELD_NUMBER: _ClassVar[int]
    COLS_FIELD_NUMBER: _ClassVar[int]
    shell_id: int
    rows: int
    cols: int
    def __init__(self, shell_id: _Optional[int] = ..., rows: _Optional[int] = ..., cols: _Optional[int] = ...) -> None: ...

class CloseRequest(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class CloseResponse(_message.Message):
    __slots__ = ("success",)
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    def __init__(self, success: bool = ...) -> None: ...

class EncryptedShellData(_message.Message):
    __slots__ = ("seq_num", "data", "chunk_offset", "byte_offset", "closed", "winsize_x", "winsize_y", "winsize_rows", "winsize_cols")
    SEQ_NUM_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    CHUNK_OFFSET_FIELD_NUMBER: _ClassVar[int]
    BYTE_OFFSET_FIELD_NUMBER: _ClassVar[int]
    CLOSED_FIELD_NUMBER: _ClassVar[int]
    WINSIZE_X_FIELD_NUMBER: _ClassVar[int]
    WINSIZE_Y_FIELD_NUMBER: _ClassVar[int]
    WINSIZE_ROWS_FIELD_NUMBER: _ClassVar[int]
    WINSIZE_COLS_FIELD_NUMBER: _ClassVar[int]
    seq_num: int
    data: _containers.RepeatedScalarFieldContainer[bytes]
    chunk_offset: int
    byte_offset: int
    closed: bool
    winsize_x: int
    winsize_y: int
    winsize_rows: int
    winsize_cols: int
    def __init__(self, seq_num: _Optional[int] = ..., data: _Optional[_Iterable[bytes]] = ..., chunk_offset: _Optional[int] = ..., byte_offset: _Optional[int] = ..., closed: bool = ..., winsize_x: _Optional[int] = ..., winsize_y: _Optional[int] = ..., winsize_rows: _Optional[int] = ..., winsize_cols: _Optional[int] = ...) -> None: ...

class EncryptedSessionData(_message.Message):
    __slots__ = ("shells", "next_sid", "next_uid", "name", "available_shells")
    class ShellsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: EncryptedShellData
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[EncryptedShellData, _Mapping]] = ...) -> None: ...
    SHELLS_FIELD_NUMBER: _ClassVar[int]
    NEXT_SID_FIELD_NUMBER: _ClassVar[int]
    NEXT_UID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_SHELLS_FIELD_NUMBER: _ClassVar[int]
    shells: _containers.MessageMap[int, EncryptedShellData]
    next_sid: int
    next_uid: int
    name: str
    available_shells: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, shells: _Optional[_Mapping[int, EncryptedShellData]] = ..., next_sid: _Optional[int] = ..., next_uid: _Optional[int] = ..., name: _Optional[str] = ..., available_shells: _Optional[_Iterable[str]] = ...) -> None: ...
