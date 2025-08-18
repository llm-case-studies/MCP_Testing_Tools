#!/usr/bin/env python3
"""
MCP Testing Suite V2 - Dynamic Project Launcher
Central hub for selecting projects and launching testing backends
"""

import os
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

from project_scanner import ProjectScanner
from session_manager import SessionManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MCP Testing Suite V2 - Project Launcher", version="2.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
project_scanner = ProjectScanner()
session_manager = SessionManager()

# Models
class ProjectInfo(BaseModel):
    path: str
    name: str
    config_sources: List[Dict[str, Any]]
    description: Optional[str] = None

class LaunchConfig(BaseModel):
    project_path: str
    config_source: str
    config_type: str  # "project", "user", "custom"
    session_name: Optional[str] = None
    test_scenario: str = "development"
    selected_servers: Optional[List[str]] = None  # If None, use all servers
    server_filter_mode: str = "include"  # "include" or "exclude"

class SessionInfo(BaseModel):
    session_id: str
    project_path: str
    config_source: str
    status: str
    backend_url: Optional[str] = None
    created_at: datetime
    last_activity: datetime

# API Endpoints

@app.get("/", response_class=HTMLResponse)
async def serve_launcher():
    """Serve the project launcher interface"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MCP Testing Suite V2 - Project Launcher</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                max-width: 1200px; 
                margin: 0 auto; 
                padding: 20px;
                background: #f5f5f5;
            }
            .header {
                background: #2196F3;
                color: white;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
            }
            .section {
                background: white;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .project-card {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 15px;
                margin: 10px 0;
                background: #f9f9f9;
            }
            .config-source {
                background: #e3f2fd;
                padding: 8px;
                margin: 5px 0;
                border-radius: 4px;
                font-size: 0.9em;
            }
            .session-active {
                background: #c8e6c9;
                border-color: #4caf50;
            }
            button {
                background: #2196F3;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                cursor: pointer;
                margin: 5px;
            }
            button:hover { background: #1976D2; }
            .btn-success { background: #4caf50; }
            .btn-danger { background: #f44336; }
            .btn-secondary { background: #757575; }
            input, select {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                margin: 5px;
            }
            .status { padding: 5px 10px; border-radius: 3px; font-size: 0.8em; }
            .status-running { background: #c8e6c9; color: #2e7d32; }
            .status-stopped { background: #ffcdd2; color: #c62828; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🚀 MCP Testing Suite V2</h1>
            <p>Dynamic Project Launcher - Select your project and start testing!</p>
        </div>

        <div class="section">
            <h2>📁 Project Scanner</h2>
            <div>
                <input type="text" id="scanPath" placeholder="/path/to/projects (leave empty for current directory)" style="width: 300px;">
                <button onclick="openFolderBrowser()">📂 Browse</button>
                <button onclick="scanProjects()">Scan for Projects</button>
                <button onclick="refreshSessions()" class="btn-secondary">Refresh Sessions</button>
            </div>
            
            <!-- Folder Browser Modal -->
            <div id="folderBrowser" style="display: none; background: white; border: 2px solid #2196F3; border-radius: 8px; padding: 20px; margin: 10px 0; max-height: 400px; overflow-y: auto;">
                <h3>📂 Select Project Directory</h3>
                <div id="currentPath" style="background: #f5f5f5; padding: 8px; border-radius: 4px; margin-bottom: 10px; font-family: monospace;"></div>
                <div id="folderList"></div>
                <div style="margin-top: 15px;">
                    <button onclick="selectCurrentFolder()" class="btn-success">Select This Folder</button>
                    <button onclick="closeFolderBrowser()" class="btn-secondary">Cancel</button>
                </div>
            </div>

            <!-- Server Selection Modal -->
            <div id="serverSelector" style="display: none; background: white; border: 2px solid #4caf50; border-radius: 8px; padding: 20px; margin: 10px 0; max-height: 500px; overflow-y: auto;">
                <h3>🎛️ Configure MCP Servers</h3>
                <div id="configInfo" style="background: #f5f5f5; padding: 10px; border-radius: 4px; margin-bottom: 15px;"></div>
                
                <div style="margin-bottom: 15px;">
                    <label><input type="radio" name="filterMode" value="include" checked> Include selected servers only</label><br>
                    <label><input type="radio" name="filterMode" value="exclude"> Exclude selected servers</label><br>
                    <label><input type="radio" name="filterMode" value="all"> Use all servers (default)</label>
                </div>
                
                <div id="serverList" style="max-height: 250px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; border-radius: 4px;"></div>
                
                <div style="margin-top: 15px;">
                    <button onclick="launchWithServerSelection()" class="btn-success">🚀 Launch with Selection</button>
                    <button onclick="closeServerSelector()" class="btn-secondary">Cancel</button>
                </div>
            </div>
            
            <div id="projectResults"></div>
        </div>

        <div class="section">
            <h2>🎮 Active Testing Sessions</h2>
            <div id="activeSessions"></div>
        </div>

        <div class="section">
            <h2>🔧 Manual Launch</h2>
            <div>
                <input type="text" id="manualProjectPath" placeholder="Project path" style="width: 300px;">
                <input type="text" id="manualConfigSource" placeholder="Config source path" style="width: 300px;">
                <select id="manualConfigType">
                    <option value="project">Project Config</option>
                    <option value="user">User Config</option>
                    <option value="custom">Custom Config</option>
                </select>
                <button onclick="launchManual()" class="btn-success">Launch Testing Backend</button>
            </div>
        </div>

        <div class="section">
            <h2>🧪 MCP Postman - Tool Testing</h2>
            <div style="margin-bottom: 10px;">
                <button onclick="openMCPPostman()" class="btn-success">🚀 Open MCP Tool Tester</button>
                <span style="margin-left: 10px; color: #666; font-size: 0.9em;">Test MCP tools from active sessions</span>
            </div>
            
            <!-- MCP Postman Modal -->
            <div id="mcpPostmanModal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000;">
                <div style="background: white; margin: 5% auto; padding: 20px; width: 90%; max-width: 1200px; border-radius: 8px; max-height: 90vh; overflow-y: auto;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h2>🧪 MCP Postman - Tool Testing</h2>
                        <button onclick="closeMCPPostman()" class="btn-secondary">✕ Close</button>
                    </div>
                    
                    <!-- Session Selection -->
                    <div style="margin-bottom: 20px; padding: 15px; background: #f0f8ff; border-radius: 5px;">
                        <label for="mcpSessionSelect"><strong>Select Active Session:</strong></label>
                        <select id="mcpSessionSelect" onchange="loadMCPServers()" style="margin-left: 10px; width: 300px;">
                            <option value="">Choose a session...</option>
                        </select>
                        <button onclick="refreshMCPSessions()" class="btn-secondary" style="margin-left: 10px;">🔄 Refresh</button>
                    </div>
                    
                    <!-- Server Discovery Panel -->
                    <div style="display: flex; gap: 20px; margin-bottom: 20px;">
                        <div style="flex: 1; background: #f9f9f9; padding: 15px; border-radius: 5px;">
                            <h3>📋 MCP Servers</h3>
                            <div id="mcpServersList">
                                <p style="color: #666;">Select a session to discover MCP servers</p>
                            </div>
                        </div>
                        
                        <div style="flex: 2; background: #f9f9f9; padding: 15px; border-radius: 5px;">
                            <h3>🔧 Tools</h3>
                            <div id="mcpToolsList">
                                <p style="color: #666;">Select a server to view available tools</p>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Tool Testing Panel -->
                    <div style="background: #f0f8ff; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
                        <h3>⚡ Tool Tester</h3>
                        <div style="display: flex; gap: 15px; margin-bottom: 15px;">
                            <div style="flex: 1;">
                                <label for="testServerName"><strong>Server:</strong></label><br>
                                <input type="text" id="testServerName" placeholder="Select server from list" style="width: 100%;" readonly>
                            </div>
                            <div style="flex: 1;">
                                <label for="testToolName"><strong>Tool:</strong></label><br>
                                <input type="text" id="testToolName" placeholder="Select tool from list" style="width: 100%;" readonly>
                            </div>
                        </div>
                        
                        <div style="margin-bottom: 15px;">
                            <label for="testArguments"><strong>Arguments (JSON):</strong></label><br>
                            <textarea id="testArguments" placeholder='{"param1": "value1", "param2": 123}' style="width: 100%; height: 100px; font-family: monospace;"></textarea>
                        </div>
                        
                        <div style="margin-bottom: 15px;">
                            <label for="testDescription"><strong>Description (optional):</strong></label><br>
                            <input type="text" id="testDescription" placeholder="Describe this test..." style="width: 100%;">
                        </div>
                        
                        <div>
                            <button onclick="executeMCPTool()" class="btn-success">🚀 Execute Tool</button>
                            <button onclick="generateSampleRequest()" class="btn-secondary">📝 Generate Sample</button>
                            <button onclick="clearToolTester()" class="btn-secondary">🧹 Clear</button>
                        </div>
                    </div>
                    
                    <!-- Results Panel -->
                    <div style="background: #f9f9f9; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
                        <h3>📊 Results</h3>
                        <div id="mcpResults">
                            <p style="color: #666;">Execute a tool to see results here</p>
                        </div>
                    </div>
                    
                    <!-- History Panel -->
                    <div style="background: #fff; border: 1px solid #ddd; padding: 15px; border-radius: 5px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                            <h3>📈 Request History</h3>
                            <div>
                                <button onclick="refreshMCPHistory()" class="btn-secondary">🔄 Refresh</button>
                                <button onclick="clearMCPHistory()" class="btn-secondary">🗑️ Clear History</button>
                            </div>
                        </div>
                        <div id="mcpHistory" style="max-height: 300px; overflow-y: auto;">
                            <p style="color: #666;">No requests in history</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            let currentBrowsePath = '.';

            // Folder Browser Functions
            async function openFolderBrowser() {
                currentBrowsePath = document.getElementById('scanPath').value || '.';
                document.getElementById('folderBrowser').style.display = 'block';
                await loadFolderContents(currentBrowsePath);
            }

            function closeFolderBrowser() {
                document.getElementById('folderBrowser').style.display = 'none';
            }

            function selectCurrentFolder() {
                document.getElementById('scanPath').value = currentBrowsePath;
                closeFolderBrowser();
                scanProjects();
            }

            async function loadFolderContents(path) {
                try {
                    const response = await fetch(`/api/browse-folders?path=${encodeURIComponent(path)}`);
                    const data = await response.json();
                    
                    document.getElementById('currentPath').textContent = data.current_path;
                    
                    let html = '';
                    data.folders.forEach(folder => {
                        const icon = folder.type === 'parent' ? '⬆️' : 
                                   folder.type === 'project' ? '📦' : '📁';
                        const style = folder.has_mcp_config ? 'background: #e8f5e8; font-weight: bold;' : '';
                        
                        html += `
                            <div style="padding: 8px; margin: 2px 0; border-radius: 4px; cursor: pointer; ${style}" 
                                 onclick="navigateToFolder('${folder.path}')">
                                ${icon} ${folder.name}
                                ${folder.has_mcp_config ? ' <span style="color: #4caf50;">✓ MCP</span>' : ''}
                            </div>
                        `;
                    });
                    
                    document.getElementById('folderList').innerHTML = html;
                } catch (error) {
                    document.getElementById('folderList').innerHTML = 
                        '<p style="color: red;">Error loading folders: ' + error.message + '</p>';
                }
            }

            async function navigateToFolder(path) {
                currentBrowsePath = path;
                await loadFolderContents(path);
            }

            // Server Selection Functions
            let currentServerConfig = null;

            async function showServerSelection(projectPath, configSource, configType, sourceIndex) {
                currentServerConfig = { projectPath, configSource, configType };
                
                try {
                    const response = await fetch(`/api/config-preview?config_path=${encodeURIComponent(configSource)}`);
                    const preview = await response.json();
                    
                    document.getElementById('configInfo').innerHTML = `
                        <strong>Config:</strong> ${configSource}<br>
                        <strong>Total Servers:</strong> ${preview.summary?.total_servers || 'Unknown'}
                    `;
                    
                    let serverHtml = '';
                    if (preview.servers) {
                        Object.entries(preview.servers).forEach(([name, config]) => {
                            serverHtml += `
                                <div style="margin: 8px 0; padding: 8px; border: 1px solid #eee; border-radius: 4px;">
                                    <label>
                                        <input type="checkbox" name="selectedServers" value="${name}" checked>
                                        <strong>${name}</strong> (${config.type || 'unknown'})
                                    </label>
                                    <div style="font-size: 0.8em; color: #666; margin-left: 20px;">
                                        ${config.description || config.command || 'No description'}
                                    </div>
                                </div>
                            `;
                        });
                    } else {
                        serverHtml = '<p>No servers found in configuration</p>';
                    }
                    
                    document.getElementById('serverList').innerHTML = serverHtml;
                    document.getElementById('serverSelector').style.display = 'block';
                    
                } catch (error) {
                    alert('Error loading server configuration: ' + error.message);
                }
            }

            function closeServerSelector() {
                document.getElementById('serverSelector').style.display = 'none';
                currentServerConfig = null;
            }

            async function launchWithServerSelection() {
                if (!currentServerConfig) return;
                
                const filterMode = document.querySelector('input[name="filterMode"]:checked').value;
                const selectedServers = Array.from(document.querySelectorAll('input[name="selectedServers"]:checked'))
                    .map(cb => cb.value);
                
                const launchConfig = {
                    project_path: currentServerConfig.projectPath,
                    config_source: currentServerConfig.configSource,
                    config_type: currentServerConfig.configType,
                    session_name: `${currentServerConfig.projectPath.split('/').pop()}-${Date.now()}`,
                    selected_servers: filterMode === 'all' ? null : selectedServers,
                    server_filter_mode: filterMode
                };
                
                try {
                    const response = await fetch('/api/launch-backend', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(launchConfig)
                    });
                    
                    const data = await response.json();
                    if (response.ok) {
                        alert(`Testing backend launched!\\nSession: ${data.session_id}\\nServers: ${filterMode === 'all' ? 'All' : selectedServers.length + ' selected'}`);
                        closeServerSelector();
                        refreshSessions();
                    } else {
                        alert('Error: ' + data.detail);
                    }
                } catch (error) {
                    alert('Error launching backend: ' + error.message);
                }
            }

            async function scanProjects() {
                const path = document.getElementById('scanPath').value || '.';
                try {
                    const response = await fetch(`/api/scan-projects?path=${encodeURIComponent(path)}`);
                    const data = await response.json();
                    displayProjects(data.projects);
                } catch (error) {
                    document.getElementById('projectResults').innerHTML = 
                        '<p style="color: red;">Error scanning projects: ' + error.message + '</p>';
                }
            }

            function displayProjects(projects) {
                const resultsDiv = document.getElementById('projectResults');
                if (projects.length === 0) {
                    resultsDiv.innerHTML = '<p>No projects with MCP configurations found.</p>';
                    return;
                }

                let html = '<h3>Found ' + projects.length + ' project(s)</h3>';
                projects.forEach(project => {
                    html += `
                        <div class="project-card">
                            <h4>📂 ${project.name}</h4>
                            <p><strong>Path:</strong> ${project.path}</p>
                            ${project.description ? '<p><strong>Description:</strong> ' + project.description + '</p>' : ''}
                            <div>
                                <strong>Config Sources:</strong>
                                ${project.config_sources.map((source, idx) => 
                                    '<div class="config-source">' + 
                                    source.type + ': ' + source.path + 
                                    ` (${source.server_count} servers: ${source.servers.slice(0,3).join(', ')}${source.servers.length > 3 ? '...' : ''})` +
                                    ' <button onclick="showServerSelection(\\''+project.path+'\\', \\''+source.path+'\\', \\''+source.type+'\\', '+idx+')">🎛️ Configure & Launch</button>' +
                                    ' <button onclick="launchProject(\\''+project.path+'\\', \\''+source.path+'\\', \\''+source.type+'\\')">🚀 Quick Launch</button>' +
                                    '</div>'
                                ).join('')}
                            </div>
                        </div>
                    `;
                });
                resultsDiv.innerHTML = html;
            }

            async function launchProject(projectPath, configSource, configType) {
                try {
                    const response = await fetch('/api/launch-backend', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            project_path: projectPath,
                            config_source: configSource,
                            config_type: configType,
                            session_name: `${projectPath.split('/').pop()}-${Date.now()}`
                        })
                    });
                    const data = await response.json();
                    if (response.ok) {
                        alert('Testing backend launched! Session: ' + data.session_id);
                        refreshSessions();
                    } else {
                        alert('Error: ' + data.detail);
                    }
                } catch (error) {
                    alert('Error launching backend: ' + error.message);
                }
            }

            async function launchManual() {
                const projectPath = document.getElementById('manualProjectPath').value;
                const configSource = document.getElementById('manualConfigSource').value;
                const configType = document.getElementById('manualConfigType').value;
                
                if (!projectPath || !configSource) {
                    alert('Please fill in both project path and config source');
                    return;
                }
                
                await launchProject(projectPath, configSource, configType);
            }

            async function refreshSessions() {
                try {
                    const [sessionsResponse, healthResponse] = await Promise.all([
                        fetch('/api/sessions'),
                        fetch('/api/health')
                    ]);
                    
                    const sessionsData = await sessionsResponse.json();
                    const healthData = await healthResponse.json();
                    
                    displaySessions(sessionsData.sessions, healthData);
                } catch (error) {
                    document.getElementById('activeSessions').innerHTML = 
                        '<p style="color: red;">Error loading sessions: ' + error.message + '</p>';
                }
            }

            function displaySessions(sessions) {
                const sessionsDiv = document.getElementById('activeSessions');
                if (sessions.length === 0) {
                    sessionsDiv.innerHTML = '<p>No active testing sessions.</p>';
                    return;
                }

                let html = '';
                sessions.forEach(session => {
                    const statusClass = session.status === 'running' ? 'status-running' : 'status-stopped';
                    html += `
                        <div class="project-card ${session.status === 'running' ? 'session-active' : ''}">
                            <h4>🎮 ${session.session_id}</h4>
                            <p><strong>Project:</strong> ${session.project_path}</p>
                            <p><strong>Config:</strong> ${session.config_source}</p>
                            <p><strong>Status:</strong> <span class="status ${statusClass}">${session.status.toUpperCase()}</span></p>
                            ${session.backend_url ? '<p><strong>Backend:</strong> <a href="' + session.backend_url + '" target="_blank">' + session.backend_url + '</a></p>' : ''}
                            <p><strong>Created:</strong> ${new Date(session.created_at).toLocaleString()}</p>
                            <div>
                                ${session.status === 'running' ? 
                                    '<button onclick="stopSession(\\''+session.session_id+'\\')">Stop Session</button>' + 
                                    '<button onclick="openBackend(\\''+session.backend_url+'\\')">Open Testing Interface</button>' :
                                    '<button onclick="removeSession(\\''+session.session_id+'\\')">Remove</button>'
                                }
                            </div>
                        </div>
                    `;
                });
                sessionsDiv.innerHTML = html;
            }

            async function stopSession(sessionId) {
                try {
                    const response = await fetch(`/api/sessions/${sessionId}/stop`, {method: 'POST'});
                    const data = await response.json();
                    alert(data.message);
                    refreshSessions();
                } catch (error) {
                    alert('Error stopping session: ' + error.message);
                }
            }

            async function removeSession(sessionId) {
                try {
                    const response = await fetch(`/api/sessions/${sessionId}`, {method: 'DELETE'});
                    const data = await response.json();
                    refreshSessions();
                } catch (error) {
                    alert('Error removing session: ' + error.message);
                }
            }

            function openBackend(url) {
                if (url) {
                    window.open(url, '_blank');
                }
            }

            // Auto-refresh sessions every 30 seconds
            setInterval(refreshSessions, 30000);
            
            // Load initial data
            window.onload = function() {
                refreshSessions();
                scanProjects();
            };

            // =============================================================================
            // MCP POSTMAN FUNCTIONALITY
            // =============================================================================
            
            let currentMCPSession = null;
            let currentMCPServers = [];
            
            // Open/Close MCP Postman Modal
            function openMCPPostman() {
                document.getElementById('mcpPostmanModal').style.display = 'block';
                refreshMCPSessions();
            }
            
            function closeMCPPostman() {
                document.getElementById('mcpPostmanModal').style.display = 'none';
            }
            
            // Session Management
            async function refreshMCPSessions() {
                try {
                    const response = await fetch('/api/sessions');
                    const data = await response.json();
                    
                    const select = document.getElementById('mcpSessionSelect');
                    select.innerHTML = '<option value="">Choose a session...</option>';
                    
                    data.sessions.forEach(session => {
                        if (session.status === 'running') {
                            const option = document.createElement('option');
                            option.value = session.session_id;
                            option.textContent = `${session.session_id} - ${session.project_path} (${session.backend_url})`;
                            select.appendChild(option);
                        }
                    });
                    
                } catch (error) {
                    console.error('Failed to refresh MCP sessions:', error);
                    showMCPError('Failed to load sessions: ' + error.message);
                }
            }
            
            // Server Discovery
            async function loadMCPServers() {
                const sessionId = document.getElementById('mcpSessionSelect').value;
                if (!sessionId) {
                    document.getElementById('mcpServersList').innerHTML = '<p style="color: #666;">Select a session to discover MCP servers</p>';
                    document.getElementById('mcpToolsList').innerHTML = '<p style="color: #666;">Select a server to view available tools</p>';
                    return;
                }
                
                currentMCPSession = sessionId;
                
                try {
                    // Find the session to get its backend URL
                    const sessionsResponse = await fetch('/api/sessions');
                    const sessionsData = await sessionsResponse.json();
                    
                    const session = sessionsData.sessions.find(s => s.session_id === sessionId);
                    if (!session) {
                        throw new Error('Session not found');
                    }
                    
                    const backendUrl = session.backend_url;
                    
                    // Discover MCP servers from the backend
                    const response = await fetch(`${backendUrl}/api/mcp/discover`);
                    const data = await response.json();
                    
                    currentMCPServers = data.servers;
                    displayMCPServers(data.servers);
                    
                } catch (error) {
                    console.error('Failed to load MCP servers:', error);
                    showMCPError('Failed to discover MCP servers: ' + error.message);
                }
            }
            
            function displayMCPServers(servers) {
                const container = document.getElementById('mcpServersList');
                
                if (!servers || servers.length === 0) {
                    container.innerHTML = '<p style="color: #666;">No MCP servers found</p>';
                    return;
                }
                
                let html = '';
                servers.forEach(server => {
                    const statusColor = server.status === 'discoverable' ? '#4CAF50' : 
                                       server.status === 'error' ? '#f44336' : '#ff9800';
                    
                    html += `
                        <div style="padding: 10px; margin: 5px 0; border: 1px solid #ddd; border-radius: 5px; cursor: pointer; background: #fff;"
                             onclick="selectMCPServer('${server.name}')">
                            <div style="font-weight: bold; color: #333;">${server.name}</div>
                            <div style="font-size: 0.9em; color: ${statusColor};">● ${server.status.toUpperCase()}</div>
                            <div style="font-size: 0.8em; color: #666;">${server.description || 'No description'}</div>
                            ${server.type ? `<div style="font-size: 0.8em; color: #999;">Type: ${server.type}</div>` : ''}
                        </div>
                    `;
                });
                
                container.innerHTML = html;
            }
            
            // Tool Discovery
            async function selectMCPServer(serverName) {
                try {
                    // Highlight selected server
                    document.querySelectorAll('#mcpServersList > div').forEach(div => {
                        div.style.background = '#fff';
                    });
                    event.target.style.background = '#e3f2fd';
                    
                    // Load tools for this server
                    const session = await getCurrentMCPSession();
                    const response = await fetch(`${session.backend_url}/api/mcp/tools/${serverName}`);
                    const data = await response.json();
                    
                    displayMCPTools(serverName, data.tools);
                    
                    // Set server in tester
                    document.getElementById('testServerName').value = serverName;
                    
                } catch (error) {
                    console.error('Failed to load tools for server:', serverName, error);
                    showMCPError(`Failed to load tools for ${serverName}: ` + error.message);
                }
            }
            
            function displayMCPTools(serverName, tools) {
                const container = document.getElementById('mcpToolsList');
                
                if (!tools || tools.length === 0) {
                    container.innerHTML = `<p style="color: #666;">No tools found for ${serverName}</p>`;
                    return;
                }
                
                let html = `<div style="margin-bottom: 10px;"><strong>Tools for ${serverName}:</strong></div>`;
                
                tools.forEach(tool => {
                    html += `
                        <div style="padding: 8px; margin: 3px 0; border: 1px solid #ddd; border-radius: 3px; cursor: pointer; background: #fff;"
                             onclick="selectMCPTool('${serverName}', '${tool.name}', ${JSON.stringify(tool.schema).replace(/"/g, '&quot;')})">
                            <div style="font-weight: bold; color: #333;">${tool.name}</div>
                            <div style="font-size: 0.8em; color: #666;">${tool.description || 'No description'}</div>
                        </div>
                    `;
                });
                
                container.innerHTML = html;
            }
            
            // Tool Testing
            function selectMCPTool(serverName, toolName, schema) {
                document.getElementById('testServerName').value = serverName;
                document.getElementById('testToolName').value = toolName;
                
                // Generate sample arguments from schema
                if (schema && schema.properties) {
                    const sampleArgs = {};
                    for (const [key, prop] of Object.entries(schema.properties)) {
                        if (prop.type === 'string') {
                            sampleArgs[key] = prop.description ? `"${prop.description}"` : '"sample_value"';
                        } else if (prop.type === 'number') {
                            sampleArgs[key] = 123;
                        } else if (prop.type === 'boolean') {
                            sampleArgs[key] = true;
                        } else {
                            sampleArgs[key] = prop.type === 'array' ? [] : {};
                        }
                    }
                    document.getElementById('testArguments').value = JSON.stringify(sampleArgs, null, 2);
                }
                
                // Highlight selected tool
                document.querySelectorAll('#mcpToolsList > div:not(:first-child)').forEach(div => {
                    div.style.background = '#fff';
                });
                event.target.style.background = '#e8f5e8';
            }
            
            async function executeMCPTool() {
                const serverName = document.getElementById('testServerName').value;
                const toolName = document.getElementById('testToolName').value;
                const argumentsText = document.getElementById('testArguments').value;
                const description = document.getElementById('testDescription').value;
                
                if (!serverName || !toolName) {
                    showMCPError('Please select a server and tool first');
                    return;
                }
                
                let arguments_obj;
                try {
                    arguments_obj = argumentsText ? JSON.parse(argumentsText) : {};
                } catch (e) {
                    showMCPError('Invalid JSON in arguments: ' + e.message);
                    return;
                }
                
                try {
                    const session = await getCurrentMCPSession();
                    
                    const response = await fetch(`${session.backend_url}/api/mcp/call-tool/${serverName}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            tool_name: toolName,
                            arguments: arguments_obj,
                            description: description
                        })
                    });
                    
                    const result = await response.json();
                    displayMCPResult(result);
                    
                    // Refresh history
                    setTimeout(refreshMCPHistory, 500);
                    
                } catch (error) {
                    console.error('Tool execution failed:', error);
                    showMCPError('Tool execution failed: ' + error.message);
                }
            }
            
            function displayMCPResult(result) {
                const container = document.getElementById('mcpResults');
                
                const statusColor = result.status.includes('success') ? '#4CAF50' : 
                                   result.status === 'error' ? '#f44336' : '#ff9800';
                
                let html = `
                    <div style="border: 1px solid #ddd; border-radius: 5px; padding: 15px; background: #fff;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                            <div style="font-weight: bold; color: #333;">
                                ${result.server_name}.${result.tool_name}
                            </div>
                            <div style="color: ${statusColor}; font-weight: bold;">
                                ${result.status.toUpperCase()}
                            </div>
                        </div>
                        
                        ${result.timing ? `
                            <div style="font-size: 0.9em; color: #666; margin-bottom: 10px;">
                                Duration: ${result.timing.duration_ms}ms | 
                                Request ID: ${result.request_id}
                            </div>
                        ` : ''}
                        
                        <div style="margin-bottom: 10px;">
                            <strong>Result:</strong>
                            <pre style="background: #f5f5f5; padding: 10px; border-radius: 3px; white-space: pre-wrap; font-family: monospace; max-height: 300px; overflow-y: auto;">${JSON.stringify(result.result, null, 2)}</pre>
                        </div>
                        
                        ${result.log_entries && result.log_entries.length > 0 ? `
                            <details style="margin-top: 10px;">
                                <summary style="cursor: pointer; font-weight: bold;">Execution Log (${result.log_entries.length} entries)</summary>
                                <div style="margin-top: 5px;">
                                    ${result.log_entries.map(entry => `
                                        <div style="font-size: 0.8em; margin: 2px 0;">
                                            <span style="color: #666;">[${entry.timestamp}]</span>
                                            <span style="color: ${entry.level === 'error' ? '#f44336' : entry.level === 'success' ? '#4CAF50' : '#333'};">
                                                ${entry.level.toUpperCase()}:
                                            </span>
                                            ${entry.message}
                                        </div>
                                    `).join('')}
                                </div>
                            </details>
                        ` : ''}
                    </div>
                `;
                
                container.innerHTML = html;
            }
            
            async function generateSampleRequest() {
                const serverName = document.getElementById('testServerName').value;
                const toolName = document.getElementById('testToolName').value;
                
                if (!serverName || !toolName) {
                    showMCPError('Please select a server and tool first');
                    return;
                }
                
                try {
                    const session = await getCurrentMCPSession();
                    
                    const response = await fetch(`${session.backend_url}/api/mcp/generate-sample/${serverName}/${toolName}`);
                    const data = await response.json();
                    
                    if (data.sample_request) {
                        document.getElementById('testArguments').value = JSON.stringify(data.sample_request.arguments, null, 2);
                        if (data.sample_request.description) {
                            document.getElementById('testDescription').value = data.sample_request.description;
                        }
                    }
                    
                } catch (error) {
                    console.error('Sample generation failed:', error);
                    showMCPError('Sample generation failed: ' + error.message);
                }
            }
            
            function clearToolTester() {
                document.getElementById('testServerName').value = '';
                document.getElementById('testToolName').value = '';
                document.getElementById('testArguments').value = '';
                document.getElementById('testDescription').value = '';
                document.getElementById('mcpResults').innerHTML = '<p style="color: #666;">Execute a tool to see results here</p>';
            }
            
            // History Management
            async function refreshMCPHistory() {
                try {
                    const session = await getCurrentMCPSession();
                    if (!session) {
                        document.getElementById('mcpHistory').innerHTML = '<p style="color: #666;">Select a session to view history</p>';
                        return;
                    }
                    
                    const response = await fetch(`${session.backend_url}/api/mcp/history`);
                    const data = await response.json();
                    
                    displayMCPHistory(data.requests);
                    
                } catch (error) {
                    console.error('Failed to refresh history:', error);
                    showMCPError('Failed to load history: ' + error.message);
                }
            }
            
            function displayMCPHistory(requests) {
                const container = document.getElementById('mcpHistory');
                
                if (!requests || requests.length === 0) {
                    container.innerHTML = '<p style="color: #666;">No requests in history</p>';
                    return;
                }
                
                let html = '';
                requests.reverse().forEach(req => {
                    const statusColor = req.status.includes('success') ? '#4CAF50' : 
                                       req.status === 'error' ? '#f44336' : '#ff9800';
                    
                    html += `
                        <div style="padding: 8px; margin: 3px 0; border: 1px solid #ddd; border-radius: 3px; background: #fff; cursor: pointer;"
                             onclick="loadHistoryRequest('${req.request_id}', ${JSON.stringify(req).replace(/"/g, '&quot;')})">
                            <div style="display: flex; justify-content: between; align-items: center;">
                                <div style="flex: 1;">
                                    <span style="font-weight: bold;">${req.server_name}.${req.tool_name}</span>
                                    <span style="color: ${statusColor}; margin-left: 10px;">● ${req.status}</span>
                                </div>
                                <div style="font-size: 0.8em; color: #666;">
                                    ${req.timing ? req.timing.duration_ms + 'ms' : ''} | ${req.request_id}
                                </div>
                            </div>
                        </div>
                    `;
                });
                
                container.innerHTML = html;
            }
            
            function loadHistoryRequest(requestId, requestData) {
                const req = JSON.parse(requestData.replace(/&quot;/g, '"'));
                
                document.getElementById('testServerName').value = req.server_name;
                document.getElementById('testToolName').value = req.tool_name;
                document.getElementById('testArguments').value = JSON.stringify(req.arguments, null, 2);
                document.getElementById('testDescription').value = req.description || '';
                
                displayMCPResult(req);
            }
            
            async function clearMCPHistory() {
                if (!confirm('Clear all request history?')) return;
                
                try {
                    const session = await getCurrentMCPSession();
                    await fetch(`${session.backend_url}/api/mcp/history`, { method: 'DELETE' });
                    
                    document.getElementById('mcpHistory').innerHTML = '<p style="color: #666;">History cleared</p>';
                    
                } catch (error) {
                    console.error('Failed to clear history:', error);
                    showMCPError('Failed to clear history: ' + error.message);
                }
            }
            
            // Utility Functions
            async function getCurrentMCPSession() {
                if (!currentMCPSession) {
                    throw new Error('No MCP session selected');
                }
                
                const response = await fetch('/api/sessions');
                const data = await response.json();
                
                const session = data.sessions.find(s => s.session_id === currentMCPSession);
                if (!session) {
                    throw new Error('Selected session not found');
                }
                
                return session;
            }
            
            function showMCPError(message) {
                const container = document.getElementById('mcpResults');
                container.innerHTML = `
                    <div style="padding: 15px; background: #ffebee; border: 1px solid #f44336; border-radius: 5px; color: #c62828;">
                        <strong>Error:</strong> ${message}
                    </div>
                `;
            }
        </script>
    </body>
    </html>
    """

