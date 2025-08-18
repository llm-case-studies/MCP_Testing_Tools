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