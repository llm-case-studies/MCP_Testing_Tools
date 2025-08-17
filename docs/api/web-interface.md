# Web Interface API Reference

The **Web Portal** (port 9090) provides a comprehensive REST API and WebSocket interface for managing MCP server testing.

## Base URL

```
http://localhost:9090
```

## Authentication

Currently no authentication required. All endpoints are open for local development.

## REST API Endpoints

### Server Management

#### `POST /api/servers`
Add a new MCP server configuration.

**Request Body:**
```json
{
  "name": "my-server",
  "type": "stdio|mock|proxy",
  "url": "http://localhost:9091",  // for http/proxy types
  "command": ["uvx", "my-server"], // for stdio type
  "description": "My test server"
}
```

**Response:**
```json
{
  "message": "Server my-server added"
}
```

#### `GET /api/servers`
List all configured servers.

**Response:**
```json
{
  "servers": [
    {
      "name": "my-server",
      "type": "stdio",
      "command": ["uvx", "my-server"],
      "description": "My test server"
    }
  ]
}
```

#### `GET /api/servers/{server_name}`
Get specific server configuration.

**Response:**
```json
{
  "name": "my-server",
  "type": "stdio",
  "command": ["uvx", "my-server"],
  "description": "My test server"
}
```

#### `DELETE /api/servers/{server_name}`
Remove server configuration.

**Response:**
```json
{
  "message": "Server my-server removed"
}
```

### Server Testing

#### `POST /api/servers/{server_name}/test-connection`
Test connection to MCP server.

**Response:**
```json
{
  "status": "connected|error",
  "response": {...},
  "latency_ms": 123.45,
  "message": "Optional error message"
}
```

#### `GET /api/servers/{server_name}/tools`
List tools available on server.

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "tools": [
      {
        "name": "file_read",
        "description": "Read file contents",
        "inputSchema": {
          "type": "object",
          "properties": {
            "path": {"type": "string"}
          },
          "required": ["path"]
        }
      }
    ]
  }
}
```

#### `POST /api/servers/{server_name}/tools/{tool_name}/call`
Call a tool on the server.

**Request Body:**
```json
{
  "param1": "value1",
  "param2": "value2"
}
```

**Response:**
```json
{
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Tool execution result"
      }
    ]
  },
  "execution_time_ms": 234.56,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

#### `GET /api/servers/{server_name}/logs`
Get server communication logs.

**Response:**
```json
{
  "logs": [
    {
      "timestamp": "2024-01-01T12:00:00Z",
      "direction": "incoming|outgoing",
      "message": {...},
      "client_info": "client:127.0.0.1"
    }
  ]
}
```

### Server Discovery

#### `POST /api/discover-servers`
Auto-discover MCP servers from configurations.

**Response:**
```json
{
  "discovered": [
    {
      "name": "claude_filesystem",
      "type": "stdio",
      "source": "claude",
      "command": ["uvx", "mcp-server-filesystem", "/workspace"],
      "description": "Claude MCP Server: filesystem",
      "validation": {
        "valid": true,
        "issues": [],
        "warnings": []
      },
      "capabilities": {
        "tools": true,
        "resources": true,
        "logging": false
      }
    }
  ],
  "config_dir": "/mcp-configs",
  "total_servers": 5
}
```

### Test Suite Management

#### `POST /api/test-suites`
Create a new test suite.

**Request Body:**
```json
{
  "name": "smoke-tests",
  "description": "Basic functionality tests",
  "tests": [
    {
      "server_name": "my-server",
      "tool_name": "file_read",
      "parameters": {"path": "/workspace/test.txt"}
    }
  ]
}
```

**Response:**
```json
{
  "message": "Test suite smoke-tests created"
}
```

#### `GET /api/test-suites`
List all test suites.

**Response:**
```json
{
  "test_suites": [
    {
      "name": "smoke-tests",
      "description": "Basic functionality tests",
      "tests": [...]
    }
  ]
}
```

#### `POST /api/test-suites/{suite_name}/run`
Run a test suite.

**Response:**
```json
{
  "suite_name": "smoke-tests",
  "timestamp": "2024-01-01T12:00:00Z",
  "results": [
    {
      "test": {
        "server_name": "my-server",
        "tool_name": "file_read",
        "parameters": {"path": "/workspace/test.txt"}
      },
      "result": {...},
      "success": true
    }
  ],
  "total_tests": 1,
  "passed": 1,
  "failed": 0
}
```

### Test Results

#### `GET /api/test-results`
Get historical test results.

**Response:**
```json
{
  "results": [
    {
      "timestamp": "2024-01-01T12:00:00Z",
      "server_name": "my-server",
      "tool_name": "file_read",
      "parameters": {...},
      "result": {...},
      "execution_time_ms": 123.45,
      "success": true
    }
  ]
}
```

#### `DELETE /api/test-results`
Clear test results history.

**Response:**
```json
{
  "message": "Test results cleared"
}
```

## Error Responses

All endpoints may return error responses in this format:

```json
{
  "detail": "Error description"
}
```

Common HTTP status codes:
- `400` - Bad Request (invalid parameters)
- `404` - Not Found (server/test suite not found)
- `500` - Internal Server Error

## WebSocket Interface

### Connection
```
ws://localhost:9090/ws
```

### Message Format
```json
{
  "type": "log|status|result",
  "data": {...}
}
```

### Example Messages

**Log Entry:**
```json
{
  "type": "log",
  "data": {
    "timestamp": "2024-01-01T12:00:00Z",
    "server": "my-server",
    "direction": "incoming",
    "message": {...}
  }
}
```

**Status Update:**
```json
{
  "type": "status",
  "data": {
    "server": "my-server",
    "status": "connected|disconnected|error",
    "message": "Optional details"
  }
}
```

**Test Result:**
```json
{
  "type": "result",
  "data": {
    "test_id": "test-123",
    "success": true,
    "result": {...},
    "execution_time_ms": 123.45
  }
}
```

## Examples

### Testing a File Server

```bash
# Discover servers
curl -X POST http://localhost:9090/api/discover-servers

# Test connection
curl -X POST http://localhost:9090/api/servers/claude_filesystem/test-connection

# List available tools
curl http://localhost:9090/api/servers/claude_filesystem/tools

# Call file read tool
curl -X POST http://localhost:9090/api/servers/claude_filesystem/tools/file_read/call \
  -H "Content-Type: application/json" \
  -d '{"path": "/workspace/README.md"}'
```

### JavaScript Client Example

```javascript
// Connect to WebSocket for real-time updates
const ws = new WebSocket('ws://localhost:9090/ws');

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Received:', message);
};

// Test a server tool
async function testTool(serverName, toolName, params) {
  const response = await fetch(`/api/servers/${serverName}/tools/${toolName}/call`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(params)
  });
  
  return await response.json();
}

// Usage
testTool('my-server', 'file_read', {path: '/workspace/test.txt'})
  .then(result => console.log('Result:', result));
```