@app.get("/api/browse-folders")
async def browse_folders(path: str = "."):
    """Browse directories for folder selection"""
    try:
        import os
        from pathlib import Path
        
        base_path = Path(path).resolve()
        if not base_path.exists() or not base_path.is_dir():
            raise HTTPException(status_code=400, detail="Invalid directory path")
        
        folders = []
        
        # Add parent directory option (unless at root)
        if base_path.parent != base_path:
            folders.append({
                "name": "..",
                "path": str(base_path.parent),
                "type": "parent"
            })
        
        # List subdirectories
        try:
            for item in sorted(base_path.iterdir()):
                if item.is_dir() and not item.name.startswith('.'):
                    # Check if it looks like a project directory
                    has_mcp_config = any(
                        (item / config).exists() 
                        for config in [".mcp.json", "mcp.json", ".claude.json", "package.json"]
                    )
                    
                    folders.append({
                        "name": item.name,
                        "path": str(item),
                        "type": "project" if has_mcp_config else "folder",
                        "has_mcp_config": has_mcp_config
                    })
        except PermissionError:
            pass
        
        return {
            "current_path": str(base_path),
            "folders": folders
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error browsing folders: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/scan-projects")
async def scan_projects(path: str = "."):
    """Scan directory for projects with MCP configurations"""
    try:
        projects = await project_scanner.scan_directory(path)
        return {"projects": projects, "scanned_path": path}
    except Exception as e:
        logger.error(f"Error scanning projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config-preview")
async def get_config_preview(config_path: str):
    """Get detailed preview of a configuration file"""
    try:
        preview = await project_scanner.get_config_preview(config_path)
        return preview
    except Exception as e:
        logger.error(f"Error getting config preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/launch-backend")
async def launch_backend(config: LaunchConfig):
    """Launch a testing backend with the specified configuration"""
    try:
        session = await session_manager.launch_session(config)
        return {
            "session_id": session.session_id,
            "backend_url": session.backend_url,
            "status": session.status,
            "message": f"Testing backend launched successfully"
        }
    except Exception as e:
        logger.error(f"Error launching backend: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions")
async def list_sessions():
    """List all testing sessions"""
    sessions = await session_manager.list_sessions()
    return {"sessions": sessions}

@app.post("/api/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    """Stop a testing session"""
    try:
        await session_manager.stop_session(session_id)
        return {"message": f"Session {session_id} stopped successfully"}
    except Exception as e:
        logger.error(f"Error stopping session: {e}")
        raise HTTPException(status_code=404, detail=str(e))

@app.delete("/api/sessions/{session_id}")
async def remove_session(session_id: str):
    """Remove a session from tracking"""
    try:
        await session_manager.remove_session(session_id)
        return {"message": f"Session {session_id} removed"}
    except Exception as e:
        logger.error(f"Error removing session: {e}")
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    sessions = await session_manager.list_sessions()
    active_count = len([s for s in sessions if s["status"] in ["starting", "running"]])
    
    return {
        "status": "healthy",
        "service": "mcp-launcher",
        "version": "2.0.0",
        "total_sessions": len(sessions),
        "active_sessions": active_count,
        "max_concurrent_sessions": session_manager.max_concurrent_sessions,
        "sessions_available": session_manager.max_concurrent_sessions - active_count
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8094)