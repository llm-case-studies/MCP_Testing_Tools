"""
Server discovery API endpoints
"""

import os
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from ..models import ServerConfig
from ..storage import servers, discovered_servers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["discovery"])


@router.post("/discover-servers")
async def discover_servers(custom_path: Optional[str] = None):
    """Auto-discover MCP servers from mounted configurations or custom path"""
    try:
        from config_discovery import MCPConfigDiscovery
    except ImportError:
        logger.error("config_discovery module not found")
        return {"error": "Server discovery not available - config_discovery module missing"}
    
    # Use custom path, mounted config directory, or fallback to local
    if custom_path:
        config_dir = custom_path
    else:
        config_dir = os.environ.get("MCP_CONFIG_DIR", "/mcp-configs")
        if not os.path.exists(config_dir):
            config_dir = os.path.expanduser("~")  # Fallback for local testing
    
    discovery = MCPConfigDiscovery(config_dir)
    discovered = discovery.discover_servers()
    
    # Store discovered servers in global cache
    discovered_servers.clear()
    discovered_servers.extend(discovered)
    
    # Add detailed discovery information
    discovery_sources = {
        "claude_config": os.path.join(config_dir, ".claude.json"),
        "gemini_config": os.path.join(config_dir, ".gemini"),
        "project_mcp": "./.mcp.json",
        "config_dir_used": config_dir
    }
    
    # Check which sources exist and were used
    sources_found = {}
    for source_name, path in discovery_sources.items():
        if os.path.exists(path):
            if source_name == "gemini_config":
                sources_found[source_name] = f"{path} (directory)"
            else:
                sources_found[source_name] = path
    
    # Add validation and execution information
    for server in discovered:
        validation = discovery.validate_server_config(server)
        capabilities = discovery.get_server_capabilities(server)
        server["validation"] = validation
        server["capabilities"] = capabilities
        
        # Add execution readiness info
        server["execution_info"] = {
            "command_available": True,  # We'll check this properly later
            "can_activate": server["validation"]["valid"],
            "ready_to_test": server["validation"]["valid"] and len(server["validation"]["issues"]) == 0
        }
    
    return {
        "discovered": discovered,
        "total_servers": len(discovered),
        "discovery_sources": discovery_sources,
        "sources_found": sources_found,
        "config_dir": config_dir
    }


@router.post("/activate-server/{server_name}")
async def activate_discovered_server(server_name: str):
    """Activate a discovered server by making it available for testing"""
    try:
        from config_discovery import MCPConfigDiscovery
    except ImportError:
        logger.error("config_discovery module not found")
        raise HTTPException(status_code=500, detail="Server discovery not available")
    
    # Rediscover to get latest info
    config_dir = os.environ.get("MCP_CONFIG_DIR", "/mcp-configs")
    if not os.path.exists(config_dir):
        config_dir = os.path.expanduser("~")
    
    discovery = MCPConfigDiscovery(config_dir)
    discovered = discovery.discover_servers()
    
    # Find the server
    target_server = None
    for server in discovered:
        if server["name"] == server_name:
            target_server = server
            break
    
    if not target_server:
        raise HTTPException(status_code=404, detail=f"Server '{server_name}' not found in discovered servers")
    
    # Check if server is valid for activation
    validation = discovery.validate_server_config(target_server)
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail=f"Server '{server_name}' failed validation: {validation['issues']}")
    
    # Create clean server name (remove source prefixes)
    clean_name = server_name.replace("claude_", "").replace("gemini_", "").replace("test_", "")
    
    # Prepare server config for activation
    server_config = ServerConfig(
        name=clean_name,
        type=target_server["type"],
        command=target_server["command"],
        description=target_server.get("description", f"Activated {clean_name} server")
    )
    
    # Add to active servers
    servers[clean_name] = server_config.dict()
    
    return {
        "message": f"Server '{clean_name}' activated successfully",
        "original_name": server_name,
        "activated_name": clean_name,
        "server_config": server_config.dict(),
        "validation": validation
    }


@router.post("/test-discovered/{server_name}")
async def test_discovered_server(server_name: str):
    """Test a discovered server without activating it permanently"""
    try:
        from config_discovery import MCPConfigDiscovery
    except ImportError:
        logger.error("config_discovery module not found")
        raise HTTPException(status_code=500, detail="Server discovery not available")
    
    # Rediscover to get latest info
    config_dir = os.environ.get("MCP_CONFIG_DIR", "/mcp-configs")
    if not os.path.exists(config_dir):
        config_dir = os.path.expanduser("~")
    
    discovery = MCPConfigDiscovery(config_dir)
    discovered = discovery.discover_servers()
    
    # Find the server
    target_server = None
    for server in discovered:
        if server["name"] == server_name:
            target_server = server
            break
    
    if not target_server:
        raise HTTPException(status_code=404, detail=f"Server '{server_name}' not found")
    
    # For now, just return server info and validation
    # TODO: Implement actual MCP communication test
    validation = discovery.validate_server_config(target_server)
    capabilities = discovery.get_server_capabilities(target_server)
    
    test_result = {
        "server_name": server_name,
        "command": target_server["command"],
        "type": target_server["type"],
        "validation": validation,
        "capabilities": capabilities,
        "test_status": "validation_only",  # Will add real testing later
        "notes": "This endpoint currently performs validation checks. Full MCP communication testing coming soon."
    }
    
    if target_server["type"] == "stdio":
        test_result["execution_notes"] = f"Would execute: {' '.join(target_server['command'])}"
    elif target_server["type"] == "http":
        test_result["execution_notes"] = f"Would connect to: {target_server.get('url', 'No URL specified')}"
    
    return test_result