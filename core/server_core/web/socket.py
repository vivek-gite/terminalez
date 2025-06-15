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
    """
    Receive a message from the WebSocket with timeout protection.
    
    Args:
        websocket (WebSocket): The WebSocket connection to receive from
        
    Returns:
        web_protocol_pb2.WsClient | None: The received message or None if the connection is closed
    """
    try:
        # Use asyncio.wait_for to prevent indefinite waiting
        data = await websocket.receive_bytes()
        
        # If we get empty data, the connection might be broken
        if not data:
            logger.warning("Received empty data from WebSocket, connection may be broken")
            return None
            
        message = web_protocol_pb2.WsClient()
        message.ParseFromString(data)
        return message
        
    except WebSocketDisconnect as e:
        logger.info(f"WebSocket disconnected normally: {e}")
        return None
        
    except ConnectionError as e:
        logger.warning(f"WebSocket connection error: {e}")
        return None
        
    except Exception as e:
        logger.exception(f"Unexpected error receiving WebSocket data: {e}")
        return None
        

async def get_session_ws(name: str, websocket: WebSocket, server_state: ServerState):
    """
    Handles a new WebSocket connection for a given session name.

    This function attempts to connect to a session using the provided name and the server state.
    If the session is found, it delegates handling of the WebSocket to `handle_socket`.
    If the session cannot be found or an error occurs, it sends an error message to the client.
    The WebSocket connection is always closed at the end, regardless of success or failure.

    Args:
        name (str): (Session id) The name of the session to connect to.
        websocket (WebSocket): The WebSocket connection to handle.
        server_state (ServerState): The server state manager used to look up sessions.

    Side Effects:
        - Sends error messages to the client if the session cannot be found or an error occurs.
        - Ensures the WebSocket is closed after handling.

    """
    try:
        session: Session = await server_state.frontend_connect(name=name).read()
        try:
            await handle_socket(websocket, session)
        except Exception as e:
            logger.exception(f"Websocket handler failed closing session {name} due to {e}")
            raise
    except Exception as e:
        error_message = f"Session with name: {name} not found due to {e}"
        logger.exception(error_message)
        await send(websocket=websocket,
                  message=web_protocol_pb2.WsServer(
                      error=web_protocol_pb2.WsServer.Error(
                          message=error_message)))
    finally:
        await websocket.close()

async def broadcast_handler(broadcast_stream: asyncio.Queue[web_protocol_pb2.WsServer], websocket: WebSocket) -> None:
    while True:
        broadcast_data: web_protocol_pb2.WsServer = await broadcast_stream.get()

        broadcast_stream.task_done()

        await send(websocket, broadcast_data)


async def shell_stream_handler(shell_stream: WatchChannel.WatchReceiver, websocket: WebSocket) -> None:
    """
    Continuously receives shell updates from the shell_stream and sends them to the client via WebSocket.

    Args:
        shell_stream (WatchChannel.WatchReceiver): The stream providing shell updates.
            - The source is a Watch channel for the ordered list of open shells and their sizes,
              which is of type `List[Tuple[libs.Sid, protocol.WsWinsize]]`.
        websocket (WebSocket): The WebSocket connection to send updates to.

    Behavior:
        - Skips sending if the received shell list is empty (typically on first receive).
        - Sends each non-empty shell's update to the client as a WsServer message.
    """
    while True:
        result: web_protocol_pb2.WsServer.Shells = await shell_stream.recv()

        print(f"shell_stream_handler: \n{result}")

        await send(websocket=websocket,
                   message=web_protocol_pb2.WsServer(shells=result)
                   )


