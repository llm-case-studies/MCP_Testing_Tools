#!/usr/bin/env python3
"""
Session Manager - Handle Docker container lifecycle for testing sessions
"""

import os
import subprocess
import logging
import uuid
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class ManagedSession:
    session_id: str
    project_path: str
    config_source: str
    config_type: str
    status: str  # "starting", "running", "stopping", "stopped", "error"
    backend_url: Optional[str] = None
    container_id: Optional[str] = None
    created_at: datetime = None
    last_activity: datetime = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.last_activity is None:
            self.last_activity = datetime.now()

class SessionManager:
    """Manages Docker-based testing sessions"""
    
    def __init__(self, max_concurrent_sessions: int = 5):
        self.sessions: Dict[str, ManagedSession] = {}
        self.port_allocator = PortAllocator(8095, 8199)  # Range for backend ports
        self.backend_image = "mcp-testing-backend"  # Will be built later
        self.network_name = "mcp-launcher-net"
        self._network_initialized = False
        self.max_concurrent_sessions = max_concurrent_sessions
    
    async def _ensure_network(self):
        """Ensure Docker network exists for session isolation"""
        try:
            # Check if network exists
            result = subprocess.run(
                ["docker", "network", "inspect", self.network_name],
                capture_output=True, text=True
            )
            
            if result.returncode != 0:
                # Create network
                logger.info(f"Creating Docker network: {self.network_name}")
                subprocess.run(
                    ["docker", "network", "create", self.network_name],
                    check=True
                )
        except Exception as e:
            logger.error(f"Error ensuring network: {e}")
    
    async def launch_session(self, config) -> ManagedSession:
        """Launch a new testing session with Docker backend"""
        # Check session limits
        active_sessions = [s for s in self.sessions.values() if s.status in ["starting", "running"]]
        if len(active_sessions) >= self.max_concurrent_sessions:
            raise ValueError(f"Maximum concurrent sessions ({self.max_concurrent_sessions}) reached. Please stop some sessions before starting new ones.")
        
        # Ensure network is initialized
        if not self._network_initialized:
            await self._ensure_network()
            self._network_initialized = True
        
        session_id = str(uuid.uuid4())[:8]
        
        # Validate paths
        if not await self._validate_paths(config.project_path, config.config_source):
            raise ValueError("Invalid project or config paths")
        
        # Allocate ports
        port_range = await self.port_allocator.allocate_range(2)
        web_port, api_port = port_range
        backend_url = f"http://localhost:{web_port}"
        
        # Create session
        session = ManagedSession(
            session_id=session_id,
            project_path=config.project_path,
            config_source=config.config_source,
            config_type=config.config_type,
            status="starting",
            backend_url=backend_url
        )
        
        self.sessions[session_id] = session
        
        # Launch container in background
        asyncio.create_task(self._launch_container(session, web_port, api_port))
        
        return session
    
    async def _launch_container(self, session: ManagedSession, web_port: int, api_port: int):
        """Launch Docker container for testing backend"""
        try:
            # Prepare Docker command
            container_name = f"mcp-backend-{session.session_id}"
            
            # Resolve absolute paths
            project_path = Path(session.project_path).resolve()
            config_path = Path(session.config_source).resolve()
            
            # Create logs directory for this session
            logs_dir = Path("./session-logs") / session.session_id
            logs_dir.mkdir(parents=True, exist_ok=True)
            
            docker_cmd = [
                "docker", "run", "-d",
                "--name", container_name,
                "--network", self.network_name,
                "-p", f"{web_port}:{web_port}",
                "-p", f"{api_port}:{api_port}",
                "-v", f"{project_path}:/workspace:rw",
                "-v", f"{logs_dir}:/app/logs:rw",
                "-e", f"WEB_PORT={web_port}",
                "-e", f"API_PORT={api_port}",
                "-e", f"SESSION_ID={session.session_id}",
                "-e", f"CONFIG_TYPE={session.config_type}",
                "--rm"  # Auto-remove when stopped
            ]
            
            # Add config mount based on type
            if session.config_type == "project":
                docker_cmd.extend(["-v", f"{config_path}:/mcp-configs/project.json:ro"])
            elif session.config_type == "user":
                if config_path.name == ".claude.json":
                    docker_cmd.extend(["-v", f"{config_path}:/mcp-configs/.claude.json:ro"])
                elif "gemini" in str(config_path):
                    docker_cmd.extend(["-v", f"{config_path.parent}:/mcp-configs/.gemini:ro"])
            elif session.config_type == "custom":
                docker_cmd.extend(["-v", f"{config_path}:/mcp-configs/custom.json:ro"])
            
            # For now, use the existing web_interface.py as backend
            # TODO: Create dedicated backend image
            docker_cmd.extend([
                "mcp_testing_tools-mcp-debug-wizard",  # Use existing image
                "python", "/app/web_interface.py"
            ])
            
            logger.info(f"Launching container for session {session.session_id}")
            logger.debug(f"Docker command: {' '.join(docker_cmd)}")
            
            # Execute Docker command
            result = subprocess.run(docker_cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                session.container_id = result.stdout.strip()
                session.status = "running"
                session.last_activity = datetime.now()
                logger.info(f"Session {session.session_id} started successfully")
                
                # Wait a moment for container to start
                await asyncio.sleep(2)
                
                # Health check
                await self._health_check_session(session)
                
            else:
                session.status = "error"
                session.error_message = result.stderr
                logger.error(f"Failed to start session {session.session_id}: {result.stderr}")
                
        except Exception as e:
            session.status = "error"
            session.error_message = str(e)
            logger.error(f"Error launching container for session {session.session_id}: {e}")
    
    async def _health_check_session(self, session: ManagedSession):
        """Check if session backend is responding"""
        try:
            # Simple health check - try to connect to backend
            import aiohttp
            async with aiohttp.ClientSession() as client:
                async with client.get(f"{session.backend_url}/api/health", timeout=5) as response:
                    if response.status == 200:
                        logger.info(f"Session {session.session_id} health check passed")
                        return True
        except Exception as e:
            logger.warning(f"Health check failed for session {session.session_id}: {e}")
        
        return False
    
    async def stop_session(self, session_id: str):
        """Stop a testing session"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        session.status = "stopping"
        
        try:
            if session.container_id:
                # Stop Docker container
                result = subprocess.run(
                    ["docker", "stop", session.container_id],
                    capture_output=True, text=True
                )
                
                if result.returncode == 0:
                    logger.info(f"Session {session_id} stopped successfully")
                else:
                    logger.warning(f"Error stopping container: {result.stderr}")
            
            session.status = "stopped"
            session.last_activity = datetime.now()
            
            # Release ports
            if session.backend_url:
                port = int(session.backend_url.split(':')[-1])
                await self.port_allocator.release_port(port)
                await self.port_allocator.release_port(port + 1)
            
        except Exception as e:
            session.status = "error"
            session.error_message = str(e)
            logger.error(f"Error stopping session {session_id}: {e}")
            raise
    
    async def remove_session(self, session_id: str):
        """Remove session from tracking"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        
        # Stop if still running
        if session.status in ["running", "starting"]:
            await self.stop_session(session_id)
        
        # Remove from tracking
        del self.sessions[session_id]
        logger.info(f"Session {session_id} removed")
    
    async def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions"""
        sessions_list = []
        for session in self.sessions.values():
            session_dict = asdict(session)
            # Convert datetime objects to strings
            session_dict["created_at"] = session.created_at.isoformat()
            session_dict["last_activity"] = session.last_activity.isoformat()
            sessions_list.append(session_dict)
        
        return sessions_list
    
    async def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Clean up old stopped sessions"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        sessions_to_remove = []
        for session_id, session in self.sessions.items():
            if (session.status == "stopped" and 
                session.last_activity < cutoff_time):
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            await self.remove_session(session_id)
            logger.info(f"Cleaned up old session: {session_id}")
    
    async def _validate_paths(self, project_path: str, config_source: str) -> bool:
        """Validate project and config paths"""
        try:
            # Validate project path
            project_path_obj = Path(project_path).resolve()
            if not project_path_obj.exists() or not project_path_obj.is_dir():
                logger.error(f"Invalid project path: {project_path}")
                return False
            
            # Validate config source
            config_path_obj = Path(config_source).resolve()
            if not config_path_obj.exists():
                logger.error(f"Invalid config source: {config_source}")
                return False
            
            # Security: prevent path traversal
            if '..' in str(project_path_obj) or '..' in str(config_path_obj):
                logger.error("Path traversal attempt detected")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating paths: {e}")
            return False

class PortAllocator:
    """Manages port allocation for testing sessions"""
    
    def __init__(self, start_port: int, end_port: int):
        self.start_port = start_port
        self.end_port = end_port
        self.allocated_ports = set()
        self.next_port = start_port
    
    async def allocate_port(self) -> int:
        """Allocate a single port"""
        while self.next_port <= self.end_port:
            port = self.next_port
            self.next_port += 1
            
            if port not in self.allocated_ports and await self._is_port_available(port):
                self.allocated_ports.add(port)
                return port
        
        raise RuntimeError("No available ports in range")
    
    async def allocate_range(self, count: int) -> List[int]:
        """Allocate a range of consecutive ports"""
        ports = []
        for _ in range(count):
            port = await self.allocate_port()
            ports.append(port)
        return ports
    
    async def release_port(self, port: int):
        """Release a port back to the pool"""
        self.allocated_ports.discard(port)
    
    async def _is_port_available(self, port: int) -> bool:
        """Check if port is available"""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(('localhost', port))
                return True
        except OSError:
            return False