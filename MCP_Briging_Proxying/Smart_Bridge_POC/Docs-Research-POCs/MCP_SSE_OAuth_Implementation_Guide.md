# MCP SSE Bridge OAuth 2.1 Implementation Guide

## Executive Summary

This document details our discoveries and solutions for implementing a Model Context Protocol (MCP) compliant SSE bridge that satisfies Claude Code's OAuth 2.1 validation requirements while maintaining "no authentication required" functionality for local network deployments.

## The Challenge

Converting stdio MCP servers to SSE transport while satisfying Claude Code's strict OAuth 2.1 compliance requirements, even for local network scenarios that don't actually require authentication.

## Key Discoveries

### 1. OAuth Discovery Endpoint Requirements

**Problem:** Claude Code expects OAuth 2.1 metadata discovery endpoints to return valid string URLs, not null values, even when no authentication is needed.

**Initial Approach (Failed):**
```json
{
  "authorization_endpoint": null,
  "token_endpoint": null,
  "registration_endpoint": null
}
```

**Error:** `Expected string, received null`

**Solution:**
```json
{
  "issuer": "http://localhost:8100",
  "authorization_endpoint": "http://localhost:8100/no-auth-required",
  "token_endpoint": "http://localhost:8100/no-auth-required",
  "scopes_supported": ["none"],
  "response_types_supported": ["code"],
  "grant_types_supported": ["authorization_code"],
  "subject_types_supported": ["public"],
  "registration_endpoint": "http://localhost:8100/no-registration-required"
}
```

### 2. Client Registration Requirements

**Problem:** Claude Code expects OAuth client registration responses with required fields `client_id` and `redirect_uris`.

**Initial Approach (Failed):**
```json
{
  "error": "registration_not_supported",
  "error_description": "No registration needed"
}
```

**Error:** 
```
"redirect_uris": Required
"client_id": Required
```

**Solution:**
```json
{
  "client_id": "no-auth-required",
  "client_secret": "no-auth-required",
  "redirect_uris": ["http://localhost:8100/no-auth-required"],
  "client_name": "MCP Client (No Auth Required)",
  "client_uri": "http://localhost:8100",
  "grant_types": ["authorization_code"],
  "response_types": ["code"],
  "scope": "none"
}
```

### 3. Response Types Support

**Problem:** Claude Code validates that the authorization server supports the `code` response type for OAuth authorization code flow.

**Error:** `Incompatible auth server: does not support response type code`

**Solution:** Explicitly declare support for `code` response type:
```json
{
  "response_types_supported": ["code"],
  "grant_types_supported": ["authorization_code"]
}
```

## Implementation Architecture

### OAuth Endpoints Implemented

1. **`/.well-known/oauth-authorization-server`** - OAuth Authorization Server Metadata
2. **`/.well-known/oauth-protected-resource`** - OAuth Protected Resource Metadata  
3. **`/no-auth-required`** - Placeholder authorization/token endpoint
4. **`/no-registration-required`** - Client registration endpoint
5. **`/register`** - Alternative client registration endpoint

### SSE Connection Flow

1. **OAuth Discovery Phase:**
   ```
   Claude Code → GET /.well-known/oauth-authorization-server
   Bridge → Returns OAuth metadata with proper string URLs
   ```

2. **Client Registration Phase:**
   ```
   Claude Code → POST /no-registration-required  
   Bridge → Returns dummy client credentials
   ```

3. **SSE Connection Phase:**
   ```
   Claude Code → GET /sse
   Bridge → Establishes SSE stream with session management
   ```

4. **MCP Protocol Phase:**
   ```
   Claude Code → POST /messages (MCP initialize)
   Bridge → Routes to stdio MCP server and returns response via SSE
   ```

## Code Implementation Details

### OAuth Authorization Server Endpoint

```python
@app.get("/.well-known/oauth-authorization-server")  
async def oauth_authorization_server(request: Request):
    port = app.state.config.port if hasattr(app.state, 'config') else 8100
    base_url = f"http://localhost:{port}"
    return JSONResponse({
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/no-auth-required",
        "token_endpoint": f"{base_url}/no-auth-required",  
        "scopes_supported": ["none"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "subject_types_supported": ["public"],
        "registration_endpoint": f"{base_url}/no-registration-required"
    })
```

### Client Registration Endpoint

