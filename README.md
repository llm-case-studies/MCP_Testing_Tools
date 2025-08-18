# MCP Testing Suite

A comprehensive containerized testing environment for Model Context Protocol (MCP) servers.

## Features

🔧 **Mock MCP Server** - HTTP-based mock server for testing MCP protocol
🔄 **Communication Proxy** - Intercept and debug MCP stdio communication  
🌐 **Web Interface** - Visual testing and debugging interface
🐳 **Containerized** - Isolated testing environment with volume mounts
📊 **Logging & Analytics** - Real-time communication monitoring
🔍 **Auto-Discovery** - Finds MCP servers from Claude/Gemini configs

## Quick Start

```bash
# Clone and start
git clone <repo>
cd MCP_Testing_Tools
chmod +x start.sh
./start.sh
```

Open http://localhost:8094 in your browser.

## Architecture

### Current Services (V1) 🧙‍♂️

- **Port 8094**: 📱 Web Portal (main interface & API)
- **Port 8095**: 🧞 Mock Genie (HTTP MCP simulator)  
- **Port 8096**: 🕵️ Proxy Spy (stdio interceptor)

### 🚀 **Coming Soon: V2 Dynamic Launcher** 
See [V2 Architecture Documentation](docs/architecture/v2-dynamic-launcher.md) for the next-generation design:
- **Dynamic project launcher** with custom config support
- **Project-level MCP configurations** (`.mcp.json`)
- **Team collaboration** with shared config repositories  
- **Multi-session testing** for different projects simultaneously
- **CI/CD integration** ready

### Volume Mounts

- `~/.claude.json` → `/mcp-configs/.claude.json` (read-only)
- `~/.gemini` → `/mcp-configs/.gemini` (read-only)
- `./workspace` → `/workspace` (read-write testing area)
- `./logs` → `/app/logs` (read-write logging)

## Usage

### 1. Discover MCP Servers

The suite automatically discovers MCP servers from:
- Claude configuration (`~/.claude.json`)
- Gemini configuration (`~/.gemini/`)
- Built-in test servers

### 2. Test Communication

**Mock Genie Testing:**
```bash
curl -X POST http://localhost:9091/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}'
```

**Proxy Spy Testing:**
```bash
# Start proxy with a real MCP server
curl -X POST http://localhost:9092/proxy/start \
  -H "Content-Type: application/json" \
  -d '{"command":["uvx","mcp-server-filesystem","/workspace"]}'

# Send commands through proxy
curl -X POST http://localhost:9092/proxy/send \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}'
```

### 3. Web Portal

Navigate to http://localhost:8094 for:
- Server discovery and configuration
- Interactive tool testing
- Real-time communication logs
- Test suite management

## Container stdio Compatibility

✅ **Full stdio support** - MCP servers communicate via stdin/stdout
✅ **Process isolation** - Each server runs in isolated subprocess
✅ **Real-time monitoring** - Live stream of communication
✅ **Error injection** - Test error handling and resilience

## Development

### Running Individual Services

```bash
# All-in-one (default)
docker-compose up

# Individual services for debugging
docker-compose --profile debug up
```

### Adding Custom MCP Servers

1. Mount server code into `/workspace`
2. Add configuration via web interface
3. Test through proxy or direct HTTP calls

### Custom Filters

The proxy supports custom filters for:
- Message delays
- Error injection  
- Content modification
- Protocol debugging

## Debugging

### View Logs
```bash
docker-compose logs -f
docker-compose logs mcp-testing
```

### Shell Access
```bash
docker-compose exec mcp-testing bash
```

### Configuration Discovery Test
```bash
docker-compose exec mcp-testing python config_discovery.py
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
# Check what's using ports
netstat -tulpn | grep :909[0-2]
# Stop conflicting services or change ports in docker-compose.yml
```

**Mount Issues:**
```bash
# Verify config files exist
ls -la ~/.claude.json ~/.gemini/
# Check permissions
docker-compose exec mcp-testing ls -la /mcp-configs/
```

**stdio Problems:**
```bash
# Test basic communication
docker-compose exec mcp-testing python -c "
import subprocess
proc = subprocess.Popen(['echo', 'hello'], stdout=subprocess.PIPE)
print(proc.stdout.read())
"
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
