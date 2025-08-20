#!/usr/bin/env python3
"""
Simple MCP Server for testing bridge functionality
"""
import asyncio
import json
import sys
from typing import Any, Dict

class SimpleMCPServer:
    def __init__(self):
        self.capabilities = {
            "tools": [
                {
                    "name": "echo",
                    "description": "Echo back a message",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "message": {
                                "type": "string",
                                "description": "Message to echo back"
                            }
                        },
                        "required": ["message"]
                    }
                }
            ]
        }
    
    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming MCP messages"""
        if message.get("method") == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": self.capabilities,
                    "serverInfo": {
                        "name": "simple-test-server",
                        "version": "1.0.0"
                    }
                }
            }
        
        elif message.get("method") == "tools/call":
            tool_name = message.get("params", {}).get("name")
            if tool_name == "echo":
                echo_message = message.get("params", {}).get("arguments", {}).get("message", "")
                return {
                    "jsonrpc": "2.0", 
                    "id": message.get("id"),
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Echo: {echo_message}"
                            }
                        ]
                    }
                }
        
        elif message.get("method") == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "tools": self.capabilities["tools"]
                }
            }
        
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {
                "code": -32601,
                "message": "Method not found"
            }
        }
    
    async def write_message(self, message: Dict[str, Any]):
        """Write message with MCP framing"""
        json_str = json.dumps(message)
        content_length = len(json_str.encode('utf-8'))
        
        # Write headers
        sys.stdout.write(f"Content-Length: {content_length}\r\n\r\n")
        # Write content
        sys.stdout.write(json_str)
        sys.stdout.flush()
    
    async def read_message(self) -> Dict[str, Any]:
        """Read message with MCP framing"""
        # Read headers
        headers = {}
        while True:
            line = sys.stdin.readline().strip()
            if not line:
                break
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip().lower()] = value.strip()
        
        # Read content
        content_length = int(headers.get('content-length', 0))
        if content_length > 0:
            content = sys.stdin.read(content_length)
            return json.loads(content)
        
        return {}
    
    async def run(self):
        """Main server loop"""
        try:
            while True:
                message = await self.read_message()
                if not message:
                    continue
                    
                response = await self.handle_message(message)
                if response:
                    await self.write_message(response)
                    
        except (EOFError, KeyboardInterrupt):
            pass

if __name__ == "__main__":
    server = SimpleMCPServer()
    asyncio.run(server.run())