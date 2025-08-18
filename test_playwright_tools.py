#!/usr/bin/env python3
"""Test Playwright MCP server tools directly"""

import subprocess
import json
import sys
import time

def test_playwright_tools():
    """Test what tools Playwright MCP provides"""
    print("🎭 Testing Playwright MCP tools...")
    
    try:
        # Start the MCP server
        proc = subprocess.Popen(
            ["npx", "@playwright/mcp@latest"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Send initialize request first
        init_request = {
            "jsonrpc": "2.0",
            "id": "init",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        proc.stdin.write(json.dumps(init_request) + "\n")
        proc.stdin.flush()
        
        # Read initialize response
        init_response = proc.stdout.readline()
        if init_response:
            print(f"Initialize response: {init_response.strip()}")
        
        # Send tools/list request
        tools_request = {
            "jsonrpc": "2.0",
            "id": "tools",
            "method": "tools/list"
        }
        
        proc.stdin.write(json.dumps(tools_request) + "\n")
        proc.stdin.flush()
        
        # Read tools response
        tools_response = proc.stdout.readline()
        if tools_response:
            response = json.loads(tools_response.strip())
            
            if "result" in response and "tools" in response["result"]:
                tools = response["result"]["tools"]
                print(f"✅ Found {len(tools)} Playwright MCP tools:")
                
                for i, tool in enumerate(tools):
                    print(f"  {i+1}. {tool['name']}")
                    if 'description' in tool:
                        print(f"     Description: {tool['description']}")
                    if 'inputSchema' in tool:
                        props = tool['inputSchema'].get('properties', {})
                        if props:
                            print(f"     Parameters: {', '.join(props.keys())}")
                    print()
                    
                print("✅ Playwright MCP server is working with tools!")
                return True
            else:
                print(f"❌ Unexpected response: {response}")
                return False
        else:
            print("❌ No response from MCP server")
            return False
            
    except Exception as e:
        print(f"❌ Error testing Playwright MCP: {e}")
        return False
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except:
            proc.kill()

if __name__ == "__main__":
    success = test_playwright_tools()
    sys.exit(0 if success else 1)