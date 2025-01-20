from typing import List
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        """ Keep track of all active websocket connections """
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """ connect a websocket event """
        await websocket.accept()
        self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        """ disconnect a websocket event """
        self.active_connections.remove(websocket)

