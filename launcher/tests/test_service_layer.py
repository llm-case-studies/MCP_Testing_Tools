#!/usr/bin/env python3
"""
Unit tests for Service Layer
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from launcher.services import LauncherService
from launcher.session import SessionManager, ManagedSession
from launcher.project_scanner import ProjectScanner


@pytest.fixture
def mock_session_manager():
    return MagicMock(spec=SessionManager)


@pytest.fixture
def mock_project_scanner():
    return MagicMock(spec=ProjectScanner)


@pytest.fixture
def launcher_service(mock_session_manager, mock_project_scanner):
    return LauncherService(mock_session_manager, mock_project_scanner)


class TestLauncherService:
    
    @pytest.mark.asyncio
    async def test_launch_session_success(self, launcher_service, mock_session_manager):
        """Test successful session launch through service layer"""
        # Mock session manager response
        mock_session = ManagedSession(
            session_id="test123",
            project_path="/test/project",
            config_source="/test/config.json",
            config_type="project",
            status="running",
            backend_url="http://localhost:8095"
        )
        mock_session_manager.launch_session = AsyncMock(return_value=mock_session)
        
        config_data = {
            "project_path": "/test/project",
            "config_source": "/test/config.json",
            "config_type": "project"
        }
        
        # Mock Path existence checks
        with patch('launcher.services.launcher_service.Path') as mock_path:
            mock_path_obj = MagicMock()
            mock_path_obj.exists.return_value = True
            mock_path.return_value = mock_path_obj
            
            result = await launcher_service.launch_session(config_data)
            
            assert result["session_id"] == "test123"
            assert result["backend_url"] == "http://localhost:8095"
            assert result["status"] == "running"
            assert "message" in result
            mock_session_manager.launch_session.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_launch_session_validation_error(self, launcher_service):
        """Test validation error in launch session"""
        config_data = {
            "project_path": "",  # Invalid empty path
            "config_source": "/test/config.json",
            "config_type": "project"
        }
        
        with pytest.raises(ValueError, match="Empty value for required field"):
            await launcher_service.launch_session(config_data)
    
    @pytest.mark.asyncio
    async def test_list_sessions_with_stats(self, launcher_service, mock_session_manager):
        """Test list sessions with enhanced statistics"""
        mock_sessions = [
            {"session_id": "test1", "status": "running"},
            {"session_id": "test2", "status": "stopped"}
        ]
        mock_stats = {
            "total_sessions": 2,
            "status_breakdown": {"running": 1, "stopped": 1},
            "available_slots": 4
        }
        
        mock_session_manager.list_sessions = AsyncMock(return_value=mock_sessions)
        mock_session_manager.get_session_stats = AsyncMock(return_value=mock_stats)
        
        result = await launcher_service.list_sessions()
        
        assert result["sessions"] == mock_sessions
        assert result["total_sessions"] == 2
        assert result["status_breakdown"]["running"] == 1
        assert result["available_slots"] == 4
    
    @pytest.mark.asyncio
    async def test_browse_folders_enhanced(self, launcher_service):
        """Test enhanced folder browsing with project indicators"""
        with patch('launcher.services.launcher_service.Path') as mock_path:
            # Mock Path behavior
            mock_path_obj = MagicMock()
            mock_path_obj.resolve.return_value = mock_path_obj
            mock_path_obj.exists.return_value = True
            mock_path_obj.is_dir.return_value = True
            mock_path_obj.parent = MagicMock()
            mock_path_obj.parent.__ne__ = MagicMock(return_value=True)
            str(mock_path_obj.parent) == "/parent"
            
            # Mock directory iteration
            mock_item = MagicMock()
            mock_item.is_dir.return_value = True
            mock_item.name = "test-project"
            mock_item.__truediv__ = MagicMock(return_value=MagicMock(exists=MagicMock(return_value=True)))
            
            mock_path_obj.iterdir.return_value = [mock_item]
            mock_path.return_value = mock_path_obj
            
            result = await launcher_service.browse_folders("/test")
            
            assert "folders" in result
            assert "total_folders" in result
            assert "project_folders" in result
    
    @pytest.mark.asyncio
    async def test_get_health_status(self, launcher_service, mock_session_manager):
        """Test comprehensive health status"""
        mock_sessions = [{"session_id": "test1", "status": "running"}]
        mock_stats = {
            "total_sessions": 1,
            "status_breakdown": {"running": 1},
            "available_slots": 4
        }
        
        mock_session_manager.list_sessions = AsyncMock(return_value=mock_sessions)
        mock_session_manager.get_session_stats = AsyncMock(return_value=mock_stats)
        mock_session_manager.max_concurrent_sessions = 5
        
        result = await launcher_service.get_health_status()
        
        assert result["status"] == "healthy"
        assert result["service"] == "mcp-launcher"
        assert result["version"] == "2.0.0"
        assert "sessions" in result
        assert "components" in result
        assert result["sessions"]["total"] == 1
        assert result["sessions"]["active"] == 1
        assert result["components"]["session_manager"] == "operational"
    
    @pytest.mark.asyncio
    async def test_stop_session(self, launcher_service, mock_session_manager):
        """Test session stopping through service layer"""
        mock_session_manager.stop_session = AsyncMock()
        
        result = await launcher_service.stop_session("test123")
        
        assert result["message"] == "Session test123 stopped successfully"
        mock_session_manager.stop_session.assert_called_once_with("test123")
    
    @pytest.mark.asyncio
    async def test_scan_projects_enhanced(self, launcher_service, mock_project_scanner):
        """Test enhanced project scanning with metadata"""
        mock_projects = [
            {"name": "project1", "config_sources": [{"type": "project"}]},
            {"name": "project2", "config_sources": [{"type": "user"}]}
        ]
        mock_project_scanner.scan_directory = AsyncMock(return_value=mock_projects)
        
        result = await launcher_service.scan_projects("/test")
        
        assert result["projects"] == mock_projects
        assert result["total_projects"] == 2
        assert result["config_types"]["project"] == 1
        assert result["config_types"]["user"] == 1
        assert "scan_summary" in result


if __name__ == "__main__":
    pytest.main([__file__])