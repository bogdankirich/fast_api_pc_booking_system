from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_pc_update(self, pc_id: int, status: str, end_time: str = ""):
        message = {
            "type": "pc_status_update",
            "pc_id": pc_id,
            "status": status,
            "end_time": end_time,
        }
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except RuntimeError:
                pass


manager = ConnectionManager()
