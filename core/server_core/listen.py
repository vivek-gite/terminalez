import asyncio
from fastapi import FastAPI, WebSocket
import grpc.aio
import uvicorn
import logging

from core.comms_core.proto.terminalez import terminalez_pb2_grpc
from core.server_core.server_handle.grpc_server import GrpcServer
from core.server_core.state_manager.server_state import ServerState
from core.server_core.web.socket import get_session_ws


logger = logging.getLogger(__name__)
app = FastAPI()

server_state: ServerState | None = None

def init_server_state(state: ServerState):
    global server_state
    server_state = state


@app.get("/")
async def root():
    return {"message": "Hello from FastAPI!"}


@app.websocket("/api/s/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    try:
        # Acknowledge the websocket connection and upgrade from HTTP to WebSocket
        await websocket.accept()

        logger.info(f"WebSocket connection established with session ID: {session_id}")

        # Connect to the session
        await get_session_ws(name=session_id,
                             websocket=websocket,
                             server_state=server_state)

    except Exception as e:
        logger.exception(f"Websocket connection failed due to {e}")
        await websocket.close()


# Create a gRPC server
async def serve_grpc():
    server = grpc.aio.server()
    terminalez_pb2_grpc.add_TerminalEzServicer_to_server(servicer=GrpcServer(server_state=server_state),
                                                         server=server)

    listen_addr = '[::]:50051'
    server.add_insecure_port(listen_addr)

    logger.info(f"Starting gRPC server on {listen_addr}")

    await server.start()
    await server.wait_for_termination()


async def serve_fastapi():
    # Create a FastAPI server
    config = uvicorn.Config(
        app = app,
        host = "[::]",
        port = 8000,
        loop = "asyncio",
    )

    server = uvicorn.Server(config=config)
    logger.info(f"Starting FastAPI server on {config.host}:{config.port}")
    await server.serve()


async def start_servers():
    # Create tasks for both servers
    fastapi_task = asyncio.create_task(serve_fastapi())
    grpc_task = asyncio.create_task(serve_grpc())

    # wait for both servers
    await asyncio.gather(fastapi_task, grpc_task)
