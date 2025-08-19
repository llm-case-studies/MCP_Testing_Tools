"""
Main SessionManager for MCP Testing Suite
Orchestrates all session management components
Phase 3 Refactoring: Clean, focused session management
"""

import logging
from typing import Dict, List, Any

from .models import ManagedSession, SessionConfig
from .docker_manager import DockerManager
from .lifecycle import SessionLifecycleManager
from .port_allocator import PortAllocator
from .validator import SessionValidator

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages Docker-based testing sessions
    Phase 3 Refactored: Clean separation of concerns
    """
    
    def __init__(self, max_concurrent_sessions: int = 5,
                 network_name: str = "mcp-launcher-net",
                 backend_image: str = "mcp-testing-backend",
                 port_range_start: int = 8095,
                 port_range_end: int = 8199):
        """
        Initialize the session manager with all components
        
        Args:
            max_concurrent_sessions: Maximum number of concurrent sessions
            network_name: Docker network name for session isolation  
            backend_image: Docker image for testing backend
            port_range_start: Start of port allocation range
            port_range_end: End of port allocation range
        """
        self.sessions: Dict[str, ManagedSession] = {}
        self.max_concurrent_sessions = max_concurrent_sessions
        
        # Initialize components
        self.port_allocator = PortAllocator(port_range_start, port_range_end)
        self.docker_manager = DockerManager(network_name, backend_image)
        self.lifecycle_manager = SessionLifecycleManager(
            self.docker_manager, 
            self.port_allocator
        )
        
        logger.info(f"✅ SessionManager initialized (max_concurrent={max_concurrent_sessions})")
    
    async def launch_session(self, config) -> ManagedSession:
        """
        Launch a new testing session with Docker backend
        
        Args:
            config: Session configuration (dict or SessionConfig object)
            
        Returns:
            ManagedSession: The created and started session
        """
        # Convert dict to SessionConfig if needed
        if isinstance(config, dict):
            session_config = SessionConfig(
                project_path=config['project_path'],
                config_source=config['config_source'], 
                config_type=config['config_type']
            )
        else:
            session_config = config
        
        return await self.lifecycle_manager.start_session(
            session_config, 
            self.sessions, 
            self.max_concurrent_sessions
        )
    
    async def stop_session(self, session_id: str):
        """Stop a testing session"""
        await self.lifecycle_manager.stop_session(session_id, self.sessions)
    
    async def remove_session(self, session_id: str):
        """Remove session from tracking"""
        await self.lifecycle_manager.remove_session(session_id, self.sessions)
    
    async def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions"""
        return self.lifecycle_manager.list_sessions(self.sessions)
    
    async def get_session(self, session_id: str) -> ManagedSession:
        """Get a specific session"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        return self.sessions[session_id]
    
    async def health_check_session(self, session_id: str) -> bool:
        """Perform health check on a session"""
        session = await self.get_session(session_id)
        return await self.lifecycle_manager.health_check_session(session)
    
    async def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Clean up old stopped sessions"""
        await self.lifecycle_manager.cleanup_old_sessions(self.sessions, max_age_hours)
    
    async def get_session_logs(self, session_id: str, lines: int = 50) -> str:
        """Get logs from a session's container"""
        session = await self.get_session(session_id)
        if not session.container_id:
            return "No container ID available for this session"
        
        return await self.docker_manager.get_container_logs(session.container_id, lines)
    
    async def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics about current sessions"""
        total_sessions = len(self.sessions)
        status_counts = {}
        
        for session in self.sessions.values():
            status_counts[session.status] = status_counts.get(session.status, 0) + 1
        
        return {
            "total_sessions": total_sessions,
            "max_concurrent": self.max_concurrent_sessions,
            "status_breakdown": status_counts,
            "available_slots": self.max_concurrent_sessions - status_counts.get("running", 0),
            "port_allocator_stats": {
                "allocated_ports": len(self.port_allocator.allocated_ports),
                "port_range": f"{self.port_allocator.start_port}-{self.port_allocator.end_port}"
            }
        }
    
    # Legacy compatibility methods (maintain API compatibility)
    async def _validate_paths(self, project_path: str, config_source: str) -> bool:
        """Legacy compatibility: validate paths"""
        return await SessionValidator.validate_paths(project_path, config_source)
    
    async def _health_check_session(self, session: ManagedSession) -> bool:
        """Legacy compatibility: health check"""
        return await self.lifecycle_manager.health_check_session(session)
    
    async def _ensure_network(self):
        """Legacy compatibility: ensure Docker network"""
        await self.docker_manager.ensure_network()