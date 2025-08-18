#!/usr/bin/env python3
"""
Unit tests for MCP Postman backend APIs
Tests the MCP discovery, tool execution, and history management endpoints
"""

import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from web_interface import app, mcp_request_history, mcp_collections

# Create test client
client = TestClient(app)

class TestMCPPostmanAPIs:
    """Test suite for MCP Postman backend APIs"""
    
    def setup_method(self):
        """Clear state before each test"""
        global mcp_request_history, mcp_collections
        mcp_request_history.clear()
        mcp_collections.clear()
    
    @patch('config_discovery.MCPConfigDiscovery')
    @patch.dict('os.environ', {'MCP_CONFIG_DIR': '/test/config'})
    @patch('os.path.exists', return_value=True) 
    def test_mcp_discover_endpoint_success(self, mock_exists, mock_discovery_class):
            # Mock discovery instance
            mock_discovery = MagicMock()
            mock_discovery_class.return_value = mock_discovery
            
            # Mock discovered servers
            mock_servers = [
                {
                    "name": "test-server",
                    "type": "stdio",
                    "command": ["python", "server.py"],
                    "description": "Test MCP server"
                },
                {
                    "name": "another-server", 
                    "type": "http",
                    "url": "http://localhost:3000",
                    "description": "HTTP MCP server"
                }
            ]
            
            mock_discovery.discover_servers.return_value = mock_servers
            mock_discovery.get_server_capabilities.return_value = ["tools"]
            mock_discovery.validate_server_config.return_value = {"valid": True}
            
            # Test the endpoint
            response = client.get("/api/mcp/discover")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "servers" in data
            assert "total_count" in data
            assert "discovered_at" in data
            assert len(data["servers"]) == 2
            
            # Check first server
            server1 = data["servers"][0]
            assert server1["name"] == "test-server"
            assert server1["type"] == "stdio"
            assert server1["status"] == "discoverable"
            assert "capabilities" in server1
            assert "validation" in server1
    
    def test_mcp_discover_endpoint_error(self):
        """Test MCP discovery with error"""
        with patch('config_discovery.MCPConfigDiscovery') as mock_discovery_class:
            mock_discovery_class.side_effect = Exception("Discovery failed")
            
            response = client.get("/api/mcp/discover")
            
            assert response.status_code == 500
            data = response.json()
            assert "Discovery failed" in data["detail"]
    
    def test_mcp_tools_discovery(self):
        """Test tool discovery for specific server"""
        server_name = "test-server"
        
        response = client.get(f"/api/mcp/tools/{server_name}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["server_name"] == server_name
        assert "tools" in data
        assert "tool_count" in data
        assert "discovered_at" in data
        assert data["status"] == "mock_response"  # Currently returns mock data
    
    def test_mcp_call_tool_success(self):
        """Test successful MCP tool execution"""
        server_name = "test-server"
        tool_request = {
            "tool_name": "test_tool",
            "arguments": {"param1": "value1", "param2": 123},
            "description": "Test tool execution"
        }
        
        response = client.post(f"/api/mcp/call-tool/{server_name}", json=tool_request)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert data["server_name"] == server_name
        assert data["tool_name"] == tool_request["tool_name"]
        assert data["arguments"] == tool_request["arguments"]
        assert data["status"] == "mock_success"
        assert "request_id" in data
        assert "result" in data
        assert "timing" in data
        assert "log_entries" in data
        
        # Check timing info
        assert "started_at" in data["timing"]
        assert "completed_at" in data["timing"]
        assert "duration_ms" in data["timing"]
        assert isinstance(data["timing"]["duration_ms"], int)
        
        # Check that request was added to history
        assert len(mcp_request_history) == 1
        assert mcp_request_history[0]["request_id"] == data["request_id"]
    
    def test_mcp_call_tool_invalid_json(self):
        """Test tool execution with invalid request format"""
        server_name = "test-server"
        invalid_request = "not json"
        
        response = client.post(
            f"/api/mcp/call-tool/{server_name}", 
            data=invalid_request,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_mcp_history_management(self):
        """Test request history functionality"""
        # Add some test requests to history
        test_requests = [
            {
                "request_id": "req_1",
                "server_name": "server1",
                "tool_name": "tool1",
                "status": "success",
                "arguments": {"test": "data1"}
            },
            {
                "request_id": "req_2", 
                "server_name": "server2",
                "tool_name": "tool2",
                "status": "error",
                "arguments": {"test": "data2"}
            }
        ]
        
        mcp_request_history.extend(test_requests)
        
        # Test get history
        response = client.get("/api/mcp/history")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["requests"]) == 2
        assert data["total_requests"] == 2
        assert data["limit"] == 50
        
        # Test history with limit
        response = client.get("/api/mcp/history?limit=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["requests"]) == 1
        assert data["limit"] == 1
        
        # Test clear history
        response = client.delete("/api/mcp/history")
        assert response.status_code == 200
        data = response.json()
        assert data["cleared_count"] == 2
        assert len(mcp_request_history) == 0
    
    def test_mcp_collections_management(self):
        """Test MCP request collections functionality"""
        collection_name = "test-collection"
        collection_data = {
            "name": collection_name,
            "description": "Test collection for MCP requests",
            "requests": [
                {
                    "tool_name": "test_tool1",
                    "arguments": {"param": "value1"},
                    "description": "First test request"
                },
                {
                    "tool_name": "test_tool2", 
                    "arguments": {"param": "value2"},
                    "description": "Second test request"
                }
            ]
        }
        
        # Test save collection
        response = client.post(f"/api/mcp/collections/{collection_name}", json=collection_data)
        assert response.status_code == 200
        data = response.json()
        assert data["collection_name"] == collection_name
        assert data["request_count"] == 2
        
        # Test get collections list
        response = client.get("/api/mcp/collections")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["collections"]) == 1
        collection = data["collections"][0]
        assert collection["name"] == collection_name
        assert collection["request_count"] == 2
        
        # Test get specific collection
        response = client.get(f"/api/mcp/collections/{collection_name}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == collection_name
        assert len(data["requests"]) == 2
        
        # Test get non-existent collection
        response = client.get("/api/mcp/collections/nonexistent")
        assert response.status_code == 404
        
        # Test delete collection
        response = client.delete(f"/api/mcp/collections/{collection_name}")
        assert response.status_code == 200
        
        # Verify deletion
        response = client.get("/api/mcp/collections")
        assert response.status_code == 200
        data = response.json()
        assert len(data["collections"]) == 0
    
    def test_mcp_generate_sample_request(self):
        """Test sample request generation"""
        server_name = "test-server"
        tool_name = "test_tool"
        
        response = client.get(f"/api/mcp/generate-sample/{server_name}/{tool_name}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["server_name"] == server_name
        assert data["tool_name"] == tool_name
        assert "sample_request" in data
        
        sample = data["sample_request"]
        assert sample["tool_name"] == tool_name
        assert "arguments" in sample
        assert "description" in sample
    
    def test_mcp_history_size_limit(self):
        """Test that history respects size limits"""
        # Add exactly 100 requests manually
        for i in range(100):
            mcp_request_history.append({
                "request_id": f"req_{i}",
                "server_name": "server",
                "tool_name": "tool",
                "status": "success"
            })
        
        # Verify we have exactly 100
        assert len(mcp_request_history) == 100
        
        # Add one more request via API to trigger cleanup
        response = client.post("/api/mcp/call-tool/test-server", json={
            "tool_name": "cleanup_test",
            "arguments": {}
        })
        
        assert response.status_code == 200
        
        # After adding one more (101 total), cleanup should keep only 100
        # The cleanup removes the oldest, so we should have exactly 100
        assert len(mcp_request_history) == 100
        
        # Check that the oldest request was removed and newest is present
        request_ids = [r["request_id"] for r in mcp_request_history]
        assert "req_0" not in request_ids  # First request should be removed
        assert any("cleanup_test" in r.get("tool_name", "") for r in mcp_request_history)  # New request should be present
    
    def test_mcp_request_id_generation(self):
        """Test that request IDs are unique and properly formatted"""
        responses = []
        
        # Make multiple requests
        for i in range(3):
            response = client.post("/api/mcp/call-tool/test-server", json={
                "tool_name": f"test_tool_{i}",
                "arguments": {"iteration": i}
            })
            assert response.status_code == 200
            responses.append(response.json())
        
        # Check that all request IDs are unique and properly formatted
        request_ids = [r["request_id"] for r in responses]
        assert len(set(request_ids)) == 3  # All unique
        
        for req_id in request_ids:
            assert req_id.startswith("req_")
            assert len(req_id) > 4  # Has timestamp part

# Run the tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])