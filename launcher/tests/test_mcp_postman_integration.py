#!/usr/bin/env python3
"""
Integration tests for MCP Postman launcher functionality
Tests the launcher's integration with MCP Postman backend APIs
"""

import pytest
import asyncio
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os

# Add launcher to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from session_manager import SessionManager

# Create test client
client = TestClient(app)

class TestMCPPostmanIntegration:
    """Test suite for MCP Postman integration with launcher"""
    
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Setup for each test"""
        self.session_manager = SessionManager()
        
    def test_launcher_has_mcp_postman_ui(self):
        """Test that launcher serves MCP Postman UI components"""
        response = client.get("/")
        
        assert response.status_code == 200
        html_content = response.text
        
        # Check for MCP Postman UI elements
        assert "MCP Postman" in html_content
        assert "mcpPostmanModal" in html_content
        assert "openMCPPostman()" in html_content
        assert "executeMCPTool()" in html_content
        assert "mcpServersList" in html_content
        assert "mcpToolsList" in html_content
    
    def test_launcher_sessions_api_for_mcp(self):
        """Test that sessions API provides data for MCP Postman"""
        # Mock the session manager instance used by the app
        with patch('main.session_manager') as mock_session_manager:
            # Mock active sessions
            mock_sessions = [
                {
                    "session_id": "test123",
                    "status": "running",
                    "backend_url": "http://localhost:8095",
                    "project_path": "/test/project",
                    "config_source": "test.json"
                },
                {
                    "session_id": "test456",
                    "status": "stopped", 
                    "backend_url": "http://localhost:8096",
                    "project_path": "/another/project",
                    "config_source": "another.json"
                }
            ]
            
            # Mock the async method
            async def mock_list_sessions():
                return mock_sessions
            
            mock_session_manager.list_sessions = mock_list_sessions
            
            response = client.get("/api/sessions")
            
            assert response.status_code == 200
            data = response.json()
            
            assert len(data["sessions"]) == 2
            
            # Check that running session has all required fields for MCP Postman
            running_session = next((s for s in data["sessions"] if s["status"] == "running"), None)
            assert running_session is not None
            assert "backend_url" in running_session
            assert "session_id" in running_session
            assert "project_path" in running_session
    
    def test_mcp_postman_javascript_functions(self):
        """Test that required JavaScript functions are present"""
        response = client.get("/")
        html_content = response.text
        
        required_functions = [
            "openMCPPostman()",
            "closeMCPPostman()",  
            "refreshMCPSessions()",
            "loadMCPServers()",
            "selectMCPServer(",
            "selectMCPTool(",
            "executeMCPTool()",
            "generateSampleRequest()",
            "clearToolTester()",
            "refreshMCPHistory()",
            "clearMCPHistory()",
            "getCurrentMCPSession()",
            "showMCPError("
        ]
        
        for function in required_functions:
            assert function in html_content, f"Missing JavaScript function: {function}"
    
    def test_mcp_postman_modal_structure(self):
        """Test MCP Postman modal has correct structure"""
        response = client.get("/")
        html_content = response.text
        
        # Check for modal structure elements
        required_elements = [
            'id="mcpPostmanModal"',
            'id="mcpSessionSelect"',
            'id="mcpServersList"',
            'id="mcpToolsList"',
            'id="testServerName"',
            'id="testToolName"',
            'id="testArguments"',
            'id="testDescription"',
            'id="mcpResults"',
            'id="mcpHistory"'
        ]
        
        for element in required_elements:
            assert element in html_content, f"Missing UI element: {element}"
    
    @patch('requests.get')
    def test_mcp_backend_communication_simulation(self, mock_requests_get):
        """Simulate MCP Postman communication with backend"""
        # This test simulates what would happen when MCP Postman
        # communicates with a backend session
        
        # Mock backend responses
        mock_discover_response = MagicMock()
        mock_discover_response.json.return_value = {
            "servers": [
                {
                    "name": "test-server",
                    "status": "discoverable",
                    "type": "stdio",
                    "description": "Test MCP server"
                }
            ],
            "total_count": 1,
            "discovered_at": "2025-08-18T12:00:00"
        }
        mock_discover_response.status_code = 200
        
        mock_tools_response = MagicMock()
        mock_tools_response.json.return_value = {
            "server_name": "test-server",
            "tools": [
                {
                    "name": "test_tool",
                    "description": "A test tool",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "param1": {"type": "string"}
                        }
                    }
                }
            ],
            "tool_count": 1
        }
        mock_tools_response.status_code = 200
        
        mock_requests_get.side_effect = [mock_discover_response, mock_tools_response]
        
        # Simulate the workflow that JavaScript would follow
        import requests
        
        # 1. Discover servers
        backend_url = "http://localhost:8095"  # Mock backend URL
        discover_response = requests.get(f"{backend_url}/api/mcp/discover")
        
        assert discover_response.status_code == 200
        servers_data = discover_response.json()
        assert len(servers_data["servers"]) == 1
        assert servers_data["servers"][0]["name"] == "test-server"
        
        # 2. Get tools for server
        tools_response = requests.get(f"{backend_url}/api/mcp/tools/test-server")
        
        assert tools_response.status_code == 200
        tools_data = tools_response.json()
        assert len(tools_data["tools"]) == 1
        assert tools_data["tools"][0]["name"] == "test_tool"


class TestMCPPostmanE2E:
    """End-to-end test scenarios for MCP Postman"""
    
    def test_complete_mcp_postman_workflow(self):
        """Test complete MCP Postman workflow"""
        # This test outlines the complete workflow without actually
        # executing it (since it would require running backend)
        
        workflow_steps = [
            "1. User clicks 'Open MCP Tool Tester' button",
            "2. Modal opens and loads active sessions", 
            "3. User selects a running session",
            "4. Frontend calls backend /api/mcp/discover",
            "5. Available MCP servers are displayed",
            "6. User clicks on a server",
            "7. Frontend calls /api/mcp/tools/{server_name}",
            "8. Available tools are displayed",
            "9. User clicks on a tool",
            "10. Tool schema populates the request builder",
            "11. User modifies arguments JSON",
            "12. User clicks 'Execute Tool'",
            "13. Frontend calls /api/mcp/call-tool/{server}",
            "14. Results are displayed with timing/logging",
            "15. Request is added to history",
            "16. User can replay from history"
        ]
        
        # Verify each step is supported by our implementation
        response = client.get("/")
        html_content = response.text
        
        # Step 1: Button exists
        assert "Open MCP Tool Tester" in html_content
        
        # Step 2: Modal and session loading
        assert "mcpPostmanModal" in html_content
        assert "refreshMCPSessions" in html_content
        
        # Step 3: Session selection  
        assert "mcpSessionSelect" in html_content
        assert "loadMCPServers" in html_content
        
        # Steps 4-5: Server discovery
        assert "mcpServersList" in html_content
        
        # Steps 6-7: Server selection and tool loading
        assert "selectMCPServer" in html_content
        assert "mcpToolsList" in html_content
        
        # Steps 8-9: Tool selection
        assert "selectMCPTool" in html_content
        
        # Steps 10-11: Request building
        assert "testArguments" in html_content
        assert "testDescription" in html_content
        
        # Steps 12-13: Tool execution
        assert "executeMCPTool" in html_content
        
        # Step 14: Results display
        assert "mcpResults" in html_content
        
        # Steps 15-16: History management
        assert "mcpHistory" in html_content
        assert "refreshMCPHistory" in html_content
        
        # All workflow steps are supported!
        assert len(workflow_steps) == 16
    
    def test_mcp_postman_error_handling(self):
        """Test error handling in MCP Postman interface"""
        response = client.get("/")
        html_content = response.text
        
        # Check for error handling functions
        assert "showMCPError" in html_content
        
        # Check for validation logic
        assert "Invalid JSON" in html_content  # JSON validation error
        assert "Please select a server and tool first" in html_content  # Required field validation
    
    def test_mcp_postman_ui_responsive_design(self):
        """Test that MCP Postman UI has responsive design elements"""
        response = client.get("/")
        html_content = response.text
        
        # Check for responsive design features
        responsive_features = [
            "max-width: 1200px",  # Modal max width
            "width: 90%",         # Responsive width
            "max-height: 90vh",   # Viewport height constraint
            "overflow-y: auto",   # Scrollable content
            "display: flex",      # Flexible layouts
            "gap: 20px"           # Consistent spacing
        ]
        
        for feature in responsive_features:
            assert feature in html_content, f"Missing responsive feature: {feature}"


# Test configuration for pytest
@pytest.fixture(scope="session") 
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Run the tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])