from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from dataclasses import dataclass

class SessionOut(BaseModel):
    session: str

class PostAccepted(BaseModel):
    status: str = Field("accepted")
    id: Optional[str] = None

class ToggleFilterIn(BaseModel):
    enabled: bool

@dataclass
class FilterInfo:
    """Information about filtering actions taken on a message"""
    blocked: bool = False
    block_reason: Optional[str] = None
    actions_taken: List[str] = None
    pii_redacted: bool = False
    security_violation: bool = False
    modified_content: bool = False
    original_size: int = 0
    filtered_size: int = 0
    
    def __post_init__(self):
        if self.actions_taken is None:
            self.actions_taken = []
