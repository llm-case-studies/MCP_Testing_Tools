# MCP Testing Suite V2

A comprehensive testing environment for Model Context Protocol (MCP) servers with dynamic project launching and Postman-like tool testing.

## Features

🚀 **V2 Dynamic Launcher** - Project-based MCP testing with session management
🧪 **MCP Postman** - Interactive tool testing interface like Postman for APIs
🔍 **Auto-Discovery** - Finds MCP servers from Claude/Gemini configs
🎛️ **Session Management** - Multi-project testing with isolated containers
📂 **Project Scanner** - Automatic detection of MCP-enabled projects
🐳 **Containerized Backends** - Isolated testing environments
📊 **Request History** - Track and replay MCP tool calls
🔧 **Sample Generation** - Auto-generate test requests from tool schemas

## Quick Start

```bash
# Clone repository
git clone <repo>
cd MCP_Testing_Tools

# Start the launcher
cd launcher
python3 main.py
```

Open http://localhost:8094 in your browser to access the Dynamic Launcher.

## Architecture V2

### 🚀 Dynamic Launcher (Port 8094)
The main interface for project management and MCP testing:
- **Project Scanner**: Automatically find MCP-enabled projects
- **Session Management**: Launch isolated testing backends per project
- **MCP Postman**: Interactive tool testing with request history
- **Configuration Discovery**: Auto-detect Claude/Gemini MCP configs

### 🐳 Dynamic Backend Containers (Port 8095+)
Isolated testing environments launched per project:
- **Port 8095+**: Project-specific backend APIs
- **MCP Server Discovery**: Runtime server introspection
- **Tool Execution**: Real MCP tool calling with logging
- **Request Tracking**: History and collections management

### Volume Mounts

- `~/.claude.json` → `/mcp-configs/.claude.json` (read-only)
- `~/.gemini` → `/mcp-configs/.gemini` (read-only)
- `./workspace` → `/workspace` (read-write testing area)
- `./logs` → `/app/logs` (read-write logging)

## Usage

### 1. 📂 Project Management

**Scan for MCP Projects:**
1. Use the Project Scanner to find MCP-enabled projects
2. Browse directories or specify project paths
3. Review detected MCP configurations and servers
4. Launch isolated testing backends for each project

**Manual Project Launch:**
- Specify project path and config source
- Choose from project/user/custom configurations  
- Launch dedicated backend container

### 2. 🧪 MCP Postman - Tool Testing

**Interactive Testing Interface:**
1. Click "Open MCP Tool Tester" from the launcher
2. Select active testing session
3. Discover available MCP servers
4. Browse tools and their schemas
5. Craft custom requests with JSON arguments
6. Execute tools and view detailed results
7. Track request history and build collections

**API Integration:**
```bash
# Discover MCP servers
curl http://localhost:8095/api/mcp/discover

# Get tools for a server
curl http://localhost:8095/api/mcp/tools/server-name

# Execute a tool
curl -X POST http://localhost:8095/api/mcp/call-tool/server-name \
  -H "Content-Type: application/json" \
  -d '{"tool_name":"test","arguments":{"param":"value"}}'

# Get request history
curl http://localhost:8095/api/mcp/history
```

### 3. 🎛️ Session Management

Navigate to http://localhost:8094 for:
- Project discovery and configuration
- Multi-session testing management
- MCP server introspection  
- Real-time tool execution logs
- Request history and collections

## MCP Server Compatibility

✅ **stdio Protocol** - Full MCP JSON-RPC over stdin/stdout
✅ **HTTP Protocol** - Direct HTTP MCP server support  
✅ **Auto-Discovery** - Finds servers from Claude/Gemini configs
✅ **Dynamic Loading** - Runtime server discovery and introspection
✅ **Tool Schema Support** - Automatic request generation from schemas
✅ **Real-time Execution** - Live tool calling with detailed logging

## Development

### Running the Test Suite

```bash
# Run comprehensive test suite
./run_mcp_postman_tests.sh

# Individual test categories
python3 -m pytest tests/test_mcp_postman_api.py -v           # Backend API tests
python3 -m pytest launcher/tests/test_mcp_postman_integration.py -v  # Integration tests
python3 test_mcp_postman_e2e.py                             # End-to-end tests
```

### Architecture Components

**Launcher (`launcher/main.py`)**:
- FastAPI web interface on port 8094
- Project scanning and session management
- MCP Postman UI with modal interface
- RESTful APIs for frontend interaction

**Backend (`web_interface.py`)**:
- Dynamic container orchestration  
- MCP server discovery and tool execution
- Request history and collections
- JSON-RPC protocol handling

### Adding Custom Projects

1. Create project directory with MCP configuration
2. Use Project Scanner to detect and launch
3. Test via MCP Postman interface
4. Build request collections for CI/CD

## Debugging

### View Launcher Logs
```bash
# In launcher directory
python3 main.py  # Direct output to console

# Check session logs
curl http://localhost:8094/api/sessions
```

### View Backend Logs
```bash  
# Backend containers log to their respective sessions
# Access via launcher session management interface
```

### Test Configuration Discovery
```bash
# Test MCP server discovery
python3 -c "
from config_discovery import MCPConfigDiscovery
discovery = MCPConfigDiscovery('/path/to/configs')
servers = discovery.discover_servers()
print(f'Found {len(servers)} servers')
"
```

## Security

- Containers run as non-root user
- Host configs mounted read-only
- Isolated network environment
- No persistent modifications to host

## Troubleshooting

### Common Issues

**Port Conflicts:**
```bash
# Check what's using ports 8094+
lsof -i :8094
lsof -i :8095
# Stop conflicting services
kill -9 <PID>
```

**MCP Server Discovery Issues:**
```bash
# Verify config files exist
ls -la ~/.claude.json ~/.gemini/
# Test manual discovery
python3 -c "
from config_discovery import MCPConfigDiscovery
discovery = MCPConfigDiscovery('.')
print(discovery.discover_servers())
"
```

**Session Launch Problems:**
```bash
# Check Docker is running
docker ps
# Verify project paths are accessible
ls -la /path/to/project
# Check session status via API
curl http://localhost:8094/api/sessions
```

**MCP Postman Interface Issues:**
```bash
# Clear browser cache
# Check browser console for JavaScript errors
# Verify active sessions exist
curl http://localhost:8094/api/sessions
```

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Submit pull request

## License

MIT License - see LICENSE file

---

*Built with ❤️ for the MCP community*
