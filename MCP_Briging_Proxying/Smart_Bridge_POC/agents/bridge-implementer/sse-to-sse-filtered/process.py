from __future__ import annotations
import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from typing import Dict, Optional, Any

try:
    from .framing import encode_framed_json, read_framed_json
except ImportError:
    from framing import encode_framed_json, read_framed_json

logger = logging.getLogger("stdio-gateway")

@dataclass
class StdioProcess:
    cmd: str
    cwd: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    proc: Optional[asyncio.subprocess.Process] = None
    reader: Optional[asyncio.StreamReader] = None
    writer: Optional[asyncio.StreamWriter] = None
    stderr_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        logger.info("Starting stdio server: %s", self.cmd)
        self.proc = await asyncio.create_subprocess_shell(
            self.cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.cwd,
            env=self.env if self.env is not None else os.environ.copy(),
        )
        assert self.proc.stdout and self.proc.stdin and self.proc.stderr
        self.reader = self.proc.stdout
        self.writer = self.proc.stdin
        async def _pump_stderr():
            try:
                while True:
                    line = await self.proc.stderr.readline()
                    if not line:
                        break
                    logger.info("[server stderr] %s", line.rstrip().decode(errors="replace"))
            except Exception:
                logger.exception("stderr pump failed")
        self.stderr_task = asyncio.create_task(_pump_stderr())

    async def write_json(self, obj: Dict[str, Any]) -> None:
        if not self.writer:
            raise RuntimeError("Process not started")
        payload = encode_framed_json(obj)
        self.writer.write(payload)
        await self.writer.drain()

    async def read_json(self) -> Dict[str, Any]:
        if not self.reader:
            raise RuntimeError("Process not started")
        return await read_framed_json(self.reader)

    async def send_message(self, message: Dict[str, Any]) -> None:
        """Send MCP message to stdio server"""
        await self.write_json(message)

    async def receive_message(self) -> Optional[Dict[str, Any]]:
        """Receive MCP message from stdio server"""
        try:
            return await self.read_json()
        except Exception as e:
            logger.error(f"Error receiving message: {e}")
            return None

    async def terminate(self) -> None:
        """Terminate the stdio process"""
        if self.proc:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.proc.kill()
                await self.proc.wait()
        
        if self.stderr_task:
            self.stderr_task.cancel()
            try:
                await self.stderr_task
            except asyncio.CancelledError:
                pass
