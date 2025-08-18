#!/usr/bin/env python3
"""
Project Scanner - Discover projects with MCP configurations
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class ProjectScanner:
    """Scans directories for projects with MCP configurations"""
    
    def __init__(self):
        self.mcp_config_files = [
            ".mcp.json",
            "mcp.json", 
            "mcp-config.json",
            ".mcp/config.json",
            "configs/mcp.json"
        ]
        
        self.user_config_files = [
            ".claude.json",
            ".gemini/settings.json",
            ".gemini/config.json",
            ".gemini/mcp.json"
        ]
    
    async def scan_directory(self, base_path: str, max_depth: int = 3) -> List[Dict[str, Any]]:
        """Scan directory for projects with MCP configurations"""
        projects = []
        base_path = Path(base_path).resolve()
        
        logger.info(f"Scanning {base_path} for MCP projects (depth: {max_depth})")
        
        # Check if base path itself is a project
        project_info = await self._analyze_directory(base_path)
        if project_info:
            projects.append(project_info)
        
        # Recursively scan subdirectories
        if max_depth > 0:
            try:
                for item in base_path.iterdir():
                    if item.is_dir() and not item.name.startswith('.') and item.name != 'node_modules':
                        sub_projects = await self.scan_directory(str(item), max_depth - 1)
                        projects.extend(sub_projects)
            except PermissionError:
                logger.warning(f"Permission denied scanning {base_path}")
        
        return projects
    
    async def _analyze_directory(self, dir_path: Path) -> Optional[Dict[str, Any]]:
        """Analyze a single directory for MCP configurations"""
        config_sources = []
        
        # Look for project-level MCP configs
        for config_file in self.mcp_config_files:
            config_path = dir_path / config_file
            if config_path.exists():
                config_info = await self._analyze_config_file(config_path, "project")
                if config_info:
                    config_sources.append(config_info)
        
        # Look for user-level configs in this directory (for testing)
        for config_file in self.user_config_files:
            config_path = dir_path / config_file
            if config_path.exists():
                config_info = await self._analyze_config_file(config_path, "user")
                if config_info:
                    config_sources.append(config_info)
        
        # If no configs found, not a project
        if not config_sources:
            return None
        
        # Extract project info
        project_name = dir_path.name
        description = None
        
        # Try to get description from package.json or project configs
        package_json = dir_path / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    pkg_data = json.load(f)
                    if pkg_data.get("description"):
                        description = pkg_data["description"]
                    if pkg_data.get("name"):
                        project_name = pkg_data["name"]
            except Exception:
                pass
        
        # Try to get description from first MCP config
        if not description and config_sources:
            first_config = config_sources[0]
            if first_config.get("description"):
                description = first_config["description"]
        
        return {
            "name": project_name,
            "path": str(dir_path),
            "config_sources": config_sources,
            "description": description
        }
    
    async def _analyze_config_file(self, config_path: Path, config_type: str) -> Optional[Dict[str, Any]]:
        """Analyze a single configuration file"""
        try:
            with open(config_path) as f:
                config_data = json.load(f)
            
            # Different config file structures
            servers = {}
            description = None
            
            if config_path.name == ".claude.json" or config_path.name.endswith(".claude.json"):
                servers = config_data.get("mcpServers", {})
                description = f"Claude config with {len(servers)} servers"
            elif config_path.name.endswith(".mcp.json") or "mcp" in config_path.name.lower():
                if "mcpServers" in config_data:
                    servers = config_data["mcpServers"]
                elif "servers" in config_data:
                    servers = config_data["servers"]
                else:
                    servers = config_data
                
                description = config_data.get("description", f"MCP config with {len(servers)} servers")
            elif "gemini" in str(config_path) or config_path.name == "settings.json":
                # Handle Gemini CLI config structure (.gemini/settings.json)
                servers = config_data.get("mcpServers", {})
                description = f"Gemini config with {len(servers)} servers"
            
            if not servers:
                return None
            
            return {
                "type": config_type,
                "path": str(config_path),
                "file_name": config_path.name,
                "server_count": len(servers),
                "servers": list(servers.keys()),
                "description": description,
                "valid": True
            }
            
        except Exception as e:
            logger.warning(f"Error analyzing config {config_path}: {e}")
            return {
                "type": config_type,
                "path": str(config_path),
                "file_name": config_path.name,
                "error": str(e),
                "valid": False
            }
    
    async def validate_project_path(self, path: str) -> bool:
        """Validate that a path is safe and accessible"""
        try:
            path_obj = Path(path).resolve()
            
            # Basic security checks
            if not path_obj.exists():
                return False
            
            if not path_obj.is_dir():
                return False
            
            # Check for path traversal attempts
            if '..' in str(path_obj):
                return False
            
            # Check read permissions
            if not os.access(path_obj, os.R_OK):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating path {path}: {e}")
            return False
    
    async def get_config_preview(self, config_path: str) -> Dict[str, Any]:
        """Get a preview of a configuration file"""
        try:
            config_path_obj = Path(config_path)
            if not config_path_obj.exists():
                return {"error": "Configuration file not found"}
            
            with open(config_path_obj) as f:
                config_data = json.load(f)
            
            # Extract preview information
            preview = {
                "file_path": str(config_path_obj),
                "file_size": config_path_obj.stat().st_size,
                "servers": {},
                "summary": {}
            }
            
            # Extract server information
            servers = {}
            if "mcpServers" in config_data:
                servers = config_data["mcpServers"]
            elif "servers" in config_data:
                servers = config_data["servers"]
            
            for server_name, server_config in servers.items():
                preview["servers"][server_name] = {
                    "type": server_config.get("type", "unknown"),
                    "command": server_config.get("command", ""),
                    "description": server_config.get("description", "")
                }
            
            preview["summary"] = {
                "total_servers": len(servers),
                "stdio_servers": sum(1 for s in servers.values() if s.get("type") == "stdio"),
                "http_servers": sum(1 for s in servers.values() if s.get("type") == "http"),
            }
            
            return preview
            
        except Exception as e:
            logger.error(f"Error getting config preview for {config_path}: {e}")
            return {"error": str(e)}