#!/usr/bin/env python3
"""
Enhanced MCP SSE Bridge with Content Filtering - Based on simple_bridge.py
Adds comprehensive content filtering and security features to the working simple bridge
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
    from .content_filters import ContentFilter, FilterConfig
    from .models import FilterInfo
except ImportError:
    from process import StdioProcess
    from broker import Broker
    from content_filters import ContentFilter, FilterConfig
    from models import FilterInfo

# ----------------------------- Logging ------------------------------------
logger = logging.getLogger("filtered-simple-bridge")

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

# ----------------------------- Enhanced Broker Class ----------------------

class FilteredBroker(Broker):
    """Enhanced broker with content filtering capabilities"""
    
    def __init__(self, process: StdioProcess, filter_config: FilterConfig):
        super().__init__(process)
        self.content_filter = ContentFilter(filter_config)
        self.filter_metrics = {
            "messages_filtered": 0,
            "content_blocked": 0,
            "pii_redacted": 0,
            "security_violations": 0
        }
        
    async def route_from_client(self, session_id: str, payload: Dict[str, Any]):
        """Route message from client with content filtering"""
        try:
            # Apply content filtering to outbound message
            filtered_payload, filter_info = await self.content_filter.filter_message(payload, "outbound")
            
            # Log filtering actions
            if filter_info.actions_taken:
                logger.info(f"Content filtering applied to outbound message {payload.get('id', 'no-id')}: {filter_info.actions_taken}")
                self._update_filter_metrics(filter_info)
            
            # If message was blocked, send error response instead of forwarding
            if filter_info.blocked:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": payload.get("id"),
                    "error": {
                        "code": -32000,
                        "message": "Content blocked by security filter",
                        "data": {"reason": filter_info.block_reason}
                    }
                }
                await self._send(session_id, error_response)
                logger.warning(f"Blocked outbound message {payload.get('id', 'no-id')}: {filter_info.block_reason}")
                return
            
            # Forward filtered message to underlying process
            await super().route_from_client(session_id, filtered_payload)
            
        except Exception as e:
            logger.error(f"Error in filtered route_from_client: {e}")
            # Send error response to client
            error_response = {
                "jsonrpc": "2.0",
                "id": payload.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Internal error during content filtering: {str(e)}"
                }
            }
            await self._send(session_id, error_response)
    
    async def route_from_server(self, data: Dict[str, Any]):
        """Route message from server with content filtering"""
        try:
            # Apply content filtering to inbound message
            filtered_data, filter_info = await self.content_filter.filter_message(data, "inbound")
            
            # Log filtering actions
            if filter_info.actions_taken:
                logger.info(f"Content filtering applied to inbound message {data.get('id', 'no-id')}: {filter_info.actions_taken}")
                self._update_filter_metrics(filter_info)
            
            # If message was blocked, don't forward to client
            if filter_info.blocked:
                logger.warning(f"Blocked inbound message {data.get('id', 'no-id')}: {filter_info.block_reason}")
                return
            
            # Forward filtered message to client sessions
            await super().route_from_server(filtered_data)
            
        except Exception as e:
            logger.error(f"Error in filtered route_from_server: {e}")
            # Continue with original data if filtering fails
            await super().route_from_server(data)
    
    def _update_filter_metrics(self, filter_info: FilterInfo):
        """Update filtering metrics"""
        if filter_info.blocked:
            self.filter_metrics["content_blocked"] += 1
        if filter_info.pii_redacted:
            self.filter_metrics["pii_redacted"] += 1
        if filter_info.security_violation:
            self.filter_metrics["security_violations"] += 1
        if filter_info.actions_taken:
            self.filter_metrics["messages_filtered"] += 1
    
    def get_filter_metrics(self) -> Dict[str, Any]:
        """Get current filtering metrics"""
        return {
            **self.filter_metrics,
            "filter_config": self.content_filter.config.model_dump(),
            "uptime_seconds": time.time() - getattr(self, 'start_time', time.time())
        }
    
    def update_filter_config(self, new_config: FilterConfig):
        """Update content filter configuration at runtime"""
        self.content_filter.config = new_config
        logger.info("Content filter configuration updated")

# ----------------------------- FastAPI App --------------------------------
app = FastAPI(
    title="Filtered Simple MCP Bridge", 
    version="1.1.0", 
    description="Simple MCP SSE bridge with comprehensive content filtering and security"
)

# Global broker instance
broker: Optional[FilteredBroker] = None

@app.get("/health")
async def health():
    """Health check endpoint with filtering status"""
    health_info = {
        "status": "ok" if broker else "initializing",
        "auth_mode": AUTH_MODE,
        "connections": len(broker.sessions) if broker else 0,
        "content_filtering": {"enabled": True}
    }
    
    if broker:
        health_info["filter_metrics"] = broker.get_filter_metrics()
    
    return health_info

@app.get("/sse")
async def sse_events(request: Request,
                    session: Optional[str] = None,
                    authorization: Optional[str] = Header(default=None),
                    x_api_key: Optional[str] = Header(default=None)):
    """SSE event stream for MCP connection with auto-session creation - EXACT COPY from simple_bridge.py"""
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
        logger.info(f"Created new filtered session {session_id} for client {client_info} with priority {priority}")
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
    """Generate SSE event stream for a session per MCP spec - EXACT COPY from simple_bridge.py"""
    session = broker.get_session(session_id)
    logger.debug(f"Starting filtered SSE stream for session: {session_id}")
    
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
    """Send message to MCP server with content filtering - Enhanced version of simple_bridge.py"""
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
                    "name": "Filtered Smart Bridge",
                    "version": "1.1.0"
                }
            }
        }
        await broker._send(session_id, bridge_response)
        logger.info(f"Sent filtered bridge initialize response to session {session_id}")
        
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
    
    logger.debug(f"Routing message {message_id} to session {session_id} with content filtering")
    await broker.route_from_client(session_id, payload)
    
    # Per MCP spec: return 202 Accepted for messages (responses come via SSE)
    return JSONResponse({"status": "accepted"}, status_code=202)

@app.get("/sessions")
async def list_sessions():
    """List all active sessions with details - EXACT COPY from simple_bridge.py"""
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
    """Terminate a specific session - EXACT COPY from simple_bridge.py"""
    if not broker:
        raise HTTPException(503, "Bridge not ready")
    
    if session_id not in broker.sessions:
        raise HTTPException(404, f"Session {session_id} not found")
    
    # TODO: Implement session cleanup in broker
    logger.info(f"Session termination requested for {session_id}")
    return {"status": "session termination requested", "session": session_id}

# ----------------------------- Filter Management Endpoints ---------------

@app.get("/filters")
async def list_filters():
    """List content filter configuration and metrics"""
    if not broker:
        raise HTTPException(503, "Bridge not ready")
    
    return {
        "status": "enabled",
        "config": broker.content_filter.config.model_dump(),
        "metrics": broker.get_filter_metrics()
    }

@app.post("/filters/config")
async def update_filter_config(new_config: dict):
    """Update content filter configuration at runtime"""
    if not broker:
        raise HTTPException(503, "Bridge not ready")
    
    try:
        # Validate and create new config
        filter_config = FilterConfig(**new_config)
        broker.update_filter_config(filter_config)
        
        logger.info("Content filter configuration updated via API")
        return {"status": "configuration updated", "config": new_config}
    except Exception as e:
        logger.error(f"Failed to update filter configuration: {e}")
        raise HTTPException(400, f"Invalid configuration: {e}")

@app.get("/filters/metrics")
async def get_filter_metrics():
    """Get detailed filtering metrics"""
    if not broker:
        raise HTTPException(503, "Bridge not ready")
    
    return broker.get_filter_metrics()

def load_tools_config(tools_config_path: Optional[str]) -> Dict[str, Any]:
    """Load tools configuration from JSON file - EXACT COPY from simple_bridge.py"""
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

def load_filter_config(config_path: Optional[str]) -> FilterConfig:
    """Load filter configuration from JSON file"""
    if not config_path or not os.path.exists(config_path):
        logger.info("Using default filter configuration")
        return FilterConfig()
    
    try:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
            logger.info(f"Loaded filter configuration from {config_path}")
            return FilterConfig(**config_data)
    except Exception as e:
        logger.warning(f"Failed to load filter config from {config_path}: {e}")
        return FilterConfig()

# OAuth/Auth endpoints for Claude Code compatibility - EXACT COPY from simple_bridge.py
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

def setup_logging(log_level: str, log_location: Optional[str] = None, log_pattern: str = "filtered_bridge_{server}_{port}.log", 
                 server_name: str = "unknown", port: int = 8100):
    """Configure logging based on arguments - EXACT COPY from simple_bridge.py"""
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
    """Test if the underlying stdio MCP server is responding properly - EXACT COPY from simple_bridge.py"""
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

async def init_broker(cmd: str, filter_config: FilterConfig):
    """Initialize the broker with the given command and content filtering"""
    global broker
    
    try:
        logger.info(f"Starting stdio server: {cmd}")
        process = StdioProcess(cmd)
        await process.start()
        
        # Test server health before continuing
        is_healthy = await test_stdio_server_health(process)
        if not is_healthy:
            logger.warning("Stdio server health check failed, but continuing anyway...")
        
        broker = FilteredBroker(process, filter_config)
        logger.info(f"✓ Filtered broker successfully initialized with command: {cmd}")
        
    except Exception as e:
        logger.error(f"✗ Failed to initialize filtered broker: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description="Filtered Simple MCP Bridge")
    parser.add_argument("--port", type=int, default=8100, help="Port to run on")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--cmd", required=True, help="Command to run MCP server")
    parser.add_argument("--log_level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logging level")
    parser.add_argument("--log_location", help="Directory for log files (optional)")
    parser.add_argument("--log_pattern", default="filtered_bridge_{server}_{port}.log", help="Log filename pattern (supports {server}, {port}, {date})")
    parser.add_argument("--queue_strategy", default="fifo", choices=["fifo", "priority", "round_robin"], help="Request queueing strategy")
    parser.add_argument("--max_queue_size", type=int, default=100, help="Maximum queue size per session")
    parser.add_argument("--session_timeout", type=int, default=3600, help="Session timeout in seconds")
    parser.add_argument("--tools_config", help="JSON file with tool definitions for bridge-level discovery")
    parser.add_argument("--filter_config", help="JSON file with content filter configuration")
    
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
    
    # Load filter configuration
    filter_config = load_filter_config(args.filter_config)
    
    # Store configuration in app state
    app.state.config = args
    app.state.tools_config = tools_config
    app.state.filter_config = filter_config
    
    # Initialize broker on startup
    @app.on_event("startup")
    async def startup():
        await init_broker(cmd, filter_config)
    
    logger.info(f"Starting Filtered Simple MCP Bridge on {args.host}:{args.port}")
    logger.info(f"Auth mode: {AUTH_MODE}")
    logger.info(f"Command: {cmd}")
    logger.info(f"Log level: {args.log_level}")
    logger.info(f"Queue strategy: {args.queue_strategy}")
    logger.info(f"Max queue size: {args.max_queue_size}")
    logger.info(f"Session timeout: {args.session_timeout}s")
    logger.info(f"Content filtering: Enabled")
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