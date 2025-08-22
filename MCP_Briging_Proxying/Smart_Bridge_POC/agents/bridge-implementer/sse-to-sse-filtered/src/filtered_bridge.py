#!/usr/bin/env python3
"""
SSE-to-SSE Bridge with Content Filtering for MCP
Enhanced version of simple_bridge.py with comprehensive content filtering and security features
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
    from .sse_process import SSEProcess
    from .enhanced_broker import EnhancedBroker
    from .content_filters import ContentFilter, FilterConfig
    from .models import FilterInfo
except ImportError:
    from sse_process import SSEProcess
    from enhanced_broker import EnhancedBroker
    from content_filters import ContentFilter, FilterConfig
    from models import FilterInfo

# ----------------------------- Logging ------------------------------------
logger = logging.getLogger("filtered-bridge")

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
    title="Filtered SSE-to-SSE MCP Bridge", 
    version="2.0.0", 
    description="SSE-to-SSE MCP bridge with comprehensive content filtering and security"
)

# Global broker instance
broker: Optional[EnhancedBroker] = None

@app.get("/health")
async def health():
    """Enhanced health check endpoint with filtering status"""
    if not broker:
        return {
            "status": "initializing",
            "auth_mode": AUTH_MODE,
            "connections": 0
        }
        
    status = broker.get_status()
    return {
        "status": "ok",
        "auth_mode": AUTH_MODE,
        "connections": status["total_sessions"],
        "uptime_seconds": status["uptime_seconds"],
        "messages_processed": status["total_messages"],
        "error_count": status["error_count"],
        "sse_connection": status["sse_connection"],
        "content_filtering": {
            "enabled": True,
            "metrics": status["content_filter_metrics"]
        }
    }

@app.get("/status")
async def detailed_status():
    """Detailed status endpoint for monitoring"""
    if not broker:
        raise HTTPException(503, "Bridge not ready")
        
    return {
        "broker_status": broker.get_status(),
        "session_details": broker.get_session_details(),
        "filter_info": broker.get_filter_info()
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
    """Generate SSE event stream for a session per MCP spec"""
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
    """Send message to MCP server with content filtering"""
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
                    "name": "Filtered SSE Bridge",
                    "version": "2.0.0"
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
        logger.debug(f"Forwarding initialize to underlying SSE server")
        await broker.route_from_client(session_id, server_init_payload)
        
        return JSONResponse({"status": "accepted"}, status_code=202)
    
    # Handle discovery requests at bridge level
    discovery_methods = ["tools/list", "resources/list", "prompts/list"]
    if payload.get("method") in discovery_methods:
        session_id = request.query_params.get("session")
        if not session_id or session_id not in broker.sessions:
            raise HTTPException(400, "Valid session required for discovery")
            
        method = payload.get("method")
        request_id = payload.get("id")
        
        logger.info(f"Handling bridge-level discovery: {method} (id: {request_id})")
        
        if method == "tools/list":
            # Return available tools from upstream server configuration
            tools_response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": getattr(app.state, 'upstream_tools', [])}
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
            logger.info(f"Sent bridge tools/list response (id: {request_id}) to session {session_id}")
            return JSONResponse({"status": "accepted"}, status_code=202)
    
    # Ensure message has required JSON-RPC fields
    if isinstance(payload, dict) and "jsonrpc" not in payload:
        payload["jsonrpc"] = "2.0"
    if "id" not in payload and payload.get("method"):
        payload["id"] = str(uuid.uuid4())
    
    # Get session ID
    session_id = request.query_params.get("session")
    
    # Fallback: single open session
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
    """List all active sessions with enhanced details"""
    if not broker:
        raise HTTPException(503, "Bridge not ready")
    
    return broker.get_session_details()

@app.delete("/sessions/{session_id}")
async def terminate_session(session_id: str):
    """Terminate a specific session"""
    if not broker:
        raise HTTPException(503, "Bridge not ready")
    
    if session_id not in broker.sessions:
        raise HTTPException(404, f"Session {session_id} not found")
    
    # Clean up session
    del broker.sessions[session_id]
    logger.info(f"Session {session_id} terminated")
    return {"status": "session terminated", "session": session_id}

# ----------------------------- Filter Management Endpoints ---------------

@app.get("/filters")
async def list_filters():
    """List available content filters"""
    if not broker:
        raise HTTPException(503, "Bridge not ready")
    
    return {
        "filters": broker.get_filter_info(),
        "metrics": broker.content_filter.get_metrics()
    }

@app.post("/filters/config")
async def update_filter_config(new_config: dict):
    """Update content filter configuration"""
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
    
    return broker.content_filter.get_metrics()

# ----------------------------- Utility Functions -------------------------

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

def setup_logging(log_level: str, log_location: Optional[str] = None, log_pattern: str = "filtered_bridge_{port}.log", 
                 port: int = 8201):
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

async def test_sse_server_health(sse_url: str, api_key: Optional[str] = None) -> bool:
    """Test if the upstream SSE MCP server is responding properly"""
    try:
        logger.info(f"Testing SSE server health at {sse_url}")
        
        # Create temporary SSE process for health check
        test_proc = SSEProcess(sse_url, api_key)
        
        try:
            await test_proc.start()
            
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
            
            await test_proc.write_json(test_init)
            logger.debug("Sent health check initialize request to SSE server")
            
            # Wait for response with timeout
            response = await asyncio.wait_for(test_proc.read_json(), timeout=10.0)
            
            if response.get("id") == "health-check" and "result" in response:
                logger.info("✓ SSE server health check passed - server is responsive")
                return True
            else:
                logger.warning(f"⚠ SSE server health check failed - unexpected response: {response}")
                return False
                
        finally:
            await test_proc.cleanup()
            
    except asyncio.TimeoutError:
        logger.error("✗ SSE server health check failed - server not responding within 10s")
        return False
    except Exception as e:
        logger.error(f"✗ SSE server health check failed - error: {e}")
        return False

async def init_broker(sse_url: str, api_key: Optional[str], filter_config: FilterConfig):
    """Initialize the enhanced broker with SSE connection and content filtering"""
    global broker
    
    try:
        logger.info(f"Starting SSE connection to: {sse_url}")
        sse_process = SSEProcess(sse_url, api_key)
        
        # Test server health before continuing
        is_healthy = await test_sse_server_health(sse_url, api_key)
        if not is_healthy:
            logger.warning("SSE server health check failed, but continuing anyway...")
        
        broker = EnhancedBroker(sse_process, filter_config)
        await broker.start()
        logger.info(f"✓ Enhanced broker successfully initialized with SSE endpoint: {sse_url}")
        
    except Exception as e:
        logger.error(f"✗ Failed to initialize enhanced broker: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description="Filtered SSE-to-SSE MCP Bridge")
    parser.add_argument("--port", type=int, default=8201, help="Port to run on")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--sse_url", required=True, help="URL of upstream SSE MCP server")
    parser.add_argument("--api_key", help="API key for upstream server (optional)")
    parser.add_argument("--filter_config", help="JSON file with content filter configuration")
    parser.add_argument("--log_level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logging level")
    parser.add_argument("--log_location", help="Directory for log files (optional)")
    parser.add_argument("--log_pattern", default="filtered_bridge_{port}.log", help="Log filename pattern")
    
    args = parser.parse_args()
    
    # Setup logging first
    setup_logging(args.log_level, args.log_location, args.log_pattern, args.port)
    
    # Load filter configuration
    filter_config = load_filter_config(args.filter_config)
    
    # Store configuration in app state
    app.state.config = args
    app.state.filter_config = filter_config
    
    # Initialize broker on startup
    @app.on_event("startup")
    async def startup():
        await init_broker(args.sse_url, args.api_key, filter_config)
    
    logger.info(f"Starting Filtered SSE-to-SSE MCP Bridge on {args.host}:{args.port}")
    logger.info(f"Auth mode: {AUTH_MODE}")
    logger.info(f"Upstream SSE URL: {args.sse_url}")
    logger.info(f"Log level: {args.log_level}")
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