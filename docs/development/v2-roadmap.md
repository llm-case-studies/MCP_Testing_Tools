# MCP Testing Suite V2 Development Roadmap

## 🎯 Project: Dynamic Project Launcher Architecture

**Goal**: Transform from fixed-config testing tool to flexible, project-aware MCP testing platform

**Timeline**: 4 phases, estimated 2-3 weeks total development

---

## 📋 Phase 1: Foundation (Week 1, Days 1-3)
**Goal**: Basic launcher functionality with simple project selection

### **Deliverables**
- [ ] **Lightweight Project Launcher** (Stage 1)
  - [ ] Minimal FastAPI app for project selection
  - [ ] Simple file browser for project directories
  - [ ] Basic config source detection (`.mcp.json`, `~/.claude.json`)
  - [ ] Session ID generation and tracking

- [ ] **Dynamic Backend Launcher**
  - [ ] Docker command generation with custom mounts
  - [ ] Basic session management (start/stop)
  - [ ] Health check for launched backends

- [ ] **Updated Documentation**
  - [ ] Architecture v2 documentation
  - [ ] Development setup instructions
  - [ ] API documentation for launcher endpoints

### **Technical Tasks**
```bash
# New files to create
./launcher/
├── main.py              # FastAPI launcher app
├── project_scanner.py   # Directory scanning logic
├── session_manager.py   # Docker container management
└── templates/
    └── index.html       # Simple project selector UI

# Modified files
./docker-compose.yml     # Add launcher service
./docs/architecture/     # V2 architecture docs
```

### **API Endpoints (Phase 1)**
```python
GET  /                           # Project selector UI
GET  /api/scan-projects          # Find projects with MCP configs
POST /api/launch-backend         # Start testing backend
GET  /api/sessions               # List active sessions
POST /api/sessions/{id}/stop     # Stop testing session
```

### **Testing Criteria**
- [ ] Launcher starts in < 5 seconds
- [ ] Can discover projects with `.mcp.json`
- [ ] Can launch backend with custom project mount
- [ ] Backend accessible on dynamic ports
- [ ] Session termination works correctly

---

## 📋 Phase 2: Enhanced Discovery (Week 1, Days 4-5)
**Goal**: Comprehensive configuration discovery and validation

### **Deliverables**
- [ ] **Project-Level Config Support**
  - [ ] `.mcp.json` parsing and validation
  - [ ] Alternative project config locations (`./configs/`, `./.mcp/`)
  - [ ] Config schema validation and error reporting

- [ ] **Multi-Source Discovery**
  - [ ] Priority-based config source selection
  - [ ] User config integration (`~/.claude.json`, `~/.gemini/`)
  - [ ] Custom path support for team configs

- [ ] **Improved Validation**
  - [ ] Server command availability checking
  - [ ] Environment variable validation
  - [ ] Dependency verification (node, python, uvx)

### **Technical Tasks**
```python
# Enhanced discovery logic
def discover_project_configs(project_path: str) -> List[ConfigSource]:
    """Discover all MCP config sources in priority order"""
    sources = []
    
    # Priority 1: Project-level configs
    sources.extend(scan_project_configs(project_path))
    
    # Priority 2: User-level configs (if selected)
    if include_user_configs:
        sources.extend(scan_user_configs())
    
    # Priority 3: Custom paths
    sources.extend(scan_custom_paths(custom_paths))
    
    return validate_and_rank(sources)
```

### **Configuration Schema**
```json
{
  "project_mcp_config": {
    "schema_version": "2.0",
    "servers": {...},
    "testing": {
      "scenarios": ["development", "staging"],
      "default_scenario": "development"
    },
    "metadata": {
      "name": "My MCP Project",
      "description": "Project-specific MCP configuration"
    }
  }
}
```

### **Testing Criteria**
- [ ] Discovers all config types correctly
- [ ] Validates server configurations
- [ ] Handles missing dependencies gracefully
- [ ] Priority ordering works correctly

---

## 📋 Phase 3: Advanced Features (Week 2, Days 1-4)
**Goal**: Production-ready features and multiple session support

### **Deliverables**
- [ ] **Multi-Session Support**
  - [ ] Concurrent testing sessions
  - [ ] Port management and allocation
  - [ ] Session isolation and resource tracking

- [ ] **Enhanced UI**
  - [ ] Rich project browser with previews
  - [ ] Config source visualization
  - [ ] Real-time session status dashboard
  - [ ] Session logs and monitoring

- [ ] **Team Collaboration Features**
  - [ ] Shared config repositories
  - [ ] Team workspace support
  - [ ] Configuration templates
  - [ ] Import/export functionality

