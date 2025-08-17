# Quick Start Guide 🚀

Get your **MCP Debug Wizard** up and running in just 5 minutes! This guide will have you testing MCP servers faster than you can say "abracadabra"! 🧙‍♂️✨

## 📋 Prerequisites

- **Docker** & **docker-compose** installed
- **curl** for testing (optional)
- MCP configurations (Claude/Gemini) for auto-discovery (optional)

### Quick Prerequisites Check

```bash
# Check Docker
docker --version
docker-compose --version

# Check if you have MCP configs (will be auto-discovered)
ls ~/.claude.json ~/.gemini/ 2>/dev/null || echo "No MCP configs found (that's OK!)"
```

## 🚀 Installation & Startup

### 1. Clone the Repository

```bash
git clone https://github.com/llm-case-studies/MCP_Testing_Tools
cd MCP_Testing_Tools
```

### 2. Start the Magic! ✨

```bash
chmod +x start.sh
./start.sh
```

The startup script will:
- 🔨 Build the Docker containers
- 🏃 Start all three services
- 🔍 Run health checks
- 🧙‍♂️ Test configuration discovery

### 3. Verify Everything is Running

You should see output like:
```
🎉 MCP Debug Wizard is ready! 🧙‍♂️✨

📱 Web Portal:    http://localhost:9090
🧞 Mock Genie:    http://localhost:9091
🕵️ Proxy Spy:     http://localhost:9092
```

## 🎯 Your First Test

### Open the Web Portal

Navigate to **http://localhost:9090** in your browser.

### Test the Mock Genie

Let's start with a simple test of our mock MCP server:

```bash
curl -X POST http://localhost:9091/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}'
```

You should get a response showing available mock tools!

### Discover Your Real MCP Servers

In the Web Portal:

1. Click **"Discover Servers"**
2. See auto-discovered servers from your Claude/Gemini configs
3. Click **"Test Connection"** on any server
4. Explore available tools

## 🧞 Mock Genie - HTTP Testing

The **Mock Genie** simulates MCP protocol over HTTP, perfect for testing client implementations.

### Available Mock Tools

```bash
# List available tools
curl http://localhost:9091/mcp \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}'

# Call the file_read tool
curl http://localhost:9091/mcp \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":"2",
    "method":"tools/call",
    "params":{
      "name":"file_read",
      "arguments":{"path":"/workspace/test.txt"}
    }
  }'
```

### View Mock Server Logs

```bash
curl http://localhost:9091/debug/logs
```

## 🕵️ Proxy Spy - Real Server Testing

The **Proxy Spy** intercepts communication with real MCP servers running via stdio.

### Start a Real MCP Server

```bash
# Start a filesystem server through the proxy
curl -X POST http://localhost:9092/proxy/start \
  -H "Content-Type: application/json" \
  -d '{"command":["uvx","mcp-server-filesystem","/workspace"]}'
```

### Send Commands Through Proxy

```bash
# List tools on the real server
curl -X POST http://localhost:9092/proxy/send \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}'

# Call a tool
curl -X POST http://localhost:9092/proxy/send \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":"2",
    "method":"tools/call",
    "params":{
      "name":"file_read",
      "arguments":{"path":"/workspace"}
    }
  }'
```

### View Communication Logs

```bash
curl http://localhost:9092/proxy/logs
```

## 📱 Web Portal - Visual Testing

The **Web Portal** provides a user-friendly interface for all testing activities.

### Key Features to Try

1. **Server Discovery**
   - Auto-finds Claude/Gemini MCP servers
   - Validates configurations
   - Shows server capabilities

2. **Interactive Tool Testing**
   - Select server and tool
   - Fill in parameters
   - See real-time results

3. **Test Suite Management**
   - Create reusable test suites
   - Run multiple tests at once
   - Track test history

4. **Real-time Monitoring**
   - Live communication logs
   - WebSocket updates
   - Error tracking

## 🛠️ Common First-Time Tasks

### Add a Custom Mock Tool

```bash
curl -X POST http://localhost:9091/debug/tools \
  -H "Content-Type: application/json" \
  -d '{
    "name": "custom_calculator",
    "description": "Perform basic calculations",
    "inputSchema": {
      "type": "object",
      "properties": {
        "operation": {"type": "string", "enum": ["add", "subtract"]},
        "a": {"type": "number"},
        "b": {"type": "number"}
      },
      "required": ["operation", "a", "b"]
    }
  }'
```

### Create Your First Test Suite

Via the Web Portal:

1. Go to "Test Suites" section
2. Click "Create New Suite"
3. Add tests for different servers/tools
4. Run the suite and view results

### Monitor Real-time Communication

1. Open Web Portal
2. Start a proxy session with a real server
3. Send commands and watch the live logs
4. Try enabling filters (delays, errors)

## 🎯 Next Steps

Now that you're up and running:

1. **Read the [User Guide](web-portal.md)** for detailed Web Portal usage
2. **Try [Debugging Tutorial](../tutorials/debugging-communication.md)** for advanced debugging
3. **Explore [Custom Filters](../tutorials/custom-filters.md)** for message manipulation
4. **Check [Troubleshooting](troubleshooting.md)** if you hit any issues

## 🆘 Quick Troubleshooting

### Port Already in Use?
```bash
# Check what's using the ports
netstat -tulpn | grep :909[0-2]

# Or change ports in docker-compose.yml
```

### Services Not Starting?
```bash
# Check logs
docker-compose logs

# Restart services
docker-compose restart
```

### Can't Access Web Portal?
```bash
# Verify containers are running
docker-compose ps

# Check health
curl http://localhost:9090/ || echo "Service not responding"
```

### Auto-discovery Not Finding Servers?
```bash
# Check config discovery
docker-compose exec mcp-debug-wizard python config_discovery.py

# Verify config files exist and are readable
ls -la ~/.claude.json ~/.gemini/
```

## 🎉 You're Ready!

Congratulations! Your **MCP Debug Wizard** is now ready to help you test, debug, and develop MCP servers. 

Happy testing! 🧙‍♂️✨

---

**Next:** [Web Portal User Guide](web-portal.md) | **Troubleshooting:** [Common Issues](troubleshooting.md)