"""
Session lifecycle management for MCP Testing Suite
Handles session start, stop, cleanup operations
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any
from dataclasses import asdict

from .models import ManagedSession, SessionConfig
from .docker_manager import DockerManager
from .validator import SessionValidator
from .port_allocator import PortAllocator

logger = logging.getLogger(__name__)


class SessionLifecycleManager:
    """Manages the complete lifecycle of testing sessions"""
    
    def __init__(self, docker_manager: DockerManager, port_allocator: PortAllocator):
        self.docker_manager = docker_manager
        self.port_allocator = port_allocator
    
    async def start_session(self, config: SessionConfig, sessions: Dict[str, ManagedSession], 
                           max_concurrent: int) -> ManagedSession:
        """
        Start a new testing session
        
        Args:
            config: Session configuration
            sessions: Current sessions dictionary (will be modified)
            max_concurrent: Maximum concurrent sessions allowed
            
        Returns:
            ManagedSession: The created session
        """
        # Validate session limits
        active_sessions = [s for s in sessions.values() if s.status in ["starting", "running"]]
        if not await SessionValidator.validate_session_limits(len(active_sessions), max_concurrent):
            raise ValueError(f"Maximum concurrent sessions ({max_concurrent}) reached. Please stop some sessions before starting new ones.")
        
        # Validate configuration
        if not SessionValidator.validate_session_config(config):
            raise ValueError("Invalid session configuration")
        
        # Validate paths
        if not await SessionValidator.validate_paths(config.project_path, config.config_source):
            raise ValueError("Invalid project or config paths")
        
        # Create session
        session_id = str(uuid.uuid4())[:8]
        session = ManagedSession(
            session_id=session_id,
            project_path=config.project_path,
            config_source=config.config_source,
            config_type=config.config_type,
            status="starting"
        )
        
        sessions[session_id] = session
        logger.info(f"🚀 Starting session {session_id}")
        
        try:
            # Allocate ports
            web_port, api_port = await self.port_allocator.allocate_range(2)
            logger.debug(f"Allocated ports: web={web_port}, api={api_port}")
            
            # Set backend URL
            session.backend_url = f"http://localhost:{web_port}"
            
            # Launch container
            container_id = await self.docker_manager.launch_container(session, web_port, api_port)
            session.container_id = container_id
            
            # Wait a moment for container to initialize
            import asyncio
            await asyncio.sleep(2)
            
            # Update session status
            session.status = "running"
            session.last_activity = datetime.now()
            
            logger.info(f"✅ Session {session_id} started successfully")
            return session
            
        except Exception as e:
            session.status = "error"
            session.error_message = str(e)
            logger.error(f"❌ Failed to start session {session_id}: {e}")
            
            # Clean up on failure
            try:
                if hasattr(session, 'container_id') and session.container_id:
                    await self.docker_manager.stop_container(session.container_id)
                await self.port_allocator.release_port(web_port)
                await self.port_allocator.release_port(api_port)
            except:
                pass  # Best effort cleanup
            
            raise
    
    async def stop_session(self, session_id: str, sessions: Dict[str, ManagedSession]):
        """Stop a testing session"""
        if session_id not in sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = sessions[session_id]
        session.status = "stopping"
        
        logger.info(f"🛑 Stopping session {session_id}")
        
        try:
            # Stop Docker container
            if session.container_id:
                await self.docker_manager.stop_container(session.container_id)
            
            # Release ports (extract from backend_url or track separately)
            # TODO: Improve port tracking in future iterations
            
            session.status = "stopped"
            session.last_activity = datetime.now()
            
            logger.info(f"✅ Session {session_id} stopped successfully")
            
        except Exception as e:
            session.status = "error"
            session.error_message = f"Error stopping session: {e}"
            logger.error(f"❌ Error stopping session {session_id}: {e}")
            raise
    
    async def remove_session(self, session_id: str, sessions: Dict[str, ManagedSession]):
        """Remove session from tracking"""
        if session_id not in sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = sessions[session_id]
        
        logger.info(f"🗑️ Removing session {session_id}")
        
        # Stop if still running
        if session.status in ["running", "starting"]:
            await self.stop_session(session_id, sessions)
        
        # Remove from tracking
        del sessions[session_id]
        logger.info(f"✅ Session {session_id} removed")
    
    async def health_check_session(self, session: ManagedSession) -> bool:
        """Perform health check on a session"""
        return await SessionValidator.health_check_session(session)
    
    async def cleanup_old_sessions(self, sessions: Dict[str, ManagedSession], max_age_hours: int = 24):
        """Clean up old stopped sessions"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        sessions_to_remove = []
        for session_id, session in sessions.items():
            if (session.status == "stopped" and 
                session.last_activity < cutoff_time):
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            try:
                await self.remove_session(session_id, sessions)
                logger.info(f"🧹 Cleaned up old session: {session_id}")
            except Exception as e:
                logger.error(f"Error cleaning up session {session_id}: {e}")
    
    @staticmethod
    def list_sessions(sessions: Dict[str, ManagedSession]) -> List[Dict[str, Any]]:
        """List all sessions with serialized data"""
        sessions_list = []
        for session in sessions.values():
            session_dict = asdict(session)
            # Convert datetime objects to strings for JSON serialization
            if session.created_at:
                session_dict["created_at"] = session.created_at.isoformat()
            if session.last_activity:
                session_dict["last_activity"] = session.last_activity.isoformat()
            sessions_list.append(session_dict)
        
        return sessions_list