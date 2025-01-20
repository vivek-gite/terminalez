from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class InitiateConnectionRequest(_message.Message):
    __slots__ = ("m_name",)
    M_NAME_FIELD_NUMBER: _ClassVar[int]
    m_name: str
    def __init__(self, m_name: _Optional[str] = ...) -> None: ...

class InitiateConnectionResponse(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class NewShell(_message.Message):
    __slots__ = ("shell_id", "x", "y")
    SHELL_ID_FIELD_NUMBER: _ClassVar[int]
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    shell_id: int
    x: int
    y: int
    def __init__(self, shell_id: _Optional[int] = ..., x: _Optional[int] = ..., y: _Optional[int] = ...) -> None: ...

class TerminalInput(_message.Message):
    __slots__ = ("shell_id", "data", "offset")
    SHELL_ID_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    shell_id: int
    data: str
    offset: int
    def __init__(self, shell_id: _Optional[int] = ..., data: _Optional[str] = ..., offset: _Optional[int] = ...) -> None: ...

class TerminalOutput(_message.Message):
    __slots__ = ("shell_id", "data")
    SHELL_ID_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    shell_id: int
    data: str
    def __init__(self, shell_id: _Optional[int] = ..., data: _Optional[str] = ...) -> None: ...

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
    __slots__ = ("m_name", "data", "created_shell", "closed_shell")
    M_NAME_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    CREATED_SHELL_FIELD_NUMBER: _ClassVar[int]
    CLOSED_SHELL_FIELD_NUMBER: _ClassVar[int]
    m_name: str
    data: TerminalOutput
    created_shell: NewShell
    closed_shell: int
    def __init__(self, m_name: _Optional[str] = ..., data: _Optional[_Union[TerminalOutput, _Mapping]] = ..., created_shell: _Optional[_Union[NewShell, _Mapping]] = ..., closed_shell: _Optional[int] = ...) -> None: ...

class ServerUpdate(_message.Message):
    __slots__ = ("terminal_input", "create_shell", "close_shell", "sync", "resize")
    TERMINAL_INPUT_FIELD_NUMBER: _ClassVar[int]
    CREATE_SHELL_FIELD_NUMBER: _ClassVar[int]
    CLOSE_SHELL_FIELD_NUMBER: _ClassVar[int]
    SYNC_FIELD_NUMBER: _ClassVar[int]
    RESIZE_FIELD_NUMBER: _ClassVar[int]
    terminal_input: TerminalInput
    create_shell: NewShell
    close_shell: int
    sync: SequenceNumbers
    resize: TerminalSize
    def __init__(self, terminal_input: _Optional[_Union[TerminalInput, _Mapping]] = ..., create_shell: _Optional[_Union[NewShell, _Mapping]] = ..., close_shell: _Optional[int] = ..., sync: _Optional[_Union[SequenceNumbers, _Mapping]] = ..., resize: _Optional[_Union[TerminalSize, _Mapping]] = ...) -> None: ...

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
    __slots__ = ("m_name",)
    M_NAME_FIELD_NUMBER: _ClassVar[int]
    m_name: str
    def __init__(self, m_name: _Optional[str] = ...) -> None: ...

class CloseResponse(_message.Message):
    __slots__ = ("success",)
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    def __init__(self, success: bool = ...) -> None: ...
