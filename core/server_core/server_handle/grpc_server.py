import asyncio
import logging
import random
from typing import AsyncIterable, Coroutine, AsyncIterator, Tuple
from datetime import datetime, timezone
import grpc.aio

from core.comms_core.proto.identifiers import libs
from core.comms_core.proto.terminalez import terminalez_pb2_grpc, terminalez_pb2
from core.comms_core.utils.rw_lock import ReadWriteLock
from core.comms_core.utils.task_registry import task_registry
from core.server_core.state_manager.server_state import ServerState
from core.server_core.state_manager.session import Metadata, Session

SYNC_INTERVAL = 5
PING_INTERVAL = 2

logger = logging.getLogger(__name__)


class GrpcServer(terminalez_pb2_grpc.TerminalEzServicer):
    def __init__(self, server_state: ServerState):
        self.server_state = server_state

    @staticmethod
    def generate_random_number_string(length: int) -> str:
        if length <= 0:
            raise ValueError("Length must be a positive integer")
        random_digits = [str(random.randint(0, 9)) for _ in range(length)]
        return ''.join(random_digits)

    async def InitiateConnection(self,
                                 request: terminalez_pb2.InitialConnectionRequest,
                                 context: grpc.aio.ServicerContext) -> terminalez_pb2.InitialConnectionResponse | None:
        """
        Initiates a new connection by generating a random session name, creating a new session, and returning the session details.

        Args:
            request (terminalez_pb2.InitialConnectionRequest): The initial connection request containing client details.
            context (grpc.aio.ServicerContext): The gRPC context for the request.

        Returns:
            terminalez_pb2.InitialConnectionResponse: The response containing the session ID and URL.

        Raises:
            Exception: If a session with the generated name already exists.
            ValueError: If the generated random number string length is not positive.
        """
        try:
            random_name = self.generate_random_number_string(10)
            logger.info(f"Initiating connection with name {random_name}")

            session = self.server_state.lookup(random_name)
            if session is not None:
                raise Exception("Session already exists")

            metadata: Metadata = Metadata(name=request.m_name, available_shells=list(request.available_shells))
            print(metadata)
            await self.server_state.insert(random_name, Session(metadata=metadata))
            url = f"/s/{random_name}"

            return terminalez_pb2.InitialConnectionResponse(
                session_id=random_name,
                url=url)
        except Exception as e:
            logger.exception(f"Error initiating connection: {e}")
        return None

    async def Channel(self,
                      request_iterator: AsyncIterable[terminalez_pb2.ClientUpdate],
                      context: grpc.aio.ServicerContext) -> AsyncIterable[terminalez_pb2.ServerUpdate]:
        """
        Handles a bidirectional streaming RPC for the gRPC server.
        This method processes a stream of `ClientUpdate` messages from the client and
        yields `ServerUpdate` messages back to the client. The first message from the
        client must contain the session name, which is used to connect to the backend
        session.
        Args:
            request_iterator (AsyncIterable[terminalez_pb2.ClientUpdate]): An asynchronous
                iterator of `ClientUpdate` messages from the client.
            context (grpc.aio.ServicerContext): The gRPC context for the RPC call.
        Returns:
            AsyncIterable[terminalez_pb2.ServerUpdate]: An asynchronous iterator of
            `ServerUpdate` messages to be sent to the client.
        Raises:
            Exception: If the first message does not contain the session name or if the
            session is not found.
        """
        session_name = None
        stream_task = None
        
        try:
            iterator = request_iterator.__aiter__()
            first_message = await iterator.__anext__()
            if not first_message.HasField("session_id"):
                raise Exception("First message must contain the session id")

            logger.info(f"Received first message: {first_message}")

            session_name = first_message.session_id
            session_rw_lock: ReadWriteLock[Session] = await self.server_state.backend_connect(session_name)

            if session_rw_lock is None:
                raise Exception("Session not found, please initiate connection first")

            result_queue = asyncio.Queue()

            # Get the session from the read lock
            session: Session = await session_rw_lock.read()

            # Create a context string for this channel's tasks
            channel_context = f"channel_{session_name}"
            
            # Start the stream handler using our task registry to prevent orphaned tasks
            try:
                stream_task = task_registry.create_task(
                    handle_streaming(result_queue, iterator, session, channel_context),
                    name="stream_handler",
                    context=channel_context
                )
            except Exception as e:
                # Ensure any tasks we created are cleaned up if this fails
                if session_name:
                    await task_registry.cancel_context_tasks(channel_context)
                raise ConnectionError(f"connection exiting early due to an error: {e}")

            logger.info(f"Starting channel handler for session {session_name}")
            # Yield the results from the result queue
            while True:
                try:
                    mickey_data = await result_queue.get()
                    logger.info(f"Yielding data from result queue: {mickey_data}")
                    yield mickey_data
                except asyncio.CancelledError:
                    break
        except Exception as e:
            logger.exception(f"Error handling channel: {e}")
        finally:
            # Clean up any tasks associated with this channel when we're done
            if session_name:
                channel_context = f"channel_{session_name}"
                task_count = await task_registry.cancel_context_tasks(channel_context)
                logger.info(f"Cleaned up {task_count} tasks for channel {session_name}")
                
            # Cancel the stream task explicitly to ensure it's stopped
            if stream_task and not stream_task.done():
                stream_task.cancel()
                try:
                    await asyncio.wait_for(asyncio.shield(stream_task), timeout=2.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass

    async def Close(self,
                    request: terminalez_pb2.CloseRequest,
                    context: grpc.aio.ServicerContext) -> terminalez_pb2.CloseResponse | None:
        """
        Closes the session with the given name.
        Args:
            request (terminalez_pb2.CloseRequest): The request containing the session name.
            context (grpc.aio.ServicerContext): The gRPC context for the request.
        Returns:
            terminalez_pb2.CloseResponse: The response indicating the session is closed.
        Raises:
            Exception: If the session is not found.
        """
        try:
            session_name = request.session_id
            # session_rw_lock: ReadWriteLock[Session] = self.server_state.lookup(session_name)
            # if session_rw_lock is None:
            #     raise Exception("Session not found")
            #
            # session: Session = await session_rw_lock.read_mut()
            # await session.shutdown_session()
            await self.server_state.close_session(session_name)

            return terminalez_pb2.CloseResponse(success=True)
        except Exception as e:
            logger.exception(f"Error closing session: {e}")
        return None


async def handle_streaming(result_queue: asyncio.Queue,
                           iterator: AsyncIterator[terminalez_pb2.ClientUpdate],
                           session: Session,
                           channel_context: str) -> None:
    """
    Handles the streaming of messages between the client and server.
    This coroutine listens for various events such as sync intervals, ping intervals,
    buffered server updates, incoming client messages, and session termination. It processes
    the first completed event and cancels the remaining pending tasks.
    Args:
        result_queue (asyncio.Queue): The queue to send results to.
        iterator (AsyncIterator[terminalez_pb2.ClientUpdate]): An asynchronous iterator for client updates.
        session (Session): The current session object.
        channel_context (str): The context string for this channel's tasks.
    Raises:
        Exception: If there is an error in sending sync interval, buffered server updates, or handling incoming client messages.
    Returns:
        None
    """
    # Create a queue for incoming client messages
    requests_queue = asyncio.Queue()
    
    # Context for tasks specific to this stream handler
    stream_context = f"{channel_context}_stream"
    
    try:
        # Start a single background task that consumes the iterator
        # and puts results into the queue
        iterator_task = task_registry.create_task(
            consume_iterator(iterator, requests_queue),
            name="iterator_consumer",
            context=stream_context
        )

        while True:
            # Create tasks with proper context for tracking
            tasks = [
                task_registry.create_task(asyncio.sleep(SYNC_INTERVAL), name="sync_interval", context=stream_context),
                task_registry.create_task(asyncio.sleep(PING_INTERVAL), name="ping_interval", context=stream_context),
                task_registry.create_task(send_buffered_server_updates(session=session), name="send_buffered_server_updates", context=stream_context),
                task_registry.create_task(get_queue_data(requests_queue), name="incoming_client_messages", context=stream_context),
                task_registry.create_task(session.terminated(), name="terminated", context=stream_context)
            ]

            try:
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

                # Cancel all pending tasks - they're tracked by the registry so they
                # will be automatically removed once cancelled
                for task in pending:
                    if task.get_name() == "terminated":
                        # If the session is terminated, we don't want to cancel it
                        continue
                    task.cancel()

                # Get the first completed task
                done_result = done.pop()

                # Log the completed task
                logger.info(f"The first completed task is {done_result.get_name()}")

                # Handle the completed task
                match done_result.get_name():
                    case "sync_interval":
                        try:
                            await send_msg(result_queue, await sync_interval(session))
                        except Exception as e:
                            logger.error(f"Failed to send sync interval: {e}")
                            await send_error(result_queue, f"Sync interval error: {str(e)}")
                            # Continue the loop instead of raising which would terminate everything
                            continue

                    case "ping_interval":
                        try:
                            await send_msg(result_queue, await ping_interval())
                        except Exception as e:
                            logger.error(f"Failed to send ping: {e}")
                            # Continue the loop instead of terminating
                            continue
                            
                    case "send_buffered_server_updates":
                        try:
                            await send_msg(result_queue, done_result.result())
                        except Exception as e:
                            logger.error(f"Failed to send buffered server updates: {e}")
                            await send_error(result_queue, f"Server update error: {str(e)}")
                            continue
                            
                    case "incoming_client_messages":
                        try:
                            result: terminalez_pb2.ClientUpdate = done_result.result()
                            logger.info(f"Incoming client message: {result}")
                            await incoming_client_messages(result_queue, session, result)
                        except Exception as e:
                            logger.error(f"Failed to handle incoming client messages: {e}")
                            await send_error(result_queue, f"Client message error: {str(e)}")
                            continue

                    case "terminated":
                        message = "Disconnecting because session is terminated"
                        await send_msg(result_queue, terminalez_pb2.ServerUpdate(error=message))
                        return
                        
            except asyncio.CancelledError:
                logger.info("Stream handler was cancelled")
                break
                
            except Exception as e:
                logger.exception(f"Unexpected error in stream handler: {e}")
                try:
                    await send_error(result_queue, f"Stream error: {str(e)}")
                except:
                    pass
                # Continue the loop instead of terminating
                continue
                
    except Exception as e:
        logger.exception(f"Fatal error in stream handler: {e}")
        try:
            await send_error(result_queue, f"Fatal stream error: {str(e)}")
        except:
            pass
    finally:
        # Always clean up tasks specific to this stream handler
        task_count = await task_registry.cancel_context_tasks(stream_context)
        logger.info(f"Cleaned up {task_count} tasks for stream handler")


async def sync_interval(session: Session) -> terminalez_pb2.ServerUpdate:
    """
    Generates a `ServerUpdate` message containing the current sequence numbers of each shell for the session.

    Args:
        session (Session): The session for which to generate the sequence numbers.

    Returns:
        terminalez_pb2.ServerUpdate: A `ServerUpdate` message with the current sequence numbers.
    """
    server_update = terminalez_pb2.ServerUpdate(sync=await session.sequence_numbers())
    return server_update


async def ping_interval() -> terminalez_pb2.ServerUpdate:
    """
    Generates a `ServerUpdate` message containing the current timestamp as a ping.
    This is used to identify the latency.

    Returns:
        terminalez_pb2.ServerUpdate: A `ServerUpdate` message with the current timestamp as a ping.
    """
    return terminalez_pb2.ServerUpdate(ping=get_timestamp())


async def send_buffered_server_updates(session: Session) -> terminalez_pb2.ServerUpdate:
    """
    Retrieves the next buffered server update message for the given session.
    This is used to send the command that needs to be executed on the host machine terminal.

    Args:
        session (Session): The session from which to retrieve the buffered message.

    Returns:
        Coroutine: A coroutine that retrieves the next buffered server update message.
    """
    message:terminalez_pb2.ServerUpdate = await session.buffer_message.get()
    return message


async def consume_iterator(iterator: AsyncIterator[terminalez_pb2.ClientUpdate],
                            requests_queue: asyncio.Queue) -> None:
    """Consumes the async iterator and puts items into the queue with backpressure control.
    Only this function will access the iterator directly."""
    
    # Backpressure configuration for gRPC stream
    MAX_QUEUE_SIZE = 200  # Maximum messages before applying backpressure
    BACKPRESSURE_DELAY = 0.005  # Delay when queue is getting full
    
    try:
        while True:
            try:
                # Apply backpressure if queue is getting full
                if requests_queue.qsize() >= MAX_QUEUE_SIZE:
                    logger.warning(f"gRPC requests queue is full ({requests_queue.qsize()}), applying backpressure")
                    await asyncio.sleep(BACKPRESSURE_DELAY)

                # Get the next item from the iterator
                item = await iterator.__anext__()

                # Use non-blocking put to avoid hanging
                requests_queue.put_nowait(item)

            except StopAsyncIteration:
                logger.info("Client has closed the stream (StopAsyncIteration).")
                # Signal that the iterator is exhausted
                await requests_queue.put(None)
                break
            except Exception as e:
                logger.exception(f"Error consuming iterator: {e}")
                raise
    except asyncio.CancelledError:
        logger.info("Iterator consumer task was cancelled")
        raise

async def get_queue_data(queue: asyncio.Queue) -> terminalez_pb2.ClientUpdate:
    """Gets data from the queue. Returns None if the iterator is exhausted."""
    return await queue.get()


async def incoming_client_messages(result_queue: asyncio.Queue, session: Session, result: terminalez_pb2.ClientUpdate):
    try:
        await handle_update(result_queue, session, result)
    except Exception as e:
        raise Exception(f"Error handling client updates: {str(e)}")


async def handle_update(result_queue: asyncio.Queue, session: Session, update: terminalez_pb2.ClientUpdate):
    """
    Handles updates from the client and processes them based on the type of message received.
    Args:
        result_queue (asyncio.Queue): The queue to send error messages to.
        session (Session): The current session object.
        update (terminalez_pb2.ClientUpdate): The update message from the client.
    Raises:
        Exception: If there is an error while adding data, adding a shell, or closing a shell.
    Processes the following types of client messages:
        - "session_id": Sends an error message indicating an unexpected session_id message.
        - "data": Adds data to the session.
        - "created_shell": Adds a new shell to the session.
        - "closed_shell": Closes an existing shell in the session.
        - "pong": Measures and sends the latency.
        - "error": Logs the error message.
    """
    session.update_access_time()

    try:
        match update.WhichOneof("client_message"):
            case "session_id":
                await send_error(result_queue, "unexpected session_id message")
            case "data":
                logger.info(f"Adding data to shell {update.data.shell_id} and \n data: {update.data.data}")

                terminal_output: terminalez_pb2.TerminalOutput = update.data
                try:
                    await session.add_data(
                        sid=libs.Sid(value=terminal_output.shell_id),
                        data=terminal_output.data,
                        seq=terminal_output.seq_num)

                except Exception as e:
                    await send_error(result_queue, f"Error adding data: {str(e)}")
                    # Log the error but don't re-raise to prevent stream termination
                    logger.error(f"Error adding data in handle update: {e}")

            case "created_shell":
                logger.info(
                    f"Adding shell {update.created_shell.shell_id} at location ({update.created_shell.x}, {update.created_shell.y})")

                sid: libs.Sid = libs.Sid(value=update.created_shell.shell_id)
                location: Tuple[int, int] = (update.created_shell.x, update.created_shell.y)
                try:
                    await session.add_shell(
                        sid=sid,
                        location=location)
                except Exception as e:
                    await send_error(result_queue, f"Error adding shell: {str(e)}")
                    logger.error(f"Error adding shell in handle update: {e}")

            case "closed_shell":
                logger.info(f"Closing shell {update.closed_shell}")

                sid: libs.Sid = libs.Sid(value=update.closed_shell)
                try:
                    await session.close_shell(sid=sid)
                except Exception as e:
                    await send_error(result_queue, f"Error closing shell: {str(e)}")
                    logger.exception(f"Error closing shell in handle update: {e}")

            case "pong":
                try:
                    latency_sec = get_timestamp() - update.pong
                    latency_ms = int(latency_sec * 1000)  # Convert to milliseconds
                    logger.info(f"Measured ping latency: {latency_ms}ms")
                    
                    # Use task registry for any background operation
                    asyncio.create_task(
                        session.send_latency_measurement(latency_ms),
                        name="send_latency"
                    )
                except Exception as e:
                    logger.error(f"Error processing ping-pong: {e}")

            case "error":
                logger.error(f"Error from client: {update.error}")
            case _:
                # Heartbeat message, ignored
                pass
                
    except Exception as e:
        # Catch-all error handler to prevent stream termination
        logger.exception(f"Unexpected error in handle_update: {e}")
        await send_error(result_queue, f"Internal error: {str(e)}")


def get_timestamp() -> int:
    now = datetime.now(timezone.utc)
    return int(now.timestamp())


async def send_msg(result_queue: asyncio.Queue, msg: terminalez_pb2.ServerUpdate):
    await result_queue.put(msg)


async def send_error(result_queue: asyncio.Queue, error: str):
    await send_msg(result_queue, terminalez_pb2.ServerUpdate(error=error))
