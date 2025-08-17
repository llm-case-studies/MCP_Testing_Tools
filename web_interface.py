#!/usr/bin/env python3
"""
Web Interface for MCP Testing
Central hub for testing MCP servers, tools, and communication
"""

import json
import logging
import os
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MCP Testing Interface", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
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

# In-memory storage
servers = {}
test_suites = {}
test_results = []

@app.post("/api/servers")
async def add_server(server: ServerConfig):
    """Add a new MCP server configuration"""
    servers[server.name] = server.dict()
    logger.info(f"Added server: {server.name}")
    return {"message": f"Server {server.name} added"}

@app.get("/api/servers")
async def list_servers():
    """List all configured servers"""
    return {"servers": list(servers.values())}

@app.get("/api/servers/{server_name}")
async def get_server(server_name: str):
    """Get specific server configuration"""
    if server_name not in servers:
        raise HTTPException(status_code=404, detail="Server not found")
    return servers[server_name]

@app.delete("/api/servers/{server_name}")
async def remove_server(server_name: str):
    """Remove server configuration"""
    if server_name not in servers:
        raise HTTPException(status_code=404, detail="Server not found")
    del servers[server_name]
    return {"message": f"Server {server_name} removed"}

@app.post("/api/servers/{server_name}/test-connection")
async def test_server_connection(server_name: str):
    """Test connection to MCP server"""
    if server_name not in servers:
        raise HTTPException(status_code=404, detail="Server not found")
    
    server = servers[server_name]
    
    try:
        if server["type"] == "mock":
            # Test mock server
            response = requests.get(f"{server['url']}/")
            return {
                "status": "connected",
                "response": response.json(),
                "latency_ms": response.elapsed.total_seconds() * 1000
            }
        elif server["type"] == "proxy":
            # Test proxy server
            response = requests.get(f"{server['url']}/")
            return {
                "status": "connected", 
                "response": response.json(),
                "latency_ms": response.elapsed.total_seconds() * 1000
            }
        else:
            return {"status": "unsupported", "message": "Direct server testing not implemented"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/servers/{server_name}/tools")
async def list_server_tools(server_name: str):
    """List tools available on server"""
    if server_name not in servers:
        raise HTTPException(status_code=404, detail="Server not found")
    
    server = servers[server_name]
    
    try:
        if server["type"] == "mock":
            response = requests.post(
                f"{server['url']}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": "1",
                    "method": "tools/list"
                }
            )
            return response.json()
        elif server["type"] == "proxy":
            response = requests.post(
                f"{server['url']}/proxy/send",
                json={
                    "jsonrpc": "2.0",
                    "id": "1", 
                    "method": "tools/list"
                }
            )
            return response.json()
        else:
            return {"error": "Direct server tool listing not implemented"}
            
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/servers/{server_name}/tools/{tool_name}/call")
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

@app.get("/api/servers/{server_name}/logs")
async def get_server_logs(server_name: str):
    """Get server communication logs"""
    if server_name not in servers:
        raise HTTPException(status_code=404, detail="Server not found")
    
    server = servers[server_name]
    
    try:
        if server["type"] == "mock":
            response = requests.get(f"{server['url']}/debug/logs")
            return response.json()
        elif server["type"] == "proxy":
            response = requests.get(f"{server['url']}/proxy/logs")
            return response.json()
        else:
            return {"logs": [], "message": "Logs not available for this server type"}
            
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/test-suites")
async def create_test_suite(suite: TestSuite):
    """Create a new test suite"""
    test_suites[suite.name] = suite.dict()
    return {"message": f"Test suite {suite.name} created"}

@app.get("/api/test-suites")
async def list_test_suites():
    """List all test suites"""
    return {"test_suites": list(test_suites.values())}

@app.post("/api/test-suites/{suite_name}/run")
async def run_test_suite(suite_name: str):
    """Run a test suite"""
    if suite_name not in test_suites:
        raise HTTPException(status_code=404, detail="Test suite not found")
    
    suite = test_suites[suite_name]
    results = []
    
    for test in suite["tests"]:
        try:
            result = await call_server_tool(
                test["server_name"],
                test["tool_name"],
                test["parameters"]
            )
            results.append({
                "test": test,
                "result": result,
                "success": "error" not in result
            })
        except Exception as e:
            results.append({
                "test": test,
                "result": {"error": str(e)},
                "success": False
            })
    
    suite_result = {
        "suite_name": suite_name,
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "total_tests": len(results),
        "passed": sum(1 for r in results if r["success"]),
        "failed": sum(1 for r in results if not r["success"])
    }
    
    return suite_result

@app.get("/api/test-results")
async def get_test_results():
    """Get historical test results"""
    return {"results": test_results}

@app.delete("/api/test-results")
async def clear_test_results():
    """Clear test results history"""
    global test_results
    test_results = []
    return {"message": "Test results cleared"}

@app.post("/api/discover-servers")
async def discover_servers():
    """Auto-discover MCP servers from mounted configurations"""
    from config_discovery import MCPConfigDiscovery
    
    # Use mounted config directory or fallback to local
    config_dir = os.environ.get("MCP_CONFIG_DIR", "/mcp-configs")
    if not os.path.exists(config_dir):
        config_dir = os.path.expanduser("~")  # Fallback for local testing
    
    discovery = MCPConfigDiscovery(config_dir)
    discovered = discovery.discover_servers()
    
    # Add validation information
    for server in discovered:
        validation = discovery.validate_server_config(server)
        capabilities = discovery.get_server_capabilities(server)
        server["validation"] = validation
        server["capabilities"] = capabilities
    
    return {
        "discovered": discovered,
        "config_dir": config_dir,
        "total_servers": len(discovered)
    }

# Serve the frontend (basic HTML)
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve basic web interface"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MCP Testing Interface</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; }
            button { padding: 10px 15px; margin: 5px; }
            pre { background: #f5f5f5; padding: 10px; overflow-x: auto; }
            input, textarea { width: 100%; padding: 5px; margin: 5px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>MCP Testing Interface</h1>
            
            <div class="section">
                <h2>Quick Start</h2>
                <button onclick="discoverServers()">Discover Servers</button>
                <button onclick="testMockServer()">Test Mock Server</button>
                <button onclick="startProxy()">Start Proxy</button>
            </div>
            
            <div class="section">
                <h2>Server Management</h2>
                <div id="servers"></div>
            </div>
            
            <div class="section">
                <h2>Tool Testing</h2>
                <div id="tools"></div>
            </div>
            
            <div class="section">
                <h2>Logs</h2>
                <div id="logs"></div>
            </div>
        </div>
        
        <script>
            // Basic JavaScript for testing
            async function discoverServers() {
                const response = await fetch('/api/discover-servers', {method: 'POST'});
                const data = await response.json();
                console.log('Discovered servers:', data);
            }
            
            async function testMockServer() {
                const response = await fetch('/api/servers/mock_server/test-connection', {method: 'POST'});
                const data = await response.json();
                console.log('Mock server test:', data);
            }
            
            // More functions would be added for a full interface
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9090)