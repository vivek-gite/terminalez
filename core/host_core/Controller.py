import asyncio
import logging
import queue
from datetime import datetime, timezone
from typing import Optional, Tuple

import grpc
import grpc.aio
from core.comms_core.proto.terminalez import terminalez_pb2_grpc, terminalez_pb2
from core.host_core.console_handler import ConsoleHandler
from core.host_core.runner import Runner

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 2 # seconds


class GrpcClient:
    def __init__(self, server_address: str):
        self.server_address = server_address
        self.channel: Optional[grpc.aio.Channel] = None
        self.stub: Optional[terminalez_pb2_grpc.TerminalEzStub] = None
        self.name: str = ""
        self.shells_output_queue: queue.Queue = queue.Queue()
        # self.shells_input_queue: dict = {}
        self.console_handler: ConsoleHandler = ConsoleHandler(self.shells_output_queue)

    async def connect(self) -> None:
        """Establishes connection to the gRPC server"""
        self.channel = grpc.aio.insecure_channel(self.server_address)
        self.stub = terminalez_pb2_grpc.TerminalEzStub(self.channel)

    async def close(self) -> None:
        """Closes the gRPC channel gracefully"""
        logger.info("Closing the gRPC channel")
        request = terminalez_pb2.CloseRequest(session_id=self.name)
        if self.channel and (self.channel.get_state() in (grpc.ChannelConnectivity.IDLE, grpc.ChannelConnectivity.READY)):
            await self.stub.Close(request)
            await self.channel.close()

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
                available_shells=Runner.available_terminals_list()
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

        self.console_handler.output_pipe.put_nowait(client_update)

        terminal_path = shell_info.strip().split(";")[1]

        await asyncio.create_task(self.console_handler.shell_task(sid=sid, terminal_path=terminal_path))

        close_shell = terminalez_pb2.ClientUpdate(closed_shell=sid)
        self.console_handler.output_pipe.put_nowait(close_shell)


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
            done_result = done.pop()

            # Log the completed task
            logger.info(f"The first completed task in try_channel is {done_result.get_name()}")

            # Handle the completed task
            match done_result.get_name():
                case "heartbeat_interval":
                    await send_message(response_stream, terminalez_pb2.ClientUpdate())
                    continue
                case "shell_output_data":
                    shell_output = self.shells_output_queue.get_nowait()
                    self.shells_output_queue.task_done()
                    await send_message(response_stream, shell_output)
                    continue
                case _:
                    pass

            message:terminalez_pb2.ServerUpdate = done_result.result()

            match message.WhichOneof("server_message"):
                case "terminal_input":
                    data = message.terminal_input
                    decoded_data = data.data.decode("utf-8")
                    sender: queue.Queue = self.console_handler.terminal_writes.get(data.shell_id)

                    sender.put_nowait(decoded_data)
                case "create_shell":
                    id = message.create_shell.shell_id
                    if id not in self.console_handler.terminal_writes:
                        asyncio.create_task(self.spawn_shell_task(id, message.create_shell.x, message.create_shell.y, message.create_shell.shell_info ))
                    else:
                        logger.error(f"Shell with ID {id} already exists.")
                case "close_shell":
                    id = message.close_shell
                    del self.console_handler.terminal_writes[id]

                    await send_message(response_stream, terminalez_pb2.ClientUpdate(closed_shell=id))
                case "sync":
                    pass
                case "resize":
                    pass
                case "ping":
                    # Echo back the timestamp
                    logger.info(f"Received ping: {message.ping}")
                    await send_message(response_stream, terminalez_pb2.ClientUpdate(pong=message.ping))
                case "error":
                    logger.error(f"Server returned error: {message.error}")


async def shell_output_data(shell_output_queue: queue.Queue):
    while True:
        if shell_output_queue._qsize() > 0:
            break
        await asyncio.sleep(1)


async def get_stream_data(response_stream: grpc.aio.StreamStreamCall, incoming_data_queue: asyncio.Queue):
    try:
        data = await response_stream.read()
        incoming_data_queue.put_nowait(data)
    except asyncio.CancelledError as e:
        logger.exception(f"Error in reading stream data: {e}")
        raise

async def get_incoming_data_queue(queue: asyncio.Queue) -> terminalez_pb2.ServerUpdate:
    """Gets data from the queue. Returns None if the iterator is exhausted."""
    return await queue.get()

async def send_message(stream: grpc.aio.StreamStreamCall, message: terminalez_pb2.ClientUpdate):
    try:
        if message is None:
            await stream.done_writing()
        await stream.write(message)
    except asyncio.CancelledError as e:
        logger.exception(f"Error in sending message: {e}")
        raise