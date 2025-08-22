#!/usr/bin/env python3
"""
Integration tests for the filtered SSE bridge
Tests end-to-end scenarios and integration with Firecrawl
"""

import asyncio
import json
import pytest
import aiohttp
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sse_process import SSEProcess
from enhanced_broker import EnhancedBroker
from content_filters import FilterConfig

class TestSSEProcess:
    """Test SSE process connection functionality"""
    
    @pytest.mark.asyncio
    async def test_sse_connection_establishment(self):
        """Test establishing SSE connection"""
        # Mock the aiohttp response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.content = AsyncMock()
        
        # Mock SSE stream data
        async def mock_content():
            yield b"event: endpoint\n"
            yield b"data: http://localhost:3000/messages?session=test123\n\n"
            yield b"event: message\n"
            yield b'data: {"jsonrpc": "2.0", "id": "health-check", "result": {}}\n\n'
            
        mock_response.content.__aiter__ = mock_content
        
        with patch('aiohttp.ClientSession.get', return_value=mock_response):
            sse_proc = SSEProcess("http://localhost:3000/sse")
            
            # Should not raise exception
            await sse_proc.start()
            assert sse_proc.running
            assert sse_proc.message_endpoint == "http://localhost:3000/messages?session=test123"
            
            await sse_proc.cleanup()
            
    @pytest.mark.asyncio
    async def test_sse_message_exchange(self):
        """Test sending and receiving messages via SSE"""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        
        sse_proc = SSEProcess("http://localhost:3000/sse")
        sse_proc.session = mock_session
        sse_proc.message_endpoint = "http://localhost:3000/messages"
        sse_proc.running = True
        
        # Mock POST request
        mock_session.post.return_value.__aenter__.return_value.status = 202
        
        test_message = {
            "jsonrpc": "2.0",
            "id": "test-123",
            "method": "tools/call",
            "params": {"name": "test_tool"}
        }
        
        # Should not raise exception
        await sse_proc.write_json(test_message)
        
        # Verify POST was called
        mock_session.post.assert_called_once()

class TestEnhancedBroker:
    """Test enhanced broker with filtering"""
    
    def setup_method(self):
        """Set up test environment"""
        self.mock_sse_proc = MagicMock()
        self.mock_sse_proc.running = True
        self.filter_config = FilterConfig()
        
    @pytest.mark.asyncio
    async def test_broker_initialization(self):
        """Test broker initialization with SSE process"""
        self.mock_sse_proc.start = AsyncMock()
        self.mock_sse_proc.read_json = AsyncMock()
        
        broker = EnhancedBroker(self.mock_sse_proc, self.filter_config)
        
        # Should initialize without error
        await broker.start()
        
        assert len(broker.sessions) == 0
        assert broker.content_filter is not None
        
    @pytest.mark.asyncio
    async def test_session_management(self):
        """Test session creation and management"""
        broker = EnhancedBroker(self.mock_sse_proc, self.filter_config)
        
        # Create session
        session_id = broker.create_session()
        assert session_id in broker.sessions
        
        # Get session
        session = broker.get_session(session_id)
        assert session.session_id == session_id
        
        # Get session details
        details = broker.get_session_details()
        assert details["active_sessions"] == 1
        assert session_id in details["sessions"]
        
    @pytest.mark.asyncio
    async def test_message_routing_with_filtering(self):
        """Test message routing with content filtering applied"""
        broker = EnhancedBroker(self.mock_sse_proc, self.filter_config)
        self.mock_sse_proc.write_json = AsyncMock()
        
        session_id = broker.create_session()
        
        # Test clean message (should pass through)
        clean_message = {
            "jsonrpc": "2.0",
            "id": "test-1",
            "method": "tools/call",
            "params": {"name": "test_tool"}
        }
        
        await broker.route_from_client(session_id, clean_message)
        self.mock_sse_proc.write_json.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_blocked_message_handling(self):
        """Test handling of blocked messages"""
        # Configure strict filtering
        strict_config = FilterConfig(
            blocked_domains=["malware.test.com"]
        )
        broker = EnhancedBroker(self.mock_sse_proc, strict_config)
        self.mock_sse_proc.write_json = AsyncMock()
        
        session_id = broker.create_session()
        
        # Test blocked message
        blocked_message = {
            "jsonrpc": "2.0",
            "id": "test-blocked",
            "method": "tools/call",
            "params": {
                "name": "firecrawl_scrape",
                "arguments": {"url": "https://malware.test.com/page"}
            }
        }
        
        await broker.route_from_client(session_id, blocked_message)
        
        # Should not call upstream server
        self.mock_sse_proc.write_json.assert_not_called()
        
        # Check session metrics
        session = broker.get_session(session_id)
        assert session.filter_metrics.get("blocked_messages", 0) >= 1

