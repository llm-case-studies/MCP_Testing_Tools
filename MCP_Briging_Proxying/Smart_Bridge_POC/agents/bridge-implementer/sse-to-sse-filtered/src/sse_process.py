#!/usr/bin/env python3
"""
SSE Process Module - Connects to upstream SSE MCP servers
Replaces StdioProcess for SSE-to-SSE bridge architecture
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional, AsyncGenerator
import aiohttp
from urllib.parse import urljoin, urlparse

logger = logging.getLogger("sse-process")

class SSEProcess:
    """
    SSE MCP server client that maintains connection to upstream SSE server
    Compatible with existing Broker interface from simple_bridge.py
    """
    
    def __init__(self, sse_url: str, api_key: Optional[str] = None):
        self.sse_url = sse_url
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        self.sse_reader_task: Optional[asyncio.Task] = None
        self.sse_response: Optional[aiohttp.ClientResponse] = None
        self.message_endpoint: str = ""
        self.session_id: Optional[str] = None
        self.message_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self.running = False
        self.headers = {}
        
        if self.api_key:
            self.headers["X-API-Key"] = self.api_key
            
        # Parse base URL for message endpoint
        parsed = urlparse(sse_url)
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        
    async def start(self):
        """Initialize SSE connection to upstream server"""
        logger.info(f"Starting SSE connection to {self.sse_url}")
        
        # Create HTTP session
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers=self.headers
        )
        
        try:
            # Connect to SSE endpoint
            self.sse_response = await self.session.get(
                self.sse_url,
                headers={**self.headers, "Accept": "text/event-stream", "Cache-Control": "no-cache"}
            )
            
            if self.sse_response.status != 200:
                raise Exception(f"SSE connection failed: {self.sse_response.status}")
                
            logger.info("✓ SSE connection established")
            
            # Start reading SSE events
            self.running = True
            self.sse_reader_task = asyncio.create_task(self._sse_reader_loop())
            
            # Wait for endpoint event to get message URL
            await self._wait_for_endpoint()
            
        except Exception as e:
            logger.error(f"Failed to start SSE connection: {e}")
            await self.cleanup()
            raise
            
    async def _wait_for_endpoint(self, timeout: float = 10.0):
        """Wait for endpoint event from SSE stream"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                if message.get("event") == "endpoint":
                    self.message_endpoint = message.get("data", "")
                    logger.info(f"Received endpoint: {self.message_endpoint}")
                    # Extract session ID from endpoint URL
                    if "session=" in self.message_endpoint:
                        self.session_id = self.message_endpoint.split("session=")[1].split("&")[0]
                    return
                else:
                    # Put non-endpoint message back for normal processing
                    await self.message_queue.put(message)
            except asyncio.TimeoutError:
                continue
                
        raise Exception("Timeout waiting for SSE endpoint event")
        
    async def _sse_reader_loop(self):
        """Read SSE events from upstream server"""
        try:
            async for line in self.sse_response.content:
                if not self.running:
                    break
                    
                line_str = line.decode('utf-8').strip()
                if not line_str:
                    continue
                    
                # Parse SSE event format
                if line_str.startswith("event: "):
                    event_type = line_str[7:]
                elif line_str.startswith("data: "):
                    data = line_str[6:]
                    
                    if event_type == "endpoint":
                        # Special handling for endpoint events
                        await self.message_queue.put({"event": "endpoint", "data": data})
                    elif event_type == "message":
                        # Parse JSON message data
                        try:
                            message_data = json.loads(data)
                            await self.message_queue.put(message_data)
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse SSE message: {e}")
                elif line_str.startswith(": "):
                    # SSE comment/heartbeat - ignore
                    continue
                    
        except Exception as e:
            logger.error(f"SSE reader loop error: {e}")
        finally:
            logger.info("SSE reader loop ended")
            
    async def read_json(self) -> Dict[str, Any]:
        """Read next JSON message from upstream server (compatible with StdioProcess)"""
        if not self.running:
            raise Exception("SSE process not running")
            
        message = await self.message_queue.get()
        logger.debug(f"Read message: {message}")
        return message
        
    async def write_json(self, obj: Dict[str, Any]):
        """Send JSON message to upstream server (compatible with StdioProcess)"""
        if not self.running or not self.session or not self.message_endpoint:
            raise Exception("SSE process not ready for writing")
            
        try:
            logger.debug(f"Sending message: {obj}")
            
            # Send to message endpoint
            async with self.session.post(
                self.message_endpoint,
                json=obj,
                headers=self.headers
            ) as response:
                if response.status not in (200, 202):
                    logger.warning(f"Message send failed: {response.status}")
                    
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise
            
    async def cleanup(self):
        """Clean up SSE connection"""
        logger.info("Cleaning up SSE connection")
        self.running = False
        
        if self.sse_reader_task:
            self.sse_reader_task.cancel()
            try:
                await self.sse_reader_task
            except asyncio.CancelledError:
                pass
                
        if self.sse_response:
            self.sse_response.close()
            
        if self.session:
            await self.session.close()