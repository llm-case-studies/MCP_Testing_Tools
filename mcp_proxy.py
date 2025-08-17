#!/usr/bin/env python3
"""
MCP Communication Proxy/Interceptor
Sits between MCP client and server to log/debug/filter communication
"""

import json
import asyncio
import logging
import subprocess
import sys
import websockets
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MCP Proxy", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProxySession:
    def __init__(self, server_command: List[str]):
        self.server_command = server_command
        self.server_process = None
        self.message_log = []
        self.websocket_clients = set()
        self.filters = []
        
    async def start_server(self):
        """Start the MCP server process"""
        self.server_process = await asyncio.create_subprocess_exec(
            *self.server_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        logger.info(f"Started MCP server: {' '.join(self.server_command)}")
        
    async def stop_server(self):
        """Stop the MCP server process"""
        if self.server_process:
            self.server_process.terminate()
            await self.server_process.wait()
            logger.info("Stopped MCP server")
            
    def log_message(self, direction: str, message: Dict[str, Any], filtered: bool = False):
        """Log MCP message with metadata"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "direction": direction,  # "client_to_server" or "server_to_client"
            "message": message,
            "filtered": filtered
        }
        self.message_log.append(log_entry)
        
        # Broadcast to WebSocket clients
        asyncio.create_task(self.broadcast_log_entry(log_entry))
        
        logger.info(f"{direction.upper()}: {json.dumps(message, indent=2)}")
        
    async def broadcast_log_entry(self, log_entry: Dict[str, Any]):
        """Broadcast log entry to all connected WebSocket clients"""
        if self.websocket_clients:
            message = json.dumps(log_entry)
            disconnected = set()
            for client in self.websocket_clients:
                try:
                    await client.send_text(message)
                except:
                    disconnected.add(client)
            # Remove disconnected clients
            self.websocket_clients -= disconnected
            
    def apply_filters(self, message: Dict[str, Any], direction: str) -> tuple[Dict[str, Any], bool]:
        """Apply filters to message, return (modified_message, was_filtered)"""
        original_message = message.copy()
        filtered = False
        
        for filter_func in self.filters:
            try:
                message, was_modified = filter_func(message, direction)
                if was_modified:
                    filtered = True
            except Exception as e:
                logger.error(f"Filter error: {e}")
                
        return message, filtered
        
    async def send_to_server(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send message to MCP server and get response"""
        if not self.server_process:
            await self.start_server()
            
        # Apply filters
        filtered_message, was_filtered = self.apply_filters(message, "client_to_server")
        self.log_message("client_to_server", message, was_filtered)
        
        try:
            # Send to server
            message_str = json.dumps(filtered_message) + "\n"
            self.server_process.stdin.write(message_str.encode())
            await self.server_process.stdin.drain()
            
            # Read response
            response_line = await self.server_process.stdout.readline()
            if response_line:
                response = json.loads(response_line.decode().strip())
                
                # Apply filters to response
                filtered_response, response_filtered = self.apply_filters(response, "server_to_client")
                self.log_message("server_to_client", response, response_filtered)
                
                return filtered_response
                
        except Exception as e:
            logger.error(f"Communication error: {e}")
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Proxy error: {str(e)}"
                }
            }
            
        return None

# Global proxy session
proxy_session = None

class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    method: str
    params: Optional[Dict[str, Any]] = None

class FilterConfig(BaseModel):
    name: str
    enabled: bool
    config: Dict[str, Any]

@app.post("/proxy/start")
async def start_proxy(server_config: Dict[str, Any]):
    """Start MCP proxy with server configuration"""
    global proxy_session
    
    command = server_config.get("command", [])
    if not command:
        return {"error": "Server command required"}
        
    proxy_session = ProxySession(command)
    await proxy_session.start_server()
    
    return {"message": "Proxy started", "command": command}

@app.post("/proxy/stop")
async def stop_proxy():
    """Stop MCP proxy"""
    global proxy_session
    
    if proxy_session:
        await proxy_session.stop_server()
        proxy_session = None
        
    return {"message": "Proxy stopped"}

@app.post("/proxy/send")
async def send_message(request: MCPRequest):
    """Send message through proxy to MCP server"""
    global proxy_session
    
    if not proxy_session:
        return {"error": "Proxy not started"}
        
    response = await proxy_session.send_to_server(request.dict())
    return response

@app.get("/proxy/logs")
async def get_proxy_logs():
    """Get communication logs"""
    global proxy_session
    
    if not proxy_session:
        return {"logs": []}
        
    return {"logs": proxy_session.message_log}

@app.delete("/proxy/logs")
async def clear_proxy_logs():
    """Clear communication logs"""
    global proxy_session
    
    if proxy_session:
        proxy_session.message_log = []
        
    return {"message": "Logs cleared"}

@app.websocket("/proxy/logs/stream")
async def websocket_logs(websocket: WebSocket):
    """WebSocket endpoint for real-time log streaming"""
    global proxy_session
    
    await websocket.accept()
    
    if proxy_session:
        proxy_session.websocket_clients.add(websocket)
        
        try:
            while True:
                # Keep connection alive
                await websocket.receive_text()
        except WebSocketDisconnect:
            if proxy_session:
                proxy_session.websocket_clients.discard(websocket)

# Built-in filters
def delay_filter(message: Dict[str, Any], direction: str, delay_ms: int = 100) -> tuple[Dict[str, Any], bool]:
    """Add artificial delay to messages"""
    import time
    time.sleep(delay_ms / 1000)
    return message, False

def error_injection_filter(message: Dict[str, Any], direction: str, error_rate: float = 0.1) -> tuple[Dict[str, Any], bool]:
    """Randomly inject errors"""
    import random
    if direction == "server_to_client" and random.random() < error_rate:
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {
                "code": -32603,
                "message": "Injected error for testing"
            }
        }, True
    return message, False

def logging_filter(message: Dict[str, Any], direction: str) -> tuple[Dict[str, Any], bool]:
    """Enhanced logging filter"""
    if message.get("method") == "tools/call":
        tool_name = message.get("params", {}).get("name", "unknown")
        logger.info(f"Tool call intercepted: {tool_name}")
    return message, False

@app.post("/proxy/filters")
async def configure_filters(filters: List[FilterConfig]):
    """Configure message filters"""
    global proxy_session
    
    if not proxy_session:
        return {"error": "Proxy not started"}
        
    proxy_session.filters = []
    
    for filter_config in filters:
        if not filter_config.enabled:
            continue
            
        if filter_config.name == "delay":
            delay_ms = filter_config.config.get("delay_ms", 100)
            proxy_session.filters.append(lambda msg, dir: delay_filter(msg, dir, delay_ms))
        elif filter_config.name == "error_injection":
            error_rate = filter_config.config.get("error_rate", 0.1)
            proxy_session.filters.append(lambda msg, dir: error_injection_filter(msg, dir, error_rate))
        elif filter_config.name == "logging":
            proxy_session.filters.append(logging_filter)
            
    return {"message": f"Configured {len(proxy_session.filters)} filters"}

@app.get("/")
async def root():
    """Health check and info endpoint"""
    global proxy_session
    
    return {
        "service": "MCP Proxy",
        "version": "1.0.0",
        "status": "running" if proxy_session else "stopped",
        "endpoints": {
            "start": "/proxy/start",
            "stop": "/proxy/stop", 
            "send": "/proxy/send",
            "logs": "/proxy/logs",
            "logs_stream": "/proxy/logs/stream",
            "filters": "/proxy/filters"
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9092)