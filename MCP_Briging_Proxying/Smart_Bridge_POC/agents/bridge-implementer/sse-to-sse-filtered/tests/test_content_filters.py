#!/usr/bin/env python3
"""
Test suite for content filtering functionality
Tests all filtering scenarios: blacklist, sanitization, PII redaction, response management
"""

import asyncio
import json
import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from content_filters import ContentFilter, FilterConfig

class TestContentFilters:
    """Test content filtering functionality"""
    
    def setup_method(self):
        """Set up test environment"""
        self.default_config = FilterConfig()
        self.content_filter = ContentFilter(self.default_config)
        
    @pytest.mark.asyncio
    async def test_blacklist_domain_filtering(self):
        """Test domain blacklist filtering"""
        config = FilterConfig(
            blocked_domains=["malware.test.com", "ads.example.com"]
        )
        filter_instance = ContentFilter(config)
        
        # Test blocked domain
        blocked_message = {
            "jsonrpc": "2.0",
            "id": "test-1",
            "method": "tools/call",
            "params": {
                "name": "firecrawl_scrape",
                "arguments": {"url": "https://malware.test.com/page"}
            }
        }
        
        result = await filter_instance.filter_message(
            "client_to_server", "test-session", blocked_message
        )
        assert result is None  # Should be blocked
        
        # Test allowed domain
        allowed_message = {
            "jsonrpc": "2.0",
            "id": "test-2",
            "method": "tools/call",
            "params": {
                "name": "firecrawl_scrape",
                "arguments": {"url": "https://legitimate.site.com/page"}
            }
        }
        
        result = await filter_instance.filter_message(
            "client_to_server", "test-session", allowed_message
        )
        assert result is not None  # Should pass through
        assert result == allowed_message
        
    @pytest.mark.asyncio
    async def test_keyword_blacklist_filtering(self):
        """Test keyword blacklist filtering"""
        config = FilterConfig(
            blocked_keywords=["malicious", "virus", "exploit"]
        )
        filter_instance = ContentFilter(config)
        
        # Test blocked keyword
        blocked_message = {
            "jsonrpc": "2.0",
            "result": {
                "content": "This is a malicious website with virus content"
            }
        }
        
        result = await filter_instance.filter_message(
            "client_to_server", "test-session", blocked_message
        )
        assert result is None  # Should be blocked
        
        # Test clean content
        clean_message = {
            "jsonrpc": "2.0",
            "result": {
                "content": "This is a legitimate website with good content"
            }
        }
        
        result = await filter_instance.filter_message(
            "client_to_server", "test-session", clean_message
        )
        assert result is not None  # Should pass through
        
    @pytest.mark.asyncio
    async def test_html_sanitization(self):
        """Test HTML content sanitization"""
        config = FilterConfig(
            remove_scripts=True,
            remove_tracking=True,
            normalize_whitespace=True
        )
        filter_instance = ContentFilter(config)
        
        # Test script removal
        malicious_html = """
        <div>
            <h1>Title</h1>
            <script>alert('XSS')</script>
            <p onclick="malicious()">Click me</p>
            <img src="tracking-pixel.gif" />
        </div>
        """
        
        message = {
            "jsonrpc": "2.0",
            "result": {
                "content": malicious_html
            }
        }
        
        result = await filter_instance.filter_message(
            "server_to_client", "test-session", message
        )
        
        assert result is not None
        content = result["result"]["content"]
        assert "<script>" not in content
        assert "alert" not in content
        assert "onclick" not in content
        
    @pytest.mark.asyncio
    async def test_pii_redaction(self):
        """Test PII redaction functionality"""
        config = FilterConfig(
            redact_emails=True,
            redact_phones=True,
            redact_ssns=True,
            redact_credit_cards=True
        )
        filter_instance = ContentFilter(config)
        
        # Test various PII types
        pii_content = """
        Contact: john.doe@example.com
        Phone: (555) 123-4567
        SSN: 123-45-6789
        Credit Card: 4111-1111-1111-1111
        """
        
        message = {
            "jsonrpc": "2.0",
            "result": {
                "content": pii_content
            }
        }
        
        result = await filter_instance.filter_message(
            "server_to_client", "test-session", message
        )
        
        assert result is not None
        content = result["result"]["content"]
        assert "[EMAIL_REDACTED]" in content
        assert "[PHONE_REDACTED]" in content
        assert "[SSN_REDACTED]" in content
        assert "[CREDIT_CARD_REDACTED]" in content
        assert "john.doe@example.com" not in content
        assert "(555) 123-4567" not in content
        assert "123-45-6789" not in content
        assert "4111-1111-1111-1111" not in content
        
    @pytest.mark.asyncio
    async def test_response_size_management(self):
        """Test response summarization and truncation"""
        config = FilterConfig(
            max_response_length=100,
            summarize_threshold=50
        )
        filter_instance = ContentFilter(config)
        
        # Test summarization
        long_content = "This is a very long piece of content. " * 50
        
        message = {
            "jsonrpc": "2.0",
            "result": {
                "content": long_content
            }
        }
        
        result = await filter_instance.filter_message(
            "server_to_client", "test-session", message
        )
        
        assert result is not None
        content = result["result"]["content"]
        assert len(content) <= config.max_response_length
        
    @pytest.mark.asyncio
    async def test_clean_passthrough(self):
        """Test that clean content passes through unmodified"""
        clean_message = {
            "jsonrpc": "2.0",
            "id": "test-clean",
            "method": "tools/call",
            "params": {
                "name": "firecrawl_scrape",
                "arguments": {"url": "https://legitimate.site.com/article"}
            }
        }
        
        result = await filter_instance.filter_message(
            "client_to_server", "test-session", clean_message
        )
        
        assert result == clean_message  # Should be identical
        
    @pytest.mark.asyncio
    async def test_filter_metrics(self):
        """Test that filter metrics are properly tracked"""
        initial_metrics = self.content_filter.get_metrics()
        assert initial_metrics["total_requests"] == 0
        
        # Process a message
        message = {"jsonrpc": "2.0", "result": {"content": "test"}}
        await self.content_filter.filter_message(
            "server_to_client", "test-session", message
        )
        
        updated_metrics = self.content_filter.get_metrics()
        assert updated_metrics["total_requests"] == 1
        
    @pytest.mark.asyncio
    async def test_configuration_update(self):
        """Test runtime configuration updates"""
        # Initially allow all
        config = FilterConfig(blocked_domains=[])
        filter_instance = ContentFilter(config)
        
        message = {
            "jsonrpc": "2.0",
            "params": {"arguments": {"url": "https://test.com"}}
        }
        
        # Should pass initially
        result = await filter_instance.filter_message(
            "client_to_server", "test-session", message
        )
        assert result is not None
        
        # Update config to block domain
        new_config = FilterConfig(blocked_domains=["test.com"])
        filter_instance.update_config(new_config)
        
        # Should now be blocked
        result = await filter_instance.filter_message(
            "client_to_server", "test-session", message
        )
        assert result is None
        
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test that filtering errors don't break the system"""
        # Create a message that might cause processing errors
        malformed_message = {
            "jsonrpc": "2.0",
            "result": {
                "content": {"nested": {"very": {"deep": "content"}}}
            }
        }
        
        # Should not throw exception
        result = await self.content_filter.filter_message(
            "server_to_client", "test-session", malformed_message
        )
        
        # Should return some result (either filtered or original)
        assert result is not None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])