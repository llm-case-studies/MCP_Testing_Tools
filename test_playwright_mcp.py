#!/usr/bin/env python3
"""Test Playwright MCP server functionality"""

import subprocess
import json
import sys

def test_playwright_mcp():
    """Test basic Playwright MCP server communication"""
    print("🎭 Testing Playwright MCP server...")
    
    try:
        # Start the MCP server
        proc = subprocess.Popen(
            ["npx", "@playwright/mcp@latest"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send tools/list request
        request = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tools/list"
        }
        
        proc.stdin.write(json.dumps(request) + "\n")
        proc.stdin.flush()
        
        # Read response
        response_line = proc.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            
            if "result" in response and "tools" in response["result"]:
                tools = response["result"]["tools"]
                print(f"✅ Found {len(tools)} Playwright MCP tools:")
                for tool in tools[:5]:  # Show first 5 tools
                    print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
                
                if len(tools) > 5:
                    print(f"  ... and {len(tools) - 5} more tools")
                    
                print("✅ Playwright MCP server is working!")
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
    success = test_playwright_mcp()
    sys.exit(0 if success else 1)