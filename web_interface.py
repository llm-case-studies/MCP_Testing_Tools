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
async def discover_servers(custom_path: Optional[str] = None):
    """Auto-discover MCP servers from mounted configurations or custom path"""
    from config_discovery import MCPConfigDiscovery
    
    # Use custom path, mounted config directory, or fallback to local
    if custom_path:
        config_dir = custom_path
    else:
        config_dir = os.environ.get("MCP_CONFIG_DIR", "/mcp-configs")
        if not os.path.exists(config_dir):
            config_dir = os.path.expanduser("~")  # Fallback for local testing
    
    discovery = MCPConfigDiscovery(config_dir)
    discovered = discovery.discover_servers()
    
    # Add detailed discovery information
    discovery_sources = {
        "claude_config": os.path.join(config_dir, ".claude.json"),
        "gemini_config": os.path.join(config_dir, ".gemini"),
        "project_mcp": "./.mcp.json",
        "config_dir_used": config_dir
    }
    
    # Check which sources exist and were used
    sources_found = {}
    for source_name, path in discovery_sources.items():
        if os.path.exists(path):
            if source_name == "gemini_config":
                sources_found[source_name] = f"{path} (directory)"
            else:
                sources_found[source_name] = path
    
    # Add validation and execution information
    for server in discovered:
        validation = discovery.validate_server_config(server)
        capabilities = discovery.get_server_capabilities(server)
        server["validation"] = validation
        server["capabilities"] = capabilities
        
        # Add execution readiness info
        server["execution_info"] = {
            "command_available": True,  # We'll check this properly later
            "can_activate": server["validation"]["valid"],
            "ready_to_test": server["validation"]["valid"] and len(server["validation"]["issues"]) == 0
        }
    
    return {
        "discovered": discovered,
        "total_servers": len(discovered),
        "discovery_sources": discovery_sources,
        "sources_found": sources_found,
        "config_dir": config_dir
    }

@app.post("/api/activate-server/{server_name}")
async def activate_discovered_server(server_name: str):
    """Activate a discovered server by making it available for testing"""
    from config_discovery import MCPConfigDiscovery
    
    # Rediscover to get latest info
    config_dir = os.environ.get("MCP_CONFIG_DIR", "/mcp-configs")
    if not os.path.exists(config_dir):
        config_dir = os.path.expanduser("~")
    
    discovery = MCPConfigDiscovery(config_dir)
    discovered = discovery.discover_servers()
    
    # Find the server
    target_server = None
    for server in discovered:
        if server["name"] == server_name:
            target_server = server
            break
    
    if not target_server:
        raise HTTPException(status_code=404, detail=f"Server '{server_name}' not found in discovered servers")
    
    # Check if server is valid for activation
    validation = discovery.validate_server_config(target_server)
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail=f"Server '{server_name}' failed validation: {validation['issues']}")
    
    # Create clean server name (remove source prefixes)
    clean_name = server_name.replace("claude_", "").replace("gemini_", "").replace("test_", "")
    
    # Prepare server config for activation
    server_config = ServerConfig(
        name=clean_name,
        type=target_server["type"],
        command=target_server["command"],
        description=target_server.get("description", f"Activated {clean_name} server")
    )
    
    # Add to active servers
    servers[clean_name] = server_config.dict()
    
    return {
        "message": f"Server '{clean_name}' activated successfully",
        "original_name": server_name,
        "activated_name": clean_name,
        "server_config": server_config.dict(),
        "validation": validation
    }

