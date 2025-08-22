#!/usr/bin/env python3
"""
Content Filtering Framework for SSE Bridge Security
Implements comprehensive content sanitization, PII redaction, and response management
"""

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, field
from html import escape, unescape
import html.parser
from urllib.parse import urlparse

logger = logging.getLogger("content-filters")

@dataclass
class FilterConfig:
    """Configuration for content filtering"""
    # Blacklist filtering
    blocked_domains: List[str] = field(default_factory=list)
    blocked_keywords: List[str] = field(default_factory=list)
    blocked_patterns: List[str] = field(default_factory=list)
    
    # Content sanitization
    remove_scripts: bool = True
    remove_tracking: bool = True
    remove_ads: bool = True
    normalize_whitespace: bool = True
    
    # PII redaction
    redact_emails: bool = True
    redact_phones: bool = True
    redact_ssns: bool = True
    redact_credit_cards: bool = True
    
    # Response management
    max_response_length: int = 15000
    summarize_threshold: int = 5000
    preserve_structure: bool = True
    
    # Performance settings
    enable_caching: bool = True
    cache_ttl: int = 300  # 5 minutes
    
    # Audit settings
    log_blocked_content: bool = True
    log_pii_redactions: bool = True
    log_response_summaries: bool = True

@dataclass
class FilterMetrics:
    """Metrics for filter performance tracking"""
    total_requests: int = 0
    blocked_requests: int = 0
    pii_redactions: int = 0
    content_sanitizations: int = 0
    response_summaries: int = 0
    total_processing_time: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0

class HTMLSanitizer(html.parser.HTMLParser):
    """HTML sanitizer that removes dangerous content while preserving structure"""
    
    def __init__(self, config: FilterConfig):
        super().__init__()
        self.config = config
        self.output = []
        self.skip_content = False
        
        # Tags to completely remove (including content)
        self.remove_tags = {'script', 'style', 'iframe', 'object', 'embed'}
        if config.remove_tracking:
            self.remove_tags.update({'img'})  # Remove tracking pixels
        if config.remove_ads:
            self.remove_tags.update({'ins', 'aside'})  # Common ad containers
            
        # Attributes to remove
        self.remove_attrs = {
            'onclick', 'onload', 'onerror', 'onmouseover', 'onmouseout',
            'onfocus', 'onblur', 'onchange', 'onsubmit', 'onreset',
            'style'  # Remove inline styles
        }
        
    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.remove_tags:
            self.skip_content = True
            return
            
        # Filter attributes
        clean_attrs = []
        for name, value in attrs:
            if name.lower() not in self.remove_attrs:
                # Additional attribute sanitization
                if name.lower() in ('src', 'href') and value:
                    # Basic URL validation
                    if not self._is_safe_url(value):
                        continue
                clean_attrs.append((name, escape(value) if value else ''))
                
        # Reconstruct tag
        attr_str = ' '.join([f'{name}="{value}"' for name, value in clean_attrs])
        tag_str = f'<{tag}'
        if attr_str:
            tag_str += f' {attr_str}'
        tag_str += '>'
        self.output.append(tag_str)
        
    def handle_endtag(self, tag):
        if tag.lower() in self.remove_tags:
            self.skip_content = False
            return
        self.output.append(f'</{tag}>')
        
    def handle_data(self, data):
        if not self.skip_content:
            self.output.append(escape(data))
            
    def _is_safe_url(self, url: str) -> bool:
        """Basic URL safety check"""
        try:
            parsed = urlparse(url)
            # Block javascript: and data: URLs
            if parsed.scheme.lower() in ('javascript', 'data', 'vbscript'):
                return False
            return True
        except:
            return False
            
    def get_output(self) -> str:
        return ''.join(self.output)

