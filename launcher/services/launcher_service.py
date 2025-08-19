"""
Launcher Service - Business logic layer for MCP Testing Suite
Coordinates between API endpoints and core components
"""

import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

try:
    from ..session import SessionManager, SessionConfig
    from ..project_scanner import ProjectScanner
except ImportError:
    from session import SessionManager, SessionConfig
    from project_scanner import ProjectScanner

logger = logging.getLogger(__name__)


class LauncherService:
    """
    Service layer that coordinates business logic for the MCP Testing Suite
    Provides clean abstraction between API endpoints and core components
    """
    
    def __init__(self, session_manager: SessionManager, project_scanner: ProjectScanner):
        self.session_manager = session_manager
        self.project_scanner = project_scanner
        logger.info("✅ LauncherService initialized")
    
    # Session Management Services
    
    async def launch_session(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Launch a new testing session with comprehensive validation and error handling
        
        Args:
            config_data: Raw configuration data from API request
            
        Returns:
            Dict containing session information and status
            
        Raises:
            ValueError: If configuration is invalid
            RuntimeError: If session launch fails
        """
        try:
            # Validate configuration
            self._validate_launch_config(config_data)
            
            # Create session config
            session_config = SessionConfig(
                project_path=config_data['project_path'],
                config_source=config_data['config_source'],
                config_type=config_data['config_type']
            )
            
            # Launch session
            session = await self.session_manager.launch_session(session_config)
            
            logger.info(f"✅ Session {session.session_id} launched successfully")
            
            return {
                "session_id": session.session_id,
                "backend_url": session.backend_url,
                "status": session.status,
                "message": "Testing backend launched successfully",
                "project_path": session.project_path,
                "config_type": session.config_type
            }
            
        except ValueError as e:
            logger.error(f"❌ Invalid configuration: {e}")
            raise ValueError(f"Invalid configuration: {e}")
        except Exception as e:
            logger.error(f"❌ Failed to launch session: {e}")
            raise RuntimeError(f"Failed to launch session: {e}")
    
    async def stop_session(self, session_id: str) -> Dict[str, str]:
        """
        Stop a testing session with proper cleanup
        
        Args:
            session_id: ID of session to stop
            
        Returns:
            Dict with success message
            
        Raises:
            ValueError: If session not found
            RuntimeError: If stop operation fails
        """
        try:
            await self.session_manager.stop_session(session_id)
            logger.info(f"✅ Session {session_id} stopped successfully")
            
            return {"message": f"Session {session_id} stopped successfully"}
            
        except ValueError as e:
            logger.error(f"❌ Session not found: {e}")
            raise ValueError(str(e))
        except Exception as e:
            logger.error(f"❌ Failed to stop session {session_id}: {e}")
            raise RuntimeError(f"Failed to stop session: {e}")
    
    async def remove_session(self, session_id: str) -> Dict[str, str]:
        """
        Remove a session from tracking
        
        Args:
            session_id: ID of session to remove
            
        Returns:
            Dict with success message
        """
        try:
            await self.session_manager.remove_session(session_id)
            logger.info(f"✅ Session {session_id} removed successfully")
            
            return {"message": f"Session {session_id} removed"}
            
        except ValueError as e:
            logger.error(f"❌ Session not found: {e}")
            raise ValueError(str(e))
        except Exception as e:
            logger.error(f"❌ Failed to remove session {session_id}: {e}")
            raise RuntimeError(f"Failed to remove session: {e}")
    
    async def list_sessions(self) -> Dict[str, Any]:
        """
        List all sessions with additional metadata
        
        Returns:
            Dict containing sessions list and summary statistics
        """
        try:
            sessions = await self.session_manager.list_sessions()
            stats = await self.session_manager.get_session_stats()
            
            return {
                "sessions": sessions,
                "total_sessions": stats["total_sessions"],
                "status_breakdown": stats["status_breakdown"],
                "available_slots": stats["available_slots"]
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to list sessions: {e}")
            raise RuntimeError(f"Failed to list sessions: {e}")
    
    async def get_session_details(self, session_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific session
        
        Args:
            session_id: ID of session to get details for
            
        Returns:
            Dict with detailed session information
        """
        try:
            session = await self.session_manager.get_session(session_id)
            
            # Perform health check
            health_status = await self.session_manager.health_check_session(session_id)
            
            return {
                "session_id": session.session_id,
                "project_path": session.project_path,
                "config_source": session.config_source,
                "config_type": session.config_type,
                "status": session.status,
                "backend_url": session.backend_url,
                "container_id": session.container_id,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "last_activity": session.last_activity.isoformat() if session.last_activity else None,
                "error_message": session.error_message,
                "health_status": "healthy" if health_status else "unhealthy"
            }
            
        except ValueError as e:
            logger.error(f"❌ Session not found: {e}")
            raise ValueError(str(e))
        except Exception as e:
            logger.error(f"❌ Failed to get session details: {e}")
            raise RuntimeError(f"Failed to get session details: {e}")
    
    # Project Management Services
    
    async def browse_folders(self, path: str = ".") -> Dict[str, Any]:
        """
        Browse directories for project selection with enhanced metadata
        
        Args:
            path: Directory path to browse
            
        Returns:
            Dict containing folder information and metadata
        """
        try:
            base_path = Path(path).resolve()
            
            if not base_path.exists() or not base_path.is_dir():
                raise ValueError("Invalid directory path")
            
            folders = []
            
            # Add parent directory option (unless at root)
            if base_path.parent != base_path:
                folders.append({
                    "name": "..",
                    "path": str(base_path.parent),
                    "type": "parent"
                })
            
            # List subdirectories with enhanced metadata
            try:
                for item in sorted(base_path.iterdir()):
                    if item.is_dir() and not item.name.startswith('.'):
                        # Check if it looks like a project directory
                        has_mcp_config = any(
                            (item / config).exists() 
                            for config in [".mcp.json", "mcp.json", ".claude.json", "package.json"]
                        )
                        
                        # Additional project indicators
                        has_git = (item / ".git").exists()
                        has_node_modules = (item / "node_modules").exists()
                        has_python = any((item / f).exists() for f in ["requirements.txt", "pyproject.toml", "setup.py"])
                        
                        folders.append({
                            "name": item.name,
                            "path": str(item),
                            "type": "project" if has_mcp_config else "folder",
                            "has_mcp_config": has_mcp_config,
                            "has_git": has_git,
                            "has_node_modules": has_node_modules,
                            "has_python": has_python,
                            "project_indicators": sum([has_mcp_config, has_git, has_node_modules, has_python])
                        })
            except PermissionError:
                logger.warning(f"Permission denied accessing {base_path}")
            
            return {
                "current_path": str(base_path),
                "folders": folders,
                "total_folders": len([f for f in folders if f["type"] != "parent"]),
                "project_folders": len([f for f in folders if f["type"] == "project"])
            }
            
        except ValueError as e:
            logger.error(f"❌ Invalid path: {e}")
            raise ValueError(str(e))
        except Exception as e:
            logger.error(f"❌ Error browsing folders: {e}")
            raise RuntimeError(f"Error browsing folders: {e}")
    
    async def scan_projects(self, path: str = ".") -> Dict[str, Any]:
        """
        Scan directory for projects with MCP configurations
        
        Args:
            path: Directory path to scan
            
        Returns:
            Dict containing discovered projects and metadata
        """
        try:
            projects = await self.project_scanner.scan_directory(path)
            
            # Enhance with additional metadata
            project_count_by_type = {}
            for project in projects:
                for config in project.get("config_sources", []):
                    config_type = config.get("type", "unknown")
                    project_count_by_type[config_type] = project_count_by_type.get(config_type, 0) + 1
            
            return {
                "projects": projects,
                "scanned_path": path,
                "total_projects": len(projects),
                "config_types": project_count_by_type,
                "scan_summary": f"Found {len(projects)} projects in {path}"
            }
            
        except Exception as e:
            logger.error(f"❌ Error scanning projects: {e}")
            raise RuntimeError(f"Error scanning projects: {e}")
    
    async def get_config_preview(self, config_path: str) -> Dict[str, Any]:
        """
        Get detailed preview of a configuration file with validation
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Dict containing configuration preview and validation results
        """
        try:
            preview = await self.project_scanner.get_config_preview(config_path)
            
            # Add validation information
            validation_results = self._validate_config_preview(preview)
            preview["validation"] = validation_results
            
            return preview
            
        except Exception as e:
            logger.error(f"❌ Error getting config preview: {e}")
            raise RuntimeError(f"Error getting config preview: {e}")
    
    # Health and Status Services
    
    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive health status of the launcher service
        
        Returns:
            Dict containing detailed health information
        """
        try:
            sessions = await self.session_manager.list_sessions()
            session_stats = await self.session_manager.get_session_stats()
            
            active_count = len([s for s in sessions if s["status"] in ["starting", "running"]])
            
            return {
                "status": "healthy",
                "service": "mcp-launcher",
                "version": "2.0.0",
                "timestamp": logger.handlers[0].formatter.formatTime(logger.makeRecord('', 0, '', 0, '', (), None)) if logger.handlers else None,
                "sessions": {
                    "total": len(sessions),
                    "active": active_count,
                    "available_slots": self.session_manager.max_concurrent_sessions - active_count,
                    "max_concurrent": self.session_manager.max_concurrent_sessions,
                    "status_breakdown": session_stats["status_breakdown"]
                },
                "components": {
                    "session_manager": "operational",
                    "project_scanner": "operational",
                    "port_allocator": "operational"
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting health status: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "service": "mcp-launcher",
                "version": "2.0.0"
            }
    
    # Private helper methods
    
    def _validate_launch_config(self, config_data: Dict[str, Any]) -> None:
        """Validate launch configuration data"""
        required_fields = ['project_path', 'config_source', 'config_type']
        
        for field in required_fields:
            if field not in config_data:
                raise ValueError(f"Missing required field: {field}")
            if not config_data[field]:
                raise ValueError(f"Empty value for required field: {field}")
        
        # Validate config_type
        valid_types = ['project', 'user', 'custom']
        if config_data['config_type'] not in valid_types:
            raise ValueError(f"Invalid config_type. Must be one of: {valid_types}")
        
        # Validate paths exist
        project_path = Path(config_data['project_path'])
        config_path = Path(config_data['config_source'])
        
        if not project_path.exists():
            raise ValueError(f"Project path does not exist: {config_data['project_path']}")
        
        if not config_path.exists():
            raise ValueError(f"Config source does not exist: {config_data['config_source']}")
    
    def _validate_config_preview(self, preview: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration preview and return validation results"""
        validation = {
            "is_valid": True,
            "warnings": [],
            "errors": []
        }
        
        # Check for required MCP fields
        if "mcpServers" not in preview.get("content", {}):
            validation["warnings"].append("No 'mcpServers' section found")
        
        # Check server configurations
        servers = preview.get("content", {}).get("mcpServers", {})
        if isinstance(servers, dict):
            for server_name, server_config in servers.items():
                if not isinstance(server_config, dict):
                    validation["errors"].append(f"Invalid configuration for server '{server_name}'")
                    continue
                
                if "command" not in server_config and "stdio" not in server_config:
                    validation["warnings"].append(f"Server '{server_name}' missing command/stdio configuration")
        
        if validation["errors"]:
            validation["is_valid"] = False
        
        return validation