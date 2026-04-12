"""
ConnectionManager
─────────────────
Manages active WebSocket connections per user.
Each user_id may have multiple sockets (multi-device).
Thread-safe for async FastAPI.
"""

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        # user_id -> list of active WebSocket connections
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)
        self._lock = asyncio.Lock()

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def connect(self, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections[user_id].append(ws)
        log.info("WS connected: user=%s  total_sockets=%d", user_id, self.socket_count(user_id))

    async def disconnect(self, user_id: str, ws: WebSocket) -> None:
        async with self._lock:
            sockets = self._connections.get(user_id, [])
            if ws in sockets:
                sockets.remove(ws)
            if not sockets:
                self._connections.pop(user_id, None)
        log.info("WS disconnected: user=%s  remaining=%d", user_id, self.socket_count(user_id))

    # ── Presence ───────────────────────────────────────────────────────────────

    def is_online(self, user_id: str) -> bool:
        return bool(self._connections.get(user_id))

    def online_users(self) -> list[str]:
        return list(self._connections.keys())

    def socket_count(self, user_id: str) -> int:
        return len(self._connections.get(user_id, []))

    # ── Delivery ───────────────────────────────────────────────────────────────

    async def send_to_user(self, user_id: str, payload: dict) -> bool:
        """Send JSON payload to all sockets of a user. Returns True if at least one delivery succeeded."""
        sockets = list(self._connections.get(user_id, []))
        if not sockets:
            return False

        dead: list[WebSocket] = []
        delivered = False

        for ws in sockets:
            try:
                await ws.send_text(json.dumps(payload, default=str))
                delivered = True
            except Exception:
                dead.append(ws)

        # Clean up dead sockets
        if dead:
            async with self._lock:
                for ws in dead:
                    try:
                        self._connections[user_id].remove(ws)
                    except ValueError:
                        pass
                if not self._connections.get(user_id):
                    self._connections.pop(user_id, None)

        return delivered

    async def broadcast_to_conversation(
        self,
        user_ids: list[str],
        payload: dict,
        exclude_sender: str | None = None,
    ) -> None:
        """Broadcast to all participants of a conversation."""
        tasks = [
            self.send_to_user(uid, payload)
            for uid in user_ids
            if uid != exclude_sender
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def send_error(self, ws: WebSocket, code: str, message: str) -> None:
        try:
            await ws.send_text(json.dumps({
                "event": "error",
                "data": {"code": code, "message": message},
            }))
        except Exception:
            pass

    # ── Heartbeat helper ──────────────────────────────────────────────────────

    async def ping(self, ws: WebSocket) -> bool:
        """Ping a single socket. Returns False if dead."""
        try:
            await ws.send_text(json.dumps({"event": "ping", "data": {"ts": datetime.now(timezone.utc).isoformat()}}))
            return True
        except Exception:
            return False


# Singleton — import this anywhere
manager = ConnectionManager()
