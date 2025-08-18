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
            
            /* Adventure Chooser Styles */
            .adventure-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .adventure-tile {
                background: white;
                border: 2px solid #e0e0e0;
                border-radius: 12px;
                padding: 24px;
                cursor: pointer;
                transition: all 0.3s ease;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                position: relative;
                text-align: left;
            }
            .adventure-tile:hover {
                border-color: #2196F3;
                box-shadow: 0 4px 16px rgba(33, 150, 243, 0.2);
                transform: translateY(-2px);
            }
            .tile-icon {
                font-size: 2.5em;
                margin-bottom: 12px;
                display: block;
            }
            .tile-title {
                font-size: 1.4em;
                font-weight: bold;
                color: #333;
                margin-bottom: 6px;
            }
            .tile-subtitle {
                font-size: 1em;
                color: #666;
                margin-bottom: 12px;
                line-height: 1.4;
            }
            .tile-meta {
                font-size: 0.85em;
                color: #888;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 16px;
                font-weight: 500;
            }
            .tile-demo {
                font-size: 0.9em;
                color: #2196F3;
                text-decoration: underline;
                cursor: pointer;
                display: inline-block;
                padding: 4px 0;
                border-radius: 4px;
                transition: color 0.2s ease;
            }
            .tile-demo:hover {
                color: #1976D2;
                background: rgba(33, 150, 243, 0.1);
                padding: 4px 8px;
                text-decoration: none;
            }
            .quick-actions {
                display: flex;
                gap: 12px;
                flex-wrap: wrap;
                justify-content: center;
                padding: 20px 0;
                border-top: 1px solid #eee;
            }
            .advanced-mode-hidden {
                display: none;
            }
            
            /* Mode Toggle Styles */
            .mode-toggle {
                display: flex;
                background: #f5f5f5;
                border-radius: 8px;
                padding: 4px;
                gap: 2px;
            }
            .mode-btn {
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 0.9em;
                font-weight: 500;
                transition: all 0.3s ease;
                background: transparent;
                color: #666;
            }
            .mode-btn:hover {
                background: #e0e0e0;
                color: #333;
            }
            .mode-btn.active {
                background: #2196F3;
                color: white;
                box-shadow: 0 2px 4px rgba(33, 150, 243, 0.3);
            }
            .learning-mode.active {
                background: #4caf50;
                box-shadow: 0 2px 4px rgba(76, 175, 80, 0.3);
            }
            
            /* Learning Mode Specific Styles */
            .learning-tile {
                background: linear-gradient(135deg, #e8f5e8 0%, #f1f8e9 100%);
                border: 2px solid #c8e6c9;
            }
            .learning-tile:hover {
                border-color: #4caf50;
                box-shadow: 0 4px 16px rgba(76, 175, 80, 0.2);
            }
            .learning-tile .tile-icon {
                background: #4caf50;
                color: white;
                width: 60px;
                height: 60px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.8em;
                margin-bottom: 16px;
            }
            .learning-progress {
                background: #e8f5e8;
                border-radius: 12px;
                padding: 8px 12px;
                font-size: 0.8em;
                color: #2e7d32;
                margin-top: 8px;
                display: inline-block;
            }
            
            /* Educational overlays and tooltips */
            .edu-tooltip {
                position: relative;
                display: inline-block;
                cursor: help;
            }
            .edu-tooltip::after {
                content: attr(data-tooltip);
                position: absolute;
                bottom: 125%;
                left: 50%;
                transform: translateX(-50%);
                background: #333;
                color: white;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 0.8em;
                white-space: nowrap;
                opacity: 0;
                visibility: hidden;
                transition: opacity 0.3s;
                z-index: 1000;
            }
            .edu-tooltip:hover::after {
                opacity: 1;
                visibility: visible;
            }
            
            /* Guided highlight for learning */
            .learning-highlight {
                position: relative;
                animation: pulse-border 2s infinite;
            }
            @keyframes pulse-border {
                0% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7); }
                70% { box-shadow: 0 0 0 10px rgba(76, 175, 80, 0); }
                100% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0); }
            }
        </style>
    </head>
    <body>
        <div class="header">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h1>🧪 MCP Testing Suite</h1>
                    <p id="headerSubtitle">Spin up MCP sessions, test tools, monitor servers, and enforce policy—locally.</p>
                </div>
                <div class="mode-toggle">
                    <button id="learningModeBtn" class="mode-btn learning-mode active" onclick="switchToLearningMode()">
                        🎓 Learning Mode
                    </button>
                    <button id="proModeBtn" class="mode-btn pro-mode" onclick="switchToProMode()">
                        ⚡ Pro Mode
                    </button>
                </div>
            </div>
        </div>
        
        <!-- Adventure Chooser -->
        <div class="section">
            <!-- Learning Mode Tiles -->
            <div id="learningModeChooser">
                <div class="adventure-grid">
                    <div class="adventure-tile learning-tile" onclick="startMCPBasics()">
                        <div class="tile-icon">🎓</div>
                        <div class="tile-title">LEARN MCP BASICS</div>
                        <div class="tile-subtitle">What is MCP and why test it?</div>
                        <div class="tile-meta">5-minute interactive tutorial</div>
                        <div class="learning-progress">Start here • 0% complete</div>
                    </div>
                    
                    <div class="adventure-tile learning-tile" onclick="startGuidedTesting()">
                        <div class="tile-icon">🧪</div>
                        <div class="tile-title">GUIDED TESTING</div>
                        <div class="tile-subtitle">Test your first MCP tool step-by-step</div>
                        <div class="tile-meta">Walkthrough with explanations</div>
                        <div class="learning-progress">Beginner • 15 mins</div>
                    </div>
                    
                    <div class="adventure-tile learning-tile" onclick="exploreExamples()">
                        <div class="tile-icon">📚</div>
                        <div class="tile-title">EXPLORE EXAMPLES</div>
                        <div class="tile-subtitle">Real MCP servers with commentary</div>
                        <div class="tile-meta">Curated examples • Best practices</div>
                        <div class="learning-progress">Intermediate • 20 mins</div>
                    </div>
                    
                    <div class="adventure-tile learning-tile" onclick="troubleshootingHelp()">
                        <div class="tile-icon">🔍</div>
                        <div class="tile-title">TROUBLESHOOTING</div>
                        <div class="tile-subtitle">Common issues and solutions</div>
                        <div class="tile-meta">Interactive problem solver</div>
                        <div class="learning-progress">Reference guide</div>
                    </div>
                </div>
                
                <div class="quick-actions">
                    <button onclick="showWhatIsMCP()" class="btn-success">🤔 What is MCP?</button>
                    <button onclick="showLearningPath()" class="btn-secondary">📋 My Learning Path</button>
                    <button onclick="switchToProMode()" class="btn-secondary" style="opacity: 0.7;">Switch to Pro Mode</button>
                </div>
            </div>
            
            <!-- Pro Mode Tiles (Original) -->
            <div id="proModeChooser" style="display: none;">
                <div class="adventure-grid">
                    <div class="adventure-tile" onclick="goToInteractive()">
                        <div class="tile-icon">🧪</div>
                        <div class="tile-title">INTERACTIVE</div>
                        <div class="tile-subtitle">Test MCP tools (Postman-style)</div>
                        <div class="tile-meta" id="interactiveMeta">Ready to start</div>
                        <div class="tile-demo" onclick="event.stopPropagation(); tryDemo('interactive')">Try demo</div>
                    </div>
                    
                    <div class="adventure-tile" onclick="goToAPI()">
                        <div class="tile-icon">🔧</div>
                        <div class="tile-title">API MODE</div>
                        <div class="tile-subtitle">Headless & CI</div>
                        <div class="tile-meta" id="apiMeta">REST ready at /api</div>
                        <div class="tile-demo" onclick="event.stopPropagation(); tryDemo('api')">Try demo</div>
                    </div>
                    
                    <div class="adventure-tile" onclick="goToMonitoring()">
                        <div class="tile-icon">📊</div>
                        <div class="tile-title">MONITORING</div>
                        <div class="tile-subtitle">Health & performance</div>
                        <div class="tile-meta" id="monitoringMeta">0 sessions running</div>
                        <div class="tile-demo" onclick="event.stopPropagation(); tryDemo('monitoring')">Try demo</div>
                    </div>
                    
                    <div class="adventure-tile" onclick="goToEnterprise()">
                        <div class="tile-icon">🔒</div>
                        <div class="tile-title">ENTERPRISE</div>
                        <div class="tile-subtitle">Security & policy</div>
                        <div class="tile-meta" id="enterpriseMeta">Policy: OFF</div>
                        <div class="tile-demo" onclick="event.stopPropagation(); tryDemo('enterprise')">Try demo</div>
                    </div>
                </div>
                
                <div class="quick-actions">
                    <button onclick="resumeLastSession()" class="btn-secondary">Resume last session</button>
                    <button onclick="selectProjectFolder()" class="btn-secondary">Select project folder</button>
                    <button onclick="showAdvancedMode()" class="btn-secondary" style="opacity: 0.7;">Advanced mode</button>
                </div>
            </div>
        </div>

        <div class="section advanced-mode-hidden" id="projectScanner">
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

        <div class="section advanced-mode-hidden" id="activeSessions">
            <h2>🎮 Active Testing Sessions</h2>
            <div id="activeSessions"></div>
        </div>

        <div class="section advanced-mode-hidden" id="manualLaunch">
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
            
            <!-- What is MCP? Educational Modal -->
            <div id="whatIsMCPModal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 2000;">
                <div style="background: white; margin: 3% auto; padding: 30px; width: 90%; max-width: 800px; border-radius: 12px; max-height: 85vh; overflow-y: auto;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px;">
                        <h2>🤔 What is MCP? (Model Context Protocol)</h2>
                        <button onclick="closeWhatIsMCPModal()" class="btn-secondary">✕ Close</button>
                    </div>
                    
                    <div class="mcp-explanation">
                        <div style="background: #e3f2fd; padding: 20px; border-radius: 8px; margin-bottom: 20px; text-align: center;">
                            <h3 style="margin-top: 0; color: #1976d2;">🧠 Think of MCP like this...</h3>
                            <p style="font-size: 1.1em; margin: 0;"><strong>MCP is like having superpowers for AI assistants!</strong></p>
                        </div>
                        
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                            <div style="background: #f9f9f9; padding: 16px; border-radius: 8px;">
                                <h4>🔧 Without MCP</h4>
                                <p>AI can only talk to you. It can't read files, search the web, or interact with your tools.</p>
                                <p style="color: #666; font-style: italic;">"Sorry, I can't actually check your files..."</p>
                            </div>
                            <div style="background: #e8f5e8; padding: 16px; border-radius: 8px;">
                                <h4>⚡ With MCP</h4>
                                <p>AI can use "tools" to read files, search the web, manage GitHub, and much more!</p>
                                <p style="color: #2e7d32; font-style: italic;">"Let me check your files and help fix that bug!"</p>
                            </div>
                        </div>
                        
                        <div style="margin-bottom: 25px;">
                            <h3>🎯 Real Examples:</h3>
                            <ul style="font-size: 1.05em; line-height: 1.6;">
                                <li><strong>📁 Filesystem MCP:</strong> AI can read, write, and organize your files</li>
                                <li><strong>🔍 Web Search MCP:</strong> AI can search the internet for current info</li>
                                <li><strong>💻 GitHub MCP:</strong> AI can create issues, review code, manage repos</li>
                                <li><strong>📊 Database MCP:</strong> AI can query and update databases</li>
                                <li><strong>🌐 API MCP:</strong> AI can call any REST API or web service</li>
                            </ul>
                        </div>
                        
                        <div style="background: #fff3e0; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                            <h3 style="margin-top: 0; color: #ef6c00;">🧪 Why Test MCP Tools?</h3>
                            <p><strong>Before giving AI superpowers, you want to make sure they work correctly!</strong></p>
                            <ul>
                                <li>Test that your MCP tools work as expected</li>
                                <li>Debug issues before AI uses them</li>
                                <li>Understand what capabilities you're giving to AI</li>
                                <li>Ensure security and performance</li>
                            </ul>
                        </div>
                        
                        <div style="text-align: center; padding: 20px 0;">
                            <p style="font-size: 1.2em; margin-bottom: 20px;"><strong>Ready to start testing?</strong></p>
                            <button onclick="startMCPBasics()" class="btn-success" style="margin-right: 10px; padding: 12px 24px;">🎓 Start Learning</button>
                            <button onclick="startGuidedTesting()" class="btn-success" style="padding: 12px 24px;">🧪 Start Testing</button>
                        </div>
                    </div>
                </div>
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
            
            // =============================================================================
            // LEARNING/PRO MODE SYSTEM - Educational Experience
            // =============================================================================
            
            let isLearningMode = true; // Default to learning mode for new users
            let learningProgress = {
                mcpBasics: 0,
                guidedTesting: 0,
                examples: 0,
                troubleshooting: 0
            };
            
            // Mode switching functions
            function switchToLearningMode() {
                console.log('🎓 Switching to Learning Mode...');
                isLearningMode = true;
                
                // Update toggle buttons
                document.getElementById('learningModeBtn').classList.add('active');
                document.getElementById('proModeBtn').classList.remove('active');
                
                // Update header
                document.getElementById('headerSubtitle').textContent = 
                    'Learn MCP step-by-step with guided tutorials and examples';
                
                // Show learning chooser, hide pro chooser
                document.getElementById('learningModeChooser').style.display = 'block';
                document.getElementById('proModeChooser').style.display = 'none';
                
                // Update learning progress
                updateLearningProgress();
            }
            
            function switchToProMode() {
                console.log('⚡ Switching to Pro Mode...');
                isLearningMode = false;
                
                // Update toggle buttons
                document.getElementById('proModeBtn').classList.add('active');
                document.getElementById('learningModeBtn').classList.remove('active');
                
                // Update header
                document.getElementById('headerSubtitle').textContent = 
                    'Spin up MCP sessions, test tools, monitor servers, and enforce policy—locally.';
                
                // Show pro chooser, hide learning chooser
                document.getElementById('proModeChooser').style.display = 'block';
                document.getElementById('learningModeChooser').style.display = 'none';
                
                // Update pro stats
                updateAdventureTileStats();
            }
            
            // =============================================================================
            // EDUCATIONAL CONTENT FUNCTIONS
            // =============================================================================
            
            // What is MCP? Modal functions
            function showWhatIsMCP() {
                console.log('🤔 Showing "What is MCP?" modal...');
                document.getElementById('whatIsMCPModal').style.display = 'block';
            }
            
            function closeWhatIsMCPModal() {
                document.getElementById('whatIsMCPModal').style.display = 'none';
            }
            
            // Learning mode tile functions
            function startMCPBasics() {
                console.log('🎓 Starting MCP Basics tutorial...');
                
                // Show engaging teaser first
                showMCPBasicsTeaser();
            }
            
            function showMCPBasicsTeaser() {
                // Create a quick teaser modal
                const teaserHTML = `
                    <div id="mcpBasicsTeaser" style="display: block; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 2000;">
                        <div style="background: linear-gradient(135deg, #4caf50 0%, #66bb6a 100%); margin: 10% auto; padding: 40px; width: 90%; max-width: 600px; border-radius: 16px; text-align: center; color: white; box-shadow: 0 8px 32px rgba(0,0,0,0.3);">
                            <div style="font-size: 3em; margin-bottom: 20px;">🧠✨</div>
                            <h2 style="margin: 0 0 15px 0; color: white;">MCP = AI Superpowers!</h2>
                            <p style="font-size: 1.2em; margin-bottom: 25px; opacity: 0.9;">In 5 minutes, you'll understand how MCP gives AI assistants the ability to actually DO things - read files, search the web, manage code, and much more!</p>
                            
                            <div style="background: rgba(255,255,255,0.1); padding: 20px; border-radius: 12px; margin: 20px 0;">
                                <p style="margin: 0; font-size: 1.1em;"><strong>🎯 What you'll learn:</strong></p>
                                <p style="margin: 10px 0 0 0;">✅ What MCP is (in plain English)<br>
                                ✅ Why it's revolutionary for AI<br>
                                ✅ Real examples you can try instantly</p>
                            </div>
                            
                            <div style="margin-top: 30px;">
                                <button onclick="beginMCPBasics()" style="background: white; color: #4caf50; border: none; padding: 15px 30px; border-radius: 8px; font-size: 1.1em; font-weight: bold; margin-right: 15px; cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.2);">🚀 Let's Go!</button>
                                <button onclick="closeMCPBasicsTeaser()" style="background: transparent; color: white; border: 2px solid rgba(255,255,255,0.3); padding: 15px 30px; border-radius: 8px; font-size: 1.1em; cursor: pointer;">Maybe Later</button>
                            </div>
                        </div>
                    </div>
                `;
                
                document.body.insertAdjacentHTML('beforeend', teaserHTML);
            }
            
            function closeMCPBasicsTeaser() {
                const teaser = document.getElementById('mcpBasicsTeaser');
                if (teaser) teaser.remove();
            }
            
            function beginMCPBasics() {
                closeMCPBasicsTeaser();
                showWhatIsMCP();
                
                // Mark progress
                learningProgress.mcpBasics = 25;
                updateLearningProgressWithTransition();
                
                // Add completion flow
                setTimeout(() => {
                    showMCPBasicsCompletion();
                }, 8000); // After they've had time to read the modal
            }
            
            function showMCPBasicsCompletion() {
                if (confirm('🎉 Great! Now you understand what MCP is!\\n\\n Ready to test your first MCP tool? This is where it gets really fun!')) {
                    closeWhatIsMCPModal();
                    startGuidedTesting();
                } else {
                    showMessage('success', '✅ MCP Basics completed! You can continue anytime from the Learning Mode dashboard.');
                    learningProgress.mcpBasics = 100;
                    updateLearningProgressWithTransition();
                }
            }
            
            function startGuidedTesting() {
                console.log('🧪 Starting guided testing...');
                
                // Open MCP Postman with educational overlays
                openMCPPostman();
                
                // Add learning highlights and guidance
                setTimeout(() => {
                    addLearningGuidance();
                }, 1000);
                
                // Mark progress
                learningProgress.guidedTesting = 50;
                updateLearningProgressWithTransition();
                
                showMessage('success', '🧪 Great! You\\'ve opened the MCP Tool Tester. Look for the green highlights - they\\'ll guide you through your first test!');
            }
            
            function exploreExamples() {
                console.log('📚 Exploring examples...');
                
                // Show engaging teaser first
                showExploreExamplesTeaser();
            }
            
            function showExploreExamplesTeaser() {
                const teaserHTML = `
                    <div id="exploreExamplesTeaser" style="display: block; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 2000;">
                        <div style="background: linear-gradient(135deg, #ff9800 0%, #ffb74d 100%); margin: 10% auto; padding: 40px; width: 90%; max-width: 600px; border-radius: 16px; text-align: center; color: white; box-shadow: 0 8px 32px rgba(0,0,0,0.3);">
                            <div style="font-size: 3em; margin-bottom: 20px;">📚🌟</div>
                            <h2 style="margin: 0 0 15px 0; color: white;">Real-World Examples!</h2>
                            <p style="font-size: 1.2em; margin-bottom: 25px; opacity: 0.9;">See MCP in action with curated examples from actual projects! Each example includes detailed explanations and is ready to run instantly.</p>
                            
                            <div style="background: rgba(255,255,255,0.1); padding: 20px; border-radius: 12px; margin: 20px 0;">
                                <p style="margin: 0; font-size: 1.1em;"><strong>🎯 Example categories:</strong></p>
                                <p style="margin: 10px 0 0 0;">🔍 Web scraping & search tools<br>
                                📁 File system operations<br>
                                🤖 AI assistance integrations</p>
                            </div>
                            
                            <div style="margin-top: 30px;">
                                <button onclick="beginExploreExamples()" style="background: white; color: #ff9800; border: none; padding: 15px 30px; border-radius: 8px; font-size: 1.1em; font-weight: bold; margin-right: 15px; cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.2);">🚀 Show Examples!</button>
                                <button onclick="closeExploreExamplesTeaser()" style="background: transparent; color: white; border: 2px solid rgba(255,255,255,0.3); padding: 15px 30px; border-radius: 8px; font-size: 1.1em; cursor: pointer;">Maybe Later</button>
                            </div>
                        </div>
                    </div>
                `;
                
                document.body.insertAdjacentHTML('beforeend', teaserHTML);
            }
            
            function closeExploreExamplesTeaser() {
                const teaser = document.getElementById('exploreExamplesTeaser');
                if (teaser) teaser.remove();
            }
            
            function beginExploreExamples() {
                closeExploreExamplesTeaser();
                showMessage('info', '📚 Opening curated examples with detailed explanations...');
                
                // Open MCP Postman with example data pre-loaded
                openMCPPostman();
                setTimeout(() => {
                    populateEducationalExamples();
                }, 500);
                
                // Mark progress  
                learningProgress.examples = 75;
                updateLearningProgressWithTransition();
            }
            
            function troubleshootingHelp() {
                console.log('🔍 Opening troubleshooting help...');
                
                // Show engaging teaser first
                showTroubleshootingTeaser();
            }
            
            function showTroubleshootingTeaser() {
                const teaserHTML = `
                    <div id="troubleshootingTeaser" style="display: block; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 2000;">
                        <div style="background: linear-gradient(135deg, #9c27b0 0%, #ba68c8 100%); margin: 10% auto; padding: 40px; width: 90%; max-width: 600px; border-radius: 16px; text-align: center; color: white; box-shadow: 0 8px 32px rgba(0,0,0,0.3);">
                            <div style="font-size: 3em; margin-bottom: 20px;">🔍🛠️</div>
                            <h2 style="margin: 0 0 15px 0; color: white;">Troubleshooting Made Easy!</h2>
                            <p style="font-size: 1.2em; margin-bottom: 25px; opacity: 0.9;">Stuck? Don't worry! I've got solutions for the most common MCP setup and testing issues. Most problems have simple fixes!</p>
                            
                            <div style="background: rgba(255,255,255,0.1); padding: 20px; border-radius: 12px; margin: 20px 0;">
                                <p style="margin: 0; font-size: 1.1em;"><strong>🎯 Common fixes for:</strong></p>
                                <p style="margin: 10px 0 0 0;">🔗 Connection problems<br>
                                ⚙️ Configuration issues<br>
                                🐛 Error message explanations</p>
                            </div>
                            
                            <div style="margin-top: 30px;">
                                <button onclick="beginTroubleshooting()" style="background: white; color: #9c27b0; border: none; padding: 15px 30px; border-radius: 8px; font-size: 1.1em; font-weight: bold; margin-right: 15px; cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.2);">🚀 Get Help!</button>
                                <button onclick="closeTroubleshootingTeaser()" style="background: transparent; color: white; border: 2px solid rgba(255,255,255,0.3); padding: 15px 30px; border-radius: 8px; font-size: 1.1em; cursor: pointer;">Maybe Later</button>
                            </div>
                        </div>
                    </div>
                `;
                
                document.body.insertAdjacentHTML('beforeend', teaserHTML);
            }
            
            function closeTroubleshootingTeaser() {
                const teaser = document.getElementById('troubleshootingTeaser');
                if (teaser) teaser.remove();
            }
            
            function beginTroubleshooting() {
                closeTroubleshootingTeaser();
                showTroubleshootingGuide();
                
                // Mark progress
                learningProgress.troubleshooting = 100;
                updateLearningProgressWithTransition();
            }
            
            function showLearningPath() {
                console.log('📋 Showing learning path...');
                const completedCount = Object.values(learningProgress).filter(p => p > 0).length;
                const totalTopics = Object.keys(learningProgress).length;
                
                showMessage('info', \`📋 Your Learning Progress:\\n\\n✅ Completed: \${completedCount}/\${totalTopics} topics\\n📈 Keep going! Each topic builds on the previous one.\`);
            }
            
            // =============================================================================
            // LEARNING TO PRO TRANSITION SYSTEM
            // =============================================================================
            
            function checkLearningCompletion() {
                console.log('🎯 Checking learning completion...');
                const progressValues = Object.values(learningProgress);
                const completedTopics = progressValues.filter(p => p >= 75).length;
                const totalTopics = progressValues.length;
                
                // If user has completed most learning topics, offer Pro Mode transition
                if (completedTopics >= Math.floor(totalTopics * 0.7) && !localStorage.getItem('hasSeenProModeTransition')) {
                    setTimeout(() => {
                        showProModeTransition();
                    }, 2000);
                    localStorage.setItem('hasSeenProModeTransition', 'true');
                }
            }
            
            function showProModeTransition() {
                const teaserHTML = `
                    <div id="proModeTransition" style="display: block; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 2500;">
                        <div style="background: linear-gradient(135deg, #1a237e 0%, #3949ab 50%, #5c6bc0 100%); margin: 8% auto; padding: 50px; width: 90%; max-width: 650px; border-radius: 20px; text-align: center; color: white; box-shadow: 0 12px 40px rgba(0,0,0,0.4); position: relative;">
                            <div style="position: absolute; top: -10px; right: -10px; width: 60px; height: 60px; background: linear-gradient(45deg, #ffd700, #ffed4e); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.5em;">🏆</div>
                            
                            <div style="font-size: 3.5em; margin-bottom: 25px;">🎓➡️🚀</div>
                            <h2 style="margin: 0 0 20px 0; color: white; font-size: 2.2em;">Congrats! Ready for Pro Mode?</h2>
                            <p style="font-size: 1.3em; margin-bottom: 30px; opacity: 0.95;">You've mastered the MCP basics! Time to unlock the full power of professional MCP testing and automation.</p>
                            
                            <div style="background: rgba(255,255,255,0.1); padding: 25px; border-radius: 15px; margin: 25px 0; text-align: left;">
                                <p style="margin: 0 0 15px 0; font-size: 1.2em; font-weight: bold; text-align: center;"><strong>🔓 Pro Mode unlocks:</strong></p>
                                <div style="display: flex; justify-content: space-between; flex-wrap: wrap;">
                                    <div style="flex: 1; margin-right: 15px; min-width: 200px;">
                                        <p style="margin: 8px 0;">⚡ Advanced testing workflows</p>
                                        <p style="margin: 8px 0;">🔧 Custom automation scripts</p>
                                        <p style="margin: 8px 0;">📊 Performance monitoring</p>
                                    </div>
                                    <div style="flex: 1; margin-left: 15px; min-width: 200px;">
                                        <p style="margin: 8px 0;">🔒 Enterprise security features</p>
                                        <p style="margin: 8px 0;">🌐 Multi-server orchestration</p>
                                        <p style="margin: 8px 0;">📈 Analytics & reporting</p>
                                    </div>
                                </div>
                            </div>
                            
                            <div style="margin-top: 35px;">
                                <button onclick="switchToProMode()" style="background: linear-gradient(45deg, #4caf50, #66bb6a); color: white; border: none; padding: 18px 35px; border-radius: 12px; font-size: 1.2em; font-weight: bold; margin-right: 20px; cursor: pointer; box-shadow: 0 6px 20px rgba(76, 175, 80, 0.4); transition: all 0.3s;">🚀 Enter Pro Mode</button>
                                <button onclick="stayInLearningMode()" style="background: transparent; color: white; border: 2px solid rgba(255,255,255,0.4); padding: 18px 35px; border-radius: 12px; font-size: 1.2em; cursor: pointer; transition: all 0.3s;">📚 Keep Learning</button>
                            </div>
                            
                            <p style="margin-top: 25px; opacity: 0.8; font-size: 0.95em;">💡 You can always switch between modes anytime!</p>
                        </div>
                    </div>
                `;
                
                document.body.insertAdjacentHTML('beforeend', teaserHTML);
            }
            
            function switchToProMode() {
                console.log('🚀 Switching to Pro Mode...');
                closeProModeTransition();
                
                // Switch to pro mode
                switchToProModeOnly();
                
                // Show celebration message
                showMessage('success', '🎉 Welcome to Pro Mode! You now have access to all advanced MCP testing features. Explore the professional adventure tiles below!');
                
                // Add smooth scroll to pro mode tiles
                setTimeout(() => {
                    const proModeChooser = document.getElementById('proModeChooser');
                    if (proModeChooser) {
                        proModeChooser.scrollIntoView({ behavior: 'smooth' });
                    }
                }, 500);
                
                // Track the transition
                localStorage.setItem('userPreferredMode', 'pro');
                localStorage.setItem('hasCompletedLearningTransition', 'true');
            }
            
            function stayInLearningMode() {
                console.log('📚 Staying in Learning Mode...');
                closeProModeTransition();
                showMessage('info', '📚 No problem! Continue exploring Learning Mode. You can switch to Pro Mode anytime from the toggle above.');
                
                // Remember they chose to stay in learning mode for now
                localStorage.setItem('hasDeclinedProMode', Date.now().toString());
            }
            
            function closeProModeTransition() {
                const modal = document.getElementById('proModeTransition');
                if (modal) modal.remove();
            }
            
            function switchToProModeOnly() {
                isLearningMode = false;
                document.getElementById('learningModeBtn').classList.remove('active');
                document.getElementById('proModeBtn').classList.add('active');
                document.getElementById('headerSubtitle').textContent = 'Professional MCP testing, automation, and monitoring tools';
                document.getElementById('learningModeChooser').style.display = 'none';
                document.getElementById('proModeChooser').style.display = 'block';
                updateAdventureTileStats();
            }
            
            // Enhanced learning progress update to check for completion
            function updateLearningProgressWithTransition() {
                updateLearningProgress();
                
                // Check if user is ready for pro mode transition
                setTimeout(() => {
                    checkLearningCompletion();
                }, 1000);
            }
            
            // =============================================================================
            // LEARNING GUIDANCE SYSTEM
            // =============================================================================
            
            function addLearningGuidance() {
                console.log('✨ Adding learning guidance...');
                
                // Add pulsing highlights to key elements
                const sessionSelect = document.getElementById('mcpSessionSelect');
                if (sessionSelect) {
                    sessionSelect.classList.add('learning-highlight');
                    addTooltip(sessionSelect, 'Start by selecting a session - this is where your MCP servers run');
                }
                
                // Show step-by-step guidance
                showStepByStepGuidance();
            }
            
            function showStepByStepGuidance() {
                const steps = [
                    '👋 Welcome! Let\\'s test your first MCP tool step-by-step.',
                    '1️⃣ First, select a session from the dropdown (or try the demo)',
                    '2️⃣ Then we\\'ll discover what MCP servers are available',
                    '3️⃣ Pick a server and explore its tools',
                    '4️⃣ Finally, execute a tool and see the results!'
                ];
                
                let currentStep = 0;
                
                function showNextStep() {
                    if (currentStep < steps.length) {
                        showMessage('info', steps[currentStep]);
                        currentStep++;
                        
                        if (currentStep < steps.length) {
                            setTimeout(showNextStep, 3000);
                        }
                    }
                }
                
                showNextStep();
            }
            
            function addTooltip(element, text) {
                element.classList.add('edu-tooltip');
                element.setAttribute('data-tooltip', text);
            }
            
            function populateEducationalExamples() {
                console.log('📚 Populating educational examples...');
                
                // Enhanced demo data with educational context
                const educationalServers = [
                    { 
                        name: 'filesystem-tutorial', 
                        status: 'active', 
                        tools: ['read_file', 'write_file', 'list_directory'],
                        description: '📁 Learn file operations - perfect for automating file management',
                        examples: [
                            { tool: 'read_file', use_case: 'Read configuration files', safety: 'Safe - only reads' },
                            { tool: 'list_directory', use_case: 'Browse project structure', safety: 'Safe - read-only' },
                            { tool: 'write_file', use_case: 'Generate reports or logs', safety: 'Caution - modifies files' }
                        ]
                    },
                    { 
                        name: 'web-search-tutorial', 
                        status: 'active', 
                        tools: ['search', 'get_page', 'summarize'],
                        description: '🔍 Learn web research - great for getting current information',
                        examples: [
                            { tool: 'search', use_case: 'Find latest documentation', safety: 'Safe - read-only' },
                            { tool: 'get_page', use_case: 'Fetch specific web content', safety: 'Safe - no modifications' },
                            { tool: 'summarize', use_case: 'Digest long articles', safety: 'Safe - analysis only' }
                        ]
                    }
                ];
                
                // Update UI with educational context
                const serversList = document.getElementById('mcpServersList');
                if (serversList) {
                    serversList.innerHTML = educationalServers.map(server => 
                        \`<div class="server-item" onclick="selectEducationalServer('\${server.name}', \${JSON.stringify(server).replace(/"/g, '&quot;')})">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <strong>\${server.name}</strong>
                                <span style="color: #4caf50;">● \${server.status}</span>
                            </div>
                            <div style="margin: 8px 0; font-size: 0.9em; color: #666;">
                                \${server.description}
                            </div>
                            <small>\${server.tools.length} tools • Click to explore with examples</small>
                        </div>\`
                    ).join('');
                }
            }
            
            function selectEducationalServer(serverName, serverData) {
                console.log(\`📚 Selected educational server: \${serverName}\`);
                showMessage('success', \`📚 Great choice! \${serverData.description}\\n\\nLet\\'s explore the tools with real-world examples...\`);
                
                // Show tools with educational context
                const toolsList = document.getElementById('mcpToolsList');
                if (toolsList && serverData.examples) {
                    toolsList.innerHTML = serverData.examples.map(example =>
                        \`<div class="tool-item" onclick="selectEducationalTool('\${serverName}', '\${example.tool}', \${JSON.stringify(example).replace(/"/g, '&quot;')})">
                            <div style="display: flex; justify-content: space-between;">
                                <strong>\${example.tool}</strong>
                                <span class="learning-progress" style="margin: 0;">\${example.safety}</span>
                            </div>
                            <div style="margin: 4px 0; color: #666; font-size: 0.9em;">
                                \${example.use_case}
                            </div>
                            <small>Click for example parameters</small>
                        </div>\`
                    ).join('');
                }
            }
            
            function selectEducationalTool(serverName, toolName, exampleData) {
                console.log(\`🔧 Selected educational tool: \${serverName}.\${toolName}\`);
                
                // Populate with educational examples
                document.getElementById('testServerName').textContent = serverName + ' (Learning Mode)';
                document.getElementById('testToolName').textContent = toolName;
                document.getElementById('testDescription').textContent = 
                    \`📚 Example: \${exampleData.use_case}\\n🛡️ Safety: \${exampleData.safety}\\n\\nThis is a realistic example you might use in practice.\`;
                
                // Add educational sample parameters
                const sampleParams = getEducationalSampleParams(toolName);
                document.getElementById('testArguments').value = JSON.stringify(sampleParams, null, 2);
                
                showMessage('success', \`🎯 Perfect! This shows a real-world use case: "\${exampleData.use_case}"\\n\\nThe parameters below are realistic examples. Try executing it!\`);
            }
            
            function getEducationalSampleParams(toolName) {
                const samples = {
                    'read_file': {
                        "path": "./README.md",
                        "note": "This reads your project's README file - a common task for AI assistants"
                    },
                    'list_directory': {
                        "path": "./",
                        "note": "Lists the current directory - helps AI understand your project structure"
                    },
                    'write_file': {
                        "path": "./test-output.txt",
                        "content": "Hello from MCP Testing Suite!",
                        "note": "Creates a test file - always be careful with write operations"
                    },
                    'search': {
                        "query": "MCP Model Context Protocol 2024",
                        "limit": 5,
                        "note": "Searches for current information about MCP"
                    },
                    'get_page': {
                        "url": "https://modelcontextprotocol.io/",
                        "note": "Gets content from the official MCP website"
                    }
                };
                
                return samples[toolName] || {
                    "example": "parameter",
                    "note": "This is an educational example - parameters will vary by tool"
                };
            }
            
            function showTroubleshootingGuide() {
                showMessage('info', '🔍 Troubleshooting Guide:\\n\\n❓ Common Issues:\\n• "No servers found" → Check your MCP configurations\\n• "Connection failed" → Verify server is running\\n• "Tool not found" → Check tool name spelling\\n\\n💡 Try the demo mode first to understand how it works!');
            }
            
            function updateLearningProgress() {
                // Update progress indicators on learning tiles
                const progressTexts = {
                    mcpBasics: learningProgress.mcpBasics > 0 ? \`Started • \${learningProgress.mcpBasics}% complete\` : 'Start here • 0% complete',
                    guidedTesting: learningProgress.guidedTesting > 0 ? \`In Progress • \${learningProgress.guidedTesting}% complete\` : 'Beginner • 15 mins',
                    examples: learningProgress.examples > 0 ? \`Explored • \${learningProgress.examples}% complete\` : 'Intermediate • 20 mins',
                    troubleshooting: learningProgress.troubleshooting > 0 ? \`Reviewed • \${learningProgress.troubleshooting}% complete\` : 'Reference guide'
                };
                
                // Update the UI (this would target specific progress elements)
                console.log('📊 Learning progress updated:', progressTexts);
            }
            
            // =============================================================================
            // ADVENTURE CHOOSER - Zero Friction Navigation
            // =============================================================================
            
            // Adventure tile navigation functions
            function goToInteractive() {
                console.log('🧪 Going to Interactive mode...');
                // First, try to launch MCP Postman with existing sessions
                openMCPPostman();
                
                // If no sessions, guide user to create one
                if (getCurrentMCPSession() === null) {
                    showMessage('info', 'No active sessions found. Let\\'s launch your first MCP testing session!');
                    showAdvancedMode(); // Show project scanner
                    document.getElementById('scanPath').focus();
                }
            }
            
            function goToAPI() {
                console.log('🔧 Going to API mode...');
                // Show API documentation and examples
                showAPIMode();
            }
            
            function goToMonitoring() {
                console.log('📊 Going to Monitoring mode...');
                // Show monitoring dashboard
                showMonitoringMode();
            }
            
            function goToEnterprise() {
                console.log('🔒 Going to Enterprise mode...');
                // Show enterprise features
                showEnterpriseMode();
            }
            
            // Demo functions - show mock data immediately
            function tryDemo(mode) {
                console.log(\`🎭 Trying demo mode: \${mode}\`);
                switch(mode) {
                    case 'interactive':
                        // Open MCP Postman with mock data
                        openMCPPostman();
                        // Populate with demo servers
                        populateDemoMCPData();
                        break;
                    case 'api':
                        showAPIDemoMode();
                        break;
                    case 'monitoring':
                        showMonitoringDemoMode();
                        break;
                    case 'enterprise':
                        showEnterpriseDemoMode();
                        break;
                }
            }
            
            // Quick action functions
            function resumeLastSession() {
                console.log('📂 Resuming last session...');
                // Try to resume the most recent session
                refreshSessions();
                // Logic to resume most recent session will be implemented
                showMessage('info', 'Resume last session feature coming soon!');
            }
            
            function selectProjectFolder() {
                console.log('📁 Selecting project folder...');
                showAdvancedMode();
                openFolderBrowser();
            }
            
            function showAdvancedMode() {
                console.log('⚙️ Showing advanced mode...');
                // Show all the advanced sections
                const advancedSections = document.querySelectorAll('.advanced-mode-hidden');
                advancedSections.forEach(section => {
                    section.classList.remove('advanced-mode-hidden');
                });
                
                // Hide the adventure chooser
                document.getElementById('adventureChooser').style.display = 'none';
                
                // Add a "Back to Simple Mode" button
                const backButton = document.createElement('button');
                backButton.innerHTML = '← Back to Simple Mode';
                backButton.className = 'btn-secondary';
                backButton.onclick = showSimpleMode;
                backButton.style.marginBottom = '20px';
                
                const firstSection = document.querySelector('.section');
                firstSection.insertBefore(backButton, firstSection.firstChild);
            }
            
            function showSimpleMode() {
                console.log('🎯 Showing simple mode...');
                // Hide advanced sections
                const advancedSections = document.querySelectorAll('.advanced-mode-hidden');
                advancedSections.forEach(section => {
                    section.classList.add('advanced-mode-hidden');
                });
                
                // Show adventure chooser
                document.getElementById('adventureChooser').style.display = 'block';
                
                // Remove back button
                const backButton = document.querySelector('button[onclick="showSimpleMode()"]');
                if (backButton) backButton.remove();
                
                // Update live stats
                updateAdventureTileStats();
            }
            
            // Demo data population
            function populateDemoMCPData() {
                console.log('🎭 Populating demo MCP data...');
                // Simulate discovering demo servers
                const demoServers = [
                    { name: 'filesystem-demo', status: 'active', tools: ['read_file', 'write_file', 'list_directory'] },
                    { name: 'web-search-demo', status: 'active', tools: ['search', 'get_page', 'summarize'] },
                    { name: 'github-demo', status: 'active', tools: ['get_repo', 'create_issue', 'search_code'] }
                ];
                
                // Update MCP session select
                const sessionSelect = document.getElementById('mcpSessionSelect');
                if (sessionSelect) {
                    sessionSelect.innerHTML = '<option value="demo-session">Demo Session (Mock Data)</option>';
                    sessionSelect.value = 'demo-session';
                }
                
                // Populate servers list
                loadDemoMCPServers(demoServers);
            }
            
            function loadDemoMCPServers(servers) {
                const serversList = document.getElementById('mcpServersList');
                if (serversList) {
                    serversList.innerHTML = servers.map(server => 
                        \`<div class="server-item" onclick="selectDemoMCPServer('\${server.name}')">
                            <strong>\${server.name}</strong> 
                            <span style="color: #4caf50;">● \${server.status}</span>
                            <br><small>\${server.tools.length} tools available</small>
                        </div>\`
                    ).join('');
                }
            }
            
            function selectDemoMCPServer(serverName) {
                console.log(\`🎯 Selected demo server: \${serverName}\`);
                showMessage('success', \`Selected demo server: \${serverName}. This is mock data for demonstration.\`);
                
                // Load demo tools for this server
                const demoTools = {
                    'filesystem-demo': [
                        { name: 'read_file', description: 'Read file contents', schema: { path: 'string' } },
                        { name: 'write_file', description: 'Write file contents', schema: { path: 'string', content: 'string' } },
                        { name: 'list_directory', description: 'List directory contents', schema: { path: 'string' } }
                    ],
                    'web-search-demo': [
                        { name: 'search', description: 'Search the web', schema: { query: 'string', limit: 'number' } },
                        { name: 'get_page', description: 'Get page content', schema: { url: 'string' } },
                        { name: 'summarize', description: 'Summarize content', schema: { text: 'string' } }
                    ],
                    'github-demo': [
                        { name: 'get_repo', description: 'Get repository info', schema: { repo: 'string' } },
                        { name: 'create_issue', description: 'Create an issue', schema: { repo: 'string', title: 'string', body: 'string' } },
                        { name: 'search_code', description: 'Search code', schema: { query: 'string', language: 'string' } }
                    ]
                };
                
                const tools = demoTools[serverName] || [];
                const toolsList = document.getElementById('mcpToolsList');
                if (toolsList) {
                    toolsList.innerHTML = tools.map(tool =>
                        \`<div class="tool-item" onclick="selectDemoMCPTool('\${serverName}', '\${tool.name}')">
                            <strong>\${tool.name}</strong>
                            <br><small>\${tool.description}</small>
                        </div>\`
                    ).join('');
                }
            }
            
            function selectDemoMCPTool(serverName, toolName) {
                console.log(\`🔧 Selected demo tool: \${serverName}.\${toolName}\`);
                // Populate test form with demo data
                document.getElementById('testServerName').textContent = serverName + ' (Demo)';
                document.getElementById('testToolName').textContent = toolName;
                document.getElementById('testDescription').textContent = 'This is a demo tool with mock responses.';
                document.getElementById('testArguments').value = JSON.stringify({
                    "demo": "parameter",
                    "note": "This is mock data for demonstration"
                }, null, 2);
            }
            
            // Update live stats on adventure tiles
            function updateAdventureTileStats() {
                // Update session count
                fetch('/api/sessions')
                    .then(response => response.json())
                    .then(data => {
                        const runningCount = data.sessions ? data.sessions.filter(s => s.status === 'running').length : 0;
                        const serverCount = runningCount * 2; // Mock estimate
                        
                        document.getElementById('interactiveMeta').textContent = 
                            serverCount > 0 ? \`\${serverCount} servers found\` : 'Ready to start';
                        document.getElementById('monitoringMeta').textContent = 
                            \`\${runningCount} session\${runningCount === 1 ? '' : 's'} running\`;
                    })
                    .catch(() => {
                        // Fallback to static text if API fails
                        document.getElementById('interactiveMeta').textContent = 'Ready to start';
                        document.getElementById('monitoringMeta').textContent = '0 sessions running';
                    });
            }
            
            // API/Monitoring/Enterprise mode functions (placeholders)
            function showAPIMode() {
                showMessage('info', 'API Mode: Full REST API documentation and examples coming soon!');
                showAdvancedMode(); // For now, show advanced mode
            }
            
            function showMonitoringMode() {
                showMessage('info', 'Monitoring Mode: Real-time server health and performance dashboards coming soon!');
                showAdvancedMode(); // For now, show advanced mode
            }
            
            function showEnterpriseMode() {
                showMessage('info', 'Enterprise Mode: Security policies, audit logs, and compliance features coming soon!');
                showAdvancedMode(); // For now, show advanced mode
            }
            
            function showAPIDemoMode() {
                showMessage('success', 'API Demo: Try these endpoints:\\n\\nGET /api/sessions\\nGET /api/mcp/discover\\nPOST /api/mcp/call-tool/{server}');
            }
            
            function showMonitoringDemoMode() {
                showMessage('success', 'Monitoring Demo: Server health: ✅ 99.9% uptime\\nActive sessions: 3\\nAvg response time: 45ms');
            }
            
            function showEnterpriseDemoMode() {
                showMessage('success', 'Enterprise Demo: Security policies: ✅ Active\\nAudit logs: ✅ Enabled\\nCompliance: ✅ SOC2 Ready');
            }
            
            // Initialize on page load
            window.addEventListener('load', function() {
                updateAdventureTileStats();
                // Refresh stats every 30 seconds
                setInterval(updateAdventureTileStats, 30000);
            });
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
    import sys
    import argparse
    import webbrowser
    import os
    
    # Command line argument parsing
    parser = argparse.ArgumentParser(description="MCP Testing Suite Dynamic Launcher")
    parser.add_argument("--port", type=int, default=8094, help="Port to run the launcher on")
    parser.add_argument("--auto-open", action="store_true", help="Automatically open browser")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    args = parser.parse_args()
    
    # Check environment variables (from START script)
    port = int(os.environ.get("MCP_TESTING_SUITE_PORT", args.port))
    auto_open = os.environ.get("MCP_TESTING_SUITE_AUTO_OPEN", "false").lower() == "true" or args.auto_open
    
    print(f"🚀 MCP Testing Suite Dynamic Launcher")
    print(f"🌐 Starting on http://{args.host}:{port}")
    
    # Auto-open browser if requested
    if auto_open:
        def open_browser():
            import time
            time.sleep(1)  # Wait for server to start
            try:
                webbrowser.open(f"http://localhost:{port}")
                print(f"🎯 Opened browser at http://localhost:{port}")
            except Exception as e:
                print(f"💡 Please open http://localhost:{port} in your browser")
        
        import threading
        threading.Thread(target=open_browser, daemon=True).start()
    
    # Start the server
    uvicorn.run(app, host=args.host, port=port)