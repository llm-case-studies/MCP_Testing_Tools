#!/usr/bin/env python3
"""
Web-based MCP Mock Server
Simulates MCP protocol over HTTP for testing and debugging
"""

import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MCP Mock Server", version="1.0.0")

# Enable CORS for web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MCP Protocol Models
class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    method: str
    params: Optional[Dict[str, Any]] = None

class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

# Mock data storage
mock_tools = {
    "file_read": {
        "name": "file_read",
        "description": "Read contents of a file",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read"}
            },
            "required": ["path"]
        }
    },
    "database_query": {
        "name": "database_query", 
        "description": "Execute database query",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL query"},
                "database": {"type": "string", "description": "Database name"}
            },
            "required": ["query"]
        }
    }
}

mock_resources = {
    "config://app.json": {
        "uri": "config://app.json",
        "name": "Application Configuration",
        "description": "Main application configuration file",
        "mimeType": "application/json"
    },
    "logs://system.log": {
        "uri": "logs://system.log", 
        "name": "System Logs",
        "description": "Current system log file",
        "mimeType": "text/plain"
    }
}

# Communication log storage
communication_log = []

def log_communication(direction: str, message: Dict[str, Any], client_info: str = ""):
    """Log MCP communication for debugging"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "direction": direction,  # "incoming" or "outgoing"
        "message": message,
        "client_info": client_info
    }
    communication_log.append(log_entry)
    logger.info(f"{direction.upper()}: {json.dumps(message, indent=2)}")

@app.post("/mcp")
async def mcp_endpoint(request: Request, mcp_request: MCPRequest):
    """Main MCP protocol endpoint"""
    
    client_ip = request.client.host if request.client else "unknown"
    log_communication("incoming", mcp_request.dict(), f"client:{client_ip}")
    
    # Handle different MCP methods
    if mcp_request.method == "initialize":
        response = MCPResponse(
            id=mcp_request.id,
            result={
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "logging": {}
                },
                "serverInfo": {
                    "name": "MCP Mock Server",
                    "version": "1.0.0"
                }
            }
        )
    
    elif mcp_request.method == "tools/list":
        response = MCPResponse(
            id=mcp_request.id,
            result={
                "tools": list(mock_tools.values())
            }
        )
    
    elif mcp_request.method == "tools/call":
        tool_name = mcp_request.params.get("name") if mcp_request.params else None
        if tool_name not in mock_tools:
            response = MCPResponse(
                id=mcp_request.id,
                error={
                    "code": -32602,
                    "message": f"Unknown tool: {tool_name}"
                }
            )
        else:
            # Simulate tool execution
            response = MCPResponse(
                id=mcp_request.id,
                result={
                    "content": [
                        {
                            "type": "text",
                            "text": f"Mock result for {tool_name} with params: {mcp_request.params.get('arguments', {})}"
                        }
                    ]
                }
            )
    
    elif mcp_request.method == "resources/list":
        response = MCPResponse(
            id=mcp_request.id,
            result={
                "resources": list(mock_resources.values())
            }
        )
    
    elif mcp_request.method == "resources/read":
        uri = mcp_request.params.get("uri") if mcp_request.params else None
        if uri not in mock_resources:
            response = MCPResponse(
                id=mcp_request.id,
                error={
                    "code": -32602,
                    "message": f"Resource not found: {uri}"
                }
            )
        else:
            # Mock resource content
            content = {
                "config://app.json": {"database": "localhost", "port": 8080},
                "logs://system.log": "2024-01-01 INFO: System started\n2024-01-01 INFO: All services ready"
            }.get(uri, f"Mock content for {uri}")
            
            response = MCPResponse(
                id=mcp_request.id,
                result={
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": mock_resources[uri]["mimeType"],
                            "text": content if isinstance(content, str) else json.dumps(content)
                        }
                    ]
                }
            )
    
    else:
        response = MCPResponse(
            id=mcp_request.id,
            error={
                "code": -32601,
                "message": f"Method not found: {mcp_request.method}"
            }
        )
    
    log_communication("outgoing", response.dict(), f"client:{client_ip}")
    return response

@app.get("/debug/logs")
async def get_communication_logs():
    """Get communication logs for debugging"""
    return {"logs": communication_log}

@app.delete("/debug/logs")
async def clear_communication_logs():
    """Clear communication logs"""
    global communication_log
    communication_log = []
    return {"message": "Logs cleared"}

@app.get("/debug/tools")
async def get_mock_tools():
    """Get configured mock tools"""
    return {"tools": mock_tools}

@app.post("/debug/tools")
async def add_mock_tool(tool_data: Dict[str, Any]):
    """Add a new mock tool"""
    tool_name = tool_data.get("name")
    if not tool_name:
        raise HTTPException(status_code=400, detail="Tool name required")
    
    mock_tools[tool_name] = tool_data
    return {"message": f"Tool {tool_name} added"}

@app.get("/debug/resources")
async def get_mock_resources():
    """Get configured mock resources"""
    return {"resources": mock_resources}

@app.post("/debug/resources")
async def add_mock_resource(resource_data: Dict[str, Any]):
    """Add a new mock resource"""
    uri = resource_data.get("uri")
    if not uri:
        raise HTTPException(status_code=400, detail="Resource URI required")
    
    mock_resources[uri] = resource_data
    return {"message": f"Resource {uri} added"}

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "MCP Mock Server",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "mcp": "/mcp",
            "debug_logs": "/debug/logs",
            "debug_tools": "/debug/tools", 
            "debug_resources": "/debug/resources"
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9091)