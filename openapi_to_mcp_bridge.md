# Bridging OpenAPI and MCP: A Simple and Powerful Solution

## Introduction

This document outlines a simple and powerful solution for bridging existing REST APIs with the Model Context Protocol (MCP). This allows us to leverage the vast ecosystem of existing web APIs and make them available to our AI agents and language models.

## The Challenge: Connecting OpenAPI to MCP

Custom GPTs and other AI agents are designed to interact with external APIs using the **OpenAPI** specification (formerly Swagger). This specification provides a standardized way for the agent to understand the API's capabilities and make calls to it.

On the other hand, **MCP (Model Context Protocol)** servers use a different protocol and are not directly callable by these agents out of the box. This creates a gap between the world of existing APIs and the world of AI agents.

## The Solution: The `FastMCP` Bridge

The solution is to create a **bridge** or a **proxy** that translates between the OpenAPI specification and the MCP protocol. This bridge exposes an OpenAPI-compatible interface to the AI agent and translates the calls to the MCP server.

The good news is that we don't have to build this bridge from scratch. The **`FastMCP`** Python library provides a built-in function, `FastMCP.from_openapi()`, that does all the heavy lifting for us.

## Draft Implementation

Here is a draft implementation of an OpenAPI to MCP bridge using the `FastMCP` library:

```python
from fastmcp import FastMCP
import uvicorn

# --- Configuration ---

# The URL to your OpenAPI specification
# This can be a local file path or a remote URL
OPENAPI_SPEC_URL = "https://petstore.swagger.io/v2/swagger.json"

# The name of your MCP server
MCP_SERVER_NAME = "PetStoreMCPServer"

# The host and port to run the MCP server on
MCP_SERVER_HOST = "127.0.0.1"
MCP_SERVER_PORT = 8000

# --- Implementation ---

def create_mcp_server_from_openapi(spec_url: str, server_name: str) -> FastMCP:
    """
    Creates an MCP server from an OpenAPI specification.

    Args:
        spec_url: The URL to the OpenAPI specification.
        server_name: The name of the MCP server.

    Returns:
        An instance of the FastMCP server.
    """
    print(f"Creating MCP server '{server_name}' from OpenAPI spec at: {spec_url}")
    mcp_server = FastMCP.from_openapi(
        name=server_name,
        spec=spec_url,
    )
    print("MCP server created successfully.")
    return mcp_server

def run_mcp_server(mcp_server: FastMCP, host: str, port: int):
    """
    Runs the MCP server.

    Args:
        mcp_server: The FastMCP server instance.
        host: The host to run the server on.
        port: The port to run the server on.
    """
    print(f"Running MCP server on http://{host}:{port}")
    uvicorn.run(mcp_server, host=host, port=port)


if __name__ == "__main__":
    # Create the MCP server
    mcp_server = create_mcp_server_from_openapi(OPENAPI_SPEC_URL, MCP_SERVER_NAME)

    # Run the MCP server
    run_mcp_server(mcp_server, MCP_SERVER_HOST, MCP_SERVER_PORT)

```

This script will:

1.  Create an MCP server from the PetStore OpenAPI specification.
2.  Run the server on `http://127.0.0.1:8000`.

You can then connect to this server with an MCP client and use the tools defined in the OpenAPI specification.

## Next Steps

*   **Test with your own API:** Replace the PetStore OpenAPI specification with the URL to your own API's specification.
*   **Explore `FastMCP` features:** The `FastMCP` library has many other features, such as authentication, proxying, and server composition. Explore the [FastMCP documentation](https://gofastmcp.com) to learn more.
*   **Integrate with your toolset:** Discuss with the team how to best incorporate this feature into our existing toolset. We could create a reusable component or a command-line tool to simplify the process of creating MCP bridges.
