from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List

router = APIRouter()

active_connections: List[WebSocket] = []

@router.websocket("/notifications")
async def notifications_ws(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await broadcast(data)
    except WebSocketDisconnect:
        active_connections.remove(websocket)

async def broadcast(message: str):
    for connection in active_connections:
        await connection.send_text(message)