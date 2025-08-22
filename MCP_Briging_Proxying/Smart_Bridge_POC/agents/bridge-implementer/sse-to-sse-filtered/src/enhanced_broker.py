#!/usr/bin/env python3
"""
Enhanced Broker for SSE-to-SSE Bridge with Content Filtering
Extends the existing broker architecture with content filtering and performance monitoring
"""

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Set, Optional, List

# Python 3.8 compatibility
try:
    from typing import Queue  # Python 3.9+
except ImportError:
    Queue = asyncio.Queue  # Python 3.8 fallback

from fastapi import WebSocket

try:
    from .sse_process import SSEProcess
    from .content_filters import ContentFilter, FilterConfig
    from .models import FilterInfo
except ImportError:
    from sse_process import SSEProcess
    from content_filters import ContentFilter, FilterConfig
    from models import FilterInfo

logger = logging.getLogger("enhanced-broker")

@dataclass
class EnhancedSession:
    """Enhanced session with filtering support"""
    session_id: str
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=100))
    websockets: Set[WebSocket] = field(default_factory=set)
    last_beat: float = field(default_factory=time.time)
    filter_metrics: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

class EnhancedBroker:
    """Enhanced broker with SSE support and content filtering"""
    
    def __init__(self, sse_proc: SSEProcess, filter_config: FilterConfig):
        self.sse_proc = sse_proc
        self.sessions: Dict[str, EnhancedSession] = {}
        self.id_to_session: Dict[Any, str] = {}  # JSON-RPC id → session_id
        self.inbox = asyncio.Queue()  # messages from sse_proc → dict
        self.max_in_flight = int(os.environ.get("BRIDGE_MAX_IN_FLIGHT", "128"))
        self.in_flight = 0
        self._inflight_lock = asyncio.Lock()
        
        # Content filtering
        self.content_filter = ContentFilter(filter_config)
        
        # Performance monitoring
        self.start_time = time.time()
        self.total_messages = 0
        self.error_count = 0
        
    async def start(self) -> None:
        """Start the enhanced broker"""
        logger.info("Starting enhanced broker with content filtering")
        await self.sse_proc.start()
        asyncio.create_task(self._reader_loop())
        asyncio.create_task(self.pump())
        logger.info("✓ Enhanced broker started successfully")
        
    async def _reader_loop(self):
        """Read messages from SSE process"""
        try:
            while True:
                msg = await self.sse_proc.read_json()
                await self.inbox.put(msg)
                self.total_messages += 1
        except Exception as e:
            logger.exception("Enhanced reader loop ended: %s", e)
            self.error_count += 1
            await self.broadcast({"type": "bridge/error", "error": str(e)})
            
    def create_session(self) -> str:
        """Create new session with enhanced tracking"""
        sid = uuid.uuid4().hex
        self.sessions[sid] = EnhancedSession(sid)
        logger.info("New enhanced session %s (total=%d)", sid, len(self.sessions))
        return sid
        
    def get_session(self, sid: str) -> EnhancedSession:
        """Get session by ID"""
        if sid not in self.sessions:
            raise KeyError("Unknown session")
        return self.sessions[sid]
        
    async def route_from_client(self, session_id: str, payload: Dict[str, Any]) -> None:
        """Route message from client with content filtering"""
        start_time = time.time()
        
        try:
            # Map request ID to session
            if "id" in payload:
                self.id_to_session[payload["id"]] = session_id
                
            # Apply content filtering (client to server)
            filtered = await self.content_filter.filter_message(
                "client_to_server", session_id, payload
            )
            
            if filtered is None:
                # Message was blocked by filters
                logger.info(f"Message blocked by content filter for session {session_id}")
                # Update session metrics
                session = self.get_session(session_id)
                session.filter_metrics["blocked_messages"] = session.filter_metrics.get("blocked_messages", 0) + 1
                return
                
            # Flow control
            async with self._inflight_lock:
                while self.in_flight >= self.max_in_flight:
                    await asyncio.sleep(0.002)
                self.in_flight += 1
                
            try:
                await self.sse_proc.write_json(filtered)
            finally:
                async with self._inflight_lock:
                    self.in_flight -= 1
                    
            # Update performance metrics
            processing_time = time.time() - start_time
            session = self.get_session(session_id)
            session.filter_metrics["avg_request_time"] = (
                session.filter_metrics.get("avg_request_time", 0) * 0.9 + processing_time * 0.1
            )
            
        except Exception as e:
            logger.error(f"Error routing message from client {session_id}: {e}")
            self.error_count += 1
            
    async def pump(self):
        """Pump messages from server to clients with filtering"""
        while True:
            msg = await self.inbox.get()
            try:
                target_sid: Optional[str] = None
                if "id" in msg and msg["id"] in self.id_to_session:
                    target_sid = self.id_to_session.pop(msg["id"], None)
                    
                if target_sid and target_sid in self.sessions:
                    # Send to specific session
                    await self._send_with_filtering(target_sid, msg)
                else:
                    # Broadcast to all sessions
                    for sid in list(self.sessions.keys()):
                        await self._send_with_filtering(sid, msg)
            finally:
                self.inbox.task_done()
                
    async def _send_with_filtering(self, session_id: str, msg: Dict[str, Any]):
        """Send message to session with content filtering applied"""
        try:
            # Apply content filtering (server to client)
            filtered = await self.content_filter.filter_message(
                "server_to_client", session_id, msg
            )
            
            if filtered is not None:
                await self._send(session_id, filtered)
            else:
                logger.debug(f"Message filtered out for session {session_id}")
                
        except Exception as e:
            logger.error(f"Error filtering message for session {session_id}: {e}")
            # On filter error, send original message as fallback
            await self._send(session_id, msg)
            
    async def _send(self, session_id: str, obj: Any) -> None:
        """Send message to session (enhanced version)"""
        if session_id not in self.sessions:
            return
            
        sess = self.sessions[session_id]
        sess.last_beat = time.time()
        
        try:
            # Format as proper MCP SSE message event
            data = f"event: message\ndata: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")
            await sess.queue.put(data)
            
            # Update session metrics
            sess.filter_metrics["messages_sent"] = sess.filter_metrics.get("messages_sent", 0) + 1
            
        except asyncio.QueueFull:
            logger.warning("Session %s SSE queue full; dropping message", session_id)
            sess.filter_metrics["dropped_messages"] = sess.filter_metrics.get("dropped_messages", 0) + 1
            
        # Handle WebSocket connections
        dead: list[WebSocket] = []
        for ws in list(sess.websockets):
            try:
                await ws.send_text(json.dumps(obj, ensure_ascii=False))
            except Exception:
                dead.append(ws)
                
        for ws in dead:
            try:
                sess.websockets.remove(ws)
            except KeyError:
                pass
                
    async def broadcast(self, obj: Any) -> None:
        """Broadcast message to all sessions"""
        for sid in list(self.sessions.keys()):
            await self._send(sid, obj)
            
    def get_status(self) -> Dict[str, Any]:
        """Get enhanced broker status"""
        uptime = time.time() - self.start_time
        
        return {
            "status": "running",
            "uptime_seconds": uptime,
            "total_sessions": len(self.sessions),
            "total_messages": self.total_messages,
            "error_count": self.error_count,
            "messages_per_second": self.total_messages / max(1, uptime),
            "in_flight_requests": self.in_flight,
            "max_in_flight": self.max_in_flight,
            "content_filter_metrics": self.content_filter.get_metrics(),
            "sse_connection": {
                "connected": self.sse_proc.running if self.sse_proc else False,
                "endpoint": self.sse_proc.message_endpoint if self.sse_proc else None,
                "session_id": self.sse_proc.session_id if self.sse_proc else None
            }
        }
        
    def get_session_details(self) -> Dict[str, Any]:
        """Get detailed session information"""
        sessions_info = {}
        
        for session_id, session in self.sessions.items():
            sessions_info[session_id] = {
                "queue_size": session.queue.qsize(),
                "websocket_count": len(session.websockets),
                "last_beat": session.last_beat,
                "age_seconds": time.time() - session.created_at,
                "filter_metrics": session.filter_metrics
            }
            
        return {
            "active_sessions": len(sessions_info),
            "sessions": sessions_info,
            "timestamp": time.time()
        }
        
    def get_filter_info(self) -> List[FilterInfo]:
        """Get filter information for management endpoints"""
        return [
            FilterInfo(
                name="content_filter",
                enabled=True,
                description="Comprehensive content filtering with PII redaction and sanitization"
            ),
            FilterInfo(
                name="blacklist_filter", 
                enabled=len(self.content_filter.config.blocked_domains) > 0,
                description="Domain and keyword blacklist filtering"
            ),
            FilterInfo(
                name="pii_redaction",
                enabled=any([
                    self.content_filter.config.redact_emails,
                    self.content_filter.config.redact_phones,
                    self.content_filter.config.redact_ssns,
                    self.content_filter.config.redact_credit_cards
                ]),
                description="Personal Identifiable Information redaction"
            ),
            FilterInfo(
                name="html_sanitization",
                enabled=any([
                    self.content_filter.config.remove_scripts,
                    self.content_filter.config.remove_tracking,
                    self.content_filter.config.remove_ads
                ]),
                description="HTML content sanitization and script removal"
            ),
            FilterInfo(
                name="response_management",
                enabled=self.content_filter.config.max_response_length > 0,
                description="Response size management with summarization and truncation"
            )
        ]
        
    def update_filter_config(self, new_config: FilterConfig):
        """Update filter configuration at runtime"""
        self.content_filter.update_config(new_config)
        logger.info("Filter configuration updated for all sessions")
        
    async def cleanup_sessions(self):
        """Clean up inactive sessions"""
        current_time = time.time()
        session_timeout = 3600  # 1 hour
        
        expired_sessions = []
        for session_id, session in self.sessions.items():
            if current_time - session.last_beat > session_timeout:
                expired_sessions.append(session_id)
                
        for session_id in expired_sessions:
            del self.sessions[session_id]
            logger.info(f"Cleaned up expired session {session_id}")
            
        return len(expired_sessions)