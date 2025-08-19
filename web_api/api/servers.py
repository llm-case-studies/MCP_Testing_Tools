"""
Server management API endpoints
"""

import logging
import requests
from fastapi import APIRouter, HTTPException
from ..models import ServerConfig
from ..storage import servers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/servers", tags=["servers"])


@router.post("")
async def add_server(server: ServerConfig):
    """Add a new MCP server configuration"""
    servers[server.name] = server.dict()
    logger.info(f"Added server: {server.name}")
    return {"message": f"Server {server.name} added"}


@router.get("")
async def list_servers():
    """List all configured servers"""
    return {"servers": list(servers.values())}


@router.get("/{server_name}")
async def get_server(server_name: str):
    """Get specific server configuration"""
    if server_name not in servers:
        raise HTTPException(status_code=404, detail="Server not found")
    return servers[server_name]


@router.delete("/{server_name}")
async def remove_server(server_name: str):
    """Remove server configuration"""
    if server_name not in servers:
        raise HTTPException(status_code=404, detail="Server not found")
    del servers[server_name]
    return {"message": f"Server {server_name} removed"}


@router.post("/{server_name}/test-connection")
async def test_server_connection(server_name: str):
    """Test connection to MCP server"""
    if server_name not in servers:
        raise HTTPException(status_code=404, detail="Server not found")
    
    server = servers[server_name]
    
    try:
        if server["type"] == "mock":
            # Test mock server
            response = requests.get(f"{server['url']}/")
            return {
                "status": "connected",
                "response": response.json(),
                "latency_ms": response.elapsed.total_seconds() * 1000
            }
        elif server["type"] == "proxy":
            # Test proxy server
            response = requests.get(f"{server['url']}/")
            return {
                "status": "connected", 
                "response": response.json(),
                "latency_ms": response.elapsed.total_seconds() * 1000
            }
        else:
            return {"status": "unsupported", "message": "Direct server testing not implemented"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/{server_name}/tools")
async def list_server_tools(server_name: str):
    """List available tools for a specific server"""
    if server_name not in servers:
        raise HTTPException(status_code=404, detail="Server not found")
    
    server = servers[server_name]
    
    try:
        if server["type"] == "mock":
            # Get tools from mock server
            response = requests.get(f"{server['url']}/tools")
            return response.json()
        elif server["type"] == "proxy":
            # Get tools from proxy server
            response = requests.get(f"{server['url']}/tools")
            return response.json()
        else:
            return {"error": "Direct server tool listing not implemented"}
            
    except Exception as e:
        logger.error(f"Error listing tools for {server_name}: {e}")
        return {"error": str(e), "tools": []}


@router.get("/{server_name}/logs")
async def get_server_logs(server_name: str):
    """Get server logs and status"""
    if server_name not in servers:
        raise HTTPException(status_code=404, detail="Server not found")
    
    server = servers[server_name]
    
    try:
        if server["type"] in ["mock", "proxy"]:
            response = requests.get(f"{server['url']}/logs")
            return response.json()
        else:
            return {"logs": [], "message": "Direct server logs not available"}
            
    except Exception as e:
        logger.error(f"Error getting logs for {server_name}: {e}")
        return {"logs": [], "error": str(e)}