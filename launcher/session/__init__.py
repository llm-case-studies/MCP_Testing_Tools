"""
Session management module for MCP Testing Suite
Phase 3 Refactoring: Clean separation of session management concerns
"""

from .models import ManagedSession, SessionConfig
from .manager import SessionManager
from .port_allocator import PortAllocator

__all__ = ['ManagedSession', 'SessionConfig', 'SessionManager', 'PortAllocator']