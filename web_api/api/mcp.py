"""
MCP (Model Context Protocol) specific API endpoints
Handles MCP server discovery, tool calling, and request management
"""

import os
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from ..models import MCPToolRequest, MCPCollection
from ..storage import mcp_request_history, mcp_collections

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


@router.get("/discover")
async def discover_mcp_servers():
    """Discover all available MCP servers with detailed introspection"""
    try:
        from config_discovery import MCPConfigDiscovery
        
        config_dir = os.environ.get("MCP_CONFIG_DIR", "/mcp-configs")
        if not os.path.exists(config_dir):
            config_dir = os.path.expanduser("~")
        
        discovery = MCPConfigDiscovery(config_dir)
        servers = discovery.discover_servers()
        
        # Enhanced server info with tool discovery
        enhanced_servers = []
        for server in servers:
            try:
                # Get basic server info
                enhanced_server = {
                    "name": server["name"],
                    "type": server["type"],
                    "command": server.get("command", []),
                    "url": server.get("url"),
                    "description": server.get("description", ""),
                    "status": "unknown",
                    "tools": [],
                    "capabilities": discovery.get_server_capabilities(server),
                    "validation": discovery.validate_server_config(server)
                }
                
                # Try to discover tools (this would need actual MCP connection)
                # For now, we'll mark as discoverable
                enhanced_server["status"] = "discoverable"
                enhanced_server["discovery_notes"] = "Use /api/mcp/tools/{server_name} to discover tools"
                
                enhanced_servers.append(enhanced_server)
                
            except Exception as e:
                logger.error(f"Error processing server {server.get('name', 'unknown')}: {e}")
                enhanced_servers.append({
                    "name": server.get("name", "unknown"),
                    "type": server.get("type", "unknown"), 
                    "status": "error",
                    "error": str(e)
                })
        
        return {
            "servers": enhanced_servers,
            "total_count": len(enhanced_servers),
            "discovered_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"MCP discovery error: {e}")
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")


@router.get("/tools/{server_name}")
async def discover_server_tools(server_name: str):
    """Discover tools available on a specific MCP server"""
    try:
        # This would connect to the actual MCP server and discover tools
        # For now, we'll return mock data structure that shows what we'd return
        
        logger.info(f"Discovering tools for server: {server_name}")
        
        # TODO: Implement actual MCP tool discovery
        # This would involve:
        # 1. Starting/connecting to the MCP server
        # 2. Sending tools/list request
        # 3. Parsing the response to get tool schemas
        
        return {
            "server_name": server_name,
            "status": "mock_response",
            "message": "This endpoint will discover actual MCP tools when connected to server",
            "tools": [
                {
                    "name": "example_tool",
                    "description": "Example tool that would be discovered",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "param1": {"type": "string", "description": "Example parameter"},
                            "param2": {"type": "number", "description": "Example number parameter"}
                        },
                        "required": ["param1"]
                    }
                }
            ],
            "tool_count": 1,
            "discovered_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Tool discovery error for {server_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Tool discovery failed: {str(e)}")


@router.post("/call-tool/{server_name}")
async def call_mcp_tool(server_name: str, request: MCPToolRequest):
    """Execute an MCP tool call with comprehensive logging"""
    try:
        start_time = datetime.now()
        
        # Create request ID for tracking
        request_id = f"req_{int(start_time.timestamp() * 1000)}"
        
        logger.info(f"MCP tool call [{request_id}]: {server_name}.{request.tool_name}")
        
        # TODO: Implement actual MCP tool calling
        # This would involve:
        # 1. Connecting to the MCP server
        # 2. Sending tools/call request with proper params
        # 3. Handling response and errors
        # 4. Logging all communication
        
        # Mock response for now
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        response_data = {
            "request_id": request_id,
            "server_name": server_name,
            "tool_name": request.tool_name,
            "arguments": request.arguments,
            "status": "mock_success",
            "result": {
                "message": "This is a mock response. Actual MCP tool execution coming soon.",
                "arguments_received": request.arguments,
                "server": server_name,
                "tool": request.tool_name
            },
            "timing": {
                "started_at": start_time.isoformat(),
                "completed_at": end_time.isoformat(),
                "duration_ms": duration_ms
            },
            "log_entries": [
                {"level": "info", "message": f"Tool call initiated: {request.tool_name}", "timestamp": start_time.isoformat()},
                {"level": "info", "message": f"Arguments: {request.arguments}", "timestamp": start_time.isoformat()},
                {"level": "success", "message": "Mock execution completed", "timestamp": end_time.isoformat()}
            ]
        }
        
        # Add to request history
        mcp_request_history.append(response_data)
        
        # Keep only last 100 requests in memory
        if len(mcp_request_history) > 100:
            mcp_request_history.pop(0)
        
        return response_data
        
    except Exception as e:
        error_time = datetime.now()
        error_response = {
            "request_id": f"req_error_{int(error_time.timestamp() * 1000)}",
            "server_name": server_name,
            "tool_name": request.tool_name,
            "status": "error",
            "error": str(e),
            "timing": {
                "failed_at": error_time.isoformat()
            }
        }
        
        mcp_request_history.append(error_response)
        logger.error(f"MCP tool call error: {e}")
        
        return error_response


@router.get("/history")
async def get_request_history(limit: int = 50):
    """Get MCP tool call history"""
    return {
        "requests": mcp_request_history[-limit:] if mcp_request_history else [],
        "total_requests": len(mcp_request_history),
        "limit": limit
    }


@router.delete("/history")
async def clear_request_history():
    """Clear MCP tool call history"""
    cleared_count = len(mcp_request_history)
    mcp_request_history.clear()
    
    return {
        "message": f"Cleared {cleared_count} request(s) from history",
        "cleared_count": cleared_count
    }


@router.get("/collections")
async def get_collections():
    """Get saved MCP tool call collections"""
    return {
        "collections": [
            {
                "name": name,
                "description": collection.description,
                "request_count": len(collection.requests)
            }
            for name, collection in mcp_collections.items()
        ]
    }


@router.post("/collections/{collection_name}")
async def save_collection(collection_name: str, collection: MCPCollection):
    """Save an MCP tool call collection"""
    mcp_collections[collection_name] = collection
    
    return {
        "message": f"Collection '{collection_name}' saved successfully",
        "collection_name": collection_name,
        "request_count": len(collection.requests)
    }


@router.get("/collections/{collection_name}")
async def get_collection(collection_name: str):
    """Get a specific MCP tool call collection"""
    if collection_name not in mcp_collections:
        raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
    
    return mcp_collections[collection_name]


@router.delete("/collections/{collection_name}")
async def delete_collection(collection_name: str):
    """Delete an MCP tool call collection"""
    if collection_name not in mcp_collections:
        raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
    
    del mcp_collections[collection_name]
    
    return {"message": f"Collection '{collection_name}' deleted successfully"}


@router.get("/generate-sample/{server_name}/{tool_name}")
async def generate_sample_request(server_name: str, tool_name: str):
    """Generate sample request for an MCP tool based on its schema"""
    try:
        # This would analyze the tool schema and generate sample values
        # For now, return a sample structure
        
        return {
            "server_name": server_name,
            "tool_name": tool_name,
            "sample_request": {
                "tool_name": tool_name,
                "arguments": {
                    "example_param": "sample_value",
                    "optional_param": 123
                },
                "description": f"Sample request for {tool_name} on {server_name}"
            },
            "notes": "This is a generated sample. Adjust parameters based on tool schema."
        }
        
    except Exception as e:
        logger.error(f"Sample generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Sample generation failed: {str(e)}")