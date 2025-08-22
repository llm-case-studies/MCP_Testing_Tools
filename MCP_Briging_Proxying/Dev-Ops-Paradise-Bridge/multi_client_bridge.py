#!/usr/bin/env python3
"""
Multi-Client Smart Bridge - DevOps Paradise Edition
Solves the Serena multi-client scaling problem while providing enterprise-grade quality tools
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import uuid
import hashlib
import docker
from typing import Any, AsyncGenerator, Dict, Optional, List, Union
from dataclasses import dataclass, field

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

try:
    from .process import StdioProcess
    from .broker import Broker
except ImportError:
    from process import StdioProcess
    from broker import Broker

# ----------------------------- Logging ------------------------------------
logger = logging.getLogger("multi-client-bridge")

# ----------------------------- Port Management ----------------------------
class PortAllocator:
    """Manages port allocation for multiple clients"""
    
    def __init__(self, start_port: int = 8200, end_port: int = 8299):
        self.start_port = start_port
        self.end_port = end_port
        self.allocated_ports = set()
        self.client_ports = {}  # client_id -> {bridge_port, dashboard_port}
        
    def allocate_ports_for_client(self, client_id: str) -> Dict[str, int]:
        """Allocate bridge and dashboard ports for a client"""
        available_ports = set(range(self.start_port, self.end_port + 1)) - self.allocated_ports
        
        if len(available_ports) < 2:
            raise Exception(f"Insufficient available ports. Need 2, have {len(available_ports)}")
        
        # Use deterministic port allocation based on client_id hash
        client_hash = hashlib.sha256(client_id.encode()).hexdigest()
        base_offset = int(client_hash[:8], 16) % (self.end_port - self.start_port - 1)
        
        bridge_port = None
        dashboard_port = None
        
        # Find two consecutive available ports starting from hash-based offset
        for i in range(self.end_port - self.start_port):
            port1 = self.start_port + ((base_offset + i) % (self.end_port - self.start_port))
            port2 = port1 + 1
            
            if port1 in available_ports and port2 in available_ports:
                bridge_port = port1
                dashboard_port = port2
                break
                
        if not bridge_port or not dashboard_port:
            # Fallback to any two available ports
            available_list = sorted(available_ports)
            bridge_port = available_list[0]
            dashboard_port = available_list[1]
        
        self.allocated_ports.add(bridge_port)
        self.allocated_ports.add(dashboard_port)
        
        ports = {
            'bridge_port': bridge_port,
            'dashboard_port': dashboard_port
        }
        
        self.client_ports[client_id] = ports
        logger.info(f"Allocated ports for client {client_id}: bridge={bridge_port}, dashboard={dashboard_port}")
        
        return ports
    
    def release_ports_for_client(self, client_id: str) -> None:
        """Release ports allocated to a client"""
        if client_id in self.client_ports:
            ports = self.client_ports[client_id]
            self.allocated_ports.discard(ports['bridge_port'])
            self.allocated_ports.discard(ports['dashboard_port'])
            del self.client_ports[client_id]
            logger.info(f"Released ports for client {client_id}")
    
    def get_client_ports(self, client_id: str) -> Optional[Dict[str, int]]:
        """Get allocated ports for a client"""
        return self.client_ports.get(client_id)

# ----------------------------- Instance Management ------------------------
@dataclass
class ClientInstance:
    """Represents a client's Serena instance"""
    client_id: str
    workspace_path: str
    container: Any = None
    bridge_port: int = 0
    dashboard_port: int = 0
    health_status: str = "initializing"
    created_at: float = field(default_factory=time.time)
    last_health_check: float = field(default_factory=time.time)

