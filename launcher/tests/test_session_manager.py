#!/usr/bin/env python3
"""
Unit tests for SessionManager
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from session_manager import SessionManager, ManagedSession, PortAllocator

class MockLaunchConfig:
    def __init__(self, project_path="/test/project", config_source="/test/config.json", 
                 config_type="project", session_name="test-session"):
        self.project_path = project_path
        self.config_source = config_source
        self.config_type = config_type
        self.session_name = session_name
        self.selected_servers = None
        self.server_filter_mode = "include"

@pytest.fixture
def session_manager():
    return SessionManager(max_concurrent_sessions=3)

@pytest.fixture
def mock_config():
    return MockLaunchConfig()

class TestSessionManager:
    
    @pytest.mark.asyncio
    async def test_session_limits(self, session_manager, mock_config):
        """Test session limit enforcement"""
        # Mock the Docker operations
        with patch.object(session_manager, '_validate_paths', return_value=True), \
             patch.object(session_manager, '_launch_container'), \
             patch.object(session_manager.port_allocator, 'allocate_range', return_value=[8095, 8096]):
            
            # Launch sessions up to limit
            sessions = []
            for i in range(3):  # max_concurrent_sessions = 3
                config = MockLaunchConfig(session_name=f"test-session-{i}")
                session = await session_manager.launch_session(config)
                sessions.append(session)
                assert session.status == "starting"
            
            # Try to launch one more - should fail
            with pytest.raises(ValueError, match="Maximum concurrent sessions"):
                await session_manager.launch_session(mock_config)
            
            # Stop one session
            await session_manager.stop_session(sessions[0].session_id)
            
            # Now should be able to launch another
            new_session = await session_manager.launch_session(mock_config)
            assert new_session.status == "starting"
    
    @pytest.mark.asyncio
    async def test_validate_paths(self, session_manager):
        """Test path validation"""
        # Mock os.path and pathlib operations
        with patch('session_manager.Path') as mock_path:
            # Valid paths
            mock_path_obj = MagicMock()
            mock_path_obj.resolve.return_value = mock_path_obj
            mock_path_obj.exists.return_value = True
            mock_path_obj.is_dir.return_value = True
            mock_path.return_value = mock_path_obj
            
            result = await session_manager._validate_paths("/valid/project", "/valid/config.json")
            assert result == True
            
            # Invalid project path
            mock_path_obj.exists.return_value = False
            result = await session_manager._validate_paths("/invalid/project", "/valid/config.json")
            assert result == False
    
    @pytest.mark.asyncio
    async def test_session_lifecycle(self, session_manager, mock_config):
        """Test complete session lifecycle"""
        with patch.object(session_manager, '_validate_paths', return_value=True), \
             patch.object(session_manager, '_launch_container') as mock_launch, \
             patch.object(session_manager.port_allocator, 'allocate_range', return_value=[8095, 8096]):
            
            # Launch session
            session = await session_manager.launch_session(mock_config)
            assert session.session_id in session_manager.sessions
            assert session.status == "starting"
            
            # List sessions
            sessions_list = await session_manager.list_sessions()
            assert len(sessions_list) == 1
            assert sessions_list[0]["session_id"] == session.session_id
            
            # Stop session
            with patch('session_manager.subprocess.run') as mock_subprocess:
                mock_subprocess.return_value.returncode = 0
                await session_manager.stop_session(session.session_id)
                assert session.status == "stopped"
            
            # Remove session
            await session_manager.remove_session(session.session_id)
            assert session.session_id not in session_manager.sessions
    
    @pytest.mark.asyncio
    async def test_cleanup_old_sessions(self, session_manager):
        """Test cleanup of old sessions"""
        # Create an old stopped session
        old_session = ManagedSession(
            session_id="old-session",
            project_path="/test/project",
            config_source="/test/config.json",
            config_type="project",
            status="stopped"
        )
        # Make it old
        old_session.last_activity = datetime(2020, 1, 1)
        
        session_manager.sessions["old-session"] = old_session
        
        # Add a recent session
        recent_session = ManagedSession(
            session_id="recent-session",
            project_path="/test/project",
            config_source="/test/config.json", 
            config_type="project",
            status="stopped"
        )
        session_manager.sessions["recent-session"] = recent_session
        
        # Cleanup with 1 hour max age
        await session_manager.cleanup_old_sessions(max_age_hours=1)
        
        # Old session should be removed, recent should remain
        assert "old-session" not in session_manager.sessions
        assert "recent-session" in session_manager.sessions

class TestPortAllocator:
    
    @pytest.mark.asyncio
    async def test_port_allocation(self):
        """Test port allocation logic"""
        allocator = PortAllocator(8095, 8099)
        
        # Allocate single port
        with patch.object(allocator, '_is_port_available', return_value=True):
            port = await allocator.allocate_port()
            assert port == 8095
            assert port in allocator.allocated_ports
        
        # Allocate range
        with patch.object(allocator, '_is_port_available', return_value=True):
            ports = await allocator.allocate_range(3)
            assert len(ports) == 3
            assert all(p in allocator.allocated_ports for p in ports)
        
        # Release port
        await allocator.release_port(ports[0])
        assert ports[0] not in allocator.allocated_ports
    
    @pytest.mark.asyncio
    async def test_port_exhaustion(self):
        """Test behavior when ports are exhausted"""
        allocator = PortAllocator(8095, 8096)  # Only 2 ports available
        
        with patch.object(allocator, '_is_port_available', return_value=True):
            # Allocate all available ports
            port1 = await allocator.allocate_port()
            port2 = await allocator.allocate_port()
            
            # Try to allocate one more - should fail
            with pytest.raises(RuntimeError, match="No available ports"):
                await allocator.allocate_port()

if __name__ == "__main__":
    pytest.main([__file__])