# V2 Dynamic Launcher Architecture - Pull Request

## 🎯 **Problem Statement**

The current MCP Testing Suite has a critical architectural limitation: **fixed Docker volume mounts** that lock users into predefined configuration locations. This prevents:

- ❌ **Project-specific testing** - Can't test different project's MCP configurations
- ❌ **Team collaboration** - No way to share project-specific MCP setups
- ❌ **Flexible development** - Must restart containers to change config sources
- ❌ **CI/CD integration** - Limited to user-level configurations only

## 🚀 **Proposed Solution**

Transform the MCP Testing Suite from a **fixed-config testing tool** into a **dynamic, project-aware testing platform** with:

### **Two-Stage Architecture**

**Stage 1: Project Launcher** (Lightweight UI)
- Scan for projects with MCP configurations
- Allow users to select project directory + config source
- Dynamically launch testing backend with custom mounts

**Stage 2: Dynamic Testing Backend** (Session-specific)
- Started with exact project/config combination
- Isolated testing environment per session
- Full MCP testing capabilities with project context

### **Configuration Discovery Hierarchy**
```
Priority 1: Custom location (user-specified path)
Priority 2: Project-level (.mcp.json, ./configs/)  ← NEW!
Priority 3: User-level (~/.claude.json, ~/.gemini/)
Priority 4: Built-in test servers
```

## 📋 **What This PR Contains**

### **Documentation Added**
- **[V2 Architecture Specification](../architecture/v2-dynamic-launcher.md)** - Complete technical design
- **[Development Roadmap](v2-roadmap.md)** - 4-phase implementation plan
- **Updated README** - Reflects new architecture direction

### **Key Features Planned**
1. **Dynamic Project Selection** - Choose any project directory
2. **Project-Level Configs** - Support for `.mcp.json` in projects
3. **Custom Config Locations** - Test any config file/directory
4. **Multi-Session Support** - Test multiple projects simultaneously
5. **Team Collaboration** - Share project-specific MCP setups
6. **CI/CD Ready** - Scriptable for automated testing

## 🏗️ **Implementation Plan**

### **Phase 1: Foundation** (Week 1, Days 1-3)
- Create lightweight project launcher
- Basic dynamic backend launching
- Simple project/config selection

### **Phase 2: Enhanced Discovery** (Week 1, Days 4-5)  
- Project-level config support (`.mcp.json`)
- Multi-source discovery and validation
- Priority-based config selection

### **Phase 3: Advanced Features** (Week 2, Days 1-4)
- Multi-session support
- Enhanced UI with project browser
- Team collaboration features

### **Phase 4: Production Ready** (Week 2-3, Days 5-7+)
- Security hardening
- Performance optimization
- Complete documentation

## 🎯 **Expected Benefits**

### **For Individual Developers**
✅ **Project Isolation** - Each project's MCP setup is independent  
✅ **Experiment Safely** - Test configs without affecting global setup  
✅ **Version Control** - Project configs can be committed to git  
✅ **Multiple Projects** - Test different projects simultaneously  

### **For Teams**
✅ **Shared Configurations** - Team members use identical MCP setups  
✅ **Reproducible Testing** - Same test environment across team  
✅ **CI/CD Integration** - Automated testing with project configs  
✅ **Onboarding** - New team members get working MCP setup instantly  

### **For MCP Ecosystem**
✅ **Wider Adoption** - Easier to test and develop MCP servers  
✅ **Best Practices** - Encourages project-level MCP configuration  
✅ **Community Growth** - Better tools → more MCP development  

## 🔄 **Migration Strategy**

### **Backward Compatibility**
- Current V1 architecture remains functional
- Existing docker-compose setup continues to work
- Users can migrate to V2 gradually

### **Migration Path**
1. **V1 (Current)**: Fixed mounts, user-level configs
2. **V1.5 (Transition)**: Both architectures available
3. **V2 (Target)**: Dynamic launcher becomes primary interface

## 📊 **Success Criteria**

### **Technical Metrics**
- **Startup Time**: Launcher < 5s, Backend < 15s
- **Resource Usage**: < 100MB RAM per session
- **Concurrent Sessions**: Support 5+ simultaneous sessions
- **Config Discovery**: 100% accuracy for standard setups

### **User Experience Metrics**
- **Setup Time**: Project to testing < 2 minutes
- **Error Rate**: < 1% session launch failures
- **Team Adoption**: Easy shared configuration setup

## 🤝 **Call for Collaboration**

This architectural evolution will significantly improve the MCP Testing Suite. We're looking for:

### **Contributors Welcome**
- **Frontend developers** - React/UI work for project launcher
- **Backend developers** - FastAPI/Docker container management
- **DevOps engineers** - CI/CD integration and deployment
- **Documentation writers** - User guides and examples
- **Testers** - Real-world usage scenarios and feedback

### **Areas for Input**
- **Configuration schema** - What should `.mcp.json` look like?
- **UI/UX design** - How should project selection work?
- **Security considerations** - Docker socket access, path validation
- **Performance requirements** - Resource limits, session management

## 📝 **Next Steps**

1. **Review and feedback** on this architecture design
2. **Approve implementation approach** and timeline
3. **Begin Phase 1 development** - Basic launcher functionality
4. **Coordinate contributions** from community members

---

**This PR contains only documentation** - no breaking changes to existing functionality. The goal is to align on the architecture direction before beginning implementation.

Ready to transform MCP testing from fixed-config limitation to dynamic project platform! 🚀