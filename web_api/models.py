"""
Data models for the MCP Testing Web API
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel


class ServerConfig(BaseModel):
    name: str
    type: str  # "mock", "proxy", "direct"
    url: Optional[str] = None
    command: Optional[List[str]] = None
    description: Optional[str] = None


class ToolTest(BaseModel):
    server_name: str
    tool_name: str
    parameters: Dict[str, Any]


class TestSuite(BaseModel):
    name: str
    description: str
    tests: List[ToolTest]


class MCPToolRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    description: Optional[str] = None


class MCPCollection(BaseModel):
    name: str
    description: str
    requests: List[MCPToolRequest]