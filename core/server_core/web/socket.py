import asyncio
import logging
from fastapi import WebSocket, WebSocketDisconnect

from core.server_core.state_manager.server_state import ServerState
from core.comms_core.proto.identifiers.libs import Sid
from core.comms_core.utils.watch import WatchChannel
from core.server_core.state_manager.session import Session
from core.comms_core.proto.identifiers import libs
from core.comms_core.proto.terminalez import terminalez_pb2
from core.server_core.web.proto.ws_protocol import web_protocol_pb2


logger = logging.getLogger(__name__)


async def send(websocket: WebSocket, message: web_protocol_pb2.WsServer | web_protocol_pb2.WsClient):
    buf = message.SerializeToString()
    await websocket.send_bytes(buf)

async def recv(websocket: WebSocket) -> web_protocol_pb2.WsClient | None:
    while True:
        try:
            data = await websocket.receive_bytes()
            message = web_protocol_pb2.WsClient()
            message.ParseFromString(data)
            return message
        except WebSocketDisconnect as e:
            logger.exception(f"Websocket receiver dropped, due to {e}")
            break
    return None


async def get_session_ws(name: str, websocket: WebSocket, server_state: ServerState):
    try:
        session: Session = await server_state.frontend_connect(name=name).read()
        try:
            await handle_socket(websocket, session)
        except Exception as e:
            logger.exception(f"Websocket handler failed closing session {name} due to {e}")
    except Exception as e:
        logger.exception(f"Session with name: {name} not found due to {e}")
        error_response = {
            "status": "error",
            "code": 1011,
            "reason": f"Session with name: {name} not found due to {e}"
        }
        await websocket.send(error_response)
    finally:
        await websocket.close()

async def broadcast_handler(broadcast_stream: asyncio.Queue, websocket: WebSocket) -> None:
    broadcast_data: web_protocol_pb2.WsServer.UserDiff = await broadcast_stream.get()
    result: web_protocol_pb2.WsServer = web_protocol_pb2.WsServer()
    result.user_diff.CopyFrom(broadcast_data)

    broadcast_stream.task_done()

    await send(websocket, result)


async def shell_stream_handler(shell_stream: WatchChannel.WatchReceiver, websocket: WebSocket) -> None:
    result: web_protocol_pb2.WsServer.Shells = await shell_stream.recv()

    await send(websocket=websocket,
               message=web_protocol_pb2.WsServer(shells=result)
               )


async def shell_chunks_handler( chunks_queue: asyncio.Queue[web_protocol_pb2.WsServer.Chunks], websocket: WebSocket) -> None:
    try:
        chunk_data: web_protocol_pb2.WsServer.Chunks = await chunks_queue.get()
        await send(websocket=websocket,
                   message=web_protocol_pb2.WsServer(chunks=chunk_data)
                   )
    except Exception as e:
        chunks_queue.shutdown(immediate=True)