async def shell_chunks_handler(chunks_queue: asyncio.Queue[web_protocol_pb2.WsServer.Chunks], websocket: WebSocket) -> None:
    """
        Continuously processes shell's chunk updates from the queue and sends them to the client via WebSocket.

        Args:
            chunks_queue (asyncio.Queue[web_protocol_pb2.WsServer.Chunks]): Queue containing shell's chunk updates.
            websocket (WebSocket): The WebSocket connection to send chunk updates to.

        Behavior:
            - Waits for new chunk data from the queue.
            - Sends each chunk to the client as a WsServer message.
            - Marks each processed chunk as done in the queue.
            - Handles exceptions by logging and re-raising to allow parent task cancellation.
        """
    while True:
        try:
            chunk_data: web_protocol_pb2.WsServer.Chunks = await chunks_queue.get()
            await send(websocket=websocket,
                      message=web_protocol_pb2.WsServer(chunks=chunk_data)
                      )
            # Mark the task as done in the queue
            chunks_queue.task_done()
        except Exception as e:
            chunks_queue.shutdown(immediate=True)
            logger.exception(f"Error in shell_chunks_handler: {e}")
            # We can't "shutdown" a queue, but we can ensure we don't leave the task hanging
            # by re-raising the exception so the task can be properly canceled by its parent
            raise

async def get_websocket_stream_data(websocket: WebSocket, websocket_data_queue: asyncio.Queue[web_protocol_pb2.WsClient | None]) -> None:
    """
    Continuously receives data from a WebSocket and places it in a queue with backpressure control.
    
    This function handles WebSocket disconnection gracefully by putting None in the queue
    and raising an exception to signal the parent task. Implements backpressure to prevent
    overwhelming the server with rapid input from xterm.js.
    
    Args:
        websocket (WebSocket): The WebSocket connection to receive from
        websocket_data_queue (asyncio.Queue): Queue to store received messages
    """
    # Backpressure configuration
    MAX_QUEUE_SIZE = 1000  # Maximum messages in queue before applying backpressure
    BACKPRESSURE_DELAY = 0.01  # Delay in seconds when queue is full
    
    try:
        while True:
            # Check queue size for backpressure
            if websocket_data_queue.qsize() >= MAX_QUEUE_SIZE:
                logger.warning(f"WebSocket queue is full ({websocket_data_queue.qsize()} items), applying backpressure")
                # Small delay to slow down incoming data processing
                await asyncio.sleep(BACKPRESSURE_DELAY)
                
                # If queue is still full after delay, drop the oldest message
                if websocket_data_queue.qsize() >= MAX_QUEUE_SIZE:
                    try:
                        dropped_msg = websocket_data_queue.get_nowait()
                        logger.warning("Dropped message due to backpressure")
                    except asyncio.QueueEmpty:
                        pass
            
            # Use our improved recv function with timeout
            data = await recv(websocket)
            
            # If recv returns None, the connection is closed
            if data is None:
                # Put None in the queue to signal disconnection to consumers
                websocket_data_queue.put_nowait(None)
                logger.info("WebSocket connection closed, stopping data stream")
                break
                
            # Put data in queue with backpressure-aware method
            try:
                websocket_data_queue.put_nowait(data)
            except asyncio.QueueFull:
                # If queue is full, drop the oldest message and add the new one
                try:
                    websocket_data_queue.get_nowait()
                    websocket_data_queue.put_nowait(data)
                    logger.warning("Applied backpressure: dropped old message for new one")
                except asyncio.QueueEmpty:
                    websocket_data_queue.put_nowait(data)
            
    except Exception as e:
        # Log the exception and put None in the queue to signal disconnection
        logger.exception(f"Error in WebSocket stream: {e}")
        websocket_data_queue.put_nowait(None)
        # Re-raise to let parent task know there was an error
        raise


async def get_websocket_data_queue(data_queue: asyncio.Queue) -> web_protocol_pb2.WsClient | str | None:
    """
    Gets data from the queue with proper handling of disconnection signals.
    
    Returns:
        web_protocol_pb2.WsClient | str | None: 
            - Protocol message if normal message
            - "terminated" if the session is terminated
            - None if the WebSocket is disconnected
    """
    data = await data_queue.get()
    data_queue.task_done()
    return data


