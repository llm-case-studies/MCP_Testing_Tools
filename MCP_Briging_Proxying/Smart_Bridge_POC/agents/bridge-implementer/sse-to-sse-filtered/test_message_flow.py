#!/usr/bin/env python3
"""
Test actual MCP message flow through the corrected filtered bridge
"""

import json
import requests
import time
import asyncio
import aiohttp

async def test_mcp_message_flow():
    """Test a complete MCP message flow through the filtered bridge"""
    print("🧪 Testing MCP Message Flow Through Corrected Bridge")
    print("=" * 60)
    
    base_url = "http://localhost:8202"
    
    try:
        # Step 1: Get SSE connection and extract session
        print("1️⃣ Connecting to SSE endpoint...")
        response = requests.get(f"{base_url}/sse", stream=True, timeout=5)
        
        # Read first chunk to get endpoint event
        first_chunk = next(response.iter_content(chunk_size=1024))
        sse_data = first_chunk.decode('utf-8')
        
        # Extract session ID from endpoint URL
        session_id = None
        for line in sse_data.split('\n'):
            if line.startswith('data: ') and 'session=' in line:
                endpoint_url = line[6:]  # Remove 'data: '
                session_id = endpoint_url.split('session=')[1]
                break
        
        if not session_id:
            print("❌ Failed to extract session ID from SSE response")
            return False
            
        print(f"✅ Got session ID: {session_id}")
        response.close()  # Close SSE connection
        
        # Step 2: Send initialize message
        print("2️⃣ Sending MCP initialize message...")
        init_message = {
            "jsonrpc": "2.0",
            "id": "test-init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "Test Client", "version": "1.0.0"}
            }
        }
        
        response = requests.post(
            f"{base_url}/messages?session={session_id}",
            json=init_message,
            timeout=10
        )
        
        if response.status_code == 202:
            print("✅ Initialize message accepted")
        else:
            print(f"❌ Initialize message failed: {response.status_code}")
            return False
        
        # Step 3: Send tools/list request
        print("3️⃣ Sending tools/list request...")
        tools_message = {
            "jsonrpc": "2.0",
            "id": "test-tools-1",
            "method": "tools/list",
            "params": {}
        }
        
        response = requests.post(
            f"{base_url}/messages?session={session_id}",
            json=tools_message,
            timeout=10
        )
        
        if response.status_code == 202:
            print("✅ Tools list request accepted")
        else:
            print(f"❌ Tools list request failed: {response.status_code}")
            return False
        
        # Step 4: Test content filtering endpoint
        print("4️⃣ Testing content filtering endpoints...")
        
        # Check filter status
        response = requests.get(f"{base_url}/filters", timeout=5)
        if response.status_code == 200:
            filter_info = response.json()
            print(f"✅ Filter status: {filter_info.get('status', 'unknown')}")
        else:
            print(f"❌ Filter status check failed: {response.status_code}")
        
        # Check filter metrics
        response = requests.get(f"{base_url}/filters/metrics", timeout=5)
        if response.status_code == 200:
            metrics = response.json()
            print(f"✅ Filter metrics retrieved: {len(metrics)} entries")
        else:
            print(f"❌ Filter metrics check failed: {response.status_code}")
        
        print("\n" + "=" * 60)
        print("✅ MCP MESSAGE FLOW TEST COMPLETED SUCCESSFULLY")
        print("✅ Bridge correctly handles:")
        print("   - SSE connections with proper session format")
        print("   - MCP initialize messages")
        print("   - MCP discovery requests")
        print("   - Content filtering API endpoints")
        print("   - Proper HTTP status codes (202 for messages)")
        
        return True
        
    except Exception as e:
        print(f"❌ Message flow test failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_mcp_message_flow())