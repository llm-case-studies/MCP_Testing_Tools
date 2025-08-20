#!/usr/bin/env python3
"""
Test script for MCP SSE Bridge
"""

import asyncio
import json
import sys
import subprocess
from pathlib import Path

def test_serena_mcp_bridge():
    """Test MCP bridge with Serena MCP server"""
    
    # Start the MCP SSE bridge with Serena MCP
    bridge_cmd = [
        sys.executable, "-m", "mcp_sse_bridge",
        "--cmd", "serena", "--stdio",
        "--port", "8099",
        "--host", "0.0.0.0"
    ]
    
    print("Starting MCP SSE Bridge for Serena MCP...")
    print(f"Command: {' '.join(bridge_cmd)}")
    
    try:
        # Change to the bridge directory
        bridge_dir = Path(__file__).parent
        subprocess.run(bridge_cmd, cwd=bridge_dir)
    except KeyboardInterrupt:
        print("\nShutting down bridge...")

def test_qdrant_memory_bridge():
    """Test MCP bridge with Qdrant Memory MCP server"""
    
    # Start the MCP SSE bridge with Qdrant Memory MCP
    bridge_cmd = [
        sys.executable, "-m", "mcp_sse_bridge", 
        "--cmd", "qdrant-memory",
        "--port", "8100",
        "--host", "0.0.0.0"
    ]
    
    print("Starting MCP SSE Bridge for Qdrant Memory MCP...")
    print(f"Command: {' '.join(bridge_cmd)}")
    
    try:
        # Change to the bridge directory  
        bridge_dir = Path(__file__).parent
        subprocess.run(bridge_cmd, cwd=bridge_dir)
    except KeyboardInterrupt:
        print("\nShutting down bridge...")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test MCP SSE Bridge")
    parser.add_argument("--server", choices=["serena", "qdrant"], default="serena",
                       help="MCP server to bridge")
    
    args = parser.parse_args()
    
    if args.server == "serena":
        test_serena_mcp_bridge()
    else:
        test_qdrant_memory_bridge()