### **Technical Tasks**
```python
# Advanced session management
class SessionManager:
    def __init__(self):
        self.active_sessions = {}
        self.port_allocator = PortAllocator(8095, 8999)
    
    async def launch_session(self, config: LaunchConfig) -> Session:
        # Port allocation
        ports = await self.port_allocator.allocate_range(2)
        
        # Resource limits
        limits = ResourceLimits(
            memory="512MB",
            cpu="0.5",
            timeout="1h"
        )
        
        # Launch with monitoring
        session = await self.docker_launcher.create_session(
            config, ports, limits
        )
        
        return session
```

### **UI Enhancements**
- [ ] Project thumbnails and descriptions
- [ ] Config source tree view
- [ ] Session activity monitoring
- [ ] Log streaming interface

### **Testing Criteria**
- [ ] Can run 3+ concurrent sessions
- [ ] Sessions are properly isolated
- [ ] Resource usage is reasonable
- [ ] UI is responsive and intuitive

---

## 📋 Phase 4: Production Ready (Week 2-3, Days 5-7+)
**Goal**: Polish, security, and production deployment features

### **Deliverables**
- [ ] **Security & Compliance**
  - [ ] Input validation and sanitization
  - [ ] Path traversal protection
  - [ ] Resource limits and monitoring
  - [ ] Audit logging

- [ ] **Performance & Reliability**
  - [ ] Resource cleanup and management
  - [ ] Error handling and recovery
  - [ ] Performance monitoring
  - [ ] Graceful degradation

- [ ] **Documentation & Deployment**
  - [ ] Complete API documentation
  - [ ] User guide with examples
  - [ ] CI/CD integration guide
  - [ ] Production deployment instructions

### **Security Features**
```python
# Security validation
class SecurityValidator:
    def validate_project_path(self, path: str) -> bool:
        # Prevent path traversal
        normalized = os.path.normpath(path)
        if '..' in normalized:
            raise SecurityError("Path traversal detected")
        
        # Validate permissions
        if not self.check_read_permissions(path):
            raise SecurityError("Insufficient permissions")
        
        return True
    
    def validate_config_content(self, config: dict) -> dict:
        # Sanitize configuration
        return sanitize_config(config)
```

### **Production Deployment**
```yaml
# docker-compose.prod.yml
services:
  mcp-launcher:
    image: mcp-launcher:v2.0
    ports:
      - "8094:8094"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./projects:/projects:ro
    environment:
      - MAX_SESSIONS=10
      - SESSION_TIMEOUT=3600
      - RESOURCE_LIMITS=enabled
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
```

### **Testing Criteria**
- [ ] Security audit passes
- [ ] Performance benchmarks met
- [ ] Documentation is complete
- [ ] Ready for production deployment

---

## 🚀 Deployment Strategy

### **Development Environment**
```bash
# Clone and setup
git clone <repo>
cd MCP_Testing_Tools
git checkout feature/v2-dynamic-launcher

# Development mode
docker-compose -f docker-compose.dev.yml up
```

### **Staging Environment**
```bash
# Staging deployment
docker-compose -f docker-compose.staging.yml up -d

# Run integration tests
./scripts/test-integration.sh
```

### **Production Environment**
```bash
# Production deployment
docker-compose -f docker-compose.prod.yml up -d

# Health checks
./scripts/health-check.sh
```

---

## 📊 Success Metrics

### **Technical Metrics**
- **Startup Time**: Launcher < 5s, Backend < 15s
- **Resource Usage**: < 100MB RAM per session
- **Concurrent Sessions**: Support 5+ simultaneous sessions
- **Uptime**: > 99% availability in production

### **User Experience Metrics**
- **Setup Time**: Project to testing < 2 minutes
- **Config Discovery**: 100% accuracy for standard setups
- **Error Rate**: < 1% session launch failures
- **Documentation**: Complete API and user documentation

### **Adoption Metrics**
- **Team Usage**: Easy sharing of project configurations
- **CI Integration**: Automated testing pipeline support
- **Community**: External contributions and feedback
- **Extensibility**: Plugin/extension development

---

## 🔄 Risk Mitigation

### **Technical Risks**
- **Docker Socket Access**: Implement security controls
- **Resource Exhaustion**: Add session limits and monitoring
- **Port Conflicts**: Implement dynamic port allocation
- **Config Validation**: Comprehensive schema validation

### **User Experience Risks**
- **Complexity**: Keep launcher interface simple
- **Performance**: Optimize for fast startup and operation
- **Compatibility**: Support multiple MCP config formats
- **Documentation**: Provide clear examples and guides

### **Project Risks**
- **Scope Creep**: Focus on core functionality first
- **Breaking Changes**: Maintain backward compatibility
- **Team Coordination**: Clear task assignment and communication
- **Testing**: Comprehensive test coverage

---

This roadmap provides a clear path from the current fixed-config architecture to a flexible, project-aware testing platform that will significantly improve the developer experience for MCP testing.