"""
Tool testing API endpoints
"""

import logging
import requests
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from ..storage import servers, test_results

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/servers", tags=["tools"])


@router.post("/{server_name}/tools/{tool_name}/call")
async def call_server_tool(server_name: str, tool_name: str, parameters: Dict[str, Any]):
    """Call a tool on the server"""
    if server_name not in servers:
        raise HTTPException(status_code=404, detail="Server not found")
    
    server = servers[server_name]
    
    try:
        call_request = {
            "jsonrpc": "2.0",
            "id": f"tool_call_{datetime.now().isoformat()}",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": parameters
            }
        }
        
        start_time = datetime.now()
        
        if server["type"] == "mock":
            response = requests.post(f"{server['url']}/mcp", json=call_request)
            result = response.json()
        elif server["type"] == "proxy":
            response = requests.post(f"{server['url']}/proxy/send", json=call_request)
            result = response.json()
        else:
            return {"error": "Direct server tool calling not implemented"}
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds() * 1000
        
        # Log test result
        test_result = {
            "timestamp": start_time.isoformat(),
            "server_name": server_name,
            "tool_name": tool_name,
            "parameters": parameters,
            "result": result,
            "execution_time_ms": execution_time,
            "success": "error" not in result
        }
        test_results.append(test_result)
        
        return {
            "result": result,
            "execution_time_ms": execution_time,
            "timestamp": start_time.isoformat()
        }
        
    except Exception as e:
        return {"error": str(e)}