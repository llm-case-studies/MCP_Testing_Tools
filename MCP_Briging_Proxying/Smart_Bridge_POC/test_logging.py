#!/usr/bin/env python3
"""
Unit and E2E tests for bridge logging functionality
"""

import os
import tempfile
import logging
import json
import subprocess
import time
import requests
import pytest
from pathlib import Path

# Import the bridge module
import sys
sys.path.insert(0, os.path.dirname(__file__))
from simple_bridge import setup_logging, logger

class TestLoggingSetup:
    """Unit tests for logging configuration"""
    
    def test_console_logging_only(self):
        """Test logging setup with console only"""
        # Clear existing handlers
        logger.handlers.clear()
        
        setup_logging("DEBUG", None)
        
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.StreamHandler)
        assert logger.level == logging.DEBUG
    
    def test_file_logging(self):
        """Test logging setup with file output"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger.handlers.clear()
            
            setup_logging("INFO", tmpdir)
            
            assert len(logger.handlers) == 2  # Console + file
            assert logger.level == logging.INFO
            
            # Check file handler exists
            file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
            assert len(file_handlers) == 1
            
            # Test logging to file
            logger.info("Test log message")
            
            log_file = Path(tmpdir) / "simple_bridge.log"
            assert log_file.exists()
            
            with open(log_file) as f:
                content = f.read()
                assert "Test log message" in content
    
    def test_log_levels(self):
        """Test different log levels"""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            logger.handlers.clear()
            setup_logging(level, None)
            assert logger.level == getattr(logging, level)

class TestBridgeLoggingE2E:
    """End-to-end tests for bridge logging in action"""
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary directory for logs"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def start_bridge(self, port, log_level, log_location=None, timeout=10):
        """Start bridge with specific logging config"""
        cmd = [
            "python3", "simple_bridge.py",
            "--port", str(port),
            "--cmd", "echo 'test'",  # Dummy command for testing
            "--log_level", log_level
        ]
        
        if log_location:
            cmd.extend(["--log_location", log_location])
        
        env = os.environ.copy()
        env["BRIDGE_AUTH_MODE"] = "none"
        
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=os.path.dirname(__file__)
        )
        
        # Wait for bridge to start
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"http://localhost:{port}/health", timeout=1)
                if response.status_code == 200:
                    return proc
            except:
                pass
            time.sleep(0.1)
        
        proc.terminate()
        raise Exception(f"Bridge failed to start on port {port}")
    
    def test_debug_logging_captures_messages(self, temp_log_dir):
        """Test that DEBUG level captures all message details"""
        port = 9001
        proc = None
        
        try:
            proc = self.start_bridge(port, "DEBUG", temp_log_dir)
            
            # Send a test message
            test_message = {
                "jsonrpc": "2.0",
                "id": "test-123",
                "method": "test/method",
                "params": {"key": "value"}
            }
            
            # This should fail (no session) but we want to test logging
            try:
                requests.post(
                    f"http://localhost:{port}/messages",
                    json=test_message,
                    timeout=2
                )
            except:
                pass  # Expected to fail
            
            time.sleep(1)  # Let logs flush
            
            # Check log file contains message details
            log_file = Path(temp_log_dir) / "simple_bridge.log"
            assert log_file.exists()
            
            with open(log_file) as f:
                content = f.read()
                assert "test/method" in content
                assert "test-123" in content
                assert "Full message payload" in content
        
        finally:
            if proc:
                proc.terminate()
                proc.wait()
    
    def test_info_logging_level(self, temp_log_dir):
        """Test that INFO level doesn't show DEBUG messages"""
        port = 9002
        proc = None
        
        try:
            proc = self.start_bridge(port, "INFO", temp_log_dir)
            
            # Send a test message
            test_message = {"jsonrpc": "2.0", "id": "test-456", "method": "test"}
            
            try:
                requests.post(f"http://localhost:{port}/messages", json=test_message, timeout=2)
            except:
                pass
            
            time.sleep(1)
            
            log_file = Path(temp_log_dir) / "simple_bridge.log"
            with open(log_file) as f:
                content = f.read()
                assert "Received message from" in content  # INFO level
                assert "Full message payload" not in content  # DEBUG level
        
        finally:
            if proc:
                proc.terminate()
                proc.wait()
    
    def test_sse_connection_logging(self, temp_log_dir):
        """Test that SSE connections are properly logged"""
        port = 9003
        proc = None
        
        try:
            proc = self.start_bridge(port, "DEBUG", temp_log_dir)
            
            # Make SSE connection
            response = requests.get(
                f"http://localhost:{port}/sse",
                headers={"Accept": "text/event-stream"},
                timeout=2,
                stream=True
            )
            
            time.sleep(1)
            
            log_file = Path(temp_log_dir) / "simple_bridge.log"
            with open(log_file) as f:
                content = f.read()
                assert "SSE connection from" in content
                assert "Auto-created SSE session" in content
        
        finally:
            if proc:
                proc.terminate()
                proc.wait()

def run_logging_tests():
    """Run all logging tests"""
    # Run unit tests
    test_setup = TestLoggingSetup()
    test_setup.test_console_logging_only()
    test_setup.test_file_logging()
    test_setup.test_log_levels()
    print("✓ Unit tests passed")
    
    # Run E2E tests  
    test_e2e = TestBridgeLoggingE2E()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_e2e.test_debug_logging_captures_messages(tmpdir)
        print("✓ DEBUG logging test passed")
        
        test_e2e.test_info_logging_level(tmpdir)
        print("✓ INFO logging test passed")
        
        test_e2e.test_sse_connection_logging(tmpdir)
        print("✓ SSE logging test passed")
    
    print("✓ All logging tests passed!")

if __name__ == "__main__":
    run_logging_tests()