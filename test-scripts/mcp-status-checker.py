#!/usr/bin/env python3
"""
MCP Status Checker - Detect failed MCP servers and diagnose issues
"""

import json
import subprocess
import sys
import os
import requests
from datetime import datetime

class MCPStatusChecker:
    def __init__(self):
        self.global_config = "/home/alex/.claude.json"
        self.project_config = ".mcp.json"
        self.servers = {}
        self.load_all_configs()
    
    def load_all_configs(self):
        """Load both global and project MCP configurations"""
        print("🔍 Loading MCP configurations...")
        
        # Load global config
        try:
            with open(self.global_config, 'r') as f:
                global_data = json.load(f)
                global_servers = global_data.get('mcpServers', {})
                print(f"📂 Global config: {len(global_servers)} servers")
                for name in global_servers:
                    self.servers[name] = {
                        'config': global_servers[name],
                        'source': 'global',
                        'scope': 'user'
                    }
        except Exception as e:
            print(f"❌ Failed to load global config: {e}")
        
        # Load project config
        if os.path.exists(self.project_config):
            try:
                with open(self.project_config, 'r') as f:
                    project_data = json.load(f)
                    project_servers = project_data.get('mcpServers', {})
                    print(f"📦 Project config: {len(project_servers)} servers")
                    for name in project_servers:
                        self.servers[name] = {
                            'config': project_servers[name],
                            'source': 'project',
                            'scope': 'shared'
                        }
            except Exception as e:
                print(f"❌ Failed to load project config: {e}")
        else:
            print("📦 No project config found")
        
        print(f"📊 Total servers discovered: {len(self.servers)}")
        print()
    
    def test_server_connectivity(self, server_name, server_config):
        """Test if MCP server can be reached and initialized"""
        print(f"🔬 Testing {server_name} connectivity...")
        
        try:
            # Build command and environment
            cmd = [server_config['command']] + server_config.get('args', [])
            env_vars = server_config.get('env', {})
            
            # Expand environment variables
            expanded_env = {}
            missing_env = []
            for key, value in env_vars.items():
                if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                    env_key = value[2:-1]
                    env_value = os.environ.get(env_key)
                    if env_value:
                        expanded_env[key] = env_value
                    else:
                        expanded_env[key] = f"MISSING_{env_key}"
                        missing_env.append(env_key)
                else:
                    expanded_env[key] = value
            
            if missing_env:
                print(f"   ⚠️  Missing environment variables: {missing_env}")
                return {"status": "warning", "issue": f"Missing env vars: {missing_env}"}
            
            # Prepare environment
            full_env = dict(os.environ)
            full_env.update(expanded_env)
            
            # Start process with timeout
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
                    "capabilities": {"roots": {"listChanged": True}},
                    "clientInfo": {"name": "mcp-status-checker", "version": "1.0.0"}
                }
            }
            
            request_json = json.dumps(initialize_request) + "\n"
            
            try:
                stdout, stderr = process.communicate(input=request_json, timeout=10)
                
                if process.returncode == 0:
                    if stdout and 'result' in stdout:
                        print(f"   ✅ Server responds successfully")
                        return {"status": "connected", "output": stdout}
                    else:
                        print(f"   ❌ Server started but no valid response")
                        return {"status": "failed", "issue": "No valid initialize response"}
                else:
                    print(f"   ❌ Server failed (exit code {process.returncode})")
                    if stderr:
                        print(f"   Error: {stderr[:200]}...")
                    return {"status": "failed", "issue": f"Exit code {process.returncode}", "stderr": stderr}
                    
            except subprocess.TimeoutExpired:
                print(f"   ⏰ Server timeout")
                process.kill()
                return {"status": "timeout", "issue": "Server initialization timeout"}
                
        except FileNotFoundError:
            print(f"   ❌ Command not found: {cmd[0]}")
            return {"status": "not_found", "issue": f"Command not found: {cmd[0]}"}
        except Exception as e:
            print(f"   ❌ Test failed: {e}")
            return {"status": "error", "issue": str(e)}
    
    def check_external_dependencies(self, server_name, server_config):
        """Check external dependencies for specific servers"""
        print(f"🔗 Checking dependencies for {server_name}...")
        
        # Qdrant-specific checks
        if 'qdrant' in server_name.lower():
            env_vars = server_config.get('env', {})
            qdrant_url = env_vars.get('QDRANT_URL', '')
            collection_name = env_vars.get('COLLECTION_NAME', 'shared_memories')
            
            if qdrant_url:
                try:
                    # Extract host and port
                    if 'http://' in qdrant_url:
                        url_part = qdrant_url.replace('http://', '')
                        if ':' in url_part:
                            host, port = url_part.split(':')
                        else:
                            host, port = url_part, '6333'
                    else:
                        host, port = qdrant_url.split(':') if ':' in qdrant_url else (qdrant_url, '6333')
                    
                    print(f"   Testing Qdrant connection to {host}:{port}...")
                    response = requests.get(f"http://{host}:{port}/collections", timeout=5)
                    
                    if response.status_code == 200:
                        collections = response.json()
                        print(f"   ✅ Qdrant accessible with {len(collections['result']['collections'])} collections")
                        
                        # REAL FUNCTIONAL TEST: Check vector configuration
                        print(f"   🧪 Testing collection '{collection_name}' vector configuration...")
                        collection_response = requests.get(f"http://{host}:{port}/collections/{collection_name}", timeout=5)
                        
                        if collection_response.status_code == 200:
                            collection_info = collection_response.json()
                            vectors_config = collection_info.get('result', {}).get('config', {}).get('params', {}).get('vectors', {})
                            
                            if vectors_config:
                                vector_names = list(vectors_config.keys())
                                print(f"   📊 Available vectors: {vector_names}")
                                
                                # Check if configured embedding model matches available vectors
                                embedding_model = env_vars.get('EMBEDDING_MODEL', '')
                                expected_vector_name = self._get_expected_vector_name(embedding_model)
                                
                                if expected_vector_name in vector_names:
                                    print(f"   ✅ Vector configuration matches: {expected_vector_name}")
                                    return {"status": "connected", "collections": len(collections['result']['collections']), "vector_match": True}
                                else:
                                    print(f"   ❌ Vector mismatch! Expected: {expected_vector_name}, Available: {vector_names}")
                                    return {"status": "vector_mismatch", "issue": f"Expected vector '{expected_vector_name}' not found", "available_vectors": vector_names}
                            else:
                                print(f"   ⚠️  No vector configuration found in collection")
                                return {"status": "no_vectors", "issue": "Collection has no vector configuration"}
                        else:
                            print(f"   ❌ Cannot access collection '{collection_name}': {collection_response.status_code}")
                            return {"status": "collection_error", "issue": f"Collection access failed: {collection_response.status_code}"}
                    else:
                        print(f"   ❌ Qdrant returned status {response.status_code}")
                        return {"status": "failed", "issue": f"HTTP {response.status_code}"}
                        
                except Exception as e:
                    print(f"   ❌ Cannot reach Qdrant: {e}")
                    return {"status": "unreachable", "issue": str(e)}
            else:
                print(f"   ⚠️  No QDRANT_URL configured")
                return {"status": "unconfigured", "issue": "No QDRANT_URL"}
        
        # Brave search checks
        elif 'brave' in server_name.lower():
            env_vars = server_config.get('env', {})
            api_key = env_vars.get('BRAVE_API_KEY', '')
            
            if not api_key or 'MISSING' in api_key:
                print(f"   ⚠️  BRAVE_API_KEY not set")
                return {"status": "unconfigured", "issue": "Missing BRAVE_API_KEY"}
            else:
                print(f"   ✅ BRAVE_API_KEY configured")
                return {"status": "configured"}
        
        print(f"   ℹ️  No specific dependency checks for {server_name}")
        return {"status": "unknown"}
    
    def run_comprehensive_check(self):
        """Run comprehensive MCP status check"""
        print("🧪 MCP Comprehensive Status Check")
        print("=" * 80)
        print(f"Working directory: {os.getcwd()}")
        print(f"Timestamp: {datetime.now()}")
        print()
        
        results = {}
        
        for server_name, server_info in self.servers.items():
            print(f"🖥️  Checking {server_name} ({server_info['source']} config)")
            print("-" * 60)
            
            server_config = server_info['config']
            
            # Test server connectivity
            connectivity = self.test_server_connectivity(server_name, server_config)
            
            # Check dependencies
            dependencies = self.check_external_dependencies(server_name, server_config)
            
            results[server_name] = {
                'source': server_info['source'],
                'connectivity': connectivity,
                'dependencies': dependencies,
                'overall_status': self.determine_overall_status(connectivity, dependencies)
            }
            
            print()
        
        # Summary
        print("📊 SUMMARY")
        print("=" * 80)
        
        for server_name, result in results.items():
            status = result['overall_status']
            source = result['source']
            
            if status == 'healthy':
                icon = "✅"
            elif status == 'warning':
                icon = "⚠️ "
            elif status == 'failed':
                icon = "❌"
            else:
                icon = "❓"
            
            print(f"{icon} {server_name} ({source}): {status}")
            
            # Show issues
            if result['connectivity']['status'] != 'connected':
                print(f"   Connectivity: {result['connectivity'].get('issue', 'Unknown issue')}")
            
            if result['dependencies']['status'] in ['failed', 'unreachable', 'unconfigured']:
                print(f"   Dependencies: {result['dependencies'].get('issue', 'Unknown issue')}")
        
        return results
    
    def _get_expected_vector_name(self, embedding_model):
        """Map embedding model names to expected vector names in Qdrant"""
        model_mapping = {
            'all-MiniLM-L6-v2': 'fast-all-minilm-l6-v2',
            'sentence-transformers/all-MiniLM-L6-v2': 'fast-all-minilm-l6-v2', 
            'BAAI/bge-small-en-v1.5': 'fast-bge-small-en-v1.5',
            'bge-small-en-v1.5': 'fast-bge-small-en-v1.5'
        }
        return model_mapping.get(embedding_model, f'fast-{embedding_model.lower().replace("/", "-").replace("_", "-")}')
    
    def determine_overall_status(self, connectivity, dependencies):
        """Determine overall server status"""
        # Special handling for vector mismatch
        if dependencies.get('status') == 'vector_mismatch':
            return 'failed'
        elif connectivity['status'] == 'connected' and dependencies['status'] in ['connected', 'configured', 'unknown']:
            return 'healthy'
        elif connectivity['status'] in ['warning', 'timeout'] or dependencies['status'] in ['warning', 'unconfigured']:
            return 'warning'
        else:
            return 'failed'

if __name__ == "__main__":
    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    os.chdir(project_dir)
    
    checker = MCPStatusChecker()
    results = checker.run_comprehensive_check()