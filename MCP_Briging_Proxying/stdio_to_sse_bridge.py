#!/usr/bin/env python3
"""
Stdio → SSE bridge for MCP/LSP-style JSON-RPC servers.

This service launches a stdio-based server (e.g., Serena) and exposes:
  - POST /messages         : send a JSON-RPC request/notification to the stdio server
  - GET  /events?session=  : Server-Sent Events stream for responses/notifications
  - GET  /health           : liveness & readiness

Key features
- Content-Length framing for stdio (\r\n headers, exact byte reads)
- Per-client sessions with independent SSE streams
- Correlates responses by `id` back to the originating session
- Broadcasts notifications (no `id`) to all sessions
- Back-pressure-safe queues with size bounds and timeouts
- Heartbeats on SSE

Run:
  python stdio_to_sse_bridge.py --cmd "serena --flag1 --flag2" --port 8080

Requires: fastapi, uvicorn
  pip install fastapi uvicorn

Notes:
- Only one stdio process is spawned; it represents a single logical MCP client.
- Multiple SSE clients can attach concurrently; requests are serialized through the
  bridge and responses are demultiplexed by `id`.
- If your server can handle concurrency safely, you may raise the in-flight cap.
"""

from __future__ import annotations
import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse, PlainTextResponse

# ----------------------------- Logging ------------------------------------
logger = logging.getLogger("stdio-sse-bridge")
handler = logging.StreamHandler(sys.stderr)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# ----------------------------- Framing ------------------------------------
CRLF = b"\r\n"
HEADER_SEP = CRLF + CRLF

async def read_exact(stream: asyncio.StreamReader, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = await stream.read(n - len(buf))
        if not chunk:
            raise EOFError("Unexpected EOF while reading framed body")
        buf.extend(chunk)
    return bytes(buf)

async def read_headers(stream: asyncio.StreamReader) -> Dict[str, str]:
    # Read until CRLFCRLF
    data = bytearray()
    while True:
        chunk = await stream.read(1)
        if not chunk:
            raise EOFError("Unexpected EOF while reading headers")
        data.extend(chunk)
        if data.endswith(HEADER_SEP):
            break
    header_text = data[:-4].decode("ascii", errors="strict")
    headers: Dict[str, str] = {}
    for line in header_text.split("\r\n"):
        if not line:
            continue
        if ":" not in line:
            raise ValueError(f"Malformed header line: {line!r}")
        k, v = line.split(":", 1)
        headers[k.strip().lower()] = v.strip()
    return headers

async def read_framed_json(stream: asyncio.StreamReader) -> Dict[str, Any]:
    headers = await read_headers(stream)
    if "content-length" not in headers:
        raise ValueError("Missing Content-Length header")
    try:
        length = int(headers["content-length"]) 
    except Exception as e:
        raise ValueError("Bad Content-Length") from e
    body = await read_exact(stream, length)
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Bad JSON payload: {e}")

def encode_framed_json(obj: Dict[str, Any]) -> bytes:
    data = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(data)}\r\n\r\n".encode("ascii")
    return header + data

# ----------------------------- Process ------------------------------------
@dataclass
class StdioProcess:
    cmd: str
    cwd: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    proc: Optional[asyncio.subprocess.Process] = None
    reader: Optional[asyncio.StreamReader] = None
    writer: Optional[asyncio.StreamWriter] = None
    stderr_task: Optional[asyncio.Task] = None
    stdout_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        logger.info("Starting stdio server: %s", self.cmd)
        self.proc = await asyncio.create_subprocess_shell(
            self.cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.cwd,
            env=self.env,
        )
        assert self.proc.stdout and self.proc.stdin and self.proc.stderr
        self.reader = self.proc.stdout
        self.writer = self.proc.stdin
        # stderr logger
        async def _pump_stderr():
            try:
                while True:
                    line = await self.proc.stderr.readline()
                    if not line:
                        break
                    logger.info("[server stderr] %s", line.rstrip().decode(errors="replace"))
            except Exception:
                logger.exception("stderr pump failed")
        self.stderr_task = asyncio.create_task(_pump_stderr())

    async def write_json(self, obj: Dict[str, Any]) -> None:
        if not self.writer:
            raise RuntimeError("Process not started")
        payload = encode_framed_json(obj)
        self.writer.write(payload)
        await self.writer.drain()

    async def read_json(self) -> Dict[str, Any]:
        if not self.reader:
            raise RuntimeError("Process not started")
        return await read_framed_json(self.reader)

    async def wait(self) -> int:
        assert self.proc is not None
        return await self.proc.wait()

    async def terminate(self) -> None:
        if self.proc and self.proc.returncode is None:
            logger.info("Terminating stdio server")
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                logger.warning("Killing stdio server")
                self.proc.kill()
                await self.proc.wait()

# ----------------------------- Broker -------------------------------------
@dataclass
class Session:
    session_id: str
    queue: asyncio.Queue[bytes] = field(default_factory=lambda: asyncio.Queue(maxsize=100))
    last_beat: float = field(default_factory=time.time)