class TestEndToEndIntegration:
    """End-to-end integration tests"""
    
    @pytest.mark.asyncio
    async def test_firecrawl_integration_flow(self):
        """Test complete flow with simulated Firecrawl server"""
        # This test simulates the complete flow:
        # 1. Connect to mock Firecrawl SSE server
        # 2. Process web scraping request
        # 3. Apply content filtering
        # 4. Return filtered results
        
        # Mock Firecrawl responses
        mock_firecrawl_responses = [
            {
                "jsonrpc": "2.0",
                "id": "init-response",
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "Firecrawl", "version": "1.0.0"}
                }
            },
            {
                "jsonrpc": "2.0",
                "id": "scrape-response",
                "result": {
                    "content": "This is clean website content without PII",
                    "metadata": {"url": "https://example.com"}
                }
            }
        ]
        
        # Test with permissive filtering (should pass through)
        permissive_config = FilterConfig(
            blocked_domains=[],
            redact_emails=False,
            max_response_length=50000
        )
        
        # Mock the entire SSE process
        mock_sse_proc = MagicMock()
        mock_sse_proc.running = True
        mock_sse_proc.start = AsyncMock()
        mock_sse_proc.write_json = AsyncMock()
        mock_sse_proc.read_json = AsyncMock(side_effect=mock_firecrawl_responses)
        
        broker = EnhancedBroker(mock_sse_proc, permissive_config)
        session_id = broker.create_session()
        
        # Simulate initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": "init-123",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "Test Client", "version": "1.0.0"}
            }
        }
        
        await broker.route_from_client(session_id, init_request)
        
        # Simulate scraping request
        scrape_request = {
            "jsonrpc": "2.0",
            "id": "scrape-456",
            "method": "tools/call",
            "params": {
                "name": "firecrawl_scrape",
                "arguments": {
                    "url": "https://example.com",
                    "formats": ["markdown"]
                }
            }
        }
        
        await broker.route_from_client(session_id, scrape_request)
        
        # Verify upstream calls were made
        assert mock_sse_proc.write_json.call_count >= 1
        
    @pytest.mark.asyncio
    async def test_pii_redaction_integration(self):
        """Test PII redaction in realistic web scraping scenario"""
        # Mock response with PII
        pii_response = {
            "jsonrpc": "2.0",
            "id": "scrape-pii",
            "result": {
                "content": """
                <div>
                    <h1>Contact Information</h1>
                    <p>Email: contact@example.com</p>
                    <p>Phone: (555) 123-4567</p>
                    <p>SSN: 123-45-6789</p>
                </div>
                """,
                "metadata": {"url": "https://example.com/contact"}
            }
        }
        
        # Configure PII redaction
        pii_config = FilterConfig(
            redact_emails=True,
            redact_phones=True,
            redact_ssns=True
        )
        
        filter_instance = ContentFilter(pii_config)
        
        # Apply filtering
        filtered = await filter_instance.filter_message(
            "server_to_client", "test-session", pii_response
        )
        
        content = filtered["result"]["content"]
        assert "[EMAIL_REDACTED]" in content
        assert "[PHONE_REDACTED]" in content
        assert "[SSN_REDACTED]" in content
        assert "contact@example.com" not in content
        assert "(555) 123-4567" not in content
        assert "123-45-6789" not in content
        
    @pytest.mark.asyncio
    async def test_malicious_content_blocking(self):
        """Test blocking of malicious content"""
        # Mock malicious scraping request
        malicious_request = {
            "jsonrpc": "2.0",
            "id": "malicious-scrape",
            "method": "tools/call",
            "params": {
                "name": "firecrawl_scrape",
                "arguments": {
                    "url": "https://malware.test.com/exploit"
                }
            }
        }
        
        # Configure strict filtering
        strict_config = FilterConfig(
            blocked_domains=["malware.test.com"],
            blocked_keywords=["exploit"]
        )
        
        filter_instance = ContentFilter(strict_config)
        
        # Should be blocked
        result = await filter_instance.filter_message(
            "client_to_server", "test-session", malicious_request
        )
        
        assert result is None  # Blocked
        
    @pytest.mark.asyncio
    async def test_large_response_handling(self):
        """Test handling of large responses with summarization"""
        # Mock large response
        large_content = "This is a very long article. " * 1000
        large_response = {
            "jsonrpc": "2.0",
            "id": "large-content",
            "result": {
                "content": large_content,
                "metadata": {"url": "https://example.com/article"}
            }
        }
        
        # Configure size limits
        size_config = FilterConfig(
            max_response_length=1000,
            summarize_threshold=500
        )
        
        filter_instance = ContentFilter(size_config)
        
        # Apply filtering
        filtered = await filter_instance.filter_message(
            "server_to_client", "test-session", large_response
        )
        
        filtered_content = filtered["result"]["content"]
        assert len(filtered_content) <= size_config.max_response_length
        assert "[SUMMARIZED]" in filtered_content or "[TRUNCATED]" in filtered_content

if __name__ == "__main__":
    pytest.main([__file__, "-v"])