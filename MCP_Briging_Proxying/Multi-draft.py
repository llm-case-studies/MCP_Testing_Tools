# Create enhanced stdio gateway with OpenAPI, SSE, WebSocket, streaming HTML, and pluggable filters
code = r'''#!/usr/bin/env python3
"""
Stdio ↔ Gateway: JSON-RPC stdio server exposed over HTTP POST, SSE, WebSocket,
+ streaming HTML viewer. Includes OpenAPI docs, pluggable filter chain for
sanitization, logging, and on-the-fly enhancement.

Usage
-----
  pip install fastapi uvicorn pydantic
  python stdio_gateway_v1_1.py --cmd "serena --stdio" --port 8080

Endpoints (OpenAPI at /docs)
----------------------------
- POST /sessions                     → create client session {session}
- GET  /events?session=...           → SSE stream of responses/notifications
- POST /messages?session=...         → send JSON-RPC to stdio server
- WS   /ws?session=...               → bidirectional via WebSocket
- GET  /live                         → streaming HTML console (SSE based)
- GET  /filters                      → list installed filters
- POST /filters/{name}               → {enabled: bool} toggle at runtime
- GET  /health                       → liveness

Design
------
- One stdio child process (Serena) shared by many clients.
- Broker correlates replies (by JSON-RPC id) back to the originating session.
- Notifications (no id) are broadcast to all sessions.
- FilterChain hooks:
    • client_to_server(session, message) → message | None (drop)
    • server_to_client(session, message) → message | None (drop)
  Filters can redact, enrich (attach `bridge_meta`), or block.

Notes
-----
- Keep server logs on stderr; protocol framing on stdout only.
- SSE heartbeats and WebSocket support included.
- Built-in filters:
    1) redact_secrets: masks common key/token patterns in strings
    2) add_bridge_meta: adds timestamps + direction
"""

from __future__ import annotations
import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, Optional, Callable, List, Set

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse, PlainTextResponse, HTMLResponse
from pydantic import BaseModel, Field

# ----------------------------- Logging ------------------------------------
logger = logging.getLogger("stdio-gateway")
handler = logging.StreamHandler(sys.stderr)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# ----------------------------- Models (OpenAPI) ---------------------------
class SessionOut(BaseModel):
    session: str

class PostAccepted(BaseModel):
    status: str = Field("accepted")
    id: Optional[str] = None

class ToggleFilterIn(BaseModel):
    enabled: bool

class FilterInfo(BaseModel):
    name: str
    enabled: bool
    description: Optional[str] = None

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
    data = bytearray()
    while True:
        ch = await stream.read(1)
        if not ch:
            raise EOFError("Unexpected EOF while reading headers")
        data.extend(ch)
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

# ----------------------------- Filters ------------------------------------
FilterFunc = Callable[[str, str, Dict[str, Any]], asyncio.Future]

class FilterChain:
    def __init__(self):
        self.filters: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, func: Callable[[str, str, Dict[str, Any]], Any], *, enabled: bool = True, description: str = ""):
        self.filters[name] = {"func": func, "enabled": enabled, "description": description}

    def set_enabled(self, name: str, enabled: bool):
        if name not in self.filters:
            raise KeyError(name)
        self.filters[name]["enabled"] = enabled

    def list(self) -> List[FilterInfo]:
        out: List[FilterInfo] = []
        for n, meta in self.filters.items():
            out.append(FilterInfo(name=n, enabled=bool(meta["enabled"]), description=meta.get("description")))
        return out

    async def apply(self, direction: str, session_id: str, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        obj = message
        for n, meta in self.filters.items():
            if not meta["enabled"]:
                continue
            func = meta["func"]
            try:
                res = func(direction, session_id, obj)
                if asyncio.iscoroutine(res):
                    res = await res
                if res is None:  # dropped by filter
                    logger.info("Message dropped by filter %s", n)
                    return None
                obj = res
            except Exception:
                logger.exception("Filter %s failed; passing message through", n)
        return obj

filters = FilterChain()

# Built-in: redact secrets in strings
SECRET_PATTERNS = [
    re.compile(r"(?i)(?:api|secret|access|bearer)[-_ ]?(?:key|token)\s*[:=]\s*[A-Za-z0-9._-]{12,}"),
    re.compile(r"(?i)sk-[A-Za-z0-9]{20,}"),
]

def _walk_strings(value: Any, fn: Callable[[str], str]) -> Any:
    if isinstance(value, str):
        return fn(value)
    if isinstance(value, list):
        return [_walk_strings(v, fn) for v in value]
    if isinstance(value, dict):
        return {k: _walk_strings(v, fn) for k, v in value.items()}
    return value


def redact_secrets(direction: str, session_id: str, msg: Dict[str, Any]) -> Dict[str, Any]:
    def scrub(s: str) -> str:
        out = s
        for pat in SECRET_PATTERNS:
            out = pat.sub("[REDACTED]", out)
        return out
    return _walk_strings(msg, scrub)

filters.register("redact_secrets", redact_secrets, description="Masks common API keys/tokens in all string fields")

# Built-in: add bridge meta (timestamps & direction)

def add_bridge_meta(direction: str, session_id: str, msg: Dict[str, Any]) -> Dict[str, Any]:
    meta = msg.get("bridge_meta", {}) if isinstance(msg, dict) else {}
    meta.update({"ts": time.time(), "direction": direction, "session": session_id})
    if isinstance(msg, dict):
        msg["bridge_meta"] = meta
    return msg

filters.register("add_bridge_meta", add_bridge_meta, enabled=False, description="Attach bridge_meta with ts/direction/session")

# ----------------------------- Broker -------------------------------------
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
        self._reader_task: Optional[asyncio.Task] = None
        self.max_in_flight = int(os.environ.get("BRIDGE_MAX_IN_FLIGHT", "128"))
        self.in_flight = 0
        self._inflight_lock = asyncio.Lock()

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
        # Correlate responses by id if present
        if "id" in payload:
            self.id_to_session[payload["id"]] = session_id
        # Filters (client → server)
        filtered = await filters.apply("client_to_server", session_id, payload)
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
        # Demultiplex proc → sessions
        while True:
            msg = await self.inbox.get()
            try:
                # Filters (server → client)
                target_sid: Optional[str] = None
                if "id" in msg and msg["id"] in self.id_to_session:
                    target_sid = self.id_to_session.pop(msg["id"], None)
                if target_sid and target_sid in self.sessions:
                    filtered = await filters.apply("server_to_client", target_sid, msg)
                    if filtered is not None:
                        await self._send(target_sid, filtered)
                else:
                    # Notifications and unknown → broadcast
                    for sid in list(self.sessions.keys()):
                        filtered = await filters.apply("server_to_client", sid, msg)
                        if filtered is not None:
                            await self._send(sid, filtered)
            finally:
                self.inbox.task_done()

    async def _send(self, session_id: str, obj: Any) -> None:
        if session_id not in self.sessions:
            return
        sess = self.sessions[session_id]
        # SSE
        try:
            data = f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")
            await sess.queue.put(data)
        except asyncio.QueueFull:
            logger.warning("Session %s SSE queue full; dropping message", session_id)
        # WebSockets
        dead: List[WebSocket] = []
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
        # Used only for bridge/system events\n        for sid in list(self.sessions.keys()):\n            await self._send(sid, obj)\n\n# ----------------------------- App ----------------------------------------\napp = FastAPI(title="Stdio Gateway", version="1.1.0", description="Expose a stdio JSON-RPC server over HTTP/SSE/WebSocket with filters")\n\nbridge_proc: Optional[StdioProcess] = None\nbroker: Optional[Broker] = None\n\n@app.on_event("startup")\nasync def _startup():\n    global bridge_proc, broker\n    if not hasattr(app.state, "config"):\n        return\n    cfg = app.state.config\n    bridge_proc = StdioProcess(cmd=cfg.cmd, cwd=cfg.cwd, env=os.environ.copy())\n    broker = Broker(bridge_proc)\n    await broker.start()\n\n@app.get("/health")\nasync def health():\n    ok = (bridge_proc is not None and broker is not None and bridge_proc.proc and bridge_proc.proc.returncode is None)\n    return JSONResponse({"status": "ok" if ok else "degraded"})\n\n@app.post("/sessions", response_model=SessionOut)\nasync def create_session():\n    if broker is None:\n        raise HTTPException(503, "Bridge not ready")\n    sid = broker.create_session()\n    return SessionOut(session=sid)\n\n@app.get("/events")\nasync def events(session: str):\n    if broker is None:\n        raise HTTPException(503, "Bridge not ready")\n    try:\n        sess = broker.get_session(session)\n    except KeyError:\n        raise HTTPException(404, "Unknown session")\n\n    async def event_stream() -> AsyncGenerator[bytes, None]:\n        yield b"retry: 3000\\n\\n"\n        hello = {"type": "bridge/hello", "session": session, "ts": time.time()}\n        yield f"data: {json.dumps(hello)}\\n\\n".encode()\n        while True:\n            try:\n                try:\n                    item = await asyncio.wait_for(sess.queue.get(), timeout=15)\n                    yield item\n                    sess.queue.task_done()\n                except asyncio.TimeoutError:\n                    yield b": keep-alive\\n\\n"  # SSE heartbeat\n                sess.last_beat = time.time()\n            except asyncio.CancelledError:\n                break\n            except Exception:\n                logger.exception("SSE stream error")\n                break\n\n    return StreamingResponse(event_stream(), media_type="text/event-stream")\n\n@app.websocket("/ws")\nasync def ws_endpoint(websocket: WebSocket):\n    await websocket.accept()\n    # session param is optional; auto-create if missing\n    params = dict(websocket.query_params)\n    sid = params.get("session")\n    if broker is None:\n        await websocket.close(code=1011)\n        return\n    if not sid:\n        sid = broker.create_session()\n        await websocket.send_text(json.dumps({"type": "bridge/session", "session": sid}))\n    try:\n        sess = broker.get_session(sid)\n    except KeyError:\n        await websocket.close(code=1008)\n        return\n    sess.websockets.add(websocket)\n    try:\n        while True:\n            msg = await websocket.receive_text()\n            try:\n                payload = json.loads(msg)\n            except Exception:\n                await websocket.send_text(json.dumps({"error": "invalid json"}))\n                continue\n            if isinstance(payload, dict) and "jsonrpc" not in payload:\n                payload["jsonrpc"] = "2.0"\n            if "id" not in payload and payload.get("method"):\n                payload["id"] = str(uuid.uuid4())\n            await broker.route_from_client(sid, payload)\n    except WebSocketDisconnect:\n        pass\n    finally:\n        try:\n            sess.websockets.remove(websocket)\n        except KeyError:\n            pass\n\n@app.post("/messages", response_model=PostAccepted)\nasync def post_message(request: Request):\n    if broker is None:\n        raise HTTPException(503, "Bridge not ready")\n    try:\n        payload = await request.json()\n    except Exception:\n        raise HTTPException(400, "Invalid JSON")\n\n    session_id = request.query_params.get("session")\n    if not session_id:\n        raise HTTPException(400, "session query parameter is required")\n    if session_id not in broker.sessions:\n        raise HTTPException(404, "Unknown session")\n\n    if isinstance(payload, dict) and "jsonrpc" not in payload:\n        payload["jsonrpc"] = "2.0"\n    if "id" not in payload and payload.get("method"):\n        payload["id"] = str(uuid.uuid4())\n\n    await broker.route_from_client(session_id, payload)\n    return PostAccepted(id=str(payload.get("id")))\n\n@app.get("/filters", response_model=List[FilterInfo])\nasync def list_filters():\n    return filters.list()\n\n@app.post("/filters/{name}")\nasync def toggle_filter(name: str, body: ToggleFilterIn):\n    try:\n        filters.set_enabled(name, body.enabled)\n    except KeyError:\n        raise HTTPException(404, f"Unknown filter {name}")\n    return {"status": "ok", "name": name, "enabled": body.enabled}\n\n@app.get("/live")\nasync def live():\n    # Auto-create a session for this page\n    if broker is None:\n        raise HTTPException(503, "Bridge not ready")\n    sid = broker.create_session()\n    html = f\"\"\"\n<!doctype html>\n<html>\n<head><meta charset=\\\"utf-8\\\"><title>Stdio Gateway Live</title></head>\n<body style=\\\"font-family: system-ui, sans-serif; margin: 1rem;\\\">\n<h1>Live Stream (session {sid})</h1>\n<pre id=\\\"log\\\" style=\\\"border:1px solid #ccc; padding:1rem; height:50vh; overflow:auto; background:#fafafa\\\"></pre>\n<form id=\\\"f\\\" style=\\\"margin-top:1rem\\\">\n  <textarea id=\\\"payload\\\" rows=\\\"6\\\" style=\\\"width:100%\\\" placeholder='{{\"jsonrpc\":\"2.0\",\"method\":\"ping\",\"id\":\"1\"}}'></textarea>\n  <button>Send</button>\n</form>\n<script>\n  const sid = {json.dumps(sid)!r};\n  const log = document.getElementById('log');\n  function append(x) { log.textContent += x + \\\"\\n\\\"; log.scrollTop = log.scrollHeight; }\n  const es = new EventSource('/events?session=' + sid);\n  es.onmessage = (e) => append(e.data);\n  es.onerror = () => append('[SSE error]');\n  document.getElementById('f').addEventListener('submit', async (ev) => {\n    ev.preventDefault();\n    const t = document.getElementById('payload').value || '{}';\n    try { JSON.parse(t); } catch { append('[Invalid JSON]'); return; }\n    await fetch('/messages?session=' + sid, {method:'POST', headers:{'content-type':'application/json'}, body:t});\n    append('> ' + t);\n  });\n</script>\n</body>\n</html>\n\"\"\"\n    return HTMLResponse(html)\n\n@app.get(\"/\")\nasync def root():\n    return PlainTextResponse(\"Stdio gateway is running. See /docs for OpenAPI, /live for a viewer.\")\n\n# ----------------------------- Main ---------------------------------------\n\ndef parse_args(argv: Optional[list[str]] = None):\n    p = argparse.ArgumentParser(description=\"Stdio gateway\")\n    p.add_argument(\"--cmd\", required=True, help=\"Command to run the stdio server, e.g. 'serena --stdio'\")\n    p.add_argument(\"--port\", type=int, default=int(os.environ.get(\"PORT\", 8080)))\n    p.add_argument(\"--host\", default=os.environ.get(\"HOST\", \"0.0.0.0\"))\n    p.add_argument(\"--cwd\", default=None)\n    return p.parse_args(argv)\n\n\ndef main():\n    args = parse_args()\n    app.state.config = args\n    import uvicorn\n    uvicorn.run(app, host=args.host, port=args.port, log_level=\"info\")\n\nif __name__ == \"__main__\":\n    try:\n        main()\n    except KeyboardInterrupt:\n        pass\n'''\n\n# Write to file\nwith open('/mnt/data/stdio_gateway_v1_1.py', 'w', encoding='utf-8') as f:\n    f.write(code)\n\nprint('Wrote /mnt/data/stdio_gateway_v1_1.py')
