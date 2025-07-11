# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: web_protocol.proto
# Protobuf Python Version: 5.29.0
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    5,
    29,
    0,
    '',
    'web_protocol.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x12web_protocol.proto\x12\x0bws_protocol\"=\n\tWsWinsize\x12\t\n\x01x\x18\x01 \x01(\x05\x12\t\n\x01y\x18\x02 \x01(\x05\x12\x0c\n\x04rows\x18\x03 \x01(\x05\x12\x0c\n\x04\x63ols\x18\x04 \x01(\x05\"k\n\x06WsUser\x12\x0c\n\x04name\x18\x01 \x01(\t\x12*\n\x06\x63ursor\x18\x02 \x01(\x0b\x32\x15.ws_protocol.WsCursorH\x00\x88\x01\x01\x12\x12\n\x05\x66ocus\x18\x03 \x01(\x05H\x01\x88\x01\x01\x42\t\n\x07_cursorB\x08\n\x06_focus\" \n\x08WsCursor\x12\t\n\x01x\x18\x01 \x01(\x05\x12\t\n\x01y\x18\x02 \x01(\x05\"\xda\t\n\x08WsServer\x12,\n\x05hello\x18\x01 \x01(\x0b\x32\x1b.ws_protocol.WsServer.HelloH\x00\x12,\n\x05users\x18\x02 \x01(\x0b\x32\x1b.ws_protocol.WsServer.UsersH\x00\x12\x33\n\tuser_diff\x18\x03 \x01(\x0b\x32\x1e.ws_protocol.WsServer.UserDiffH\x00\x12.\n\x06shells\x18\x04 \x01(\x0b\x32\x1c.ws_protocol.WsServer.ShellsH\x00\x12.\n\x06\x63hunks\x18\x05 \x01(\x0b\x32\x1c.ws_protocol.WsServer.ChunksH\x00\x12;\n\rshell_latency\x18\x06 \x01(\x0b\x32\".ws_protocol.WsServer.ShellLatencyH\x00\x12*\n\x04pong\x18\x07 \x01(\x0b\x32\x1a.ws_protocol.WsServer.PongH\x00\x12,\n\x05\x65rror\x18\x08 \x01(\x0b\x32\x1b.ws_protocol.WsServer.ErrorH\x00\x12=\n\x0e\x63hat_broadcast\x18\t \x01(\x0b\x32#.ws_protocol.WsServer.ChatBroadcastH\x00\x1a\x45\n\x05Hello\x12\x0f\n\x07user_id\x18\x01 \x01(\x05\x12\x11\n\thost_name\x18\x02 \x01(\t\x12\x18\n\x10\x61vailable_shells\x18\x03 \x03(\t\x1a\x81\x01\n\x05Users\x12\x35\n\x05users\x18\x01 \x03(\x0b\x32&.ws_protocol.WsServer.Users.UsersEntry\x1a\x41\n\nUsersEntry\x12\x0b\n\x03key\x18\x01 \x01(\x05\x12\"\n\x05value\x18\x02 \x01(\x0b\x32\x13.ws_protocol.WsUser:\x02\x38\x01\x1a\xba\x01\n\x08UserDiff\x12\x0f\n\x07user_id\x18\x01 \x01(\x05\x12!\n\x04user\x18\x02 \x01(\x0b\x32\x13.ws_protocol.WsUser\x12>\n\x06\x61\x63tion\x18\x03 \x01(\x0e\x32).ws_protocol.WsServer.UserDiff.ActionTypeH\x00\x88\x01\x01\"/\n\nActionType\x12\n\n\x06JOINED\x10\x00\x12\x08\n\x04LEFT\x10\x01\x12\x0b\n\x07\x43HANGED\x10\x02\x42\t\n\x07_action\x1a\x89\x01\n\x06Shells\x12\x38\n\x06shells\x18\x01 \x03(\x0b\x32(.ws_protocol.WsServer.Shells.ShellsEntry\x1a\x45\n\x0bShellsEntry\x12\x0b\n\x03key\x18\x01 \x01(\x05\x12%\n\x05value\x18\x02 \x01(\x0b\x32\x16.ws_protocol.WsWinsize:\x02\x38\x01\x1a\x34\n\x06\x43hunks\x12\x0b\n\x03sid\x18\x01 \x01(\x05\x12\r\n\x05index\x18\x02 \x01(\x05\x12\x0e\n\x06\x63hunks\x18\x03 \x03(\x0c\x1a\x1f\n\x0cShellLatency\x12\x0f\n\x07latency\x18\x01 \x01(\x05\x1a\x19\n\x04Pong\x12\x11\n\ttimestamp\x18\x01 \x01(\x03\x1a\x18\n\x05\x45rror\x12\x0f\n\x07message\x18\x01 \x01(\t\x1aU\n\rChatBroadcast\x12\x0f\n\x07user_id\x18\x01 \x01(\x05\x12\x0f\n\x07message\x18\x02 \x01(\t\x12\x11\n\tuser_name\x18\x03 \x01(\t\x12\x0f\n\x07sent_at\x18\x04 \x01(\x03\x42\x10\n\x0eserver_message\"\xaf\x07\n\x08WsClient\x12\x31\n\x08set_name\x18\x01 \x01(\x0b\x32\x1d.ws_protocol.WsClient.SetNameH\x00\x12\x35\n\nset_cursor\x18\x02 \x01(\x0b\x32\x1f.ws_protocol.WsClient.SetCursorH\x00\x12\x33\n\tset_focus\x18\x03 \x01(\x0b\x32\x1e.ws_protocol.WsClient.SetFocusH\x00\x12.\n\x06\x63reate\x18\x04 \x01(\x0b\x32\x1c.ws_protocol.WsClient.CreateH\x00\x12,\n\x05\x63lose\x18\x05 \x01(\x0b\x32\x1b.ws_protocol.WsClient.CloseH\x00\x12*\n\x04move\x18\x06 \x01(\x0b\x32\x1a.ws_protocol.WsClient.MoveH\x00\x12*\n\x04\x64\x61ta\x18\x07 \x01(\x0b\x32\x1a.ws_protocol.WsClient.DataH\x00\x12\x34\n\tsubscribe\x18\x08 \x01(\x0b\x32\x1f.ws_protocol.WsClient.SubscribeH\x00\x12*\n\x04ping\x18\t \x01(\x0b\x32\x1a.ws_protocol.WsClient.PingH\x00\x12\x39\n\x0c\x63hat_message\x18\n \x01(\x0b\x32!.ws_protocol.WsClient.ChatMessageH\x00\x1a\x17\n\x07SetName\x12\x0c\n\x04name\x18\x01 \x01(\t\x1a\x32\n\tSetCursor\x12%\n\x06\x63ursor\x18\x01 \x01(\x0b\x32\x15.ws_protocol.WsCursor\x1a\x1c\n\x08SetFocus\x12\x10\n\x08shell_id\x18\x01 \x01(\x05\x1a\x32\n\x06\x43reate\x12\t\n\x01x\x18\x01 \x01(\x05\x12\t\n\x01y\x18\x02 \x01(\x05\x12\x12\n\nshell_info\x18\x03 \x01(\t\x1a\x16\n\x05\x43lose\x12\r\n\x05shell\x18\x01 \x01(\x05\x1aI\n\x04Move\x12\r\n\x05shell\x18\x01 \x01(\x05\x12)\n\x04size\x18\x02 \x01(\x0b\x32\x16.ws_protocol.WsWinsizeH\x00\x88\x01\x01\x42\x07\n\x05_size\x1a\x33\n\x04\x44\x61ta\x12\r\n\x05shell\x18\x01 \x01(\x05\x12\x0c\n\x04\x64\x61ta\x18\x02 \x01(\x0c\x12\x0e\n\x06offset\x18\x03 \x01(\x05\x1a-\n\tSubscribe\x12\r\n\x05shell\x18\x01 \x01(\x05\x12\x11\n\tchunk_num\x18\x02 \x01(\x05\x1a\x19\n\x04Ping\x12\x11\n\ttimestamp\x18\x01 \x01(\x03\x1a\x1e\n\x0b\x43hatMessage\x12\x0f\n\x07message\x18\x01 \x01(\tB\x10\n\x0e\x63lient_messageb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'web_protocol_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_WSSERVER_USERS_USERSENTRY']._loaded_options = None
  _globals['_WSSERVER_USERS_USERSENTRY']._serialized_options = b'8\001'
  _globals['_WSSERVER_SHELLS_SHELLSENTRY']._loaded_options = None
  _globals['_WSSERVER_SHELLS_SHELLSENTRY']._serialized_options = b'8\001'
  _globals['_WSWINSIZE']._serialized_start=35
  _globals['_WSWINSIZE']._serialized_end=96
  _globals['_WSUSER']._serialized_start=98
  _globals['_WSUSER']._serialized_end=205
  _globals['_WSCURSOR']._serialized_start=207
  _globals['_WSCURSOR']._serialized_end=239
  _globals['_WSSERVER']._serialized_start=242
  _globals['_WSSERVER']._serialized_end=1484
  _globals['_WSSERVER_HELLO']._serialized_start=709
  _globals['_WSSERVER_HELLO']._serialized_end=778
  _globals['_WSSERVER_USERS']._serialized_start=781
  _globals['_WSSERVER_USERS']._serialized_end=910
  _globals['_WSSERVER_USERS_USERSENTRY']._serialized_start=845
  _globals['_WSSERVER_USERS_USERSENTRY']._serialized_end=910
  _globals['_WSSERVER_USERDIFF']._serialized_start=913
  _globals['_WSSERVER_USERDIFF']._serialized_end=1099
  _globals['_WSSERVER_USERDIFF_ACTIONTYPE']._serialized_start=1041
  _globals['_WSSERVER_USERDIFF_ACTIONTYPE']._serialized_end=1088
  _globals['_WSSERVER_SHELLS']._serialized_start=1102
  _globals['_WSSERVER_SHELLS']._serialized_end=1239
  _globals['_WSSERVER_SHELLS_SHELLSENTRY']._serialized_start=1170
  _globals['_WSSERVER_SHELLS_SHELLSENTRY']._serialized_end=1239
  _globals['_WSSERVER_CHUNKS']._serialized_start=1241
  _globals['_WSSERVER_CHUNKS']._serialized_end=1293
  _globals['_WSSERVER_SHELLLATENCY']._serialized_start=1295
  _globals['_WSSERVER_SHELLLATENCY']._serialized_end=1326
  _globals['_WSSERVER_PONG']._serialized_start=1328
  _globals['_WSSERVER_PONG']._serialized_end=1353
  _globals['_WSSERVER_ERROR']._serialized_start=1355
  _globals['_WSSERVER_ERROR']._serialized_end=1379
  _globals['_WSSERVER_CHATBROADCAST']._serialized_start=1381
  _globals['_WSSERVER_CHATBROADCAST']._serialized_end=1466
  _globals['_WSCLIENT']._serialized_start=1487
  _globals['_WSCLIENT']._serialized_end=2430
  _globals['_WSCLIENT_SETNAME']._serialized_start=1997
  _globals['_WSCLIENT_SETNAME']._serialized_end=2020
  _globals['_WSCLIENT_SETCURSOR']._serialized_start=2022
  _globals['_WSCLIENT_SETCURSOR']._serialized_end=2072
  _globals['_WSCLIENT_SETFOCUS']._serialized_start=2074
  _globals['_WSCLIENT_SETFOCUS']._serialized_end=2102
  _globals['_WSCLIENT_CREATE']._serialized_start=2104
  _globals['_WSCLIENT_CREATE']._serialized_end=2154
  _globals['_WSCLIENT_CLOSE']._serialized_start=2156
  _globals['_WSCLIENT_CLOSE']._serialized_end=2178
  _globals['_WSCLIENT_MOVE']._serialized_start=2180
  _globals['_WSCLIENT_MOVE']._serialized_end=2253
  _globals['_WSCLIENT_DATA']._serialized_start=2255
  _globals['_WSCLIENT_DATA']._serialized_end=2306
  _globals['_WSCLIENT_SUBSCRIBE']._serialized_start=2308
  _globals['_WSCLIENT_SUBSCRIBE']._serialized_end=2353
  _globals['_WSCLIENT_PING']._serialized_start=2355
  _globals['_WSCLIENT_PING']._serialized_end=2380
  _globals['_WSCLIENT_CHATMESSAGE']._serialized_start=2382
  _globals['_WSCLIENT_CHATMESSAGE']._serialized_end=2412
# @@protoc_insertion_point(module_scope)