```python
@app.post("/no-registration-required")
async def no_registration_required(request: Request):
    port = app.state.config.port if hasattr(app.state, 'config') else 8100
    base_url = f"http://localhost:{port}"
    
    return JSONResponse({
        "client_id": "no-auth-required",
        "client_secret": "no-auth-required", 
        "redirect_uris": [f"{base_url}/no-auth-required"],
        "client_name": "MCP Client (No Auth Required)",
        "client_uri": base_url,
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "scope": "none"
    })
```

### No-Auth Placeholder Endpoints

```python
@app.get("/no-auth-required")
@app.post("/no-auth-required")
async def no_auth_required():
    return JSONResponse({
        "error": "no_authentication_required",
        "error_description": "This MCP server operates without authentication for local network use"
    })
```

## Connection Exchange Sequence

### 1. Initial Discovery
```
Claude Code:
  GET /.well-known/oauth-authorization-server
  
Bridge Response:
  200 OK
  {
    "issuer": "http://localhost:8101",
    "authorization_endpoint": "http://localhost:8101/no-auth-required",
    "token_endpoint": "http://localhost:8101/no-auth-required",
    "response_types_supported": ["code"],
    "grant_types_supported": ["authorization_code"]
  }
```

### 2. Client Registration
```
Claude Code:
  POST /no-registration-required
  
Bridge Response:
  200 OK
  {
    "client_id": "no-auth-required",
    "redirect_uris": ["http://localhost:8101/no-auth-required"],
    "response_types": ["code"]
  }
```

### 3. SSE Connection Establishment
```
Claude Code:
  GET /sse
  Headers: {
    "Accept": "text/event-stream",
    "User-Agent": "claude-code/1.0.85"
  }
  
Bridge Response:
  200 OK
  Content-Type: text/event-stream
  [Streaming connection established]
```

### 4. MCP Protocol Communication
```
Claude Code:
  POST /messages
  {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "claude-code", "version": "1.0.85"}
    }
  }
  
Bridge → stdio MCP Server → Bridge Response via SSE:
  {
    "jsonrpc": "2.0", 
    "id": 1,
    "result": {
      "protocolVersion": "2024-11-05",
      "capabilities": {"tools": [...]},
      "serverInfo": {"name": "test-server", "version": "1.0.0"}
    }
  }
```

## Error Patterns Encountered

### 1. Null Value Validation Errors
```json
{
  "code": "invalid_type",
  "expected": "string", 
  "received": "null",
  "path": ["authorization_endpoint"]
}
```

### 2. Missing Required Fields
```json
{
  "code": "invalid_type",
  "expected": "array",
  "received": "undefined", 
  "path": ["redirect_uris"]
}
```

### 3. Response Type Compatibility
```
Error: Incompatible auth server: does not support response type code
```

## Session Management

The bridge maintains active SSE sessions with:
- Unique session IDs for each connection
- Heartbeat mechanisms (30-second intervals)
- Message queuing for reliable delivery
- Connection state tracking

```python
class Session:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.websockets = set() 
        self.last_beat = time.time()
```

## Debug and Monitoring

Debug endpoint provides real-time bridge status:
```json
{
  "bridge_status": "running",
  "active_sessions": 2,
  "session_details": {
    "session_id": {
      "queue_size": 0,
      "websocket_count": 0, 
      "last_beat": 1755708387.657
    }
  },
  "in_flight_messages": 0,
  "auth_required": false
}
```

## Key Insights for MCP SSE Implementation

1. **OAuth 2.1 Compliance is Mandatory** - Even for local "no-auth" scenarios, Claude Code requires full OAuth metadata structure

2. **String URLs Required** - All OAuth endpoints must be valid string URLs, null values cause validation failures

3. **Response Type Support** - Must explicitly declare support for `"code"` response type

4. **Client Registration Fields** - `client_id` and `redirect_uris` are strictly required fields

5. **Session Management Critical** - Proper SSE session handling with heartbeats ensures connection stability

6. **Placeholder Strategy Works** - Using meaningful placeholder URLs that return "no auth needed" responses satisfies validation while maintaining intended behavior

## Testing Results

✅ OAuth discovery endpoints working  
✅ Client registration validation passing  
✅ SSE connections establishing successfully  
✅ Multiple active sessions supported  
✅ MCP protocol message routing functional  
✅ Session heartbeats maintaining connections  

## Next Steps for Research

1. Survey latest MCP SSE implementations in open source projects
2. Compare OAuth handling strategies across different MCP clients
3. Document best practices for production MCP bridge deployment
4. Investigate PKCE requirements and security considerations
5. Research token lifecycle management for stateful deployments

---

*This documentation represents the accumulated knowledge from implementing a working MCP SSE bridge that satisfies Claude Code's OAuth 2.1 validation requirements.*