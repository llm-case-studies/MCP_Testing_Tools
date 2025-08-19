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
        const response = await fetch('/api/browse-folders?path=' + encodeURIComponent(path));
        const data = await response.json();
        
        document.getElementById('currentPath').textContent = data.current_path;
        
        let html = '';
        data.folders.forEach(folder => {
            const icon = folder.type === 'parent' ? '⬆️' : 
                       folder.type === 'project' ? '📦' : '📁';
            const style = folder.has_mcp_config ? 'background: #e8f5e8; font-weight: bold;' : '';
            
            html += '<div style="padding: 8px; margin: 2px 0; border-radius: 4px; cursor: pointer; ' + style + '" ' +
                     'onclick="navigateToFolder(\'' + folder.path + '\')">' +
                    icon + ' ' + folder.name +
                    (folder.has_mcp_config ? ' <span style="color: #4caf50;">✓ MCP</span>' : '') +
                '</div>';
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
    projects.forEach(function(project) {
        html += '<div class="project-card">' +
            '<h4>📂 ' + project.name + '</h4>' +
            '<p><strong>Path:</strong> ' + project.path + '</p>' +
            (project.description ? '<p><strong>Description:</strong> ' + project.description + '</p>' : '') +
            '<div>' +
                '<strong>Config Sources:</strong>' +
                project.config_sources.map(function(source, idx) { 
                    return '<div class="config-source">' + 
                    source.type + ': ' + source.path + 
                    ' (' + source.server_count + ' servers: ' + source.servers.slice(0,3).join(', ') + (source.servers.length > 3 ? '...' : '') + ')' + 
                    ' <button>🎛️ Configure & Launch</button>' + 
                    ' <button>🚀 Quick Launch</button>' + 
                    '</div>';
                }).join('') +
            '</div>' +
        '</div>';
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
    sessions.forEach(function(session) {
        var statusClass = session.status === 'running' ? 'status-running' : 'status-stopped';
        html += '<div class="project-card ' + (session.status === 'running' ? 'session-active' : '') + '">' +
                '<h4>🎮 ' + session.session_id + '</h4>' +
                '<p><strong>Project:</strong> ' + session.project_path + '</p>' +
                '<p><strong>Config:</strong> ' + session.config_source + '</p>' +
                '<p><strong>Status:</strong> <span class="status ' + statusClass + '">' + session.status.toUpperCase() + '</span></p>' +
                (session.backend_url ? '<p><strong>Backend:</strong> <a href="' + session.backend_url + '" target="_blank">' + session.backend_url + '</a></p>' : '') +
                '<p><strong>Created:</strong> ' + new Date(session.created_at).toLocaleString() + '</p>' +
                '<div>' +
                    (session.status === 'running' ? 
                        '<button onclick="stopSession(\'' + session.session_id + '\')">Stop Session</button>' + 
                        '<button onclick="openBackend(\'' + session.backend_url + '\')">Open Testing Interface</button>' :
                        '<button onclick="removeSession(\'' + session.session_id + '\')">Remove</button>'
                    ) +
                '</div>' +
            '</div>';
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
                 onclick="selectMCPTool('${tool.name}', ${JSON.stringify(tool.schema || {}).replace(/"/g, '&quot;')})">${tool.name}</div>
        `;
    });
    
    container.innerHTML = html;
}

// =============================================================================
// LEARNING MODE FUNCTIONS
// =============================================================================

// Learning mode state
let isLearningMode = true;
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

// Learning mode tile functions
function startMCPBasics() {
    console.log('🎓 Starting MCP Basics tutorial...');
    showMCPBasicsTeaser();
}

// Phase 2 Refactored: Clean template-based teaser function
async function showMCPBasicsTeaser() {
    await showModalFromTemplate('mcp-basics-teaser');
}

function closeMCPBasicsTeaser() {
    closeModal('mcpBasicsTeaser');
}

function beginMCPBasics() {
    closeMCPBasicsTeaser();
    showWhatIsMCP();
    
    // Mark progress
    learningProgress.mcpBasics = 25;
    updateLearningProgress();
    
    // Add completion flow
    setTimeout(function() {
        showMCPBasicsCompletion();
    }, 8000);
}

function showMCPBasicsCompletion() {
    if (confirm('🎉 Great! Now you understand what MCP is!\\n\\nReady to test your first MCP tool? This is where it gets really fun!')) {
        closeWhatIsMCPModal();
        startGuidedTesting();
    } else {
        showMessage('success', '✅ MCP Basics completed! You can continue anytime from the Learning Mode dashboard.');
        learningProgress.mcpBasics = 100;
        updateLearningProgress();
    }
}

function startGuidedTesting() {
    console.log('🧪 Starting guided testing...');
    
    // Open MCP Postman with educational overlays
    openMCPPostman();
    
    // Add learning highlights and guidance
    setTimeout(function() {
        addLearningGuidance();
    }, 1000);
    
    // Mark progress
    learningProgress.guidedTesting = 50;
    updateLearningProgress();
    
    showMessage('success', '🧪 Great! You\'ve opened the MCP Tool Tester. Look for the green highlights - they\'ll guide you through your first test!');
}

function exploreExamples() {
    console.log('📚 Exploring examples...');
    showExploreExamplesTeaser();
}

// Phase 2 Refactored: Clean template-based teaser function
async function showExploreExamplesTeaser() {
    await showModalFromTemplate('explore-examples-teaser');
}

function closeExploreExamplesTeaser() {
    closeModal('exploreExamplesTeaser');
}

function beginExploreExamples() {
    closeExploreExamplesTeaser();
    showMessage('info', '📚 Opening curated examples with detailed explanations...');
    
    // Open MCP Postman with example data pre-loaded
    openMCPPostman();
    setTimeout(function() {
        populateEducationalExamples();
    }, 500);
    
    // Mark progress  
    learningProgress.examples = 75;
    updateLearningProgress();
}

function troubleshootingHelp() {
    console.log('🔍 Opening troubleshooting help...');
    showTroubleshootingTeaser();
}

// Phase 2 Refactored: Clean template-based teaser function
async function showTroubleshootingTeaser() {
    await showModalFromTemplate('troubleshooting-teaser');
}

function closeTroubleshootingTeaser() {
    closeModal('troubleshootingTeaser');
}

function beginTroubleshooting() {
    closeTroubleshootingTeaser();
    showTroubleshootingGuide();
    
    // Mark progress
    learningProgress.troubleshooting = 100;
    updateLearningProgress();
}

// Educational content functions
function showWhatIsMCP() {
    console.log('🤔 Showing "What is MCP?" modal...');
    document.getElementById('whatIsMCPModal').style.display = 'block';
}

function closeWhatIsMCPModal() {
    document.getElementById('whatIsMCPModal').style.display = 'none';
}

function showLearningPath() {
    console.log('📋 Showing learning path...');
    var completedCount = Object.values(learningProgress).filter(function(p) { return p > 0; }).length;
    var totalTopics = Object.keys(learningProgress).length;
    
    showMessage('info', '📋 Your Learning Progress:\\n\\n✅ Completed: ' + completedCount + '/' + totalTopics + ' topics\\n📈 Keep going! Each topic builds on the previous one.');
}

// Helper functions
function updateLearningProgress() {
    // Update progress indicators in the UI
    console.log('📈 Updating learning progress...');
}

function addLearningGuidance() {
    console.log('✨ Adding learning guidance...');
    
    // Add pulsing highlights to key elements
    var sessionSelect = document.getElementById('mcpSessionSelect');
    if (sessionSelect) {
        sessionSelect.classList.add('learning-highlight');
    }
}

function populateEducationalExamples() {
    console.log('📚 Populating educational examples...');
    // Implementation would populate with example MCP tools and data
}

function showTroubleshootingGuide() {
    showMessage('info', '🔍 Troubleshooting guide would appear here with common solutions and fixes.');
}

function updateAdventureTileStats() {
    // Update pro mode tile stats
    console.log('📊 Updating adventure tile stats...');
}

function showMessage(type, message) {
    // Simple message display
    if (type === 'success') {
        alert('✅ ' + message);
    } else if (type === 'info') {
        alert('ℹ️ ' + message);
    } else {
        alert(message);
    }
}

// Pro mode placeholder functions
function goToInteractive() {
    openMCPPostman();
}

function goToAPI() {
    showMessage('info', '🔧 API Mode features would be available here');
}

function goToMonitoring() {
    showMessage('info', '📊 Monitoring features would be available here');
}

function goToEnterprise() {
    showMessage('info', '🔒 Enterprise features would be available here');
}

function tryDemo(mode) {
    showMessage('info', '🎮 Demo for ' + mode + ' mode would start here');
}

function resumeLastSession() {
    showMessage('info', '⏮️ Resume last session functionality');
}

function selectProjectFolder() {
    openFolderBrowser();
}

function showAdvancedMode() {
    // Show advanced sections
    var advancedSections = document.querySelectorAll('.advanced-mode-hidden');
    advancedSections.forEach(function(section) {
        section.style.display = 'block';
    });
    showMessage('success', '🔧 Advanced mode activated! All sections are now visible.');
}

// Complete the MCP Tool selection function
function selectMCPTool(toolName, schema) {
    try {
        // Set tool in tester
        document.getElementById('testToolName').value = toolName;
        
        // Try to populate arguments with sample data from schema
        if (schema && schema.properties) {
            var sampleArgs = {};
            Object.keys(schema.properties).forEach(function(key) {
                var prop = schema.properties[key];
                if (prop.type === 'string') {
                    sampleArgs[key] = prop.example || 'sample_value';
                } else if (prop.type === 'number') {
                    sampleArgs[key] = prop.example || 123;
                } else if (prop.type === 'boolean') {
                    sampleArgs[key] = true;
                }
            });
            
            document.getElementById('testArguments').value = JSON.stringify(sampleArgs, null, 2);
        }
        
        showMessage('success', 'Tool ' + toolName + ' selected! Check the arguments and click Execute.');
        
    } catch (error) {
        console.error('Failed to select tool:', error);
        showMessage('error', 'Failed to select tool: ' + error.message);
    }
}

// MCP Tool execution and helper functions
function executeMCPTool() {
    showMessage('info', '🚀 Tool execution would happen here');
}

function generateSampleRequest() {
    showMessage('info', '📝 Sample request generation would happen here');
}

function clearToolTester() {
    document.getElementById('testServerName').value = '';
    document.getElementById('testToolName').value = '';
    document.getElementById('testArguments').value = '';
    document.getElementById('testDescription').value = '';
}

function refreshMCPHistory() {
    showMessage('info', '🔄 MCP history refresh would happen here');
}

function clearMCPHistory() {
    showMessage('info', '🗑️ MCP history clear would happen here');
}

function showMCPError(message) {
    showMessage('error', 'MCP Error: ' + message);
}

async function getCurrentMCPSession() {
    var sessionId = document.getElementById('mcpSessionSelect').value;
    var sessionsResponse = await fetch('/api/sessions');
    var sessionsData = await sessionsResponse.json();
    return sessionsData.sessions.find(function(s) { return s.session_id === sessionId; });
}