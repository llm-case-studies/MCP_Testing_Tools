#!/usr/bin/env python3
"""
MCP Configuration Discovery
Discovers MCP servers from mounted configuration files
"""

import json
import os
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class MCPConfigDiscovery:
    def __init__(self, config_dir: str = "/mcp-configs"):
        self.config_dir = Path(config_dir)
        
    def discover_servers(self) -> List[Dict[str, Any]]:
        """Discover MCP servers from all available configuration files"""
        discovered = []
        
        # Discover from Claude configuration
        claude_servers = self._discover_claude_servers()
        discovered.extend(claude_servers)
        
        # Discover from Gemini configuration
        gemini_servers = self._discover_gemini_servers()
        discovered.extend(gemini_servers)
        
        # Add built-in test servers
        discovered.extend(self._get_builtin_servers())
        
        logger.info(f"Discovered {len(discovered)} MCP servers")
        return discovered
        
    def _discover_claude_servers(self) -> List[Dict[str, Any]]:
        """Discover servers from Claude configuration"""
        servers = []
        claude_config_path = self.config_dir / ".claude.json"
        
        if not claude_config_path.exists():
            logger.debug("Claude config not found at %s", claude_config_path)
            return servers
            
        try:
            with open(claude_config_path, 'r') as f:
                claude_config = json.load(f)
                
            mcp_servers = claude_config.get("mcpServers", {})
            
            for server_name, config in mcp_servers.items():
                command = config.get("command")
                args = config.get("args", [])
                env = config.get("env", {})
                
                if command:
                    # Build full command with arguments
                    full_command = [command] + args
                    
                    servers.append({
                        "name": f"claude_{server_name}",
                        "type": "stdio",
                        "source": "claude",
                        "command": full_command,
                        "env": env,
                        "description": f"Claude MCP Server: {server_name}",
                        "original_config": config
                    })
                    
            logger.info(f"Found {len(servers)} servers in Claude config")
            
        except Exception as e:
            logger.error(f"Error reading Claude config: {e}")
            
        return servers
        
    def _discover_gemini_servers(self) -> List[Dict[str, Any]]:
        """Discover servers from Gemini configuration"""
        servers = []
        gemini_config_dir = self.config_dir / ".gemini"
        
        # Check for various Gemini config files
        config_files = [
            gemini_config_dir / "mcp.json",
            gemini_config_dir / "config.json",
            gemini_config_dir / "servers.json"
        ]
        
        for config_path in config_files:
            if not config_path.exists():
                continue
                
            try:
                with open(config_path, 'r') as f:
                    gemini_config = json.load(f)
                    
                # Handle different Gemini config formats
                mcp_servers = (
                    gemini_config.get("mcpServers", {}) or
                    gemini_config.get("servers", {}) or
                    gemini_config
                )
                
                for server_name, config in mcp_servers.items():
                    command = config.get("command")
                    args = config.get("args", [])
                    env = config.get("env", {})
                    
                    if command:
                        full_command = [command] + args
                        
                        servers.append({
                            "name": f"gemini_{server_name}",
                            "type": "stdio",
                            "source": "gemini",
                            "command": full_command,
                            "env": env,
                            "description": f"Gemini MCP Server: {server_name}",
                            "original_config": config
                        })
                        
                logger.info(f"Found {len(servers)} servers in {config_path.name}")
                break  # Use first found config file
                
            except Exception as e:
                logger.error(f"Error reading Gemini config {config_path}: {e}")
                
        return servers
        
    def _get_builtin_servers(self) -> List[Dict[str, Any]]:
        """Get built-in test servers"""
        return [
            {
                "name": "mock_server",
                "type": "http",
                "source": "builtin",
                "url": "http://localhost:8001",
                "description": "Built-in HTTP Mock Server",
                "endpoints": {
                    "mcp": "/mcp",
                    "debug": "/debug/logs",
                    "tools": "/debug/tools"
                }
            },
            {
                "name": "proxy_server",
                "type": "proxy",
                "source": "builtin", 
                "url": "http://localhost:8002",
                "description": "Built-in MCP Proxy Server",
                "endpoints": {
                    "start": "/proxy/start",
                    "send": "/proxy/send",
                    "logs": "/proxy/logs"
                }
            },
            {
                "name": "test_qdrant",
                "type": "stdio",
                "source": "test",
                "command": ["uvx", "mcp-server-qdrant"],
                "env": {
                    "QDRANT_URL": "http://localhost:6333",
                    "COLLECTION_NAME": "test_collection",
                    "EMBEDDING_MODEL": "all-MiniLM-L6-v2"
                },
                "description": "Test Qdrant MCP Server"
            },
            {
                "name": "test_filesystem",
                "type": "stdio", 
                "source": "test",
                "command": ["uvx", "mcp-server-filesystem", "/workspace"],
                "description": "Test Filesystem MCP Server"
            }
        ]
        
    def validate_server_config(self, server: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize server configuration"""
        result = {
            "valid": True,
            "issues": [],
            "warnings": []
        }
        
        # Check required fields
        if not server.get("name"):
            result["valid"] = False
            result["issues"].append("Server name is required")
            
        if not server.get("type"):
            result["valid"] = False
            result["issues"].append("Server type is required")
            
        # Validate by type
        if server.get("type") == "stdio":
            if not server.get("command"):
                result["valid"] = False
                result["issues"].append("stdio servers require a command")
            else:
                # Check if command executable exists
                command = server["command"][0] if isinstance(server["command"], list) else server["command"]
                if not self._check_command_available(command):
                    result["warnings"].append(f"Command '{command}' may not be available")
                    
        elif server.get("type") in ["http", "proxy"]:
            if not server.get("url"):
                result["valid"] = False
                result["issues"].append(f"{server['type']} servers require a URL")
                
        return result
        
    def _check_command_available(self, command: str) -> bool:
        """Check if a command is available in the container"""
        import shutil
        return shutil.which(command) is not None
        
    def get_server_capabilities(self, server: Dict[str, Any]) -> Dict[str, Any]:
        """Get expected capabilities for a server based on its configuration"""
        capabilities = {
            "tools": True,
            "resources": False,
            "logging": False
        }
        
        server_name = server.get("name", "").lower()
        
        # Infer capabilities from server name/type
        if "qdrant" in server_name or "memory" in server_name:
            capabilities["resources"] = True
            
        if "filesystem" in server_name or "file" in server_name:
            capabilities["resources"] = True
            
        if "brave" in server_name or "search" in server_name:
            capabilities["tools"] = True
            
        return capabilities

# Example usage and testing
if __name__ == "__main__":
    import sys
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Allow override of config directory for testing
    config_dir = sys.argv[1] if len(sys.argv) > 1 else "/mcp-configs"
    
    discovery = MCPConfigDiscovery(config_dir)
    servers = discovery.discover_servers()
    
    print(f"\nDiscovered {len(servers)} MCP servers:")
    for server in servers:
        print(f"\n- {server['name']} ({server['type']})")
        print(f"  Source: {server['source']}")
        print(f"  Description: {server['description']}")
        
        if server['type'] == 'stdio':
            print(f"  Command: {' '.join(server['command'])}")
            if server.get('env'):
                print(f"  Environment: {server['env']}")
        elif server['type'] in ['http', 'proxy']:
            print(f"  URL: {server['url']}")
            
        # Validate configuration
        validation = discovery.validate_server_config(server)
        if not validation["valid"]:
            print(f"  ⚠️  Issues: {', '.join(validation['issues'])}")
        if validation["warnings"]:
            print(f"  ⚠️  Warnings: {', '.join(validation['warnings'])}")
            
        capabilities = discovery.get_server_capabilities(server)
        caps = [k for k, v in capabilities.items() if v]
        print(f"  Capabilities: {', '.join(caps)}")