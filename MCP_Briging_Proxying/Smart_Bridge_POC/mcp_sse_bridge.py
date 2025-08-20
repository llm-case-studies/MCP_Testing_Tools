#!/usr/bin/env python3
"""
MCP-compliant SSE Bridge
Converts stdio MCP servers to SSE transport following official MCP specification
"""

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
from dataclasses import dataclass, asdict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse, PlainTextResponse
import uvicorn

try:
    from .process import StdioProcess
except ImportError:
    from process import StdioProcess


# ----------------------------- Logging ------------------------------------
logger = logging.getLogger("mcp-sse-bridge")
handler = logging.StreamHandler(sys.stderr)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


# ----------------------------- MCP Models ---------------------------------
@dataclass
class MCPCapabilities:
    """MCP server capabilities"""
    resources: Optional[Dict[str, Any]] = None
    tools: Optional[Dict[str, Any]] = None
    prompts: Optional[Dict[str, Any]] = None
    sampling: Optional[Dict[str, Any]] = None


@dataclass
class MCPInitializeRequest:
    """MCP initialize request"""
    jsonrpc: str = "2.0"
    id: str = "init"
    method: str = "initialize"
    params: Dict[str, Any] = None

    def __post_init__(self):
        if self.params is None:
            self.params = {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {"listChanged": True},
                    "sampling": {}
                },
                "clientInfo": {
                    "name": "MCP SSE Bridge",
                    "version": "1.0.0"
                }
            }


@dataclass
class MCPConnection:
    """Represents a single MCP client connection"""
    connection_id: str
    stdio_process: StdioProcess
    capabilities: Optional[MCPCapabilities] = None
    initialized: bool = False
    message_queue: asyncio.Queue = None
    
    def __post_init__(self):
        if self.message_queue is None:
            self.message_queue = asyncio.Queue()


