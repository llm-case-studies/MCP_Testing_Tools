#!/usr/bin/env python3
"""
Modular Web Interface for MCP Testing
Refactored from monolithic web_interface.py into clean modular structure
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn

from .api import servers, tools, test_suites, discovery, mcp, results

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="MCP Testing Interface", version="2.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(servers.router)
app.include_router(tools.router)
app.include_router(test_suites.router)
app.include_router(results.router)
app.include_router(discovery.router)
app.include_router(mcp.router)


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the basic HTML frontend for MCP testing"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MCP Testing Interface</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
            .section { border: 1px solid #ddd; margin: 20px 0; padding: 20px; border-radius: 5px; }
            .server { background: #f9f9f9; margin: 10px 0; padding: 10px; border-radius: 3px; }
            button { background: #007cba; color: white; border: none; padding: 8px 16px; cursor: pointer; margin: 5px; }
            button:hover { background: #005a87; }
            .results { background: #f0f0f0; padding: 10px; margin: 10px 0; border-radius: 3px; white-space: pre-wrap; }
            input, select, textarea { padding: 5px; margin: 5px; border: 1px solid #ddd; border-radius: 3px; }
            .tool { background: #e8f4f8; margin: 5px 0; padding: 8px; border-radius: 3px; }
            .error { background: #ffebee; color: #c62828; }
            .success { background: #e8f5e9; color: #2e7d32; }
        </style>
    </head>
    <body>
        <h1>🧪 MCP Testing Interface v2.0</h1>
        <p>Modular FastAPI-based interface for testing MCP servers and tools</p>
        
        <div class="section">
            <h2>📡 Server Discovery</h2>
            <button onclick="discoverServers()">🔍 Discover Servers</button>
            <button onclick="loadActiveServers()">📋 Load Active Servers</button>
            <div id="discoveredServers"></div>
        </div>
        
        <div class="section">
            <h2>⚙️ Active Servers</h2>
            <div id="activeServers"></div>
            
            <h3>Add Server Manually</h3>
            <input type="text" id="serverName" placeholder="Server Name">
            <select id="serverType">
                <option value="mock">Mock Server</option>
                <option value="proxy">Proxy Server</option>
                <option value="direct">Direct Server</option>
            </select>
            <input type="text" id="serverUrl" placeholder="Server URL (for mock/proxy)">
            <input type="text" id="serverCommand" placeholder="Command (for direct, comma-separated)">
            <button onclick="addServer()">➕ Add Server</button>
        </div>
        
        <div class="section">
            <h2>🔧 Tool Testing</h2>
            <select id="toolServer"></select>
            <input type="text" id="toolName" placeholder="Tool Name">
            <textarea id="toolParams" placeholder='{"param1": "value1"}' rows="3" cols="50"></textarea>
            <br>
            <button onclick="callTool()">🚀 Call Tool</button>
            <div id="toolResults" class="results"></div>
        </div>
        
        <div class="section">
            <h2>📊 MCP Postman</h2>
            <button onclick="discoverMCPServers()">🔍 Discover MCP Servers</button>
            <button onclick="loadMCPHistory()">📜 Load History</button>
            <button onclick="clearMCPHistory()">🗑️ Clear History</button>
            <div id="mcpServers"></div>
            <div id="mcpHistory"></div>
        </div>

        <script>
            // Server Discovery Functions
            async function discoverServers() {
                try {
                    const response = await fetch('/api/discover-servers', { method: 'POST' });
                    const data = await response.json();
                    
                    let html = '<h3>Discovered Servers:</h3>';
                    if (data.discovered && data.discovered.length > 0) {
                        data.discovered.forEach(server => {
                            html += `<div class="server">
                                <strong>${server.name}</strong> (${server.type})
                                <br>Command: ${server.command ? server.command.join(' ') : 'N/A'}
                                <br>Valid: ${server.validation ? server.validation.valid : 'Unknown'}
                                <br><button onclick="activateServer('${server.name}')">Activate</button>
                                <button onclick="testDiscoveredServer('${server.name}')">Test</button>
                            </div>`;
                        });
                    } else {
                        html += '<p>No servers discovered</p>';
                    }
                    
                    document.getElementById('discoveredServers').innerHTML = html;
                } catch (error) {
                    document.getElementById('discoveredServers').innerHTML = `<div class="error">Error: ${error.message}</div>`;
                }
            }

            async function loadActiveServers() {
                try {
                    const response = await fetch('/api/servers');
                    const data = await response.json();
                    
                    let html = '';
                    if (data.servers && data.servers.length > 0) {
                        data.servers.forEach(server => {
                            html += `<div class="server">
                                <strong>${server.name}</strong> (${server.type})
                                <br>URL: ${server.url || 'N/A'}
                                <br><button onclick="testConnection('${server.name}')">Test Connection</button>
                                <button onclick="listTools('${server.name}')">List Tools</button>
                                <button onclick="removeServer('${server.name}')">Remove</button>
                            </div>`;
                        });
                    } else {
                        html = '<p>No active servers configured</p>';
                    }
                    
                    document.getElementById('activeServers').innerHTML = html;
                    
                    // Update tool server dropdown
                    const toolSelect = document.getElementById('toolServer');
                    toolSelect.innerHTML = '<option value="">Select Server</option>';
                    if (data.servers) {
                        data.servers.forEach(server => {
                            toolSelect.innerHTML += `<option value="${server.name}">${server.name}</option>`;
                        });
                    }
                } catch (error) {
                    document.getElementById('activeServers').innerHTML = `<div class="error">Error: ${error.message}</div>`;
                }
            }

            async function addServer() {
                const name = document.getElementById('serverName').value;
                const type = document.getElementById('serverType').value;
                const url = document.getElementById('serverUrl').value;
                const command = document.getElementById('serverCommand').value;
                
                if (!name) {
                    alert('Please enter a server name');
                    return;
                }
                
                const serverData = {
                    name: name,
                    type: type,
                    url: url || null,
                    command: command ? command.split(',').map(s => s.trim()) : null,
                    description: `Manually added ${type} server`
                };
                
                try {
                    const response = await fetch('/api/servers', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(serverData)
                    });
                    
                    const result = await response.json();
                    alert('Server added: ' + result.message);
                    loadActiveServers();
                    
                    // Clear form
                    document.getElementById('serverName').value = '';
                    document.getElementById('serverUrl').value = '';
                    document.getElementById('serverCommand').value = '';
                } catch (error) {
                    alert('Error adding server: ' + error.message);
                }
            }

            async function testConnection(serverName) {
                try {
                    const response = await fetch(`/api/servers/${serverName}/test-connection`, { method: 'POST' });
                    const result = await response.json();
                    alert(`Connection test result: ${result.status}\\nMessage: ${result.message || 'Success'}`);
                } catch (error) {
                    alert('Error testing connection: ' + error.message);
                }
            }

            async function callTool() {
                const server = document.getElementById('toolServer').value;
                const tool = document.getElementById('toolName').value;
                const params = document.getElementById('toolParams').value;
                
                if (!server || !tool) {
                    alert('Please select server and enter tool name');
                    return;
                }
                
                let parameters = {};
                if (params) {
                    try {
                        parameters = JSON.parse(params);
                    } catch (e) {
                        alert('Invalid JSON in parameters');
                        return;
                    }
                }
                
                try {
                    const response = await fetch(`/api/servers/${server}/tools/${tool}/call`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(parameters)
                    });
                    
                    const result = await response.json();
                    document.getElementById('toolResults').textContent = JSON.stringify(result, null, 2);
                    document.getElementById('toolResults').className = 'results ' + (result.error ? 'error' : 'success');
                } catch (error) {
                    document.getElementById('toolResults').textContent = 'Error: ' + error.message;
                    document.getElementById('toolResults').className = 'results error';
                }
            }

            async function activateServer(serverName) {
                try {
                    const response = await fetch(`/api/activate-server/${serverName}`, { method: 'POST' });
                    const result = await response.json();
                    alert('Server activated: ' + result.message);
                    loadActiveServers();
                } catch (error) {
                    alert('Error activating server: ' + error.message);
                }
            }

            async function discoverMCPServers() {
                try {
                    const response = await fetch('/api/mcp/discover');
                    const data = await response.json();
                    
                    let html = '<h3>MCP Servers:</h3>';
                    if (data.servers && data.servers.length > 0) {
                        data.servers.forEach(server => {
                            html += `<div class="server">
                                <strong>${server.name}</strong> (${server.type})
                                <br>Status: ${server.status}
                                <br>Tools: ${server.tools ? server.tools.length : 0}
                                <br><button onclick="discoverMCPTools('${server.name}')">Discover Tools</button>
                            </div>`;
                        });
                    } else {
                        html += '<p>No MCP servers found</p>';
                    }
                    
                    document.getElementById('mcpServers').innerHTML = html;
                } catch (error) {
                    document.getElementById('mcpServers').innerHTML = `<div class="error">Error: ${error.message}</div>`;
                }
            }

            async function loadMCPHistory() {
                try {
                    const response = await fetch('/api/mcp/history');
                    const data = await response.json();
                    
                    let html = '<h3>MCP Request History:</h3>';
                    if (data.requests && data.requests.length > 0) {
                        data.requests.forEach(req => {
                            html += `<div class="tool">
                                <strong>${req.server_name}.${req.tool_name}</strong>
                                <br>Status: ${req.status}
                                <br>Time: ${req.timing ? req.timing.started_at : 'N/A'}
                            </div>`;
                        });
                    } else {
                        html += '<p>No requests in history</p>';
                    }
                    
                    document.getElementById('mcpHistory').innerHTML = html;
                } catch (error) {
                    document.getElementById('mcpHistory').innerHTML = `<div class="error">Error: ${error.message}</div>`;
                }
            }

            // Auto-load on page load
            window.onload = function() {
                loadActiveServers();
            };
        </script>
    </body>
    </html>
    """


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8094)