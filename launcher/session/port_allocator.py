"""
Port allocation management for MCP Testing Suite sessions
"""

import socket
from typing import List


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
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(('localhost', port))
                return True
        except OSError:
            return False