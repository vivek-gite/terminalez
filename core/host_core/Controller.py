import asyncio
import logging
import queue
from datetime import datetime, timezone
from typing import Optional, Tuple

import grpc
import grpc.aio
from core.comms_core.proto.terminalez import terminalez_pb2_grpc, terminalez_pb2
from core.host_core.ConPTyRunner import ConPTyRunner
from core.host_core.ConPTyTerminal import Resize, ShellData, Data, Sync
from core.host_core.console_handler import ConsoleHandler

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 2 # seconds


class GrpcClient:
    def __init__(self, server_address: str):
        self.server_address = server_address
        self.channel: Optional[grpc.aio.Channel] = None
        self.stub: Optional[terminalez_pb2_grpc.TerminalEzStub] = None
        self.name: str = ""
        self.shells_output_queue: asyncio.Queue[terminalez_pb2.ClientUpdate] = asyncio.Queue(maxsize=1000)  # Bounded queue to prevent memory issues
        # self.shells_input_queue: dict = {}
        self.console_handler: ConsoleHandler = ConsoleHandler(self.shells_output_queue)

    async def connect(self) -> None:
        """Establishes connection to the gRPC server"""
        self.channel = grpc.aio.insecure_channel(self.server_address)
        self.stub = terminalez_pb2_grpc.TerminalEzStub(self.channel)

    async def close(self) -> None:
        """Closes the gRPC channel gracefully"""
        logger.info("Closing the gRPC channel")
        
        # Shutdown console handler first to clean up terminals
        try:
            await self.console_handler.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down console handler: {e}")
        
        # Close gRPC connection
        request = terminalez_pb2.CloseRequest(session_id=self.name)
        if self.channel and (self.channel.get_state() in (grpc.ChannelConnectivity.IDLE, grpc.ChannelConnectivity.READY)):
            try:
                await self.stub.Close(request)
                await self.channel.close()
            except Exception as e:
                logger.error(f"Error closing gRPC channel: {e}")

    async def initiate_connection(self, machine_name: str) -> Tuple[str, str]:
        """
        Initiates a connection with the server and gets a session ID and URL.

        Args:
            machine_name (str): Name of the machine initiating the connection

        Returns:
            Tuple[str, str]: Session ID and URL pair

        Raises:
            Exception: If connection fails or server returns an error
        """
        if not machine_name or not machine_name.strip():
            raise ValueError("Machine name cannot be empty")

        if not self.stub:
            raise Exception("Client not connected - call connect() first")

        try:
            request = terminalez_pb2.InitialConnectionRequest(
                m_name=machine_name,
                available_shells=ConPTyRunner.available_terminals_list()
            )

            response = await asyncio.wait_for(
                self.stub.InitiateConnection(request),
                timeout=10.0  # 10 seconds timeout
            )

            if not response or not response.session_id or not response.url:
                raise ValueError("Server returned invalid response")

            # Set the session id
            self.name = response.session_id

            return response.session_id, response.url


        except asyncio.TimeoutError as e:
            logger.exception(f"Connection request timed out for machine: {machine_name}. Error: {e}")
            raise TimeoutError("Server connection timed out")
        except grpc.RpcError as e:
            logger.exception(f"gRPC error during connection: {e}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error during connection: {e}")
            raise



    async def run(self):
        last_retry: float = datetime.now(timezone.utc).timestamp()
        retries: int = 0
        while True:
            try:
                await self.try_channel()
            except Exception as e:
                logger.exception(f"Error in gRPC connection: {e}")
                current_time: float = datetime.now(timezone.utc).timestamp()
                if last_retry - current_time > 10:
                    # Resetting the retries to prevent the backoff interval
                    # from growing indefinitely if errors are infrequent
                    retries = 0
                logger.error(f"Disconnected, retrying in {2 ** retries} seconds...")
                await asyncio.sleep(2 ** retries)  # Exponential backoff
                retries += 1
            except asyncio.CancelledError as e:
                logger.exception(f"Error in running the channel: {e}")
                break
            last_retry = datetime.now(timezone.utc).timestamp()



    async def spawn_shell_task(self, sid: int, x: int, y: int, shell_info: str="") -> None:
        create_shell = terminalez_pb2.NewShell(shell_id=sid, x=x, y=y, shell_info=shell_info)
        client_update = terminalez_pb2.ClientUpdate(created_shell=create_shell)

        await self.console_handler.output_pipe.put(client_update)

        terminal_path = shell_info.strip().split(";")[1]

        shell_task = asyncio.create_task(self.console_handler.shell_task(sid=sid, terminal_path=terminal_path))
        await shell_task

        close_shell = terminalez_pb2.ClientUpdate(closed_shell=sid)
        await self.console_handler.output_pipe.put(close_shell)


    # TODO: Implement the sync mechanism
    async def try_channel(self):

        await self.connect()

        hello = terminalez_pb2.ClientUpdate(session_id=self.name)

        response_stream: grpc.aio.StreamStreamCall = self.stub.Channel()

        await send_message(response_stream, hello)

        # Create a queue to store incoming messages from the server
        incoming_data_queue = asyncio.Queue()
        # Start a background task to continuously read data from the gRPC stream
        # and add it to the queue for processing
        asyncio.create_task(get_stream_data(response_stream, incoming_data_queue))

        while True:
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(get_incoming_data_queue(incoming_data_queue), name="response_stream"),
                    asyncio.create_task(asyncio.sleep(HEARTBEAT_INTERVAL), name="heartbeat_interval"),
                    asyncio.create_task(shell_output_data(self.shells_output_queue), name="shell_output_data")
                ],
                return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel all pending tasks
            for task in pending:
                task.cancel()

            # Get the first completed task
            done_result = done.pop()            # Log the completed task
            logger.info(f"The first completed task in try_channel is {done_result.get_name()}")
              # Handle the completed task
            match done_result.get_name():
                case "heartbeat_interval":
                    await send_message(response_stream, terminalez_pb2.ClientUpdate())
                    continue
                case "shell_output_data":
                    shell_output = done_result.result()
                    if shell_output is not None:
                        self.shells_output_queue.task_done()
                        await send_message(response_stream, shell_output)
                        
                        # Monitor queue size for potential backpressure issues
                        qsize = self.shells_output_queue.qsize()
                        if qsize > 50:  # Warn if queue is growing large
                            logger.warning(f"Shell output queue size is high: {qsize} - potential backpressure")
                    continue
                case _:
                    pass

            message: terminalez_pb2.ServerUpdate = done_result.result()

            match message.WhichOneof("server_message"):
                case "terminal_input":
                    data = message.terminal_input
                    
                    # Creating a new Data object to send to the terminal
                    shell_data = Data(data=data.data)
                    sent = await self.console_handler.send_input_to_terminal(sid=data.shell_id, data=shell_data)
                    if not sent:
                        logger.error(f"Failed to send input to terminal with ID {data.shell_id}")
                        await send_message(response_stream, terminalez_pb2.ClientUpdate(error=f"Failed to send input to terminal {data.shell_id}"))
                case "create_shell":
                    shell_id = message.create_shell.shell_id
                    if shell_id not in self.console_handler.active_terminals:
                        asyncio.create_task(self.spawn_shell_task(shell_id, message.create_shell.x, message.create_shell.y, message.create_shell.shell_info ))
                    else:
                        logger.error(f"Shell with ID {shell_id} already exists.")
                case "close_shell":
                    shell_id = message.close_shell
                    # Clean up terminal through the console handler's cleanup method
                    if shell_id in self.console_handler.active_terminals:
                        await self.console_handler._cleanup_terminal(shell_id)

                    await send_message(response_stream, terminalez_pb2.ClientUpdate(closed_shell=shell_id))
                case "sync":
                    seq_nums_map: terminalez_pb2.SequenceNumbers = message.sync
                    for sid, seq in seq_nums_map.map.items():
                        shell_data_sync = Sync(seq=seq)
                        sent = await self.console_handler.send_input_to_terminal(sid=sid, data=shell_data_sync)
                        if not sent:
                            logger.warning("No sender found for shell ID %s", sid)
                            await send_message(response_stream, terminalez_pb2.ClientUpdate(closed_shell=sid))

                case "resize":
                    resize = Resize(message.resize.rows, message.resize.cols)
                    shell_id = message.resize.shell_id
                    
                    # Use the new send_input_to_terminal method for resize operations
                    sent = await self.console_handler.send_input_to_terminal(sid=shell_id, data=resize)
                    if not sent:
                        logger.error(f"Failed to send resize to terminal {shell_id}")
                        await send_message(response_stream, terminalez_pb2.ClientUpdate(error=f"Failed to resize terminal {shell_id}"))

                case "ping":
                    # Echo back the timestamp
                    logger.info(f"Received ping: {message.ping}")
                    await send_message(response_stream, terminalez_pb2.ClientUpdate(pong=message.ping))
                case "error":
                    logger.error(f"Server returned error: {message.error}")