class ContentFilter:
    """Main content filtering engine"""
    
    def __init__(self, config: FilterConfig):
        self.config = config
        self.metrics = FilterMetrics()
        self.cache: Dict[str, Any] = {}
        self.cache_timestamps: Dict[str, float] = {}
        
        # Compile regex patterns for performance
        self._compile_patterns()
        
    def _compile_patterns(self):
        """Pre-compile regex patterns for better performance"""
        # PII patterns
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            re.IGNORECASE
        )
        
        self.phone_pattern = re.compile(
            r'(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})',
            re.IGNORECASE
        )
        
        self.ssn_pattern = re.compile(
            r'\b(?!000|666|9\d{2})\d{3}[-.\s]?(?!00)\d{2}[-.\s]?(?!0000)\d{4}\b'
        )
        
        self.credit_card_pattern = re.compile(
            r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3[0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b'
        )
        
        # Content patterns
        self.whitespace_pattern = re.compile(r'\s+')
        
        # Compile user-defined patterns
        self.blocked_patterns = []
        for pattern_str in self.config.blocked_patterns:
            try:
                self.blocked_patterns.append(re.compile(pattern_str, re.IGNORECASE))
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern_str}': {e}")
                
    async def filter_message(self, direction: str, session_id: str, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Main filtering function for MCP messages"""
        start_time = time.time()
        self.metrics.total_requests += 1
        
        try:
            # Check cache first
            cache_key = None
            if self.config.enable_caching and direction == "server_to_client":
                cache_key = self._get_cache_key(message)
                cached_result = self._get_cached_result(cache_key)
                if cached_result is not None:
                    self.metrics.cache_hits += 1
                    return cached_result
                self.metrics.cache_misses += 1
            
            # Apply filtering pipeline
            filtered_message = await self._apply_filters(direction, session_id, message)
            
            # Cache result if applicable
            if cache_key and filtered_message is not None:
                self._cache_result(cache_key, filtered_message)
                
            # Update metrics
            processing_time = time.time() - start_time
            self.metrics.total_processing_time += processing_time
            
            return filtered_message
            
        except Exception as e:
            logger.error(f"Filter error for session {session_id}: {e}")
            # Fail-safe: return original message on filter errors
            return message
            
    async def _apply_filters(self, direction: str, session_id: str, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Apply all filters in sequence"""
        # Step 1: Blacklist filtering (client_to_server only)
        if direction == "client_to_server":
            if not await self._check_blacklist(message):
                self.metrics.blocked_requests += 1
                if self.config.log_blocked_content:
                    logger.warning(f"Blocked request from session {session_id}: blacklist violation")
                return None
                
        # Step 2: Content sanitization (server_to_client only)
        if direction == "server_to_client":
            message = await self._sanitize_content(message)
            
        # Step 3: PII redaction (both directions)
        message = await self._redact_pii(message)
        
        # Step 4: Response management (server_to_client only)
        if direction == "server_to_client":
            message = await self._manage_response_size(message)
            
        return message
        
    async def _check_blacklist(self, message: Dict[str, Any]) -> bool:
        """Check if message violates blacklist rules"""
        # Extract URLs and text content for checking
        content_items = self._extract_content(message)
        
        for content in content_items:
            # Check blocked domains
            for domain in self.config.blocked_domains:
                if domain.lower() in content.lower():
                    return False
                    
            # Check blocked keywords
            for keyword in self.config.blocked_keywords:
                if keyword.lower() in content.lower():
                    return False
                    
            # Check blocked patterns
            for pattern in self.blocked_patterns:
                if pattern.search(content):
                    return False
                    
        return True
        
    async def _sanitize_content(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize HTML content in message"""
        def sanitize_string(value: str) -> str:
            # Remove script tags and JavaScript
            if self.config.remove_scripts:
                sanitizer = HTMLSanitizer(self.config)
                sanitizer.feed(value)
                value = sanitizer.get_output()
                
            # Normalize whitespace
            if self.config.normalize_whitespace:
                value = self.whitespace_pattern.sub(' ', value).strip()
                
            return value
            
        sanitized = self._walk_strings(message, sanitize_string)
        if sanitized != message:
            self.metrics.content_sanitizations += 1
            
        return sanitized
        
    async def _redact_pii(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Redact PII from message content"""
        redactions_made = 0
        
        def redact_string(value: str) -> str:
            nonlocal redactions_made
            original_value = value
            
            if self.config.redact_emails:
                value = self.email_pattern.sub('[EMAIL_REDACTED]', value)
                
            if self.config.redact_phones:
                value = self.phone_pattern.sub('[PHONE_REDACTED]', value)
                
            if self.config.redact_ssns:
                value = self.ssn_pattern.sub('[SSN_REDACTED]', value)
                
            if self.config.redact_credit_cards:
                value = self.credit_card_pattern.sub('[CREDIT_CARD_REDACTED]', value)
                
            if value != original_value:
                redactions_made += 1
                
            return value
            
        redacted = self._walk_strings(message, redact_string)
        
        if redactions_made > 0:
            self.metrics.pii_redactions += redactions_made
            if self.config.log_pii_redactions:
                logger.info(f"Redacted {redactions_made} PII items from message")
                
        return redacted
        
    async def _manage_response_size(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Manage response size through summarization and truncation"""
        # Calculate total content length
        content_items = self._extract_content(message)
        total_length = sum(len(item) for item in content_items)
        
        if total_length <= self.config.summarize_threshold:
            return message  # No action needed
            
        # Apply summarization or truncation
        if total_length > self.config.max_response_length:
            # Truncate
            message = self._truncate_content(message, self.config.max_response_length)
            logger.info(f"Truncated response from {total_length} to {self.config.max_response_length} characters")
        elif total_length > self.config.summarize_threshold:
            # Summarize
            message = await self._summarize_content(message)
            self.metrics.response_summaries += 1
            if self.config.log_response_summaries:
                logger.info(f"Summarized response from {total_length} characters")
                
        return message
        
    def _extract_content(self, obj: Any) -> List[str]:
        """Extract all string content from nested object"""
        content = []
        
        def collect_strings(value):
            if isinstance(value, str):
                content.append(value)
            elif isinstance(value, list):
                for item in value:
                    collect_strings(item)
            elif isinstance(value, dict):
                for v in value.values():
                    collect_strings(v)
                    
        collect_strings(obj)
        return content
        
    def _walk_strings(self, value: Any, fn: Callable[[str], str]) -> Any:
        """Apply function to all strings in nested structure"""
        if isinstance(value, str):
            return fn(value)
        elif isinstance(value, list):
            return [self._walk_strings(v, fn) for v in value]
        elif isinstance(value, dict):
            return {k: self._walk_strings(v, fn) for k, v in value.items()}
        else:
            return value
            
    def _truncate_content(self, message: Dict[str, Any], max_length: int) -> Dict[str, Any]:
        """Truncate content while preserving structure"""
        current_length = 0
        
        def truncate_string(value: str) -> str:
            nonlocal current_length
            if current_length >= max_length:
                return "[TRUNCATED]"
            
            available = max_length - current_length
            if len(value) <= available:
                current_length += len(value)
                return value
            else:
                current_length = max_length
                return value[:available] + "[TRUNCATED]"
                
        return self._walk_strings(message, truncate_string)
        
    async def _summarize_content(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize content (basic implementation - could be enhanced with AI)"""
        # For now, implement basic text summarization
        # In a production system, this could integrate with LLM APIs
        
        def summarize_string(value: str) -> str:
            if len(value) <= 500:
                return value
                
            # Basic extractive summarization - take first and last portions
            sentences = value.split('. ')
            if len(sentences) <= 3:
                return value
                
            # Take first sentence, middle sentence, and last sentence
            summary_parts = [
                sentences[0],
                sentences[len(sentences) // 2] if len(sentences) > 2 else "",
                sentences[-1]
            ]
            
            summary = '. '.join(filter(None, summary_parts))
            return f"[SUMMARIZED] {summary}"
            
        return self._walk_strings(message, summarize_string)
        
    def _get_cache_key(self, message: Dict[str, Any]) -> str:
        """Generate cache key for message"""
        # Create deterministic key based on message content
        key_data = json.dumps(message, sort_keys=True)
        import hashlib
        return hashlib.md5(key_data.encode()).hexdigest()
        
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached result if still valid"""
        if cache_key not in self.cache:
            return None
            
        timestamp = self.cache_timestamps.get(cache_key, 0)
        if time.time() - timestamp > self.config.cache_ttl:
            # Cache expired
            del self.cache[cache_key]
            del self.cache_timestamps[cache_key]
            return None
            
        return self.cache[cache_key]
        
    def _cache_result(self, cache_key: str, result: Dict[str, Any]):
        """Cache filtering result"""
        self.cache[cache_key] = result
        self.cache_timestamps[cache_key] = time.time()
        
        # Simple cache size management
        if len(self.cache) > 1000:
            # Remove oldest entries
            oldest_keys = sorted(
                self.cache_timestamps.keys(),
                key=lambda k: self.cache_timestamps[k]
            )[:100]
            
            for key in oldest_keys:
                del self.cache[key]
                del self.cache_timestamps[key]
                
    def get_metrics(self) -> Dict[str, Any]:
        """Get filtering metrics for monitoring"""
        return {
            "total_requests": self.metrics.total_requests,
            "blocked_requests": self.metrics.blocked_requests,
            "pii_redactions": self.metrics.pii_redactions,
            "content_sanitizations": self.metrics.content_sanitizations,
            "response_summaries": self.metrics.response_summaries,
            "avg_processing_time": (
                self.metrics.total_processing_time / max(1, self.metrics.total_requests)
            ),
            "cache_hit_rate": (
                self.metrics.cache_hits / max(1, self.metrics.cache_hits + self.metrics.cache_misses)
            ),
            "cache_size": len(self.cache)
        }
        
    def update_config(self, new_config: FilterConfig):
        """Update configuration at runtime"""
        self.config = new_config
        self._compile_patterns()
        # Clear cache when config changes
        self.cache.clear()
        self.cache_timestamps.clear()
        logger.info("Content filter configuration updated")