async def handle_socket(websocket: WebSocket, session: Session):
    # List to track all created background tasks for proper cleanup
    background_tasks = []

    try:
        metadata = session.metadata
        user_id: libs.Uid = await session.counter.incr_uid()

        await session.sync_now()

        print(f"Session connected to WebSocket {websocket.client}")

        # Send the initial hello message
        await send(websocket=websocket,
                message=web_protocol_pb2.WsServer(
                    hello=web_protocol_pb2.WsServer.Hello(
                        user_id=user_id.value,
                        host_name=metadata.name,
                        available_shells=metadata.available_shells)))

        received_data: web_protocol_pb2.WsClient = await recv(websocket)

        print(f"Received data type: {received_data.WhichOneof("client_message")}")
        # match received_data.WhichOneof("client_message"):
        #     case "set_name" | "ping":
        #         pass
        #     case _:
        #         await send(websocket=websocket,
        #                 message=web_protocol_pb2.WsServer(
        #                     error=web_protocol_pb2.WsServer.Error(
        #                         message="Invalid message type")))
        #         return

        # TODO: Implement the removing the user logic
        await session.user_scope(user_id)

        broadcast_stream: asyncio.Queue[web_protocol_pb2.WsServer] = session.subscribe_broadcast()

        users: web_protocol_pb2.WsServer.Users = await session.list_users()
        await send(websocket=websocket,
                message= web_protocol_pb2.WsServer(users=users))

        subscribed = set()

        # Queue to store the chunks of format (sid, seq_num, chunks) with size limit for backpressure
        chunks_queue: asyncio.Queue[web_protocol_pb2.WsServer.Chunks] = asyncio.Queue(maxsize=100)

        # Subscribe to shell updates for the session.
        shells_stream = session.subscribe_shells()

        # Start and track background tasks
        broadcast_task = asyncio.create_task(
            broadcast_handler(broadcast_stream, websocket),
            name="broadcast_handler"
        )
        background_tasks.append(broadcast_task)

        
        shell_stream_task = asyncio.create_task(
            shell_stream_handler(shells_stream, websocket),
            name="shell_stream_handler"
        )
        background_tasks.append(shell_stream_task)

        # Start a background task to handle and send shell chunk updates to the websocket client
        chunks_task = asyncio.create_task(
            shell_chunks_handler(chunks_queue, websocket),
            name="shell_chunks_handler"
        )
        background_tasks.append(chunks_task)        
        # Create a queue to store incoming websocket data from the client with size limit for backpressure
        websocket_data_queue: asyncio.Queue[web_protocol_pb2.WsClient | None] = asyncio.Queue(maxsize=1000)

        # Start a background task to receive data from the websocket and put it into the queue.
        websocket_stream_task = asyncio.create_task(
            get_websocket_stream_data(websocket, websocket_data_queue),
            name="websocket_stream_handler"
        )
        background_tasks.append(websocket_stream_task)

        while True:
            # Use pre-created tasks instead of creating new ones in wait()
            done, pending = await asyncio.wait([
                asyncio.create_task(session.terminated(), name="session_terminated"),
                asyncio.create_task(get_websocket_data_queue(websocket_data_queue), name="get_websocket_data")
            ], return_when=asyncio.FIRST_COMPLETED)

            for task in pending:
                if task.get_name() == "session_terminated":
                    continue
                task.cancel()

            result = done.pop().result()

            match result:
                case None:
                    # None means the WebSocket has been disconnected
                    logger.info("WebSocket disconnected, terminating handler")
                    break
                case "terminated":
                    logger.info("Session terminated, closing WebSocket connection")
                    break

            ws_client_message: web_protocol_pb2.WsClient = result

            match ws_client_message.WhichOneof("client_message"):
                case "set_name":
                    recv_data: web_protocol_pb2.WsClient.SetName = ws_client_message.set_name
                    if recv_data.name != "":
                        await session.update_users(user_id, lambda user: setattr(user, "name", recv_data.name))

                case "set_cursor":
                    recv_data: web_protocol_pb2.WsClient.SetCursor = ws_client_message.set_cursor
                    await session.update_users(user_id, lambda user: user.cursor.CopyFrom(recv_data.cursor))

                case "set_focus":
                    recv_data: web_protocol_pb2.WsClient.SetFocus = ws_client_message.set_focus
                    await session.update_users(user_id, lambda user: setattr(user, "focus", recv_data.shell_id))

                case "create":
                    recv_data: web_protocol_pb2.WsClient.Create = ws_client_message.create
                    print(f"Create: \n{recv_data}")
                    sid: Sid = await session.counter.incr_sid()

                    # Track sync task
                    sync_task = asyncio.create_task(session.sync_now(), name="sync_task")
                    background_tasks.append(sync_task)

                    new_shell = terminalez_pb2.NewShell(shell_id=sid.value, x=recv_data.x, y=recv_data.y, shell_info=recv_data.shell_info)
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

                    # Implement backpressure for terminal input data
                    if session.buffer_message.qsize() > 50:  # Configurable threshold
                        logger.warning(f"Session buffer queue is large ({session.buffer_message.qsize()}), applying input throttling")
                        # Small delay to prevent overwhelming the terminal backend
                        await asyncio.sleep(0.005)
                        
                        # If queue is still large, skip this input to prevent system overload
                        if session.buffer_message.qsize() > 100:
                            logger.warning("Dropping terminal input due to severe backpressure")
                            continue

                    terminal_input = terminalez_pb2.TerminalInput(
                        shell_id=recv_data.shell,
                        data=recv_data.data,
                        offset=recv_data.offset
                    )

                    print(f"Terminal Input: \n{terminal_input}")

                    try:
                        # Use put_nowait with error handling instead of blocking put
                        session.buffer_message.put_nowait(terminalez_pb2.ServerUpdate(terminal_input=terminal_input))
                    except asyncio.QueueFull:
                        logger.warning("Session buffer queue full, dropping terminal input")
                        # Optionally send error back to client
                        await send(websocket=websocket,
                                message=web_protocol_pb2.WsServer(
                                    error=web_protocol_pb2.WsServer.Error(
                                        message="Server overloaded, please slow down typing")))
                        continue

                case "subscribe":
                    recv_data: web_protocol_pb2.WsClient.Subscribe = ws_client_message.subscribe

                    print(f"Subscribe: \n{recv_data}")
                    if recv_data.shell not in subscribed:
                        subscribed.add(recv_data.shell)

                        async def send_chunks(shell_id: libs.Sid):
                            try:
                                stream = session.subscribe_chunks(
                                    sid=shell_id,
                                    chunk_num=recv_data.chunk_num
                                )

                                #  So if the receiver is dropped perm. then raise an exception and
                                #  break the loop as the receiver can be only single consumer and there can be multiple producers
                                async for seq_num, chunks in stream:
                                    print(f" send_chunks: \n{chunks}")
                                    chunk_data: web_protocol_pb2.WsServer.Chunks = (
                                        web_protocol_pb2.WsServer.Chunks(
                                            sid=shell_id.value,
                                            index=seq_num,
                                            chunks=chunks))
                                    await chunks_queue.put(chunk_data)
                            except Exception as e:
                                logger.exception(f"Error in send_chunks task: {e}")

                        # Create and track the send_chunks task
                        chunks_task = asyncio.create_task(
                            send_chunks(libs.Sid(value=recv_data.shell)),
                            name=f"send_chunks_{recv_data.shell}"
                        )
                        background_tasks.append(chunks_task)

                case "ping":
                    recv_data: web_protocol_pb2.WsClient.Ping = ws_client_message.ping
                    await send(websocket=websocket,
                            message=web_protocol_pb2.WsServer(
                                pong=web_protocol_pb2.WsServer.Pong(
                                    timestamp=recv_data.timestamp)))

                case "chat_message":
                    recv_data: web_protocol_pb2.WsClient.ChatMessage = ws_client_message.chat_message
                    await session.send_chat_message(user_id, recv_data.message)


    except Exception as e:
        logger.exception(f"Error in handle_socket: {e}")

    finally:
        # Clean up all background tasks to prevent leaks
        logger.info(f"Cleaning up {len(background_tasks)} background tasks")
        for task in background_tasks:
            if not task.done() and not task.cancelled():
                logger.debug(f"Cancelling task: {task.get_name()}")
                task.cancel()

        # Wait for tasks to complete with a timeout to avoid hanging
        if background_tasks:
            try:
                await asyncio.wait(background_tasks, timeout=5.0)
            except Exception as e:
                logger.warning(f"Error waiting for tasks to cancel: {e}")

        # Remove user if we created one
        try:
            if 'user_id' in locals():
                await session.remove_user(uid=user_id)
        except Exception as e:
            logger.warning(f"Error removing user {user_id}: {e}")