async def shell_output_data(shell_output_queue: asyncio.Queue) -> Optional[terminalez_pb2.ClientUpdate]:
    """
    Gets data from the shell output queue by continuously checking if data is available.

    This function uses a while loop to check if the queue has data available,
    returning immediately when data is found or yielding control to allow other tasks to run.

    Returns:
        Optional[terminalez_pb2.ClientUpdate]: The queue data when available
    """
    try:
        while True:
            # Check if queue has data without blocking
            if not shell_output_queue.empty():
                # Get data from queue (this should not block since we checked it's not empty)
                return await shell_output_queue.get()
            else:
                # Queue is empty, yield control to other tasks briefly
                await asyncio.sleep(0.01)  # Small sleep to prevent busy waiting
    except Exception as e:
        logger.warning(f"Error retrieving shell output data: {e}")
        return None


async def get_stream_data(response_stream: grpc.aio.StreamStreamCall, incoming_data_queue: asyncio.Queue):
    """
    Continuously reads data from a gRPC stream and adds it to an async queue for processing.

    This function runs in an infinite loop until an exception occurs, reading messages
    from the gRPC stream one by one and placing them in the provided queue. It uses
    non-blocking put operations to avoid deadlocks.

    Args:
        response_stream (grpc.aio.StreamStreamCall): The bidirectional gRPC stream to read from
        incoming_data_queue (asyncio.Queue): The queue where received messages will be stored

    Raises:
        Exception: Propagates any exception that occurs during stream reading after logging it

    Note:
        This function is designed to be run as a background task and will continue
        until an exception occurs or the stream closes.
    """
    while True:
        try:
            item = await response_stream.read()
            logger.info(f"Client Received data: {item}")
            incoming_data_queue.put_nowait(item)
        except Exception as e:
            logger.exception(f"Error in reading stream data: {e}")
            raise

async def get_incoming_data_queue(data_queue: asyncio.Queue) -> terminalez_pb2.ServerUpdate:
    """Gets data from the queue. Returns None if the iterator is exhausted."""
    return await data_queue.get()

async def send_message(stream: grpc.aio.StreamStreamCall, message: terminalez_pb2.ClientUpdate):
    try:
        if message is None:
            await stream.done_writing()
        await stream.write(message)
    except asyncio.CancelledError as e:
        logger.exception(f"Error in sending message: {e}")
        raise