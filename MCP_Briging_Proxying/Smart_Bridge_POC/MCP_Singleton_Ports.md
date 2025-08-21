# MCP Bridge Singleton Port Allocation

## Overview
STDIO MCP servers are known to misbehave when run concurrently. Each underlying STDIO server should have exactly ONE bridge instance running on the device to avoid conflicts.

## Port Assignments

### Production Bridge Ports (8100-8199)
- **8100**: Qdrant Memory Server (`uvx mcp-server-qdrant`)
- **8101**: Serena MCP Server (`serena start-mcp-server --transport stdio`) 
- **8102**: Reserved for future MCP server
- **8103**: Reserved for future MCP server
- **8104-8199**: Available for additional MCP servers

### Development/Test Bridge Ports (8200-8299)
- **8200**: Test bridge instance
- **8201**: Development bridge instance
- **8202-8299**: Available for testing

## Bridge Configuration

Each bridge should be started as:
```bash
cd /path/to/Smart_Bridge_POC
BRIDGE_AUTH_MODE=none python3 simple_bridge.py \
  --port <ASSIGNED_PORT> \
  --cmd "<STDIO_SERVER_COMMAND>" \
  --log_level DEBUG \
  --log_location /var/log/mcp-bridges/
```

## MCP Client Configuration

Update `.mcp.json` to point to singleton bridges:
```json
{
  "mcpServers": {
    "qdrant-memory-bridged": {
      "type": "sse",
      "url": "http://localhost:8100/sse",
      "description": "🧠 Qdrant Vector Memory System (via Bridge)"
    },
    "serena-mcp-bridged": {
      "type": "sse", 
      "url": "http://localhost:8101/sse",
      "description": "🔍 Serena MCP (via Bridge)"
    }
  }
}
```

## Operational Notes

1. **One Bridge Per Server**: Never run multiple bridges for the same underlying STDIO server
2. **Port Persistence**: Always use the same port for the same underlying server
3. **Health Checks**: Monitor bridge health at `http://localhost:<PORT>/health`
4. **Logs**: Bridge logs include all incoming calls and responses when log_level=DEBUG
5. **Session Management**: Each bridge handles multiple client sessions internally

## Current Status
- Port 8100: Reserved for Qdrant (not yet running on production port)
- Port 8101: Reserved for Serena (not yet running on production port)
- Port 8102: Currently running Qdrant (temporary)
- Port 8103: Currently running Serena (temporary)