"""
Validation and health checking for MCP Testing Suite sessions
"""

import logging
from pathlib import Path
from typing import Optional
from .models import ManagedSession

logger = logging.getLogger(__name__)


class SessionValidator:
    """Handles path validation and session health checks"""
    
    @staticmethod
    async def validate_paths(project_path: str, config_source: str) -> bool:
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
            
            logger.debug(f"✅ Paths validated: {project_path} | {config_source}")
            return True
            
        except Exception as e:
            logger.error(f"Error validating paths: {e}")
            return False
    
    @staticmethod
    async def health_check_session(session: ManagedSession) -> bool:
        """Check if session backend is responding"""
        try:
            if not session.backend_url:
                logger.warning(f"No backend URL for session {session.session_id}")
                return False
            
            # Simple health check - try to connect to backend
            import aiohttp
            async with aiohttp.ClientSession() as client:
                async with client.get(
                    f"{session.backend_url}/api/health", 
                    timeout=5
                ) as response:
                    if response.status == 200:
                        logger.debug(f"✅ Session {session.session_id} health check passed")
                        return True
                    else:
                        logger.warning(f"Session {session.session_id} health check failed: HTTP {response.status}")
                        return False
                        
        except Exception as e:
            logger.warning(f"Health check failed for session {session.session_id}: {e}")
            return False
    
    @staticmethod
    async def validate_session_limits(active_sessions: int, max_concurrent: int) -> bool:
        """Validate session limits before creating new session"""
        if active_sessions >= max_concurrent:
            logger.error(f"Session limit reached: {active_sessions}/{max_concurrent}")
            return False
        
        logger.debug(f"✅ Session limit check passed: {active_sessions}/{max_concurrent}")
        return True
    
    @staticmethod
    def validate_session_config(config) -> bool:
        """Validate session configuration object"""
        try:
            required_fields = ['project_path', 'config_source', 'config_type']
            for field in required_fields:
                if not hasattr(config, field) or not getattr(config, field):
                    logger.error(f"Missing required config field: {field}")
                    return False
            
            # Validate config type
            valid_types = ['project', 'user', 'custom']
            if config.config_type not in valid_types:
                logger.error(f"Invalid config type: {config.config_type}. Must be one of {valid_types}")
                return False
            
            logger.debug(f"✅ Session config validated: {config.config_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error validating session config: {e}")
            return False