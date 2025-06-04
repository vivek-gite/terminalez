from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class WsWinsize(_message.Message):
    __slots__ = ("x", "y", "rows", "cols")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    ROWS_FIELD_NUMBER: _ClassVar[int]
    COLS_FIELD_NUMBER: _ClassVar[int]
    x: int
    y: int
    rows: int
    cols: int
    def __init__(self, x: _Optional[int] = ..., y: _Optional[int] = ..., rows: _Optional[int] = ..., cols: _Optional[int] = ...) -> None: ...

class WsUser(_message.Message):
    __slots__ = ("name", "cursor", "focus")
    NAME_FIELD_NUMBER: _ClassVar[int]
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    FOCUS_FIELD_NUMBER: _ClassVar[int]
    name: str
    cursor: WsCursor
    focus: int
    def __init__(self, name: _Optional[str] = ..., cursor: _Optional[_Union[WsCursor, _Mapping]] = ..., focus: _Optional[int] = ...) -> None: ...

class WsCursor(_message.Message):
    __slots__ = ("x", "y")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    x: int
    y: int
    def __init__(self, x: _Optional[int] = ..., y: _Optional[int] = ...) -> None: ...

class WsServer(_message.Message):
    __slots__ = ("hello", "users", "user_diff", "shells", "chunks", "shell_latency", "pong", "error", "chat_broadcast")
    class Hello(_message.Message):
        __slots__ = ("user_id", "metadata")
        USER_ID_FIELD_NUMBER: _ClassVar[int]
        METADATA_FIELD_NUMBER: _ClassVar[int]
        user_id: int
        metadata: str
        def __init__(self, user_id: _Optional[int] = ..., metadata: _Optional[str] = ...) -> None: ...
    class Users(_message.Message):
        __slots__ = ("users",)
        class UsersEntry(_message.Message):
            __slots__ = ("key", "value")
            KEY_FIELD_NUMBER: _ClassVar[int]
            VALUE_FIELD_NUMBER: _ClassVar[int]
            key: int
            value: WsUser
            def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[WsUser, _Mapping]] = ...) -> None: ...
        USERS_FIELD_NUMBER: _ClassVar[int]
        users: _containers.MessageMap[int, WsUser]
        def __init__(self, users: _Optional[_Mapping[int, WsUser]] = ...) -> None: ...
    class UserDiff(_message.Message):
        __slots__ = ("user_id", "user", "action")
        class ActionType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
            __slots__ = ()
            JOINED: _ClassVar[WsServer.UserDiff.ActionType]
            LEFT: _ClassVar[WsServer.UserDiff.ActionType]
            CHANGED: _ClassVar[WsServer.UserDiff.ActionType]
        JOINED: WsServer.UserDiff.ActionType
        LEFT: WsServer.UserDiff.ActionType
        CHANGED: WsServer.UserDiff.ActionType
        USER_ID_FIELD_NUMBER: _ClassVar[int]
        USER_FIELD_NUMBER: _ClassVar[int]
        ACTION_FIELD_NUMBER: _ClassVar[int]
        user_id: int
        user: WsUser
        action: WsServer.UserDiff.ActionType
        def __init__(self, user_id: _Optional[int] = ..., user: _Optional[_Union[WsUser, _Mapping]] = ..., action: _Optional[_Union[WsServer.UserDiff.ActionType, str]] = ...) -> None: ...
    class Shells(_message.Message):
        __slots__ = ("shells",)
        class ShellsEntry(_message.Message):
            __slots__ = ("key", "value")
            KEY_FIELD_NUMBER: _ClassVar[int]
            VALUE_FIELD_NUMBER: _ClassVar[int]
            key: int
            value: WsWinsize
            def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[WsWinsize, _Mapping]] = ...) -> None: ...
        SHELLS_FIELD_NUMBER: _ClassVar[int]
        shells: _containers.MessageMap[int, WsWinsize]
        def __init__(self, shells: _Optional[_Mapping[int, WsWinsize]] = ...) -> None: ...
    class Chunks(_message.Message):
        __slots__ = ("sid", "index", "chunks")
        SID_FIELD_NUMBER: _ClassVar[int]
        INDEX_FIELD_NUMBER: _ClassVar[int]
        CHUNKS_FIELD_NUMBER: _ClassVar[int]
        sid: int
        index: int
        chunks: _containers.RepeatedScalarFieldContainer[bytes]
        def __init__(self, sid: _Optional[int] = ..., index: _Optional[int] = ..., chunks: _Optional[_Iterable[bytes]] = ...) -> None: ...
    class ShellLatency(_message.Message):
        __slots__ = ("latency",)
        LATENCY_FIELD_NUMBER: _ClassVar[int]
        latency: int
        def __init__(self, latency: _Optional[int] = ...) -> None: ...
    class Pong(_message.Message):
        __slots__ = ("timestamp",)
        TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        timestamp: int
        def __init__(self, timestamp: _Optional[int] = ...) -> None: ...
    class Error(_message.Message):
        __slots__ = ("message",)
        MESSAGE_FIELD_NUMBER: _ClassVar[int]
        message: str
        def __init__(self, message: _Optional[str] = ...) -> None: ...
    class ChatBroadcast(_message.Message):
        __slots__ = ("user_id", "message", "user_name", "sent_at")
        USER_ID_FIELD_NUMBER: _ClassVar[int]
        MESSAGE_FIELD_NUMBER: _ClassVar[int]
        USER_NAME_FIELD_NUMBER: _ClassVar[int]
        SENT_AT_FIELD_NUMBER: _ClassVar[int]
        user_id: int
        message: str
        user_name: str
        sent_at: int
        def __init__(self, user_id: _Optional[int] = ..., message: _Optional[str] = ..., user_name: _Optional[str] = ..., sent_at: _Optional[int] = ...) -> None: ...
    HELLO_FIELD_NUMBER: _ClassVar[int]
    USERS_FIELD_NUMBER: _ClassVar[int]
    USER_DIFF_FIELD_NUMBER: _ClassVar[int]
    SHELLS_FIELD_NUMBER: _ClassVar[int]
    CHUNKS_FIELD_NUMBER: _ClassVar[int]
    SHELL_LATENCY_FIELD_NUMBER: _ClassVar[int]
    PONG_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    CHAT_BROADCAST_FIELD_NUMBER: _ClassVar[int]
    hello: WsServer.Hello
    users: WsServer.Users
    user_diff: WsServer.UserDiff
    shells: WsServer.Shells
    chunks: WsServer.Chunks
    shell_latency: WsServer.ShellLatency
    pong: WsServer.Pong
    error: WsServer.Error
    chat_broadcast: WsServer.ChatBroadcast
    def __init__(self, hello: _Optional[_Union[WsServer.Hello, _Mapping]] = ..., users: _Optional[_Union[WsServer.Users, _Mapping]] = ..., user_diff: _Optional[_Union[WsServer.UserDiff, _Mapping]] = ..., shells: _Optional[_Union[WsServer.Shells, _Mapping]] = ..., chunks: _Optional[_Union[WsServer.Chunks, _Mapping]] = ..., shell_latency: _Optional[_Union[WsServer.ShellLatency, _Mapping]] = ..., pong: _Optional[_Union[WsServer.Pong, _Mapping]] = ..., error: _Optional[_Union[WsServer.Error, _Mapping]] = ..., chat_broadcast: _Optional[_Union[WsServer.ChatBroadcast, _Mapping]] = ...) -> None: ...

