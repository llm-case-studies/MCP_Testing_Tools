#!/usr/bin/env python3
"""
MCP Testing Suite V2 - Dynamic Project Launcher
Central hub for selecting projects and launching testing backends
"""

import os
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

try:
    from .project_scanner import ProjectScanner
    from .session import SessionManager
    from .services import LauncherService
except ImportError:
    from project_scanner import ProjectScanner
    from session import SessionManager
    from services import LauncherService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MCP Testing Suite V2 - Project Launcher", version="2.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
project_scanner = ProjectScanner()
session_manager = SessionManager()
launcher_service = LauncherService(session_manager, project_scanner)

# Models
class ProjectInfo(BaseModel):
    path: str
    name: str
    config_sources: List[Dict[str, Any]]
    description: Optional[str] = None

class LaunchConfig(BaseModel):
    project_path: str
    config_source: str
    config_type: str  # "project", "user", "custom"
    session_name: Optional[str] = None
    test_scenario: str = "development"
    selected_servers: Optional[List[str]] = None  # If None, use all servers
    server_filter_mode: str = "include"  # "include" or "exclude"

class SessionInfo(BaseModel):
    session_id: str
    project_path: str
    config_source: str
    status: str
    backend_url: Optional[str] = None
    created_at: datetime
    last_activity: datetime

# API Endpoints

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

@app.get("/", response_class=FileResponse)
async def serve_launcher(request: Request):
    """Serve the project launcher interface"""
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))

@app.get("/api/browse-folders")
async def browse_folders(path: str = "."):
    """Browse directories for folder selection"""
    try:
        result = await launcher_service.browse_folders(path)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error browsing folders: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/scan-projects")
async def scan_projects(path: str = "."):
    """Scan directory for projects with MCP configurations"""
    try:
        result = await launcher_service.scan_projects(path)
        return result
    except Exception as e:
        logger.error(f"Error scanning projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config-preview")
async def get_config_preview(config_path: str):
    """Get detailed preview of a configuration file"""
    try:
        result = await launcher_service.get_config_preview(config_path)
        return result
    except Exception as e:
        logger.error(f"Error getting config preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/launch-backend")
async def launch_backend(config: LaunchConfig):
    """Launch a testing backend with the specified configuration"""
    try:
        result = await launcher_service.launch_session(config.dict())
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error launching backend: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions")
async def list_sessions():
    """List all testing sessions"""
    try:
        result = await launcher_service.list_sessions()
        return result
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    """Stop a testing session"""
    try:
        result = await launcher_service.stop_session(session_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error stopping session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/sessions/{session_id}")
async def remove_session(session_id: str):
    """Remove a session from tracking"""
    try:
        result = await launcher_service.remove_session(session_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error removing session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions/{session_id}")
async def get_session_details(session_id: str):
    """Get detailed information about a specific session"""
    try:
        result = await launcher_service.get_session_details(session_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting session details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    try:
        result = await launcher_service.get_health_status()
        return result
    except Exception as e:
        logger.error(f"Error getting health status: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "service": "mcp-launcher",
            "version": "2.0.0"
        }

if __name__ == "__main__":
    import sys
    import argparse
    import webbrowser
    import os
    
    # Command line argument parsing
    parser = argparse.ArgumentParser(description="MCP Testing Suite Dynamic Launcher")
    parser.add_argument("--port", type=int, default=8094, help="Port to run the launcher on")
    parser.add_argument("--auto-open", action="store_true", help="Automatically open browser")
    parser.add_argument("--no-auto-open", action="store_true", help="Do not automatically open browser")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    args = parser.parse_args()
    
    # Check environment variables (from START script)
    port = int(os.environ.get("MCP_TESTING_SUITE_PORT", args.port))
    auto_open = (os.environ.get("MCP_TESTING_SUITE_AUTO_OPEN", "false").lower() == "true" or args.auto_open) and not args.no_auto_open
    
    print(f"🚀 MCP Testing Suite Dynamic Launcher")
    print(f"🌐 Starting on http://{args.host}:{port}")
    
    # Auto-open browser if requested
    if auto_open:
        def open_browser():
            import time
            time.sleep(1)  # Wait for server to start
            try:
                webbrowser.open(f"http://localhost:{port}")
                print(f"🎯 Opened browser at http://localhost:{port}")
            except Exception as e:
                print(f"💡 Please open http://localhost:{port} in your browser")
        
        import threading
        threading.Thread(target=open_browser, daemon=True).start()
    
    # Start the server
    uvicorn.run(app, host=args.host, port=port)
