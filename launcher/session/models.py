"""
Session data models for MCP Testing Suite
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ManagedSession:
    """Data model for a managed testing session"""
    
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


@dataclass
class SessionConfig:
    """Configuration data for launching a new session"""
    
    project_path: str
    config_source: str
    config_type: str
    max_age_hours: int = 24
    
    def to_dict(self):
        """Convert to dictionary for serialization"""
        return {
            'project_path': self.project_path,
            'config_source': self.config_source,
            'config_type': self.config_type,
            'max_age_hours': self.max_age_hours
        }