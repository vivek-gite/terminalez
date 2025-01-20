from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect

from connection_manager import ConnectionManager

app = FastAPI()

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)