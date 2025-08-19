"""
In-memory storage for the MCP Testing Web API
Note: This is temporary storage that will be lost on restart.
For production use, consider implementing persistent storage.
"""

from typing import Dict, List, Any

# Server configurations
servers: Dict[str, Any] = {}

# Test suites
test_suites: Dict[str, Any] = {}

# Test results
test_results: List[Dict[str, Any]] = []

# MCP request history
mcp_request_history: List[Dict[str, Any]] = []

# MCP collections
mcp_collections: Dict[str, Any] = {}

# Discovered servers cache
discovered_servers: List[Dict[str, Any]] = []