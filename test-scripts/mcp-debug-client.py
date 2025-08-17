#!/usr/bin/env python3
"""
MCP Debug Client - Direct protocol communication for troubleshooting
"""

import json
import subprocess
import asyncio
import sys
import os
from datetime import datetime

class MCPDebugClient:
    def __init__(self, config_path=".mcp.json"):
        self.config_path = config_path
        self.servers = {}
        self.load_config()
    
    def load_config(self):
        """Load MCP server configuration"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.servers = config.get('mcpServers', {})
            print(f"✅ Loaded {len(self.servers)} MCP servers from {self.config_path}")
        except Exception as e:
            print(f"❌ Failed to load config: {e}")
            sys.exit(1)
    
    def test_server_detailed(self, server_name, server_config):
        """Detailed test with step-by-step protocol communication"""
        print(f"\n🔬 Detailed test for {server_name}")
        print("=" * 50)
        
        try:
            # Build command and environment
            cmd = [server_config['command']] + server_config.get('args', [])
            env_vars = server_config.get('env', {})
            
            # Expand environment variables
            expanded_env = {}
            for key, value in env_vars.items():
                if value.startswith('${') and value.endswith('}'):
                    env_key = value[2:-1]
                    expanded_env[key] = os.environ.get(env_key, f"MISSING_{env_key}")
                else:
                    expanded_env[key] = value
            
            print(f"📋 Command: {' '.join(cmd)}")
            print(f"🌍 Environment variables:")
            for key, value in expanded_env.items():
                if 'API_KEY' in key or 'TOKEN' in key:
                    display_value = f"{value[:8]}..." if value and len(value) > 8 else "EMPTY/MISSING"
                    print(f"   {key} = {display_value}")
                else:
                    print(f"   {key} = {value}")
            
            # Prepare environment
            full_env = dict(os.environ)
            full_env.update(expanded_env)
            
            print(f"\n🚀 Starting server process...")
            
            # Start process
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=full_env
            )
            
            # Send initialize request
            initialize_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "roots": {
                            "listChanged": True
                        },
                        "sampling": {}
                    },
                    "clientInfo": {
                        "name": "mcp-debug-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            print(f"📤 Sending initialize request...")
            request_json = json.dumps(initialize_request) + "\n"
            
            try:
                stdout, stderr = process.communicate(input=request_json, timeout=15)
                
                print(f"⏱️  Process completed with return code: {process.returncode}")
                
                if stdout:
                    print(f"📥 STDOUT ({len(stdout)} chars):")
                    print("─" * 40)
                    print(stdout[:1000] + ("..." if len(stdout) > 1000 else ""))
                    print("─" * 40)
                    
                    # Try to parse JSON response
                    try:
                        lines = [line.strip() for line in stdout.split('\n') if line.strip()]
                        for line in lines:
                            if line.startswith('{'):
                                response = json.loads(line)
                                print(f"🎯 Parsed JSON response:")
                                print(f"   ID: {response.get('id')}")
                                print(f"   Method: {response.get('method', 'N/A')}")
                                if 'result' in response:
                                    capabilities = response['result'].get('capabilities', {})
                                    print(f"   Server capabilities: {list(capabilities.keys())}")
                                    tools = capabilities.get('tools', {})
                                    if tools:
                                        print(f"   Tools available: {tools}")
                                if 'error' in response:
                                    print(f"   ❌ Error: {response['error']}")
                                break
                    except json.JSONDecodeError as e:
                        print(f"   ⚠️  Could not parse as JSON: {e}")
                
                if stderr:
                    print(f"📥 STDERR ({len(stderr)} chars):")
                    print("─" * 40)
                    print(stderr[:1000] + ("..." if len(stderr) > 1000 else ""))
                    print("─" * 40)
                
                return process.returncode == 0
                
            except subprocess.TimeoutExpired:
                print(f"⏰ Process timeout after 15 seconds")
                process.kill()
                stdout, stderr = process.communicate()
                if stderr:
                    print(f"📥 STDERR after timeout:")
                    print(stderr)
                return False
                
        except FileNotFoundError as e:
            print(f"❌ Command not found: {e}")
            return False
        except Exception as e:
            print(f"❌ Test failed: {e}")
            return False
    
    def debug_specific_server(self, server_name):
        """Debug a specific server with detailed output"""
        if server_name not in self.servers:
            print(f"❌ Server '{server_name}' not found in config")
            print(f"Available servers: {list(self.servers.keys())}")
            return False
        
        server_config = self.servers[server_name]
        return self.test_server_detailed(server_name, server_config)
    
    def list_servers(self):
        """List all configured servers"""
        print("🖥️  Configured MCP Servers:")
        print("=" * 50)
        for name, config in self.servers.items():
            cmd = [config['command']] + config.get('args', [])
            env_count = len(config.get('env', {}))
            print(f"📦 {name}")
            print(f"   Command: {' '.join(cmd)}")
            print(f"   Environment vars: {env_count}")
            print(f"   Description: {config.get('description', 'No description')}")
            print()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Debug Client")
    parser.add_argument("--server", "-s", help="Debug specific server")
    parser.add_argument("--list", "-l", action="store_true", help="List all servers")
    parser.add_argument("--config", "-c", default=".mcp.json", help="MCP config file")
    
    args = parser.parse_args()
    
    # Change to script directory  
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    os.chdir(project_dir)
    
    client = MCPDebugClient(args.config)
    
    if args.list:
        client.list_servers()
    elif args.server:
        success = client.debug_specific_server(args.server)
        sys.exit(0 if success else 1)
    else:
        print("🧪 Testing all servers...")
        for server_name in client.servers:
            success = client.debug_specific_server(server_name)
            if not success:
                sys.exit(1)
        print("✅ All tests passed!")