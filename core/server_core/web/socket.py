import asyncio
import queue
from typing import Tuple, List

import ormsgpack
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from core.comms_core.proto.identifiers.libs import Sid
from core.comms_core.utils.watch import WatchChannel

from core.server_core.web.protocol import WsServer, WsClient, WsWinsize
from core.server_core.state_manager.session import Session

from core.comms_core.utils import common_tools
from core.comms_core.proto.identifiers import libs

from core.comms_core.proto.terminalez import terminalez_pb2

async def send(websocket: WebSocket, msg: WsServer):
    buf = ormsgpack.packb(msg)
    await websocket.send_bytes(buf)

async def recv(websocket: WebSocket):
    while True:
        try:
            data = await websocket.receive_bytes()
            return ormsgpack.unpackb(data)
        except WebSocketDisconnect:
            print("Client disconnected")
            break


async def broadcast_handler(broadcast_stream: asyncio.Queue, websocket: WebSocket) -> None:
    result: WsServer.UserDiff = await broadcast_stream.get()

    broadcast_stream.task_done()

    await send(websocket, result)

async def shell_stream_handler(shell_stream: WatchChannel.WatchReceiver, websocket: WebSocket) -> None:
    result: List[Tuple[libs.Sid, WsWinsize]] = await shell_stream.recv()
    await send(websocket, WsServer.Shells(shells=result))

async def shell_chunks_handler( chunks_queue: asyncio.Queue[Tuple[libs.Sid, int, List[bytes]]], websocket: WebSocket) -> None:
    sid, index, chunks = await chunks_queue.get()
    await send(websocket, WsServer.Chunks(sid=sid, index=index, chunks=chunks))




async def handle_socket(websocket: WebSocket, session: Session):
    metadata = session.metadata
    user_id: libs.Uid = session.counter.incr_uid()

    await session.sync_now()

    # Send the initial hello message
    await send(websocket, WsServer.Hello(user_id=user_id, metadata=metadata.name))

    received_data = await recv(websocket)

    class_type = common_tools.validate(received_data, WsClient)
    match class_type:
        case WsClient.ServerResHello:
            pass
        case _:
            await send(websocket, WsServer.Error(message = "Invalid message type"))
            return

    # TODO: Implement the removing the user logic
    await session.user_scope(user_id)

    broadcast_stream: asyncio.Queue = await session.subscribe_broadcast()

    users = await session.list_users()
    await send(websocket, WsServer.Users(users = users))

    subscribed = set()

    # Queue to store the chunks of format (sid, seq_num, chunks)
    chunks_queue: asyncio.Queue[Tuple[libs.Sid, int, List[bytes]]] = asyncio.Queue()

    shells_stream = session.subscribe_shells()
    while True:

        done, pending = await asyncio.wait([
            asyncio.create_task(session.terminated()),
            asyncio.create_task(broadcast_handler(broadcast_stream, websocket)),
            asyncio.create_task(shell_stream_handler(shells_stream, websocket)),
            asyncio.create_task(shell_chunks_handler(chunks_queue, websocket)),
            asyncio.create_task(recv(websocket))
        ], return_when=asyncio.FIRST_COMPLETED)

        result = done.pop().result()


        match result:
            case None:
                continue
            case "terminated":
                break


        match common_tools.validate(result, WsClient):
            case WsClient.SetName:
                if result.name!="":
                    await session.update_users(user_id, lambda user: setattr(user, "name", result.name))

            case WsClient.SetCursor:
                await session.update_users(user_id, lambda user: setattr(user, "cursor", result.cursor))

            case WsClient.SetFocus:
                await session.update_users(user_id, lambda user: setattr(user, "focus", result.focus))

            case WsClient.Create:
                sid: Sid = await session.counter.incr_sid()
                asyncio.create_task(session.sync_now())

                new_shell = terminalez_pb2.NewShell( shell_id = sid.value, x=result.x, y=result.y)

                await session.buffer_message.put(terminalez_pb2.ServerUpdate(create_shell=new_shell))

            case WsClient.Close:
                """
                Close a specific shell.
                result is a WsClient.Close object
                schema: WsClient.Close(shell: libs.Sid)
                """
                await session.buffer_message.put(terminalez_pb2.ServerUpdate(close_shell=result.shell.value))

            case WsClient.Move:

                try:
                    wsclient_move = WsClient.Move(**result)
                    await session.move_shell(wsclient_move.shell, wsclient_move.size)
                except ValueError as e:
                    await send(websocket, WsServer.Error(message=str(e)))
                    continue

                terminal_size = terminalez_pb2.TerminalSize(shell_id=wsclient_move.shell.value,
                                                            rows=wsclient_move.size.rows,
                                                            cols=wsclient_move.size.cols)
                await session.buffer_message.put(terminal_size)

            case WsClient.Data:
                terminal_input = terminalez_pb2.TerminalInput(
                    shell_id=result.shell.value,
                    data=result.data,
                    offset=result.offset
                )

                await session.buffer_message.put(terminalez_pb2.ServerUpdate(terminal_input=terminal_input))


            case WsClient.Subscribe:
                if result.shell.value not in subscribed:
                    subscribed.add(result.shell.value)

                    async def send_chunks(shell_id: libs.Sid):
                        stream = session.subscribe_chunks(
                            sid = shell_id,
                            chunk_num = result.chunk_num
                        )

                        # TODO Enhancement: So if the receiver is dropped perm. then raise an exception and
                        #  break the loop as the receiver can be only single consumer and there can be multiple producers
                        async for seq_num, chunks in stream:
                            chunks_queue.shutdown()
                            await chunks_queue.put((shell_id, seq_num, chunks))

                    asyncio.create_task(send_chunks(
                        libs.Sid(value=result.shell.value)
                    ))

            case WsClient.Ping:
                await send(websocket, WsServer.Pong(timestamp=result.timestamp))