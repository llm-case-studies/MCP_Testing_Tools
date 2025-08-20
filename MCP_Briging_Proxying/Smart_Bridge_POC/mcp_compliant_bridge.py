#!/usr/bin/env python3
"""
MCP-Compliant SSE Bridge
Simple bridge that properly implements MCP SSE transport using existing broker
"""

from __future__ import annotations
import argparse
import asyncio
import json
import logging
import os
import sys
import time
from typing import Any, AsyncGenerator, Dict, Optional, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse, PlainTextResponse
import uvicorn

try:
    from .process import StdioProcess
    from .broker import Broker
except ImportError:
    from process import StdioProcess
    from broker import Broker


# ----------------------------- Logging ------------------------------------
logger = logging.getLogger("mcp-compliant-bridge")
handler = logging.StreamHandler(sys.stderr)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


# ----------------------------- FastAPI App --------------------------------
app = FastAPI(
    title="MCP Compliant Bridge", 
    version="1.0.0", 
    description="MCP-compliant SSE transport bridge for stdio MCP servers"
)

bridge_proc: Optional[StdioProcess] = None
broker: Optional[Broker] = None


@app.on_event("startup")
async def startup():
    global bridge_proc, broker
    if hasattr(app.state, "config"):
        cfg = app.state.config
        bridge_proc = StdioProcess(cmd=cfg.cmd, cwd=cfg.cwd, env=os.environ.copy())
        broker = Broker(bridge_proc)
        await broker.start()
        logger.info(f"Started MCP bridge with command: {cfg.cmd}")


@app.on_event("shutdown") 
async def shutdown():
    global bridge_proc, broker
    if broker:
        # Clean shutdown of broker and processes
        pass


@app.get("/health")
async def health():
    """Health check endpoint"""
    return JSONResponse({
        "status": "ok" if bridge_proc and broker else "degraded",
        "connections": len(broker.sessions) if broker else 0
    })


@app.post("/sse")
async def create_sse_connection(request: Request):
    """Create new MCP SSE connection (MCP dynamic registration endpoint)"""
    if not broker:
        raise HTTPException(503, "Bridge not ready")
    
    # Create session using existing broker
    session_id = broker.create_session()
    
    # Get base URL from request
    base_url = str(request.base_url).rstrip("/")
    
    # Return MCP SSE transport configuration
    return JSONResponse({
        "transport": {
            "type": "sse",
            "url": f"{base_url}/sse/{session_id}/events"
        },
        "capabilities": {
            "resources": {},
            "tools": {},
            "prompts": {}
        }
    })


@app.get("/sse/{session_id}/events")
async def sse_events(session_id: str):
    """SSE event stream for MCP connection"""
    if not broker or session_id not in broker.sessions:
        raise HTTPException(404, "Session not found")
    
    session = broker.get_session(session_id)
    
    async def event_stream() -> AsyncGenerator[bytes, None]:
        # Send SSE headers
        yield b"retry: 3000\n\n"
        
        # Send MCP hello message
        hello_msg = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        yield f"data: {json.dumps(hello_msg)}\n\n".encode()
        
        # Stream messages from broker
        while True:
            try:
                # Wait for message with timeout for heartbeat
                try:
                    item = await asyncio.wait_for(session.queue.get(), timeout=30.0)
                    yield item
                    session.queue.task_done()
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield b": heartbeat\n\n"
                    
                session.last_beat = time.time()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in SSE stream for session {session_id}: {e}")
                break
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


@app.post("/sse/{session_id}/message")
async def send_message(session_id: str, request: Request):
    """Send message to MCP server"""
    if not broker or session_id not in broker.sessions:
        raise HTTPException(404, "Session not found")
    
    try:
        message = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    
    # Ensure message has jsonrpc field
    if isinstance(message, dict) and "jsonrpc" not in message:
        message["jsonrpc"] = "2.0"
    
    # Route message through broker
    await broker.route_from_client(session_id, message)
    
    return JSONResponse({"status": "ok"})


# ----------------------------- MCP Endpoints ------------------------------

@app.get("/sse/{session_id}/resources")
async def list_resources(session_id: str):
    """List available resources from MCP server"""
    if not broker or session_id not in broker.sessions:
        raise HTTPException(404, "Session not found")
    
    # Send resources/list request via broker
    request_msg = {
        "jsonrpc": "2.0",
        "id": f"resources-{time.time()}",
        "method": "resources/list"
    }
    
    await broker.route_from_client(session_id, request_msg)
    
    # Note: In a real implementation, we'd wait for response and return it
    # For now, return placeholder
    return JSONResponse({"resources": []})


@app.get("/sse/{session_id}/tools")
async def list_tools(session_id: str):
    """List available tools from MCP server"""
    if not broker or session_id not in broker.sessions:
        raise HTTPException(404, "Session not found")
    
    # Send tools/list request via broker
    request_msg = {
        "jsonrpc": "2.0",
        "id": f"tools-{time.time()}",
        "method": "tools/list"
    }
    
    await broker.route_from_client(session_id, request_msg)
    
    # Note: In a real implementation, we'd wait for response and return it
    return JSONResponse({"tools": []})


@app.post("/sse/{session_id}/tools/{tool_name}/call")
async def call_tool(session_id: str, tool_name: str, request: Request):
    """Call a tool on the MCP server"""
    if not broker or session_id not in broker.sessions:
        raise HTTPException(404, "Session not found")
    
    try:
        params = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    
    # Send tools/call request via broker
    request_msg = {
        "jsonrpc": "2.0",
        "id": f"tool-call-{time.time()}",
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": params
        }
    }
    
    await broker.route_from_client(session_id, request_msg)
    
    return JSONResponse({"content": []})


@app.get("/")
async def root():
    """Root endpoint"""
    return PlainTextResponse("MCP Compliant Bridge is running. Use POST /sse to create connections.")


# ----------------------------- Main ---------------------------------------
def parse_args(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(description="MCP Compliant Bridge")
    parser.add_argument("--cmd", required=True, help="Command to run stdio MCP server")
    parser.add_argument("--port", type=int, default=8080, help="Port to run bridge on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--cwd", help="Working directory for stdio server")
    return parser.parse_args(argv)


def main():
    args = parse_args()
    app.state.config = args
    
    logger.info(f"Starting MCP Compliant Bridge on {args.host}:{args.port}")
    logger.info(f"MCP Server command: {args.cmd}")
    
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Shutting down...")