class InstanceManager:
    """Manages Docker containers for client instances"""
    
    def __init__(self):
        self.docker_client = docker.from_env()
        self.instances = {}  # client_id -> ClientInstance
        
    async def create_serena_instance(self, client_id: str, workspace_path: str, ports: Dict[str, int]) -> ClientInstance:
        """Create a dedicated Serena container for a client"""
        
        try:
            # Validate workspace path
            if not os.path.exists(workspace_path):
                raise ValueError(f"Workspace path does not exist: {workspace_path}")
            
            # Container configuration
            container_name = f"serena-{client_id}"
            
            # Environment variables for Serena
            environment = {
                'CLIENT_ID': client_id,
                'WORKSPACE': '/workspace',
                'SERENA_DASHBOARD_PORT': str(ports['dashboard_port']),
                'SERENA_CONTEXT': 'ide-assistant',
                'SERENA_DOCKER': '1'
            }
            
            # Volume mounts
            volumes = {
                workspace_path: {'bind': '/workspace', 'mode': 'rw'},
                f"{os.path.expanduser('~')}/.serena": {'bind': '/root/.serena', 'mode': 'rw'}
            }
            
            # Port mappings
            ports_mapping = {
                f"{ports['dashboard_port']}/tcp": ports['dashboard_port']
            }
            
            logger.info(f"Creating Serena container for client {client_id}")
            logger.debug(f"Container config - name: {container_name}, workspace: {workspace_path}, ports: {ports}")
            
            # Create and start container
            container = self.docker_client.containers.run(
                image="serena-quality:latest",  # Will need to build this
                name=container_name,
                environment=environment,
                volumes=volumes,
                ports=ports_mapping,
                detach=True,
                remove=True,  # Auto-remove when stopped
                network_mode="bridge"
            )
            
            # Create instance object
            instance = ClientInstance(
                client_id=client_id,
                workspace_path=workspace_path,
                container=container,
                bridge_port=ports['bridge_port'],
                dashboard_port=ports['dashboard_port']
            )
            
            self.instances[client_id] = instance
            logger.info(f"Successfully created Serena instance for client {client_id}")
            
            # Wait for container to be ready
            await self.wait_for_instance_ready(instance)
            
            return instance
            
        except Exception as e:
            logger.error(f"Failed to create Serena instance for client {client_id}: {e}")
            raise
    
    async def wait_for_instance_ready(self, instance: ClientInstance, timeout: int = 60) -> None:
        """Wait for Serena instance to be ready"""
        logger.info(f"Waiting for Serena instance {instance.client_id} to be ready...")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Check if container is running
                instance.container.reload()
                if instance.container.status != 'running':
                    logger.warning(f"Container for {instance.client_id} is not running: {instance.container.status}")
                    await asyncio.sleep(2)
                    continue
                
                # TODO: Add health check endpoint call here
                # For now, just wait a bit for Serena to initialize
                logger.info(f"Serena instance {instance.client_id} appears to be ready")
                instance.health_status = "healthy"
                return
                
            except Exception as e:
                logger.warning(f"Health check failed for {instance.client_id}: {e}")
                await asyncio.sleep(2)
        
        # Timeout reached
        instance.health_status = "unhealthy"
        raise TimeoutError(f"Serena instance {instance.client_id} did not become ready within {timeout} seconds")
    
    async def get_instance(self, client_id: str) -> Optional[ClientInstance]:
        """Get instance for client"""
        return self.instances.get(client_id)
    
    async def cleanup_instance(self, client_id: str) -> None:
        """Clean up client instance"""
        if client_id in self.instances:
            instance = self.instances[client_id]
            
            try:
                # Stop and remove container
                instance.container.stop(timeout=10)
                logger.info(f"Stopped container for client {client_id}")
            except Exception as e:
                logger.warning(f"Error stopping container for {client_id}: {e}")
            
            del self.instances[client_id]
            logger.info(f"Cleaned up instance for client {client_id}")
    
    def list_instances(self) -> Dict[str, Dict[str, Any]]:
        """List all client instances"""
        return {
            client_id: {
                'workspace_path': instance.workspace_path,
                'bridge_port': instance.bridge_port,
                'dashboard_port': instance.dashboard_port,
                'health_status': instance.health_status,
                'created_at': instance.created_at,
                'container_status': instance.container.status if instance.container else 'unknown'
            }
            for client_id, instance in self.instances.items()
        }

