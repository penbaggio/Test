from __future__ import annotations

import json
from typing import Dict, List

from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    def __init__(self) -> None:
        # user_id -> list[WebSocket]
        self.active_connections: Dict[int, List[WebSocket]] = {}
        # role -> set(user_ids)
        self.role_index: Dict[str, set[int]] = {}

    async def connect(self, user_id: int, role: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.setdefault(user_id, []).append(websocket)
        self.role_index.setdefault(role, set()).add(user_id)

    def disconnect(self, user_id: int, role: str, websocket: WebSocket) -> None:
        conns = self.active_connections.get(user_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self.active_connections.pop(user_id, None)
        # role index cleanup is optional here

    async def send_personal_message(self, user_id: int, message: dict) -> None:
        data = json.dumps(message, ensure_ascii=False)
        for ws in self.active_connections.get(user_id, []):
            await ws.send_text(data)

    async def broadcast_to_role(self, role: str, message: dict) -> None:
        data = json.dumps(message, ensure_ascii=False)
        for uid in list(self.role_index.get(role, set())):
            for ws in self.active_connections.get(uid, []):
                await ws.send_text(data)


ws_manager = ConnectionManager()