@app.post("/api/test-discovered/{server_name}")
async def test_discovered_server(server_name: str):
    """Test a discovered server without activating it permanently"""
    from config_discovery import MCPConfigDiscovery
    import subprocess
    import json
    
    # Rediscover to get latest info
    config_dir = os.environ.get("MCP_CONFIG_DIR", "/mcp-configs")
    if not os.path.exists(config_dir):
        config_dir = os.path.expanduser("~")
    
    discovery = MCPConfigDiscovery(config_dir)
    discovered = discovery.discover_servers()
    
    # Find the server
    target_server = None
    for server in discovered:
        if server["name"] == server_name:
            target_server = server
            break
    
    if not target_server:
        raise HTTPException(status_code=404, detail=f"Server '{server_name}' not found")
    
    # For now, just return server info and validation
    # TODO: Implement actual MCP communication test
    validation = discovery.validate_server_config(target_server)
    capabilities = discovery.get_server_capabilities(target_server)
    
    test_result = {
        "server_name": server_name,
        "command": target_server["command"],
        "type": target_server["type"],
        "validation": validation,
        "capabilities": capabilities,
        "test_status": "validation_only",  # Will add real testing later
        "notes": "This endpoint currently performs validation checks. Full MCP communication testing coming soon."
    }
    
    if target_server["type"] == "stdio":
        test_result["execution_notes"] = f"Would execute: {' '.join(target_server['command'])}"
    elif target_server["type"] == "http":
        test_result["execution_notes"] = f"Would connect to: {target_server.get('url', 'No URL specified')}"
    
    return test_result

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
            // Enhanced JavaScript with DOM updates
            async function discoverServers() {
                try {
                    const response = await fetch('/api/discover-servers', {method: 'POST'});
                    const data = await response.json();
                    console.log('Discovered servers:', data);
                    
                    // Update the servers section
                    const serversDiv = document.getElementById('servers');
                    serversDiv.innerHTML = '<h3>Discovered Servers (' + data.total_servers + ')</h3>';
                    
                    data.discovered.forEach(server => {
                        const serverDiv = document.createElement('div');
                        serverDiv.style.border = '1px solid #ccc';
                        serverDiv.style.margin = '10px 0';
                        serverDiv.style.padding = '10px';
                        serverDiv.style.backgroundColor = '#f9f9f9';
                        
                        let toolsHtml = '';
                        if (server.name.includes('qdrant')) {
                            toolsHtml = `
                                <div style="margin-top: 10px;">
                                    <h5>Qdrant Memory Tools:</h5>
                                    <button onclick="testQdrantStore('${server.name}')">Test Store</button>
                                    <button onclick="testQdrantFind('${server.name}')">Test Find</button>
                                </div>
                                <div id="qdrant-results-${server.name.replace(/[^a-zA-Z0-9]/g, '')}" style="margin-top: 10px;"></div>
                            `;
                        }
                        
                        serverDiv.innerHTML = `
                            <h4>${server.name} (${server.type})</h4>
                            <p><strong>Source:</strong> ${server.source}</p>
                            <p><strong>Description:</strong> ${server.description}</p>
                            <p><strong>Capabilities:</strong> ${Object.keys(server.capabilities).filter(k => server.capabilities[k]).join(', ')}</p>
                            ${server.validation.warnings.length > 0 ? '<p><strong>Warnings:</strong> ' + server.validation.warnings.join(', ') + '</p>' : ''}
                            ${toolsHtml}
                        `;
                        serversDiv.appendChild(serverDiv);
                    });
                } catch (error) {
                    console.error('Error discovering servers:', error);
                    document.getElementById('servers').innerHTML = '<p style="color: red;">Error: ' + error.message + '</p>';
                }
            }
            
            async function testQdrantStore(serverName) {
                try {
                    const testData = {
                        information: "Testing MCP Testing Suite UI integration with Qdrant at " + new Date().toISOString(),
                        metadata: {"source": "web_ui", "server": serverName, "test": true}
                    };
                    
                    // For now, show what would be stored
                    const resultDiv = document.getElementById('qdrant-results-' + serverName.replace(/[^a-zA-Z0-9]/g, ''));
                    resultDiv.innerHTML = `
                        <p style="color: blue;"><strong>Store Test (Demo):</strong></p>
                        <pre>${JSON.stringify(testData, null, 2)}</pre>
                        <p><em>Note: This would store the above data in ${serverName}</em></p>
                    `;
                } catch (error) {
                    console.error('Error testing Qdrant store:', error);
                }
            }
            
            async function testQdrantFind(serverName) {
                try {
                    const query = "MCP Testing Suite";
                    
                    // For now, show what would be searched
                    const resultDiv = document.getElementById('qdrant-results-' + serverName.replace(/[^a-zA-Z0-9]/g, ''));
                    resultDiv.innerHTML = `
                        <p style="color: green;"><strong>Find Test (Demo):</strong></p>
                        <p>Searching for: "${query}"</p>
                        <p><em>Note: This would search ${serverName} for memories matching "${query}"</em></p>
                    `;
                } catch (error) {
                    console.error('Error testing Qdrant find:', error);
                }
            }
            
            async function testMockServer() {
                try {
                    const response = await fetch('/api/servers/mock_server/test-connection', {method: 'POST'});
                    const data = await response.json();
                    console.log('Mock server test:', data);
                    
                    const logsDiv = document.getElementById('logs');
                    logsDiv.innerHTML = '<h3>Mock Server Test Result</h3><pre>' + JSON.stringify(data, null, 2) + '</pre>';
                } catch (error) {
                    console.error('Error testing mock server:', error);
                    document.getElementById('logs').innerHTML = '<p style="color: red;">Error: ' + error.message + '</p>';
                }
            }
            
            async function loadActiveServers() {
                try {
                    const response = await fetch('/api/servers');
                    const data = await response.json();
                    console.log('Active servers:', data);
                    
                    const serversDiv = document.getElementById('servers');
                    let html = '<h3>Active Servers (' + data.servers.length + ')</h3>';
                    
                    if (data.servers.length === 0) {
                        html += '<p>No active servers. Click "Discover Servers" to find available servers.</p>';
                    } else {
                        data.servers.forEach(server => {
                            html += `
                                <div style="border: 1px solid #ccc; margin: 10px 0; padding: 10px;">
                                    <h4>${server.name}</h4>
                                    <p><strong>Type:</strong> ${server.type}</p>
                                    <p><strong>Description:</strong> ${server.description || 'No description'}</p>
                                    ${server.command ? '<p><strong>Command:</strong> ' + server.command.join(' ') + '</p>' : ''}
                                    <button onclick="testServer('${server.name}')">Test Connection</button>
                                    <button onclick="listTools('${server.name}')">List Tools</button>
                                </div>
                            `;
                        });
                    }
                    
                    serversDiv.innerHTML = html;
                } catch (error) {
                    console.error('Error loading active servers:', error);
                    document.getElementById('servers').innerHTML = '<p style="color: red;">Error loading servers: ' + error.message + '</p>';
                }
            }
            
            async function testServer(serverName) {
                try {
                    const response = await fetch(`/api/servers/${serverName}/test-connection`, {method: 'POST'});
                    const data = await response.json();
                    alert('Test result: ' + JSON.stringify(data, null, 2));
                } catch (error) {
                    alert('Error testing server: ' + error.message);
                }
            }
            
            async function listTools(serverName) {
                try {
                    const response = await fetch(`/api/servers/${serverName}/tools`);
                    const data = await response.json();
                    alert('Tools: ' + JSON.stringify(data, null, 2));
                } catch (error) {
                    alert('Error listing tools: ' + error.message);
                }
            }

            async function activateServer(name, type, command, description) {
                try {
                    const commandArray = command.split(' ');
                    const serverData = {
                        name: name.replace(/^(claude_|gemini_)/, ''), // Remove prefix
                        type: type,
                        command: commandArray,
                        description: description
                    };
                    
                    const response = await fetch('/api/servers', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(serverData)
                    });
                    
                    const result = await response.json();
                    alert('Server activated: ' + result.message);
                    loadActiveServers(); // Refresh active servers list
                } catch (error) {
                    alert('Error activating server: ' + error.message);
                }
            }

            // Auto-load active servers and discover on page load
            window.onload = function() {
                loadActiveServers();
                // Don't call discoverServers automatically to avoid overwriting active servers
                // User can click "Discover Servers" button when needed
            };
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8094)