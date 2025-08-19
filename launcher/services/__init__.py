"""
Service layer for MCP Testing Suite
Provides business logic abstraction between API and core components
"""

try:
    from .launcher_service import LauncherService
except ImportError:
    from launcher_service import LauncherService

__all__ = ['LauncherService']