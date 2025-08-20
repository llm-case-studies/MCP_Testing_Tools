#!/usr/bin/env python3
"""
Test Tools MCP Server - mimics serena functionality for testing
"""
import asyncio
import json
import sys
from typing import Any, Dict

class TestToolsServer:
    def __init__(self):
        self.capabilities = {
            "tools": [
                {
                    "name": "search_code",
                    "description": "Search for code patterns in project",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query"
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "analyze_function", 
                    "description": "Analyze a specific function",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "function_name": {
                                "type": "string",
                                "description": "Function name to analyze"
                            }
                        },
                        "required": ["function_name"]
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
                        "name": "test-tools-server",
                        "version": "1.0.0"
                    }
                }
            }
        
        elif message.get("method") == "tools/call":
            tool_name = message.get("params", {}).get("name")
            args = message.get("params", {}).get("arguments", {})
            
            if tool_name == "search_code":
                query = args.get("query", "")
                return {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Code search results for '{query}':\n\n1. function test_example() - line 42\n2. class TestClass - line 156\n3. variable TEST_CONFIG - line 23"
                            }
                        ]
                    }
                }
            
            elif tool_name == "analyze_function":
                func_name = args.get("function_name", "")
                return {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": {
                        "content": [
                            {
                                "type": "text", 
                                "text": f"Function analysis for '{func_name}':\n\n- Parameters: 3\n- Return type: Dict\n- Complexity: Medium\n- Dependencies: logging, json"
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
        
        sys.stdout.write(f"Content-Length: {content_length}\r\n\r\n")
        sys.stdout.write(json_str)
        sys.stdout.flush()
    
    async def read_message(self) -> Dict[str, Any]:
        """Read message with MCP framing"""
        headers = {}
        while True:
            line = sys.stdin.readline().strip()
            if not line:
                break
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip().lower()] = value.strip()
        
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
    server = TestToolsServer()
    asyncio.run(server.run())