#!/usr/bin/env python3
"""
MCP Tool Explorer - Discover and test MCP server tools and capabilities
"""

import json
import subprocess
import sys
import os
from datetime import datetime

class MCPToolExplorer:
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
    
    def send_mcp_request(self, process, request, timeout=10):
        """Send MCP request and get response"""
        request_json = json.dumps(request) + "\n"
        try:
            stdout, stderr = process.communicate(input=request_json, timeout=timeout)
            return stdout, stderr, process.returncode
        except subprocess.TimeoutExpired:
            print(f"⏰ Request timeout after {timeout} seconds")
            process.kill()
            return None, None, -1
    
    def explore_server_tools(self, server_name, server_config):
        """Explore all tools available in a server"""
        print(f"\n🔍 Exploring tools for {server_name}")
        print("=" * 60)
        
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
            
            # Prepare environment
            full_env = dict(os.environ)
            full_env.update(expanded_env)
            
            print(f"🚀 Starting {server_name} server...")
            
            # Start process
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=full_env
            )
            
            # Step 1: Initialize
            print(f"\n📤 Step 1: Sending initialize request...")
            initialize_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "roots": {"listChanged": True},
                        "sampling": {}
                    },
                    "clientInfo": {
                        "name": "mcp-tool-explorer",
                        "version": "1.0.0"
                    }
                }
            }
            
            stdout, stderr, returncode = self.send_mcp_request(process, initialize_request)
            
            if returncode != 0:
                print(f"❌ Initialize failed with return code {returncode}")
                if stderr:
                    print(f"STDERR: {stderr}")
                return False
            
            print(f"📥 Initialize response received")
            
            # Parse initialize response
            init_response = None
            if stdout:
                lines = [line.strip() for line in stdout.split('\n') if line.strip()]
                for line in lines:
                    if line.startswith('{'):
                        try:
                            init_response = json.loads(line)
                            break
                        except json.JSONDecodeError:
                            continue
            
            if not init_response:
                print(f"❌ Could not parse initialize response")
                return False
            
            print(f"✅ Server capabilities: {list(init_response.get('result', {}).get('capabilities', {}).keys())}")
            
            # Step 2: List tools
            print(f"\n📤 Step 2: Requesting tools list...")
            
            # Start new process for tools request (hyper-mcp-shell might need fresh process)
            process2 = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=full_env
            )
            
            # Send initialize + tools/list in sequence
            requests = [
                initialize_request,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list",
                    "params": {}
                }
            ]
            
            # Send both requests
            request_data = "\n".join([json.dumps(req) for req in requests]) + "\n"
            
            try:
                stdout2, stderr2 = process2.communicate(input=request_data, timeout=15)
                returncode2 = process2.returncode
                
                if returncode2 == 0 and stdout2:
                    print(f"📥 Tools list response received")
                    
                    # Parse all responses
                    lines = [line.strip() for line in stdout2.split('\n') if line.strip()]
                    tools_response = None
                    
                    for line in lines:
                        if line.startswith('{'):
                            try:
                                response = json.loads(line)
                                if response.get('id') == 2:  # tools/list response
                                    tools_response = response
                                    break
                            except json.JSONDecodeError:
                                continue
                    
                    if tools_response:
                        tools = tools_response.get('result', {}).get('tools', [])
                        print(f"🛠️  Available tools: {len(tools)}")
                        
                        for i, tool in enumerate(tools, 1):
                            print(f"\n🔧 Tool {i}: {tool.get('name', 'Unknown')}")
                            print(f"   Description: {tool.get('description', 'No description')}")
                            
                            # Show input schema
                            input_schema = tool.get('inputSchema', {})
                            if input_schema:
                                properties = input_schema.get('properties', {})
                                required = input_schema.get('required', [])
                                print(f"   Parameters:")
                                for param_name, param_info in properties.items():
                                    req_marker = " (required)" if param_name in required else ""
                                    param_type = param_info.get('type', 'unknown')
                                    param_desc = param_info.get('description', 'No description')
                                    print(f"     - {param_name} ({param_type}){req_marker}: {param_desc}")
                        
                        return True
                    else:
                        print(f"❌ Could not parse tools list response")
                        if stdout2:
                            print(f"Raw stdout: {stdout2}")
                        return False
                else:
                    print(f"❌ Tools list failed with return code {returncode2}")
                    if stderr2:
                        print(f"STDERR: {stderr2}")
                    return False
                    
            except subprocess.TimeoutExpired:
                print(f"⏰ Tools list request timeout")
                process2.kill()
                return False
                
        except Exception as e:
            print(f"❌ Exploration failed: {e}")
            return False
    
    def demonstrate_shell_analysis(self, target_project):
        """Demonstrate shell MCP analysis on a target project"""
        print(f"\n🎯 Demonstrating shell analysis on: {target_project}")
        print("=" * 80)
        
        if not os.path.exists(target_project):
            print(f"❌ Target project not found: {target_project}")
            return
        
        # Example commands that shell MCP could run for analysis
        analysis_commands = [
            {
                "name": "find_shell_scripts",
                "command": f"find {target_project} -name '*.sh' -type f",
                "purpose": "Find all shell scripts in the project"
            },
            {
                "name": "find_nginx_configs", 
                "command": f"find {target_project} -name '*.conf' -o -name 'nginx.conf' -o -name '*.nginx' -type f",
                "purpose": "Find all nginx configuration files"
            },
            {
                "name": "check_script_permissions",
                "command": f"find {target_project} -name '*.sh' -type f -exec ls -la {{}} \\;",
                "purpose": "Check permissions on shell scripts"
            },
            {
                "name": "shellcheck_analysis",
                "command": f"find {target_project} -name '*.sh' -type f -exec shellcheck {{}} \\;",
                "purpose": "Run shellcheck on all shell scripts (if available)"
            },
            {
                "name": "nginx_syntax_check",
                "command": f"find {target_project} -name '*.conf' -type f -exec nginx -t -c {{}} \\;",
                "purpose": "Check nginx configuration syntax (if nginx available)"
            }
        ]
        
        print("🔍 Potential analysis commands the shell MCP could execute:")
        for i, cmd in enumerate(analysis_commands, 1):
            print(f"\n{i}. {cmd['name']}")
            print(f"   Purpose: {cmd['purpose']}")
            print(f"   Command: {cmd['command']}")
            
            # Actually run a safe subset of commands
            if cmd['name'] in ['find_shell_scripts', 'find_nginx_configs', 'check_script_permissions']:
                print(f"   📋 Executing...")
                try:
                    result = subprocess.run(
                        cmd['command'], 
                        shell=True, 
                        capture_output=True, 
                        text=True, 
                        timeout=10
                    )
                    if result.returncode == 0:
                        output_lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
                        if output_lines and output_lines[0]:
                            print(f"   ✅ Found {len(output_lines)} items:")
                            for line in output_lines[:5]:  # Show first 5
                                print(f"      {line}")
                            if len(output_lines) > 5:
                                print(f"      ... and {len(output_lines) - 5} more")
                        else:
                            print(f"   ℹ️  No files found")
                    else:
                        print(f"   ❌ Command failed: {result.stderr}")
                except subprocess.TimeoutExpired:
                    print(f"   ⏰ Command timeout")
                except Exception as e:
                    print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Tool Explorer")
    parser.add_argument("--server", "-s", help="Explore specific server tools")
    parser.add_argument("--analyze", "-a", help="Analyze target project directory")
    parser.add_argument("--config", "-c", default=".mcp.json", help="MCP config file")
    
    args = parser.parse_args()
    
    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    os.chdir(project_dir)
    
    explorer = MCPToolExplorer(args.config)
    
    if args.server:
        if args.server in explorer.servers:
            explorer.explore_server_tools(args.server, explorer.servers[args.server])
        else:
            print(f"❌ Server '{args.server}' not found")
            print(f"Available servers: {list(explorer.servers.keys())}")
    elif args.analyze:
        explorer.demonstrate_shell_analysis(args.analyze)
    else:
        print("🧪 Exploring all servers...")
        for server_name, server_config in explorer.servers.items():
            success = explorer.explore_server_tools(server_name, server_config)
            if not success:
                print(f"⚠️  Failed to explore {server_name}")
        
        # Also demonstrate analysis
        nginx_project = "/media/alex/LargeStorage/Projects/Nginx_RP_Pipeline"
        explorer.demonstrate_shell_analysis(nginx_project)