from __future__ import annotations
import argparse
import asyncio
import json
import logging
import os
import sys
import time
import uuid
from typing import Any, AsyncGenerator, Dict, Optional, List

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse, PlainTextResponse, HTMLResponse

from .models import SessionOut, PostAccepted, ToggleFilterIn, FilterInfo
from .process import StdioProcess
from .filters import filters
from .broker import Broker

# ----------------------------- Logging ------------------------------------
logger = logging.getLogger("stdio-gateway")
handler = logging.StreamHandler(sys.stderr)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# ----------------------------- App ----------------------------------------
app = FastAPI(title="Stdio Gateway", version="1.1.0", description="Expose a stdio JSON-RPC server over HTTP/SSE/WebSocket with filters")

bridge_proc: Optional[StdioProcess] = None
broker: Optional[Broker] = None

@app.on_event("startup")
async def _startup():
    global bridge_proc, broker
    if not hasattr(app.state, "config"):
        return
    cfg = app.state.config
    bridge_proc = StdioProcess(cmd=cfg.cmd, cwd=cfg.cwd, env=os.environ.copy())
    broker = Broker(bridge_proc)
    await broker.start()

@app.get("/health")
async def health():
    ok = (bridge_proc is not None and broker is not None and bridge_proc.proc and bridge_proc.proc.returncode is None)
    return JSONResponse({"status": "ok" if ok else "degraded"})

@app.post("/sessions", response_model=SessionOut)
async def create_session():
    if broker is None:
        raise HTTPException(503, "Bridge not ready")
    sid = broker.create_session()
    return SessionOut(session=sid)

@app.get("/events")
async def events(session: str):
    if broker is None:
        raise HTTPException(503, "Bridge not ready")
    try:
        sess = broker.get_session(session)
    except KeyError:
        raise HTTPException(404, "Unknown session")

    async def event_stream() -> AsyncGenerator[bytes, None]:
        yield b"retry: 3000\n\n"
        hello = {"type": "bridge/hello", "session": session, "ts": time.time()}
        yield f"data: {json.dumps(hello)}\n\n".encode()
        while True:
            try:
                try:
                    item = await asyncio.wait_for(sess.queue.get(), timeout=15)
                    yield item
                    sess.queue.task_done()
                except asyncio.TimeoutError:
                    yield b": keep-alive\n\n"
                sess.last_beat = time.time()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("SSE stream error")
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/register")
async def register(request: Request):
    if broker is None:
        raise HTTPException(503, "Bridge not ready")
    # Create a session for this client
    sid = broker.create_session()
    base_url = str(request.base_url).rstrip("/")
    sse_url = f"{base_url}/events?session={sid}"
    post_url = f"{base_url}/messages?session={sid}"
    # Return a response compatible with MCP SSE dynamic registration
    payload = {
        "transport": {
            "type": "sse",
            "url": sse_url,
            "headers": {"Accept": "text/event-stream"},
        },
        "send": {
            "type": "http",
            "method": "POST",
            "url": post_url,
            "headers": {"Content-Type": "application/json"},
        },
        "session": sid,
    }
    return JSONResponse(payload)

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    params = dict(websocket.query_params)
    sid = params.get("session")
    if broker is None:
        await websocket.close(code=1011)
        return
    if not sid:
        sid = broker.create_session()
        await websocket.send_text(json.dumps({"type": "bridge/session", "session": sid}))
    try:
        sess = broker.get_session(sid)
    except KeyError:
        await websocket.close(code=1008)
        return
    sess.websockets.add(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            try:
                payload = json.loads(msg)
            except Exception:
                await websocket.send_text(json.dumps({"error": "invalid json"}))
                continue
            if isinstance(payload, dict) and "jsonrpc" not in payload:
                payload["jsonrpc"] = "2.0"
            await broker.route_from_client(sid, payload)
    except WebSocketDisconnect:
        pass
    finally:
        try:
            sess.websockets.remove(websocket)
        except KeyError:
            pass

@app.post("/messages", response_model=PostAccepted)
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

    if isinstance(payload, dict) and "jsonrpc" not in payload:
        payload["jsonrpc"] = "2.0"

    await broker.route_from_client(session_id, payload)
    return PostAccepted(id=str(payload.get("id")))

@app.get("/filters", response_model=List[FilterInfo])
async def list_filters():
    return filters.list()

@app.post("/filters/{name}")
async def toggle_filter(name: str, body: ToggleFilterIn):
    try:
        filters.set_enabled(name, body.enabled)
    except KeyError:
        raise HTTPException(404, f"Unknown filter {name}")
    return {"status": "ok", "name": name, "enabled": body.enabled}

@app.get("/live")
async def live():
    if broker is None:
        raise HTTPException(503, "Bridge not ready")
    sid = broker.create_session()
    html = """<!doctype html>
<html>
<head><meta charset="utf-8"><title>Stdio Gateway Live</title></head>
<body style="font-family: system-ui, sans-serif; margin: 1rem;">
<h1>Live Stream (session SESSION_ID)</h1>
<pre id="log" style="border:1px solid #ccc; padding:1rem; height:50vh; overflow:auto; background:#fafafa"></pre>
<form id="f" style="margin-top:1rem">
  <textarea id="payload" rows="6" style="width:100%" placeholder='{"jsonrpc":"2.0","method":"ping","id":"1"}'></textarea>
  <button>Send</button>
</form>
<script>
  const sid = "SESSION_ID";
  const log = document.getElementById('log');
  function append(x) { log.textContent += x + "\\n"; log.scrollTop = log.scrollHeight; }
  const es = new EventSource('/events?session=' + sid);
  es.onmessage = (e) => append(e.data);
  es.onerror = () => append('[SSE error]');
  document.getElementById('f').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const t = document.getElementById('payload').value || '{}';
    try { JSON.parse(t); } catch { append('[Invalid JSON]'); return; }
    await fetch('/messages?session=' + sid, {method:'POST', headers:{'content-type':'application/json'}, body:t});
    append('> ' + t);
  });
</script>
</body>
</html>"""
    html = html.replace("SESSION_ID", sid)
    return HTMLResponse(html)

@app.get("/")
async def root():
    return PlainTextResponse("Stdio gateway is running. See /docs for OpenAPI, /live for a viewer.")

# ----------------------------- Main ---------------------------------------
def parse_args(argv: Optional[list[str]] = None):
    p = argparse.ArgumentParser(description="Stdio gateway")
    p.add_argument("--cmd", required=True, help="Command to run the stdio server, e.g. 'serena --stdio'")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8080)))
    p.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    p.add_argument("--cwd", default=None)
    return p.parse_args(argv)

def main():
    args = parse_args()
    app.state.config = args
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass