from pydantic import BaseModel, Field
from typing import Optional

class SessionOut(BaseModel):
    session: str

class PostAccepted(BaseModel):
    status: str = Field("accepted")
    id: Optional[str] = None

class ToggleFilterIn(BaseModel):
    enabled: bool

class FilterInfo(BaseModel):
    name: str
    enabled: bool
    description: Optional[str] = None
