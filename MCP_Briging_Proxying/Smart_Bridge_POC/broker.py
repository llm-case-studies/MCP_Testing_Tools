from __future__ import annotations
import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Set, Optional

from fastapi import WebSocket

try:
    from .process import StdioProcess
    from .filters import filters
except ImportError:
    from process import StdioProcess
    from filters import filters

logger = logging.getLogger("stdio-gateway")

@dataclass
class Session:
    session_id: str
    queue: asyncio.Queue[bytes] = field(default_factory=lambda: asyncio.Queue(maxsize=100))
    websockets: Set[WebSocket] = field(default_factory=set)
    last_beat: float = field(default_factory=time.time)

class Broker:
    def __init__(self, proc: StdioProcess):
        self.proc = proc
        self.sessions: Dict[str, Session] = {}
        self.id_to_session: Dict[Any, str] = {}  # JSON-RPC id → session_id
        self.inbox = asyncio.Queue()  # messages from proc → dict
        self.max_in_flight = int(os.environ.get("BRIDGE_MAX_IN_FLIGHT", "128"))
        self.in_flight = 0
        self._inflight_lock = asyncio.Lock()
        # Allow tests to stub/replace filters
        self.filters = filters

    async def start(self) -> None:
        await self.proc.start()
        asyncio.create_task(self._reader_loop())
        asyncio.create_task(self.pump())

    async def _reader_loop(self):
        try:
            while True:
                msg = await self.proc.read_json()
                await self.inbox.put(msg)
        except Exception as e:
            logger.exception("Reader loop ended: %s", e)
            await self.broadcast({"type": "bridge/error", "error": str(e)})

    def create_session(self) -> str:
        sid = uuid.uuid4().hex
        self.sessions[sid] = Session(sid)
        logger.info("New session %s (total=%d)", sid, len(self.sessions))
        return sid

    def get_session(self, sid: str) -> Session:
        if sid not in self.sessions:
            raise KeyError("Unknown session")
        return self.sessions[sid]

    async def route_from_client(self, session_id: str, payload: Dict[str, Any]) -> None:
        if "id" in payload:
            self.id_to_session[payload["id"]] = session_id
        filtered = await self.filters.apply("client_to_server", session_id, payload)
        if filtered is None:
            return
        async with self._inflight_lock:
            while self.in_flight >= self.max_in_flight:
                await asyncio.sleep(0.002)
            self.in_flight += 1
        try:
            await self.proc.write_json(filtered)
        finally:
            async with self._inflight_lock:
                self.in_flight -= 1

    async def pump(self):
        while True:
            msg = await self.inbox.get()
            try:
                target_sid: Optional[str] = None
                if "id" in msg and msg["id"] in self.id_to_session:
                    target_sid = self.id_to_session.pop(msg["id"], None)
                if target_sid and target_sid in self.sessions:
                    filtered = await self.filters.apply("server_to_client", target_sid, msg)
                    if filtered is not None:
                        await self._send(target_sid, filtered)
                else:
                    for sid in list(self.sessions.keys()):
                        filtered = await self.filters.apply("server_to_client", sid, msg)
                        if filtered is not None:
                            await self._send(sid, filtered)
            finally:
                self.inbox.task_done()

    async def _send(self, session_id: str, obj: Any) -> None:
        if session_id not in self.sessions:
            return
        sess = self.sessions[session_id]
        try:
            data = f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")
            await sess.queue.put(data)
        except asyncio.QueueFull:
            logger.warning("Session %s SSE queue full; dropping message", session_id)
        dead: list[WebSocket] = []
        for ws in list(sess.websockets):
            try:
                await ws.send_text(json.dumps(obj, ensure_ascii=False))
            except Exception:
                dead.append(ws)
        for ws in dead:
            try:
                sess.websockets.remove(ws)
            except KeyError:
                pass

    async def broadcast(self, obj: Any) -> None:
        for sid in list(self.sessions.keys()):
            await self._send(sid, obj)
