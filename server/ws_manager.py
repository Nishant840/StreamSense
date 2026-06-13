import logging
from fastapi import WebSocket

logger = logging.getLogger("ws-manager")

class WebSocketManager:

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            f"Client connected | "
            f"total={len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(
            f"Client disconnected | "
            f"total={len(self.active_connections)}"
        )

    async def broadcast(self, message: dict) -> None:
        dead_connections = []

        for websocket in self.active_connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                dead_connections.append(websocket)
        
        for websocket in dead_connections:
            self.disconnect(websocket)

    async def send_personal(
            self,
            websocket: WebSocket,
            message: dict,
    ) -> None:
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send personal message: {e}")
            self.disconnect(websocket)

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)