# ----------------------------- MCP Bridge ---------------------------------
class MCPSSEBridge:
    """MCP-compliant SSE Bridge that converts stdio MCP servers to SSE transport"""
    
    def __init__(self, cmd: str, cwd: Optional[str] = None):
        self.cmd = cmd
        self.cwd = cwd
        self.connections: Dict[str, MCPConnection] = {}
        self.running = False
    
    async def start(self):
        """Start the bridge"""
        self.running = True
        logger.info(f"Started MCP SSE Bridge with command: {self.cmd}")
    
    async def stop(self):
        """Stop the bridge and cleanup connections"""
        self.running = False
        for conn in self.connections.values():
            if conn.stdio_process.proc and conn.stdio_process.proc.returncode is None:
                await conn.stdio_process.terminate()
        self.connections.clear()
        logger.info("Stopped MCP SSE Bridge")
    
    async def create_connection(self) -> str:
        """Create a new MCP connection"""
        connection_id = str(uuid.uuid4())
        
        # Start stdio process for this connection
        stdio_process = StdioProcess(cmd=self.cmd, cwd=self.cwd, env=os.environ.copy())
        await stdio_process.start()
        
        # Create connection
        conn = MCPConnection(
            connection_id=connection_id,
            stdio_process=stdio_process
        )
        
        self.connections[connection_id] = conn
        
        # Start message processing task
        asyncio.create_task(self._process_stdio_messages(connection_id))
        
        # Initialize MCP connection
        await self._initialize_mcp_connection(connection_id)
        
        logger.info(f"Created MCP connection: {connection_id}")
        return connection_id
    
    async def _initialize_mcp_connection(self, connection_id: str):
        """Initialize MCP protocol with the stdio server"""
        conn = self.connections[connection_id]
        
        # Send initialize request
        init_request = MCPInitializeRequest()
        await conn.stdio_process.send_message(asdict(init_request))
        
        # Wait for initialize response
        try:
            response = await asyncio.wait_for(
                conn.stdio_process.receive_message(), 
                timeout=10.0
            )
            
            if response and response.get("result"):
                conn.capabilities = MCPCapabilities(**response["result"].get("capabilities", {}))
                conn.initialized = True
                
                # Send initialized notification
                initialized_notification = {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized"
                }
                await conn.stdio_process.send_message(initialized_notification)
                
                logger.info(f"MCP connection {connection_id} initialized successfully")
            else:
                logger.error(f"Failed to initialize MCP connection {connection_id}: {response}")
                
        except asyncio.TimeoutError:
            logger.error(f"Timeout initializing MCP connection {connection_id}")
    
    async def _process_stdio_messages(self, connection_id: str):
        """Process messages from stdio server and queue them for SSE"""
        conn = self.connections.get(connection_id)
        if not conn:
            return
            
        try:
            while self.running and conn.stdio_process.proc and conn.stdio_process.proc.returncode is None:
                try:
                    message = await asyncio.wait_for(
                        conn.stdio_process.receive_message(),
                        timeout=1.0
                    )
                    if message:
                        await conn.message_queue.put(message)
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error processing stdio message for {connection_id}: {e}")
                    break
        except Exception as e:
            logger.error(f"Stdio message processing task failed for {connection_id}: {e}")
        finally:
            # Cleanup connection
            if connection_id in self.connections:
                del self.connections[connection_id]
                logger.info(f"Cleaned up MCP connection: {connection_id}")
    
    async def send_message(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """Send message to stdio server"""
        conn = self.connections.get(connection_id)
        if not conn or not conn.initialized:
            return False
            
        try:
            await conn.stdio_process.send_message(message)
            return True
        except Exception as e:
            logger.error(f"Error sending message to {connection_id}: {e}")
            return False
    
    async def get_message_stream(self, connection_id: str) -> AsyncGenerator[bytes, None]:
        """Get SSE stream for a connection"""
        conn = self.connections.get(connection_id)
        if not conn:
            return
            
        # Send SSE headers
        yield b"retry: 3000\n\n"
        
        # Send connection established event
        hello_event = {
            "jsonrpc": "2.0",
            "method": "notifications/message",
            "params": {
                "level": "info",
                "message": f"MCP SSE connection established: {connection_id}"
            }
        }
        yield f"data: {json.dumps(hello_event)}\n\n".encode()
        
        # Stream messages
        while self.running and connection_id in self.connections:
            try:
                # Wait for message with timeout for heartbeat
                try:
                    message = await asyncio.wait_for(conn.message_queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(message)}\n\n".encode()
                    conn.message_queue.task_done()
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield b": heartbeat\n\n"
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in message stream for {connection_id}: {e}")
                break


# ----------------------------- FastAPI App --------------------------------
app = FastAPI(
    title="MCP SSE Bridge", 
    version="1.0.0", 
    description="MCP-compliant SSE transport bridge for stdio MCP servers"
)

bridge: Optional[MCPSSEBridge] = None

@app.on_event("startup")
async def startup():
    global bridge
    if hasattr(app.state, "config"):
        cfg = app.state.config
        bridge = MCPSSEBridge(cmd=cfg.cmd, cwd=cfg.cwd)
        await bridge.start()

@app.on_event("shutdown") 
async def shutdown():
    global bridge
    if bridge:
        await bridge.stop()

@app.get("/health")
async def health():
    """Health check endpoint"""
    return JSONResponse({
        "status": "ok" if bridge and bridge.running else "degraded",
        "connections": len(bridge.connections) if bridge else 0
    })

@app.post("/sse")
async def create_sse_connection(request: Request):
    """Create new MCP SSE connection (MCP dynamic registration endpoint)"""
    if not bridge:
        raise HTTPException(503, "Bridge not ready")
    
    connection_id = await bridge.create_connection()
    
    # Get base URL from request
    base_url = str(request.base_url).rstrip("/")
    
    return JSONResponse({
        "transport": {
            "type": "sse",
            "url": f"{base_url}/sse/{connection_id}/events"
        },
        "capabilities": {
            "resources": {},
            "tools": {},
            "prompts": {}
        }
    })

@app.get("/sse/{connection_id}/events")
async def sse_events(connection_id: str):
    """SSE event stream for MCP connection"""
    if not bridge or connection_id not in bridge.connections:
        raise HTTPException(404, "Connection not found")
    
    return StreamingResponse(
        bridge.get_message_stream(connection_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@app.post("/sse/{connection_id}/message")
async def send_message(connection_id: str, request: Request):
    """Send message to MCP server"""
    if not bridge or connection_id not in bridge.connections:
        raise HTTPException(404, "Connection not found")
    
    try:
        message = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    
    success = await bridge.send_message(connection_id, message)
    if not success:
        raise HTTPException(500, "Failed to send message")
    
    return JSONResponse({"status": "ok"})

# ----------------------------- MCP Endpoints ------------------------------

@app.get("/sse/{connection_id}/resources")
async def list_resources(connection_id: str):
    """List available resources from MCP server"""
    if not bridge or connection_id not in bridge.connections:
        raise HTTPException(404, "Connection not found")
    
    # Send resources/list request to MCP server
    request_msg = {
        "jsonrpc": "2.0",
        "id": f"resources-{time.time()}",
        "method": "resources/list"
    }
    
    success = await bridge.send_message(connection_id, request_msg)
    if not success:
        raise HTTPException(500, "Failed to send request")
    
    # Note: In real implementation, we'd wait for response and return it
    # For now, return empty list as placeholder
    return JSONResponse({"resources": []})

@app.get("/sse/{connection_id}/resources/{uri:path}")
async def read_resource(connection_id: str, uri: str):
    """Read a specific resource from MCP server"""
    if not bridge or connection_id not in bridge.connections:
        raise HTTPException(404, "Connection not found")
    
    # Send resources/read request to MCP server
    request_msg = {
        "jsonrpc": "2.0", 
        "id": f"resource-{time.time()}",
        "method": "resources/read",
        "params": {"uri": uri}
    }
    
    success = await bridge.send_message(connection_id, request_msg)
    if not success:
        raise HTTPException(500, "Failed to send request")
    
    # Note: In real implementation, we'd wait for response and return it
    return JSONResponse({"uri": uri, "mimeType": "text/plain", "text": ""})

@app.get("/sse/{connection_id}/tools")
async def list_tools(connection_id: str):
    """List available tools from MCP server"""
    if not bridge or connection_id not in bridge.connections:
        raise HTTPException(404, "Connection not found")
    
    # Send tools/list request to MCP server
    request_msg = {
        "jsonrpc": "2.0",
        "id": f"tools-{time.time()}",
        "method": "tools/list"
    }
    
    success = await bridge.send_message(connection_id, request_msg)
    if not success:
        raise HTTPException(500, "Failed to send request")
    
    # Note: In real implementation, we'd wait for response and return it
    return JSONResponse({"tools": []})

@app.post("/sse/{connection_id}/tools/{tool_name}/call")
async def call_tool(connection_id: str, tool_name: str, request: Request):
    """Call a tool on the MCP server"""
    if not bridge or connection_id not in bridge.connections:
        raise HTTPException(404, "Connection not found")
    
    try:
        params = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    
    # Send tools/call request to MCP server
    request_msg = {
        "jsonrpc": "2.0",
        "id": f"tool-call-{time.time()}",
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": params
        }
    }
    
    success = await bridge.send_message(connection_id, request_msg)
    if not success:
        raise HTTPException(500, "Failed to send request")
    
    # Note: In real implementation, we'd wait for response and return it
    return JSONResponse({"content": []})

@app.get("/sse/{connection_id}/prompts")
async def list_prompts(connection_id: str):
    """List available prompts from MCP server"""
    if not bridge or connection_id not in bridge.connections:
        raise HTTPException(404, "Connection not found")
    
    # Send prompts/list request to MCP server
    request_msg = {
        "jsonrpc": "2.0",
        "id": f"prompts-{time.time()}",
        "method": "prompts/list"
    }
    
    success = await bridge.send_message(connection_id, request_msg)
    if not success:
        raise HTTPException(500, "Failed to send request")
    
    # Note: In real implementation, we'd wait for response and return it
    return JSONResponse({"prompts": []})

@app.post("/sse/{connection_id}/prompts/{prompt_name}/get")
async def get_prompt(connection_id: str, prompt_name: str, request: Request):
    """Get a prompt from the MCP server"""
    if not bridge or connection_id not in bridge.connections:
        raise HTTPException(404, "Connection not found")
    
    try:
        params = await request.json()
    except Exception:
        params = {}
    
    # Send prompts/get request to MCP server
    request_msg = {
        "jsonrpc": "2.0",
        "id": f"prompt-get-{time.time()}",
        "method": "prompts/get",
        "params": {
            "name": prompt_name,
            "arguments": params
        }
    }
    
    success = await bridge.send_message(connection_id, request_msg)
    if not success:
        raise HTTPException(500, "Failed to send request")
    
    # Note: In real implementation, we'd wait for response and return it
    return JSONResponse({"messages": []})

@app.get("/")
async def root():
    """Root endpoint"""
    return PlainTextResponse("MCP SSE Bridge is running. Use POST /sse to create connections.")


# ----------------------------- Main ---------------------------------------
def parse_args(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(description="MCP SSE Bridge")
    parser.add_argument("--cmd", required=True, help="Command to run stdio MCP server")
    parser.add_argument("--port", type=int, default=8080, help="Port to run bridge on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--cwd", help="Working directory for stdio server")
    return parser.parse_args(argv)

def main():
    args = parse_args()
    app.state.config = args
    
    logger.info(f"Starting MCP SSE Bridge on {args.host}:{args.port}")
    logger.info(f"MCP Server command: {args.cmd}")
    
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Shutting down...")