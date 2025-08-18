#!/usr/bin/env python3
"""
E2E API tests for MCP Launcher
"""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

# Import main app
import sys
sys.path.append('..')
from main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def temp_project():
    """Create temporary project with MCP config"""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir) / "test_project"
        project_path.mkdir()
        
        # Create .mcp.json
        mcp_config = {
            "mcpServers": {
                "test-server-1": {
                    "type": "stdio",
                    "command": "uvx",
                    "args": ["test-server-1"],
                    "description": "Test server 1"
                },
                "test-server-2": {
                    "type": "stdio", 
                    "command": "uvx",
                    "args": ["test-server-2"],
                    "description": "Test server 2"
                }
            }
        }
        with open(project_path / ".mcp.json", "w") as f:
            json.dump(mcp_config, f)
        
        yield str(project_path)

class TestLauncherAPI:
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/api/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "mcp-launcher"
        assert "active_sessions" in data
        assert "max_concurrent_sessions" in data
    
    def test_folder_browsing(self, client, temp_project):
        """Test folder browsing API"""
        parent_path = str(Path(temp_project).parent)
        
        response = client.get(f"/api/browse-folders?path={parent_path}")
        assert response.status_code == 200
        
        data = response.json()
        assert "current_path" in data
        assert "folders" in data
        
        # Should find our test project
        project_names = [folder["name"] for folder in data["folders"]]
        assert "test_project" in project_names
        
        # Test project should be marked as having MCP config
        test_project_folder = next(f for f in data["folders"] if f["name"] == "test_project")
        assert test_project_folder["has_mcp_config"] == True
        assert test_project_folder["type"] == "project"
    
    def test_project_scanning(self, client, temp_project):
        """Test project scanning API"""
        parent_path = str(Path(temp_project).parent)
        
        response = client.get(f"/api/scan-projects?path={parent_path}")
        assert response.status_code == 200
        
        data = response.json()
        assert "projects" in data
        assert len(data["projects"]) >= 1
        
        # Find our test project
        test_project = next((p for p in data["projects"] if "test_project" in p["path"]), None)
        assert test_project is not None
        assert len(test_project["config_sources"]) == 1
        assert test_project["config_sources"][0]["server_count"] == 2
    
    def test_config_preview(self, client, temp_project):
        """Test configuration preview API"""
        config_path = str(Path(temp_project) / ".mcp.json")
        
        response = client.get(f"/api/config-preview?config_path={config_path}")
        assert response.status_code == 200
        
        data = response.json()
        assert "servers" in data
        assert "test-server-1" in data["servers"]
        assert "test-server-2" in data["servers"]
        assert data["summary"]["total_servers"] == 2
        assert data["summary"]["stdio_servers"] == 2
    
    def test_session_management(self, client, temp_project):
        """Test session management endpoints"""
        # List sessions (should be empty initially)
        response = client.get("/api/sessions")
        assert response.status_code == 200
        initial_sessions = response.json()["sessions"]
        
        # Try to launch session (will fail due to Docker not running in test)
        launch_config = {
            "project_path": temp_project,
            "config_source": str(Path(temp_project) / ".mcp.json"),
            "config_type": "project",
            "session_name": "test-session",
            "selected_servers": ["test-server-1"],
            "server_filter_mode": "include"
        }
        
        response = client.post("/api/launch-backend", json=launch_config)
        # This might fail due to Docker not being available in test environment
        # but we can still test the API structure
        assert response.status_code in [200, 500]  # 500 if Docker not available
        
        if response.status_code == 200:
            data = response.json()
            assert "session_id" in data
            assert "backend_url" in data
            
            # Test session listing
            response = client.get("/api/sessions")
            assert response.status_code == 200
            sessions = response.json()["sessions"]
            assert len(sessions) == len(initial_sessions) + 1
    
    def test_invalid_paths(self, client):
        """Test API behavior with invalid paths"""
        # Invalid folder browsing
        response = client.get("/api/browse-folders?path=/nonexistent/path")
        assert response.status_code == 400
        
        # Invalid config preview
        response = client.get("/api/config-preview?config_path=/nonexistent/config.json")
        assert response.status_code == 200  # Returns 200 with error in JSON
        data = response.json()
        assert "error" in data
        
        # Invalid project scanning (should handle gracefully)
        response = client.get("/api/scan-projects?path=/nonexistent/path")
        assert response.status_code in [200, 500]  # May return empty results or error
    
    def test_web_interface(self, client):
        """Test that web interface is served"""
        response = client.get("/")
        assert response.status_code == 200
        assert "MCP Testing Suite V2" in response.text
        assert "Project Launcher" in response.text

class TestSessionLimits:
    
    def test_session_limit_enforcement(self, client, temp_project):
        """Test that session limits are enforced"""
        # This test would require mocking the session manager
        # to avoid actually launching Docker containers
        pass  # Placeholder for integration test

if __name__ == "__main__":
    pytest.main([__file__, "-v"])