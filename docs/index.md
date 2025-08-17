# MCP Debug Wizard Documentation 🧙‍♂️

Welcome to the complete documentation for the **MCP Debug Wizard** - your magical testing suite for Model Context Protocol (MCP) servers!

## 🎯 Quick Navigation

### 🚀 Getting Started
- [Quick Start Guide](guides/quick-start.md) - Get up and running in 5 minutes
- [Installation](guides/installation.md) - Detailed setup instructions
- [First Test](tutorials/first-test.md) - Your first MCP server test

### 🏗️ Architecture & Design
- [System Architecture](architecture/overview.md) - How everything fits together
- [Service Components](architecture/services.md) - Mock Genie, Proxy Spy, Web Portal
- [Container Design](architecture/containers.md) - Docker setup and networking
- [Security Model](architecture/security.md) - Safety and isolation

### 📚 User Guides
- [Web Portal Guide](guides/web-portal.md) - Using the main interface
- [Mock Server Testing](guides/mock-testing.md) - HTTP-based MCP simulation
- [Proxy Debugging](guides/proxy-debugging.md) - stdio communication interception
- [Configuration Discovery](guides/config-discovery.md) - Auto-finding MCP servers

### 🛠️ API Reference
- [Web Interface API](api/web-interface.md) - REST endpoints and WebSocket
- [Mock Server API](api/mock-server.md) - MCP protocol simulation
- [Proxy Server API](api/proxy-server.md) - Communication interception

### 📖 Tutorials
- [Testing Your First MCP Server](tutorials/first-test.md)
- [Debugging Communication Issues](tutorials/debugging-communication.md)
- [Creating Custom Test Suites](tutorials/custom-test-suites.md)
- [Adding Custom Filters](tutorials/custom-filters.md)
- [Performance Testing](tutorials/performance-testing.md)

### 🔧 Development
- [Contributing Guide](development/contributing.md) - How to contribute
- [Development Setup](development/setup.md) - Local development environment
- [Adding New Features](development/new-features.md) - Extension architecture
- [Testing Strategy](development/testing.md) - How we test the testing tools!

### 🆘 Troubleshooting
- [Common Issues](guides/troubleshooting.md) - Solutions to frequent problems
- [Port Conflicts](guides/troubleshooting.md#port-conflicts)
- [Container Issues](guides/troubleshooting.md#container-issues)
- [MCP Communication Problems](guides/troubleshooting.md#mcp-communication)

## 🎪 What is MCP Debug Wizard?

The **MCP Debug Wizard** is a comprehensive, containerized testing environment designed to make MCP server development and debugging magical! ✨

### 🔮 Three Magical Services

1. **🧞 Mock Genie (Port 9091)**
   - HTTP-based MCP protocol simulator
   - Configurable responses and scenarios
   - Perfect for testing client implementations

2. **🕵️ Proxy Spy (Port 9092)**
   - Intercepts stdio MCP communication
   - Real-time logging and filtering
   - Debug actual server implementations

3. **📱 Web Portal (Port 9090)**
   - Visual testing dashboard
   - Auto-discovery of MCP servers
   - Test suite management

### ✨ Key Features

- **🐳 Fully Containerized** - Isolated, reproducible environment
- **🔍 Auto-Discovery** - Finds MCP servers from Claude/Gemini configs
- **📊 Real-time Monitoring** - Live WebSocket communication logs
- **🎛️ Advanced Filtering** - Inject delays, errors, modify messages
- **🛡️ Security First** - Non-root containers, read-only mounts
- **🔄 stdio Compatible** - Full MCP protocol support
- **📈 Extensible** - Plugin architecture for custom features

## 🌟 Why Use MCP Debug Wizard?

### For MCP Server Developers
- **Validate Protocol Compliance** - Ensure your server follows MCP spec
- **Debug Communication Issues** - See exactly what's being sent/received
- **Performance Testing** - Measure response times and throughput
- **Error Handling** - Test how your server handles edge cases

### For MCP Client Developers
- **Mock Server Testing** - Test against predictable responses
- **Protocol Learning** - Understand MCP message flow
- **Integration Testing** - Validate client implementations

### For Organizations
- **Evaluation** - Test MCP servers before deployment
- **Quality Assurance** - Automated testing in CI/CD pipelines
- **Training** - Educational tool for teams learning MCP

## 🚀 Quick Start

```bash
# Clone and start
git clone https://github.com/llm-case-studies/MCP_Testing_Tools
cd MCP_Testing_Tools
chmod +x start.sh
./start.sh
```

Visit **http://localhost:9090** and start testing! 🎉

## 🤝 Community

- **GitHub Repository**: [llm-case-studies/MCP_Testing_Tools](https://github.com/llm-case-studies/MCP_Testing_Tools)
- **Issues & Feature Requests**: [GitHub Issues](https://github.com/llm-case-studies/MCP_Testing_Tools/issues)
- **Discussions**: [GitHub Discussions](https://github.com/llm-case-studies/MCP_Testing_Tools/discussions)

## 📄 License

MIT License - see [LICENSE](../LICENSE) file for details.

---

*Built with ❤️ for the MCP community*