class WsClient(_message.Message):
    __slots__ = ("set_name", "set_cursor", "set_focus", "create", "close", "move", "data", "subscribe", "ping", "chat_message")
    class SetName(_message.Message):
        __slots__ = ("name",)
        NAME_FIELD_NUMBER: _ClassVar[int]
        name: str
        def __init__(self, name: _Optional[str] = ...) -> None: ...
    class SetCursor(_message.Message):
        __slots__ = ("cursor",)
        CURSOR_FIELD_NUMBER: _ClassVar[int]
        cursor: WsCursor
        def __init__(self, cursor: _Optional[_Union[WsCursor, _Mapping]] = ...) -> None: ...
    class SetFocus(_message.Message):
        __slots__ = ("shell_id",)
        SHELL_ID_FIELD_NUMBER: _ClassVar[int]
        shell_id: int
        def __init__(self, shell_id: _Optional[int] = ...) -> None: ...
    class Create(_message.Message):
        __slots__ = ("x", "y", "shell_info")
        X_FIELD_NUMBER: _ClassVar[int]
        Y_FIELD_NUMBER: _ClassVar[int]
        SHELL_INFO_FIELD_NUMBER: _ClassVar[int]
        x: int
        y: int
        shell_info: str
        def __init__(self, x: _Optional[int] = ..., y: _Optional[int] = ..., shell_info: _Optional[str] = ...) -> None: ...
    class Close(_message.Message):
        __slots__ = ("shell",)
        SHELL_FIELD_NUMBER: _ClassVar[int]
        shell: int
        def __init__(self, shell: _Optional[int] = ...) -> None: ...
    class Move(_message.Message):
        __slots__ = ("shell", "size")
        SHELL_FIELD_NUMBER: _ClassVar[int]
        SIZE_FIELD_NUMBER: _ClassVar[int]
        shell: int
        size: WsWinsize
        def __init__(self, shell: _Optional[int] = ..., size: _Optional[_Union[WsWinsize, _Mapping]] = ...) -> None: ...
    class Data(_message.Message):
        __slots__ = ("shell", "data", "offset")
        SHELL_FIELD_NUMBER: _ClassVar[int]
        DATA_FIELD_NUMBER: _ClassVar[int]
        OFFSET_FIELD_NUMBER: _ClassVar[int]
        shell: int
        data: bytes
        offset: int
        def __init__(self, shell: _Optional[int] = ..., data: _Optional[bytes] = ..., offset: _Optional[int] = ...) -> None: ...
    class Subscribe(_message.Message):
        __slots__ = ("shell", "chunk_num")
        SHELL_FIELD_NUMBER: _ClassVar[int]
        CHUNK_NUM_FIELD_NUMBER: _ClassVar[int]
        shell: int
        chunk_num: int
        def __init__(self, shell: _Optional[int] = ..., chunk_num: _Optional[int] = ...) -> None: ...
    class Ping(_message.Message):
        __slots__ = ("timestamp",)
        TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        timestamp: int
        def __init__(self, timestamp: _Optional[int] = ...) -> None: ...
    class ChatMessage(_message.Message):
        __slots__ = ("message",)
        MESSAGE_FIELD_NUMBER: _ClassVar[int]
        message: str
        def __init__(self, message: _Optional[str] = ...) -> None: ...
    SET_NAME_FIELD_NUMBER: _ClassVar[int]
    SET_CURSOR_FIELD_NUMBER: _ClassVar[int]
    SET_FOCUS_FIELD_NUMBER: _ClassVar[int]
    CREATE_FIELD_NUMBER: _ClassVar[int]
    CLOSE_FIELD_NUMBER: _ClassVar[int]
    MOVE_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    SUBSCRIBE_FIELD_NUMBER: _ClassVar[int]
    PING_FIELD_NUMBER: _ClassVar[int]
    CHAT_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    set_name: WsClient.SetName
    set_cursor: WsClient.SetCursor
    set_focus: WsClient.SetFocus
    create: WsClient.Create
    close: WsClient.Close
    move: WsClient.Move
    data: WsClient.Data
    subscribe: WsClient.Subscribe
    ping: WsClient.Ping
    chat_message: WsClient.ChatMessage
    def __init__(self, set_name: _Optional[_Union[WsClient.SetName, _Mapping]] = ..., set_cursor: _Optional[_Union[WsClient.SetCursor, _Mapping]] = ..., set_focus: _Optional[_Union[WsClient.SetFocus, _Mapping]] = ..., create: _Optional[_Union[WsClient.Create, _Mapping]] = ..., close: _Optional[_Union[WsClient.Close, _Mapping]] = ..., move: _Optional[_Union[WsClient.Move, _Mapping]] = ..., data: _Optional[_Union[WsClient.Data, _Mapping]] = ..., subscribe: _Optional[_Union[WsClient.Subscribe, _Mapping]] = ..., ping: _Optional[_Union[WsClient.Ping, _Mapping]] = ..., chat_message: _Optional[_Union[WsClient.ChatMessage, _Mapping]] = ...) -> None: ...
