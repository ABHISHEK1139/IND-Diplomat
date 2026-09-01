"""WebSocket manager for live assessment streaming.
Clients connect and subscribe to topics; server can publish job updates.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Dict, Any, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self._subscriptions: Dict[str, Set[str]] = {}  # topic -> conn_ids

    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        conn_id = f"ws_{uuid.uuid4().hex[:10]}"
        self.active_connections[conn_id] = websocket
        logger.info("[WebSocket] Client connected: %s (total: %d)", conn_id, len(self.active_connections))
        return conn_id

    def disconnect(self, conn_id: str) -> None:
        self.active_connections.pop(conn_id, None)
        for subs in self._subscriptions.values():
            subs.discard(conn_id)
        logger.info("[WebSocket] Client disconnected: %s (total: %d)", conn_id, len(self.active_connections))

    async def send_personal(self, conn_id: str, message: Dict[str, Any]) -> bool:
        ws = self.active_connections.get(conn_id)
        if ws:
            try:
                await ws.send_json(message)
                return True
            except Exception:
                self.disconnect(conn_id)
        return False

    async def broadcast(self, message: Dict[str, Any]) -> int:
        sent = 0
        disconnected = []
        for conn_id, ws in list(self.active_connections.items()):
            try:
                await ws.send_json(message)
                sent += 1
            except Exception:
                disconnected.append(conn_id)
        for conn_id in disconnected:
            self.disconnect(conn_id)
        return sent

    async def subscribe(self, conn_id: str, topic: str) -> None:
        self._subscriptions.setdefault(topic, set()).add(conn_id)

    async def publish_topic(self, topic: str, message: Dict[str, Any]) -> int:
        subscribers = self._subscriptions.get(topic, set())
        sent = 0
        for conn_id in list(subscribers):
            if await self.send_personal(conn_id, message):
                sent += 1
        return sent

    async def send_personal_bytes(self, conn_id: str, message: bytes) -> bool:
        ws = self.active_connections.get(conn_id)
        if ws:
            try:
                await ws.send_bytes(message)
                return True
            except Exception:
                self.disconnect(conn_id)
        return False

    async def publish_topic_bytes(self, topic: str, message: bytes, exclude_conn_id: str = None) -> int:
        subscribers = self._subscriptions.get(topic, set())
        sent = 0
        for conn_id in list(subscribers):
            if exclude_conn_id and conn_id == exclude_conn_id:
                continue
            if await self.send_personal_bytes(conn_id, message):
                sent += 1
        return sent


# module-level manager
manager = ConnectionManager()