async def handle_socket(websocket: WebSocket, session: Session):
    metadata = session.metadata
    user_id: libs.Uid = session.counter.incr_uid()

    await session.sync_now()

    # Send the initial hello message
    await send(websocket=websocket,
               message=web_protocol_pb2.WsServer(
                   hello=web_protocol_pb2.WsServer.Hello(
                       user_id=user_id.value,
                       metadata=metadata.name)))

    received_data: web_protocol_pb2.WsClient = await recv(websocket)

    match received_data.WhichOneof("client_message"):
        case "server_res_hello":
            pass
        case _:
            await send(websocket=websocket,
                       message=web_protocol_pb2.WsServer(
                           error=web_protocol_pb2.WsServer.Error(
                               message="Invalid message type")))
            return

    # TODO: Implement the removing the user logic
    await session.user_scope(user_id)

    broadcast_stream: asyncio.Queue = await session.subscribe_broadcast()

    users: web_protocol_pb2.WsServer.Users = await session.list_users()

    await send(websocket=websocket,
               message= web_protocol_pb2.WsServer(users=users))

    subscribed = set()

    # Queue to store the chunks of format (sid, seq_num, chunks)
    chunks_queue: asyncio.Queue[web_protocol_pb2.WsServer.Chunks] = asyncio.Queue()

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

        ws_client_message: web_protocol_pb2.WsClient = result

        match ws_client_message.WhichOneof("client_message"):
            case "set_name":
                recv_data: web_protocol_pb2.WsClient.SetName = ws_client_message.set_name
                if result.name!="":
                    await session.update_users(user_id, lambda user: setattr(user, "name", recv_data.name))

            case "set_cursor":
                recv_data: web_protocol_pb2.WsClient.SetCursor = ws_client_message.set_cursor
                await session.update_users(user_id, lambda user: setattr(user, "cursor", recv_data.cursor))

            case "set_focus":
                recv_data: web_protocol_pb2.WsClient.SetFocus = ws_client_message.set_focus
                await session.update_users(user_id, lambda user: setattr(user, "focus", recv_data.shell_id))

            case "create":
                recv_data: web_protocol_pb2.WsClient.Create = ws_client_message.create
                sid: Sid = await session.counter.incr_sid()
                asyncio.create_task(session.sync_now())

                new_shell = terminalez_pb2.NewShell( shell_id = sid.value, x=recv_data.x, y=recv_data.y, shell_info=recv_data.shell_info)

                await session.buffer_message.put(terminalez_pb2.ServerUpdate(create_shell=new_shell))

            case "close":
                """
                Close a specific shell.
                result is a WsClient.Close object
                schema: WsClient.Close(shell: libs.Sid)
                """
                recv_data: web_protocol_pb2.WsClient.Close = ws_client_message.close
                await session.buffer_message.put(terminalez_pb2.ServerUpdate(close_shell=recv_data.shell))

            case "move":
                try:
                    recv_data: web_protocol_pb2.WsClient.Move = ws_client_message.move
                    await session.move_shell(
                        sid=libs.Sid(value=recv_data.shell),
                        winsize=recv_data.size)
                except ValueError as e:
                    await send(websocket=websocket,
                               message=web_protocol_pb2.WsServer(
                                   error=web_protocol_pb2.WsServer.Error(message=str(e))
                               ))
                    continue

                terminal_size = terminalez_pb2.TerminalSize(shell_id=recv_data.shell,
                                                            rows=recv_data.size.rows,
                                                            cols=recv_data.size.cols)
                await session.buffer_message.put(terminalez_pb2.ServerUpdate(resize=terminal_size))

            case "data":
                recv_data: web_protocol_pb2.WsClient.Data = ws_client_message.data

                terminal_input = terminalez_pb2.TerminalInput(
                    shell_id=recv_data.shell,
                    data=recv_data.data,
                    offset=recv_data.offset
                )

                await session.buffer_message.put(terminalez_pb2.ServerUpdate(terminal_input=terminal_input))


            case "subscribe":
                recv_data: web_protocol_pb2.WsClient.Subscribe = ws_client_message.subscribe

                if recv_data.shell not in subscribed:
                    subscribed.add(recv_data.shell)

                    async def send_chunks(shell_id: libs.Sid):
                        stream = session.subscribe_chunks(
                            sid = shell_id,
                            chunk_num = recv_data.chunk_num
                        )

                        #  So if the receiver is dropped perm. then raise an exception and
                        #  break the loop as the receiver can be only single consumer and there can be multiple producers
                        async for seq_num, chunks in stream:
                            chunk_data: web_protocol_pb2.WsServer.Chunks = (
                                web_protocol_pb2.WsServer.Chunks(
                                    sid=shell_id.value,
                                    index=seq_num,
                                    chunks=chunks))
                            await chunks_queue.put(chunk_data)

                    asyncio.create_task(send_chunks(
                        libs.Sid(value=recv_data.shell)
                    ))

            case "ping":
                recv_data: web_protocol_pb2.WsClient.Ping = ws_client_message.ping
                await send(websocket=websocket,
                           message=web_protocol_pb2.WsServer(
                               pong=web_protocol_pb2.WsServer.Pong(
                                   timestamp=recv_data.timestamp)))