from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.websockets import manager

router = APIRouter()


@router.websocket("/ws/admin/map")
async def websocket_admin_map(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
