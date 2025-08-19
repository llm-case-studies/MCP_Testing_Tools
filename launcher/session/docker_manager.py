"""
Docker management for MCP Testing Suite sessions
Handles Docker network and container operations
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from .models import ManagedSession

logger = logging.getLogger(__name__)


class DockerManager:
    """Manages Docker network and container operations for testing sessions"""
    
    def __init__(self, network_name: str = "mcp-launcher-net", 
                 backend_image: str = "mcp-testing-backend"):
        self.network_name = network_name
        self.backend_image = backend_image
        self._network_initialized = False
    
    async def ensure_network(self):
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
                logger.info(f"✅ Docker network created: {self.network_name}")
            
            self._network_initialized = True
            
        except Exception as e:
            logger.error(f"Error ensuring network: {e}")
            raise
    
    async def launch_container(self, session: ManagedSession, web_port: int, api_port: int) -> str:
        """
        Launch Docker container for testing backend
        
        Returns:
            str: Container ID
        """
        try:
            # Ensure network exists
            if not self._network_initialized:
                await self.ensure_network()
            
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
            
            # Add the backend image
            docker_cmd.append(self.backend_image)
            
            logger.info(f"Launching container for session {session.session_id}")
            logger.debug(f"Docker command: {' '.join(docker_cmd)}")
            
            # Launch container
            result = subprocess.run(docker_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                error_msg = f"Failed to start container: {result.stderr}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            container_id = result.stdout.strip()
            logger.info(f"✅ Container launched: {container_id[:12]}")
            
            return container_id
            
        except Exception as e:
            logger.error(f"Error launching container for session {session.session_id}: {e}")
            raise
    
    async def stop_container(self, container_id: str):
        """Stop and remove a Docker container"""
        try:
            if not container_id:
                return
            
            logger.info(f"Stopping container: {container_id[:12]}")
            
            # Stop container
            subprocess.run(
                ["docker", "stop", container_id],
                capture_output=True, text=True
            )
            
            logger.info(f"✅ Container stopped: {container_id[:12]}")
            
        except Exception as e:
            logger.error(f"Error stopping container {container_id[:12]}: {e}")
    
    async def get_container_status(self, container_id: str) -> Optional[str]:
        """Get the status of a Docker container"""
        try:
            if not container_id:
                return None
            
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Status}}", container_id],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting container status {container_id[:12]}: {e}")
            return None
    
    async def get_container_logs(self, container_id: str, lines: int = 50) -> str:
        """Get logs from a Docker container"""
        try:
            if not container_id:
                return "No container ID available"
            
            result = subprocess.run(
                ["docker", "logs", "--tail", str(lines), container_id],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                return result.stdout
            else:
                return f"Error getting logs: {result.stderr}"
                
        except Exception as e:
            logger.error(f"Error getting container logs {container_id[:12]}: {e}")
            return f"Error getting logs: {e}"