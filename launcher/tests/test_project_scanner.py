#!/usr/bin/env python3
"""
Unit tests for ProjectScanner
"""

import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, mock_open

from project_scanner import ProjectScanner

@pytest.fixture
def scanner():
    return ProjectScanner()

@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory with MCP configs"""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir) / "test_project"
        project_path.mkdir()
        
        # Create .mcp.json
        mcp_config = {
            "mcpServers": {
                "test-server": {
                    "type": "stdio",
                    "command": "uvx",
                    "args": ["test-server"],
                    "description": "Test server"
                }
            }
        }
        with open(project_path / ".mcp.json", "w") as f:
            json.dump(mcp_config, f)
        
        # Create package.json
        package_json = {
            "name": "test-project",
            "description": "Test project description"
        }
        with open(project_path / "package.json", "w") as f:
            json.dump(package_json, f)
        
        yield project_path

class TestProjectScanner:
    
    @pytest.mark.asyncio
    async def test_analyze_directory_with_mcp_config(self, scanner, temp_project_dir):
        """Test analyzing directory with MCP configuration"""
        result = await scanner._analyze_directory(temp_project_dir)
        
        assert result is not None
        assert result["name"] == "test-project"
        assert result["path"] == str(temp_project_dir)
        assert result["description"] == "Test project description"
        assert len(result["config_sources"]) == 1
        
        config_source = result["config_sources"][0]
        assert config_source["type"] == "project"
        assert config_source["server_count"] == 1
        assert "test-server" in config_source["servers"]
    
    @pytest.mark.asyncio
    async def test_analyze_directory_no_config(self, scanner):
        """Test analyzing directory without MCP configuration"""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = await scanner._analyze_directory(Path(temp_dir))
            assert result is None
    
    @pytest.mark.asyncio
    async def test_scan_directory(self, scanner, temp_project_dir):
        """Test scanning directory for projects"""
        parent_dir = temp_project_dir.parent
        results = await scanner.scan_directory(str(parent_dir), max_depth=1)
        
        assert len(results) >= 1
        project_names = [p["name"] for p in results]
        assert "test-project" in project_names
    
    @pytest.mark.asyncio
    async def test_validate_project_path(self, scanner, temp_project_dir):
        """Test path validation"""
        # Valid path
        assert await scanner.validate_project_path(str(temp_project_dir)) == True
        
        # Invalid path
        assert await scanner.validate_project_path("/nonexistent/path") == False
        
        # Path traversal attempt
        assert await scanner.validate_project_path("../../../etc") == False
    
    @pytest.mark.asyncio
    async def test_get_config_preview(self, scanner, temp_project_dir):
        """Test getting configuration preview"""
        config_path = temp_project_dir / ".mcp.json"
        preview = await scanner.get_config_preview(str(config_path))
        
        assert "servers" in preview
        assert "test-server" in preview["servers"]
        assert preview["summary"]["total_servers"] == 1
        assert preview["summary"]["stdio_servers"] == 1
    
    @pytest.mark.asyncio
    async def test_analyze_claude_config(self, scanner):
        """Test analyzing Claude configuration format"""
        claude_config = {
            "mcpServers": {
                "claude-server": {
                    "type": "stdio",
                    "command": "uvx",
                    "args": ["claude-server"],
                    "description": "Claude MCP server"
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.claude.json', delete=False) as f:
            json.dump(claude_config, f)
            f.flush()
            
            try:
                result = await scanner._analyze_config_file(Path(f.name), "user")
                assert result is not None
                assert result["type"] == "user"
                assert result["server_count"] == 1
                assert "claude-server" in result["servers"]
            finally:
                os.unlink(f.name)
    
    @pytest.mark.asyncio
    async def test_analyze_invalid_config(self, scanner):
        """Test analyzing invalid configuration file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content {")
            f.flush()
            
            try:
                result = await scanner._analyze_config_file(Path(f.name), "project")
                assert result is not None
                assert result["valid"] == False
                assert "error" in result
            finally:
                os.unlink(f.name)

if __name__ == "__main__":
    pytest.main([__file__])