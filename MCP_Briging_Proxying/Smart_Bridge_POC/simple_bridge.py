#!/usr/bin/env python3
"""
Simplified MCP SSE Bridge - Compatible with Claude Code without mandatory OAuth
Based on GPT-5 feedback for clean SSE transport without authentication complexity
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import uuid
from typing import Any, AsyncGenerator, Dict, Optional, List, Union

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

try:
    from .process import StdioProcess
    from .broker import Broker
except ImportError:
    from process import StdioProcess
    from broker import Broker

# ----------------------------- Logging ------------------------------------
logger = logging.getLogger("simple-bridge")

# ----------------------------- Auth Configuration -------------------------
AUTH_MODE = os.getenv("BRIDGE_AUTH_MODE", "none")  # none|bearer|apikey
AUTH_SECRET = os.getenv("BRIDGE_AUTH_SECRET", "")

def check_auth(authorization: Optional[str] = None, x_api_key: Optional[str] = None):
    """Check authentication based on configured mode"""
    if AUTH_MODE == "none":
        return
    if AUTH_MODE == "bearer":
        if not authorization or not authorization.strip().lower().startswith("bearer "):
            raise HTTPException(401, "Bearer token required")
        token = authorization.split()[-1] if authorization else ""
        if token != AUTH_SECRET:
            raise HTTPException(401, "Invalid bearer token")
    if AUTH_MODE == "apikey":
        if x_api_key != AUTH_SECRET:
            raise HTTPException(401, "Invalid API key")

# ----------------------------- FastAPI App --------------------------------
app = FastAPI(
    title="Simple MCP Bridge", 
    version="1.0.0", 
    description="Simplified MCP SSE bridge for stdio MCP servers"
)

# Global broker instance
broker: Optional[Broker] = None

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "auth_mode": AUTH_MODE,
        "connections": len(broker.sessions) if broker else 0
    }

@app.get("/sse")
async def sse_events(request: Request,
                    session: Optional[str] = None,
                    authorization: Optional[str] = Header(default=None),
                    x_api_key: Optional[str] = Header(default=None)):
    """SSE event stream for MCP connection with auto-session creation"""
    # Check authentication
    check_auth(authorization, x_api_key)
    
    if not broker:
        raise HTTPException(503, "Bridge not ready")
    
    # Log the SSE connection attempt with full client details
    client_info = f"{request.client.host}:{request.client.port}" if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    priority = request.query_params.get("priority", "normal")
    
    logger.info(f"New SSE connection from {client_info}, User-Agent: {user_agent}")
    
    # Auto-create session if not provided
    if not session:
        session_id = broker.create_session()
        logger.info(f"Created new session {session_id} for client {client_info} with priority {priority}")
        logger.debug(f"Session details - ID: {session_id}, Client: {client_info}, Priority: {priority}, UA: {user_agent}")
        
        # Return stream with MCP SSE endpoint event first (as per spec)
        async def preface():
            # Required: Send endpoint event first per MCP spec
            base_url = str(request.base_url).rstrip("/")
            endpoint_url = f"{base_url}/messages?session={session_id}"
            yield f"event: endpoint\ndata: {endpoint_url}\n\n".encode()
            
            # Fall through to normal stream
            async for chunk in event_stream_generator(session_id):
                yield chunk
        return StreamingResponse(preface(), media_type="text/event-stream")
    else:
        session_id = session
        if session_id not in broker.sessions:
            raise HTTPException(404, f"Session {session_id} not found")
    
    return StreamingResponse(event_stream_generator(session_id), media_type="text/event-stream")

async def event_stream_generator(session_id: str) -> AsyncGenerator[bytes, None]:
    """Generate SSE event stream for a session per MCP spec"""
    session = broker.get_session(session_id)
    logger.debug(f"Starting SSE stream for session: {session_id}")
    
    # Stream messages from broker
    while True:
        try:
            # Wait for message with timeout for heartbeat (15s per spec)
            try:
                item = await asyncio.wait_for(session.queue.get(), timeout=15.0)
                # Item should already be properly formatted as SSE by broker
                yield item
                session.queue.task_done()
            except asyncio.TimeoutError:
                # Send heartbeat comment per MCP spec
                yield b": heartbeat\n\n"
                
            session.last_beat = time.time()
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in SSE stream for session {session_id}: {e}")
            break

@app.post("/messages")
async def send_message(request: Request,
                      authorization: Optional[str] = Header(default=None),
                      x_api_key: Optional[str] = Header(default=None)):
    """Send message to MCP server with auto-session support"""
    # Check authentication
    check_auth(authorization, x_api_key)
    
    if not broker:
        raise HTTPException(503, "Bridge not ready")
    
    # Log request details
    client_info = f"{request.client.host}:{request.client.port}" if request.client else "unknown"
    priority = request.query_params.get("priority", "normal")
    
    try:
        payload = await request.json()
        message_id = payload.get("id", "no-id")
        method = payload.get("method", "no-method")
        
        logger.info(f"Received message from {client_info}: {method} (id: {message_id}, priority: {priority})")
        logger.debug(f"Full message payload: {json.dumps(payload, indent=2)}")
    except Exception as e:
        logger.error(f"Failed to parse JSON from {client_info}: {e}")
        raise HTTPException(400, "Invalid JSON")
    
    # Handle MCP initialize request specially (bridge-level response + forward to server)
    if payload.get("method") == "initialize":
        session_id = request.query_params.get("session")
        if not session_id or session_id not in broker.sessions:
            raise HTTPException(400, "Valid session required for initialize")
            
        # 1) Send immediate bridge-level response to Claude Code
        bridge_response = {
            "jsonrpc": "2.0",
            "id": payload.get("id"),
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "resources": {},
                    "tools": {},
                    "prompts": {},
                    "logging": {}
                },
                "serverInfo": {
                    "name": "Smart Bridge",
                    "version": "1.0.0"
                }
            }
        }
        await broker._send(session_id, bridge_response)
        logger.info(f"Sent bridge initialize response to session {session_id}")
        
        # 2) Also forward initialize to underlying server so it's ready for other requests
        server_init_payload = {
            "jsonrpc": "2.0", 
            "id": f"bridge-init-{payload.get('id')}",
            "method": "initialize",
            "params": payload.get("params", {})
        }
        logger.debug(f"Forwarding initialize to underlying server")
        await broker.route_from_client(session_id, server_init_payload)
        
        return JSONResponse({"status": "accepted"}, status_code=202)
    
    # Handle discovery requests at bridge level (underlying servers often don't implement these)
    discovery_methods = ["tools/list", "resources/list", "prompts/list"]
    if payload.get("method") in discovery_methods:
        session_id = request.query_params.get("session")
        if not session_id or session_id not in broker.sessions:
            raise HTTPException(400, "Valid session required for discovery")
            
        # Get server type from command for appropriate tool definitions
        cmd = app.state.config.cmd.lower() if hasattr(app.state, 'config') else ""
        method = payload.get("method")
        request_id = payload.get("id")
        
        logger.info(f"Handling bridge-level discovery: {method} (id: {request_id}) for {cmd}")
        
        if method == "tools/list":
            # Check if we have a tools config loaded
            tools_config = getattr(app.state, 'tools_config', {})
            
            if tools_config and "tools" in tools_config:
                # Use config file tools
                tools_response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"tools": tools_config["tools"]}
                }
            elif "qdrant" in cmd:
                # Fallback to hardcoded Qdrant tools
                tools_response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": [
                            {
                                "name": "qdrant-find",
                                "description": "Look up memories in Qdrant. Use this tool when you need to find memories by their content, access memories for further analysis, or get some personal information about the user",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "query": {"type": "string", "description": "What to search for"}
                                    },
                                    "required": ["query"]
                                }
                            },
                            {
                                "name": "qdrant-store", 
                                "description": "Keep the memory for later use, when you are asked to remember something.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "information": {"type": "string", "description": "Text to store"},
                                        "metadata": {"type": "object", "description": "Extra metadata"}
                                    },
                                    "required": ["information"]
                                }
                            }
                        ]
                    }
                }
            elif "serena" in cmd:
                # Fallback to hardcoded Serena tools
                tools_response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": [
                            {
                                "name": "list_dir",
                                "description": "List files and directories in a given path",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "path": {"type": "string", "description": "Directory path to list"}
                                    },
                                    "required": ["path"]
                                }
                            }
                        ]
                    }
                }
            else:
                # No tools available
                tools_response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"tools": []}
                }
                
        elif method == "resources/list":
            resources_response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"resources": []}
            }
            await broker._send(session_id, resources_response)
            logger.info(f"Sent bridge resources/list response (id: {request_id}) to session {session_id}")
            return JSONResponse({"status": "accepted"}, status_code=202)
            
        elif method == "prompts/list":
            prompts_response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"prompts": []}
            }
            await broker._send(session_id, prompts_response)
            logger.info(f"Sent bridge prompts/list response (id: {request_id}) to session {session_id}")
            return JSONResponse({"status": "accepted"}, status_code=202)
        
        # Send tools response if we got here
        if method == "tools/list":
            await broker._send(session_id, tools_response)
            logger.info(f"Sent bridge tools/list response (id: {request_id}) to session {session_id} - {len(tools_response['result']['tools'])} tools")
            return JSONResponse({"status": "accepted"}, status_code=202)
    
    # Ensure message has required JSON-RPC fields
    if isinstance(payload, dict) and "jsonrpc" not in payload:
        payload["jsonrpc"] = "2.0"
    if "id" not in payload and payload.get("method"):
        payload["id"] = str(uuid.uuid4())
    
    # 1) Try explicit query param
    session_id = request.query_params.get("session")
    
    # 2) Fallback: single open session
    if not session_id and len(broker.sessions) == 1:
        session_id = next(iter(broker.sessions.keys()))
    
    if not session_id or session_id not in broker.sessions:
        raise HTTPException(400, "No valid session (pass ?session=..., or open exactly one SSE stream)")
    
    # Add priority metadata to the payload for broker processing
    if "meta" not in payload:
        payload["meta"] = {}
    payload["meta"]["priority"] = priority
    payload["meta"]["client_info"] = client_info
    payload["meta"]["timestamp"] = time.time()
    
    logger.debug(f"Routing message {message_id} to session {session_id} with priority {priority}")
    await broker.route_from_client(session_id, payload)
    
    # Per MCP spec: return 202 Accepted for messages (responses come via SSE)
    return JSONResponse({"status": "accepted"}, status_code=202)

@app.get("/sessions")
async def list_sessions():
    """List all active sessions with details"""
    if not broker:
        raise HTTPException(503, "Bridge not ready")
    
    sessions_info = {}
    for session_id, session in broker.sessions.items():
        sessions_info[session_id] = {
            "queue_size": session.queue.qsize(),
            "websocket_count": len(session.websockets),
            "last_beat": session.last_beat,
            "age_seconds": time.time() - session.last_beat
        }
    
    logger.debug(f"Session list requested - {len(sessions_info)} active sessions")
    return {
        "active_sessions": len(sessions_info),
        "sessions": sessions_info,
        "timestamp": time.time()
    }

@app.delete("/sessions/{session_id}")
async def terminate_session(session_id: str):
    """Terminate a specific session"""
    if not broker:
        raise HTTPException(503, "Bridge not ready")
    
    if session_id not in broker.sessions:
        raise HTTPException(404, f"Session {session_id} not found")
    
    # TODO: Implement session cleanup in broker
    logger.info(f"Session termination requested for {session_id}")
    return {"status": "session termination requested", "session": session_id}

def load_tools_config(tools_config_path: Optional[str]) -> Dict[str, Any]:
    """Load tools configuration from JSON file"""
    if not tools_config_path:
        return {}
    
    try:
        with open(tools_config_path, 'r') as f:
            config = json.load(f)
            logger.info(f"Loaded tools config from {tools_config_path}")
            return config
    except Exception as e:
        logger.warning(f"Failed to load tools config from {tools_config_path}: {e}")
        return {}

# OAuth/Auth endpoints for Claude Code compatibility
@app.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server():
    """OAuth Authorization Server Metadata - indicates no auth required"""
    return JSONResponse({
        "error": "no_authentication_required",
        "error_description": "This MCP server operates without authentication"
    }, status_code=404)

@app.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource():
    """OAuth Protected Resource Metadata - indicates no auth required"""
    return JSONResponse({
        "error": "no_authentication_required", 
        "error_description": "This MCP server operates without authentication"
    }, status_code=404)

@app.post("/register")
async def register_client():
    """Client registration - not required for this bridge"""
    return JSONResponse({
        "error": "no_registration_required",
        "error_description": "Client registration not required for this bridge"
    }, status_code=404)

def setup_logging(log_level: str, log_location: Optional[str] = None, log_pattern: str = "bridge_{server}_{port}.log", 
                 server_name: str = "unknown", port: int = 8100):
    """Configure logging based on arguments"""
    logger.handlers.clear()  # Remove any existing handlers
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if log_location specified
    if log_location:
        os.makedirs(log_location, exist_ok=True)
        
        # Generate log filename from pattern
        from datetime import datetime
        log_filename = log_pattern.format(
            server=server_name,
            port=port,
            date=datetime.now().strftime("%Y%m%d")
        )
        
        file_handler = logging.FileHandler(os.path.join(log_location, log_filename))
        file_formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        logger.info(f"Logging to file: {os.path.join(log_location, log_filename)}")
    
    # Set level
    logger.setLevel(getattr(logging, log_level.upper()))

async def test_stdio_server_health(process: StdioProcess) -> bool:
    """Test if the underlying stdio MCP server is responding properly"""
    try:
        logger.info("Testing stdio server health...")
        
        # Send a basic ping/initialize to test responsiveness
        test_init = {
            "jsonrpc": "2.0",
            "id": "health-check",
            "method": "initialize", 
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "Bridge Health Check", "version": "1.0.0"}
            }
        }
        
        await process.write_json(test_init)
        logger.debug("Sent health check initialize request")
        
        # Wait for response with timeout
        response = await asyncio.wait_for(process.read_json(), timeout=10.0)
        
        if response.get("id") == "health-check" and "result" in response:
            logger.info("✓ Stdio server health check passed - server is responsive")
            return True
        else:
            logger.warning(f"⚠ Stdio server health check failed - unexpected response: {response}")
            return False
            
    except asyncio.TimeoutError:
        logger.error("✗ Stdio server health check failed - server not responding within 10s")
        return False
    except Exception as e:
        logger.error(f"✗ Stdio server health check failed - error: {e}")
        return False

async def init_broker(cmd: str):
    """Initialize the broker with the given command and health checks"""
    global broker
    
    try:
        logger.info(f"Starting stdio server: {cmd}")
        process = StdioProcess(cmd)
        await process.start()
        
        # Test server health before continuing
        is_healthy = await test_stdio_server_health(process)
        if not is_healthy:
            logger.warning("Stdio server health check failed, but continuing anyway...")
        
        broker = Broker(process)
        logger.info(f"✓ Broker successfully initialized with command: {cmd}")
        
    except Exception as e:
        logger.error(f"✗ Failed to initialize broker: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description="Simple MCP Bridge")
    parser.add_argument("--port", type=int, default=8100, help="Port to run on")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--cmd", required=True, help="Command to run MCP server")
    parser.add_argument("--log_level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logging level")
    parser.add_argument("--log_location", help="Directory for log files (optional)")
    parser.add_argument("--log_pattern", default="bridge_{server}_{port}.log", help="Log filename pattern (supports {server}, {port}, {date})")
    parser.add_argument("--queue_strategy", default="fifo", choices=["fifo", "priority", "round_robin"], help="Request queueing strategy")
    parser.add_argument("--max_queue_size", type=int, default=100, help="Maximum queue size per session")
    parser.add_argument("--session_timeout", type=int, default=3600, help="Session timeout in seconds")
    parser.add_argument("--tools_config", help="JSON file with tool definitions for bridge-level discovery")
    
    args = parser.parse_args()
    
    # Extract server name from command for logging
    server_name = "unknown"
    if "qdrant" in args.cmd.lower():
        server_name = "qdrant"
    elif "serena" in args.cmd.lower():
        server_name = "serena"
    elif "echo" in args.cmd.lower():
        server_name = "test"
    
    # Setup logging first
    setup_logging(args.log_level, args.log_location, args.log_pattern, server_name, args.port)
    
    # Use command as string
    cmd = args.cmd
    
    # Load tools configuration if provided
    tools_config = load_tools_config(args.tools_config)
    
    # Store configuration in app state
    app.state.config = args
    app.state.tools_config = tools_config
    
    # Initialize broker on startup
    @app.on_event("startup")
    async def startup():
        await init_broker(cmd)
    
    logger.info(f"Starting Simple MCP Bridge on {args.host}:{args.port}")
    logger.info(f"Auth mode: {AUTH_MODE}")
    logger.info(f"Command: {cmd}")
    logger.info(f"Log level: {args.log_level}")
    logger.info(f"Queue strategy: {args.queue_strategy}")
    logger.info(f"Max queue size: {args.max_queue_size}")
    logger.info(f"Session timeout: {args.session_timeout}s")
    if args.log_location:
        logger.info(f"Log location: {args.log_location}")
    
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info"
    )

if __name__ == "__main__":
    main()