class Broker:
    def __init__(self, proc: StdioProcess):
        self.proc = proc
        self.sessions: Dict[str, Session] = {}
        self.id_to_session: Dict[Any, str] = {}  # JSON-RPC id → session_id
        self.inbox = asyncio.Queue()  # messages from proc → dict
        self._reader_task: Optional[asyncio.Task] = None
        self._gc_task: Optional[asyncio.Task] = None
        self.max_in_flight = 128
        self.in_flight = 0
        self._inflight_lock = asyncio.Lock()

    async def start(self) -> None:
        await self.proc.start()
        self._reader_task = asyncio.create_task(self._reader_loop())
        self._gc_task = asyncio.create_task(self._gc_loop())

    async def _reader_loop(self):
        try:
            while True:
                msg = await self.proc.read_json()
                await self.inbox.put(msg)
        except Exception as e:
            logger.exception("Reader loop ended: %s", e)
            # broadcast poison-pill event
            await self.broadcast({"type": "bridge/error", "error": str(e)})

    async def _gc_loop(self):
        while True:
            await asyncio.sleep(30)
            now = time.time()
            stale = [sid for sid, s in self.sessions.items() if now - s.last_beat > 300]
            for sid in stale:
                logger.info("GC removing stale session %s", sid)
                self.sessions.pop(sid, None)

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
        # Correlate responses by id if present
        if "id" in payload:
            self.id_to_session[payload["id"]] = session_id
        async with self._inflight_lock:
            while self.in_flight >= self.max_in_flight:
                await asyncio.sleep(0.005)
            self.in_flight += 1
        try:
            await self.proc.write_json(payload)
        finally:
            async with self._inflight_lock:
                self.in_flight -= 1

    async def pump(self):
        # Demultiplex proc → sessions
        while True:
            msg = await self.inbox.get()
            try:
                if "id" in msg and msg["id"] in self.id_to_session:
                    sid = self.id_to_session.pop(msg["id"], None)
                    if sid and sid in self.sessions:
                        await self._send(sid, msg)
                    else:
                        await self.broadcast(msg)  # fallback
                else:
                    # Notifications and uncorrelated events → broadcast
                    await self.broadcast(msg)
            finally:
                self.inbox.task_done()

    async def _send(self, session_id: str, obj: Any) -> None:
        if session_id not in self.sessions:
            return
        try:
            data = f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")
            await self.sessions[session_id].queue.put(data)
        except asyncio.QueueFull:
            logger.warning("Session %s queue full; dropping message", session_id)

    async def broadcast(self, obj: Any) -> None:
        data = f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")
        for s in list(self.sessions.values()):
            try:
                await s.queue.put(data)
            except asyncio.QueueFull:
                logger.warning("Session %s queue full; dropping broadcast", s.session_id)

# ----------------------------- App ----------------------------------------
app = FastAPI()

bridge_proc: Optional[StdioProcess] = None
broker: Optional[Broker] = None

@app.on_event("startup")
async def _startup():
    global bridge_proc, broker
    # Parse CLI when running as module
    if not hasattr(app.state, "config"):
        return
    cfg = app.state.config
    bridge_proc = StdioProcess(cmd=cfg.cmd, cwd=cfg.cwd, env=os.environ.copy())
    broker = Broker(bridge_proc)
    await broker.start()
    asyncio.create_task(broker.pump())

@app.get("/health")
async def health():
    ok = (bridge_proc is not None and broker is not None and bridge_proc.proc and bridge_proc.proc.returncode is None)
    return JSONResponse({"status": "ok" if ok else "degraded"})

@app.post("/sessions")
async def create_session():
    if broker is None:
        raise HTTPException(503, "Bridge not ready")
    sid = broker.create_session()
    return {"session": sid}

@app.get("/events")
async def events(session: str):
    if broker is None:
        raise HTTPException(503, "Bridge not ready")
    try:
        sess = broker.get_session(session)
    except KeyError:
        raise HTTPException(404, "Unknown session")

    async def event_stream() -> AsyncGenerator[bytes, None]:
        # Initial retry advice per SSE spec
        yield b"retry: 3000\n\n"
        # Send a hello event
        hello = {"type": "bridge/hello", "session": session, "ts": time.time()}
        yield f"data: {json.dumps(hello)}\n\n".encode()
        while True:
            try:
                # Heartbeat if idle
                try:
                    item = await asyncio.wait_for(sess.queue.get(), timeout=15)
                    yield item
                    sess.queue.task_done()
                except asyncio.TimeoutError:
                    yield b": keep-alive\n\n"  # SSE comment as heartbeat
                sess.last_beat = time.time()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("SSE stream error")
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.post("/messages")
async def post_message(request: Request):
    if broker is None:
        raise HTTPException(503, "Bridge not ready")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")

    session_id = request.query_params.get("session")
    if not session_id:
        raise HTTPException(400, "session query parameter is required")
    if session_id not in broker.sessions:
        raise HTTPException(404, "Unknown session")

    # Ensure JSON-RPC 2.0 basics if desired (optional)
    if isinstance(payload, dict) and "jsonrpc" not in payload:
        payload["jsonrpc"] = "2.0"
    # If client omitted id (notification), we pass through unchanged.
    # For requests that expect replies and lack an id, assign one.
    if "id" not in payload and payload.get("method"):
        payload["id"] = str(uuid.uuid4())

    await broker.route_from_client(session_id, payload)
    return JSONResponse({"status": "accepted", "id": payload.get("id")})

@app.get("/")
async def root():
    return PlainTextResponse("Stdio→SSE bridge is running. Use /sessions, /events, /messages.")

# ----------------------------- Main ---------------------------------------

def parse_args(argv: Optional[list[str]] = None):
    p = argparse.ArgumentParser(description="Stdio→SSE bridge")
    p.add_argument("--cmd", required=True, help="Command to run the stdio server, e.g. 'serena --stdio'")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8080)))
    p.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    p.add_argument("--cwd", default=None)
    return p.parse_args(argv)


def main():
    args = parse_args()
    # Stash config for startup event
    app.state.config = args
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