# ----------------------------- Multi-Client Bridge ------------------------
class MultiClientBridge:
    """Main multi-client bridge orchestrator"""
    
    def __init__(self):
        self.port_allocator = PortAllocator()
        self.instance_manager = InstanceManager()
        self.client_sessions = {}  # client_id -> session_info
        
    async def register_client(self, client_id: str, workspace_path: str) -> Dict[str, Any]:
        """Register a new client and provision resources"""
        
        logger.info(f"Registering new client: {client_id} with workspace: {workspace_path}")
        
        try:
            # Allocate ports
            ports = self.port_allocator.allocate_ports_for_client(client_id)
            
            # Create Serena instance
            instance = await self.instance_manager.create_serena_instance(
                client_id, workspace_path, ports
            )
            
            # Store client session info
            self.client_sessions[client_id] = {
                'workspace_path': workspace_path,
                'ports': ports,
                'instance': instance,
                'registered_at': time.time()
            }
            
            logger.info(f"Successfully registered client {client_id}")
            
            return {
                'client_id': client_id,
                'bridge_port': ports['bridge_port'],
                'dashboard_port': ports['dashboard_port'],
                'dashboard_url': f"http://localhost:{ports['dashboard_port']}/dashboard",
                'mcp_sse_url': f"http://localhost:{ports['bridge_port']}/sse",
                'status': 'ready'
            }
            
        except Exception as e:
            logger.error(f"Failed to register client {client_id}: {e}")
            # Clean up partial allocation
            self.port_allocator.release_ports_for_client(client_id)
            raise
    
    async def unregister_client(self, client_id: str) -> None:
        """Unregister client and clean up resources"""
        
        logger.info(f"Unregistering client: {client_id}")
        
        try:
            # Clean up instance
            await self.instance_manager.cleanup_instance(client_id)
            
            # Release ports
            self.port_allocator.release_ports_for_client(client_id)
            
            # Remove session info
            if client_id in self.client_sessions:
                del self.client_sessions[client_id]
            
            logger.info(f"Successfully unregistered client {client_id}")
            
        except Exception as e:
            logger.error(f"Error unregistering client {client_id}: {e}")
            raise
    
    async def get_client_status(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get status for a specific client"""
        
        if client_id not in self.client_sessions:
            return None
        
        session = self.client_sessions[client_id]
        instance = session['instance']
        
        return {
            'client_id': client_id,
            'workspace_path': session['workspace_path'],
            'bridge_port': session['ports']['bridge_port'],
            'dashboard_port': session['ports']['dashboard_port'],
            'health_status': instance.health_status,
            'registered_at': session['registered_at'],
            'uptime_seconds': time.time() - session['registered_at']
        }
    
    def list_clients(self) -> Dict[str, Dict[str, Any]]:
        """List all registered clients"""
        return {
            client_id: {
                'workspace_path': session['workspace_path'],
                'ports': session['ports'],
                'health_status': session['instance'].health_status,
                'registered_at': session['registered_at']
            }
            for client_id, session in self.client_sessions.items()
        }

# ----------------------------- FastAPI Bridge App -------------------------
app = FastAPI(
    title="DevOps Paradise Bridge", 
    version="1.0.0", 
    description="Multi-client MCP bridge for Serena quality tools"
)

# Global bridge instance
multi_bridge: Optional[MultiClientBridge] = None

@app.on_event("startup")
async def startup():
    global multi_bridge
    multi_bridge = MultiClientBridge()
    logger.info("DevOps Paradise Bridge started successfully")

@app.get("/health")
async def health():
    """Bridge health check"""
    if not multi_bridge:
        raise HTTPException(503, "Bridge not ready")
    
    return {
        "status": "ok",
        "bridge_type": "multi_client",
        "active_clients": len(multi_bridge.client_sessions),
        "clients": list(multi_bridge.client_sessions.keys())
    }

@app.post("/clients/register")
async def register_client(request: Request):
    """Register a new client"""
    if not multi_bridge:
        raise HTTPException(503, "Bridge not ready")
    
    try:
        payload = await request.json()
        client_id = payload.get('client_id')
        workspace_path = payload.get('workspace_path')
        
        if not client_id:
            client_id = f"client-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        
        if not workspace_path:
            raise HTTPException(400, "workspace_path is required")
        
        result = await multi_bridge.register_client(client_id, workspace_path)
        return JSONResponse(result)
        
    except Exception as e:
        logger.error(f"Error registering client: {e}")
        raise HTTPException(500, f"Registration failed: {str(e)}")

@app.delete("/clients/{client_id}")
async def unregister_client(client_id: str):
    """Unregister a client"""
    if not multi_bridge:
        raise HTTPException(503, "Bridge not ready")
    
    try:
        await multi_bridge.unregister_client(client_id)
        return {"status": "unregistered", "client_id": client_id}
        
    except Exception as e:
        logger.error(f"Error unregistering client {client_id}: {e}")
        raise HTTPException(500, f"Unregistration failed: {str(e)}")

@app.get("/clients")
async def list_clients():
    """List all registered clients"""
    if not multi_bridge:
        raise HTTPException(503, "Bridge not ready")
    
    return {
        "clients": multi_bridge.list_clients(),
        "total_clients": len(multi_bridge.client_sessions)
    }

@app.get("/clients/{client_id}/status")
async def get_client_status(client_id: str):
    """Get status for a specific client"""
    if not multi_bridge:
        raise HTTPException(503, "Bridge not ready")
    
    status = await multi_bridge.get_client_status(client_id)
    if not status:
        raise HTTPException(404, f"Client {client_id} not found")
    
    return status

# ----------------------------- Setup Functions ----------------------------
def setup_logging(log_level: str, log_location: Optional[str] = None):
    """Configure logging"""
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if log_location specified
    if log_location:
        os.makedirs(log_location, exist_ok=True)
        
        log_filename = f"multi_client_bridge_{int(time.time())}.log"
        file_handler = logging.FileHandler(os.path.join(log_location, log_filename))
        file_formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        logger.info(f"Logging to file: {os.path.join(log_location, log_filename)}")
    
    # Set level
    logger.setLevel(getattr(logging, log_level.upper()))

def main():
    parser = argparse.ArgumentParser(description="DevOps Paradise Multi-Client Bridge")
    parser.add_argument("--port", type=int, default=8100, help="Bridge management port")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--log_level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logging level")
    parser.add_argument("--log_location", help="Directory for log files (optional)")
    parser.add_argument("--client_port_start", type=int, default=8200, help="Start of client port range")
    parser.add_argument("--client_port_end", type=int, default=8299, help="End of client port range")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level, args.log_location)
    
    logger.info(f"Starting DevOps Paradise Bridge on {args.host}:{args.port}")
    logger.info(f"Client port range: {args.client_port_start}-{args.client_port_end}")
    logger.info(f"Log level: {args.log_level}")
    if args.log_location:
        logger.info(f"Log location: {args.log_location}")
    
    # Override port allocator range if specified
    if hasattr(app.state, 'port_start'):  # Will be set during startup
        app.state.port_start = args.client_port_start
        app.state.port_end = args.client_port_end
    
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info"
    )

if __name__ == "__main__":
    main()