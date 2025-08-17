# Troubleshooting Guide 🔧

Having issues with your **MCP Debug Wizard**? Don't worry - this guide covers the most common problems and their solutions! 🧙‍♂️🔍

## 🚨 Quick Diagnostics

### Health Check Commands

```bash
# Check if containers are running
docker-compose ps

# Test all service endpoints
curl -f http://localhost:9090/ && echo "✅ Web Portal OK"
curl -f http://localhost:9091/ && echo "✅ Mock Genie OK"  
curl -f http://localhost:9092/ && echo "✅ Proxy Spy OK"

# Check container logs
docker-compose logs --tail=50
```

### Service Status Check

```bash
# Quick status of all services
for port in 9090 9091 9092; do
  if curl -s -f http://localhost:$port/ > /dev/null; then
    echo "✅ Port $port: OK"
  else
    echo "❌ Port $port: FAILED"
  fi
done
```

## 🔌 Port Conflicts

### Problem: "Port already in use"

**Symptoms:**
- `docker-compose up` fails with port binding errors
- Services won't start
- "Address already in use" errors

**Diagnosis:**
```bash
# Check what's using our ports
netstat -tulpn | grep :909[0-2]
# or
lsof -i :9090 -i :9091 -i :9092
```

**Solutions:**

#### Option 1: Stop Conflicting Services
```bash
# Find and stop the conflicting process
sudo kill $(lsof -t -i:9090)  # Replace with actual port
```

#### Option 2: Change Ports
Edit `docker-compose.yml`:
```yaml
ports:
  - "19090:9090"  # Change external port
  - "19091:9091"
  - "19092:9092"
```

Update your URLs to use the new ports (e.g., `http://localhost:19090`).

#### Option 3: Use Different Port Range
```bash
# Use completely different ports
sed -i 's/909/191/g' docker-compose.yml
sed -i 's/909/191/g' *.py
sed -i 's/909/191/g' start.sh
```

## 🐳 Container Issues

### Problem: Containers Won't Start

**Symptoms:**
- `docker-compose up` hangs or fails
- Container exits immediately
- "Failed to start" errors

**Diagnosis:**
```bash
# Check container status
docker-compose ps

# View container logs
docker-compose logs mcp-debug-wizard

# Check Docker daemon
docker info
```

**Solutions:**

#### Docker Daemon Issues
```bash
# Restart Docker daemon
sudo systemctl restart docker

# Or restart Docker Desktop (on Mac/Windows)
```

#### Permission Issues
```bash
# Fix Docker permissions (Linux)
sudo usermod -aG docker $USER
# Log out and back in

# Fix file permissions
chmod +x start.sh
sudo chown -R $USER:$USER .
```

#### Resource Issues
```bash
# Clean up Docker
docker system prune -a

# Free up disk space
docker volume prune
docker image prune -a
```

### Problem: Container Health Check Failing

**Symptoms:**
- Container shows as "unhealthy"
- Services accessible but marked unhealthy

**Diagnosis:**
```bash
# Check health status
docker-compose ps

# View health check logs
docker inspect mcp-debug-wizard | grep -A 10 Health
```

**Solutions:**
```bash
# Restart containers
docker-compose restart

# Rebuild with no cache
docker-compose build --no-cache
docker-compose up -d
```

## 🔗 Network & Connectivity

### Problem: Can't Access Web Portal

**Symptoms:**
- Browser shows "This site can't be reached"
- Connection refused errors
- Services appear to be running

**Diagnosis:**
```bash
# Test local connectivity
curl -v http://localhost:9090/

# Check if service is binding correctly
docker-compose exec mcp-debug-wizard netstat -tlnp | grep :9090

# Check container networking
docker network ls
docker network inspect mcp_testing_tools_mcp-net
```

**Solutions:**

#### Service Binding Issues
```bash
# Check if services are binding to 0.0.0.0
docker-compose logs mcp-debug-wizard | grep "Uvicorn running"

# Should see: "Uvicorn running on http://0.0.0.0:9090"
```

#### Firewall Issues
```bash
# Check firewall (Linux)
sudo ufw status
sudo ufw allow 9090:9092/tcp

# Check iptables
sudo iptables -L | grep 909
```

#### Browser Cache
```bash
# Clear browser cache or try
curl http://localhost:9090/

# Try different browser or incognito mode
```

### Problem: Services Can't Communicate

**Symptoms:**
- Web Portal can't reach Mock Genie or Proxy Spy
- Internal service errors

**Diagnosis:**
```bash
# Test internal connectivity
docker-compose exec mcp-debug-wizard curl http://localhost:9091/
docker-compose exec mcp-debug-wizard curl http://localhost:9092/

# Check network configuration
docker network inspect mcp_testing_tools_mcp-net
```

**Solutions:**
```bash
# Recreate network
docker-compose down
docker network prune
docker-compose up -d
```

## 📁 Volume Mount Issues

### Problem: Config Files Not Found

**Symptoms:**
- Auto-discovery finds no servers
- "Config file not found" errors
- Permission denied errors

**Diagnosis:**
```bash
# Check if config files exist on host
ls -la ~/.claude.json ~/.gemini/

# Check mounted files in container
docker-compose exec mcp-debug-wizard ls -la /mcp-configs/

# Test config discovery
docker-compose exec mcp-debug-wizard python config_discovery.py
```

**Solutions:**

#### Missing Config Files
```bash
# Create minimal test config
echo '{"mcpServers":{}}' > ~/.claude.json
mkdir -p ~/.gemini
echo '{"mcpServers":{}}' > ~/.gemini/mcp.json
```

#### Permission Issues
```bash
# Fix permissions
chmod 644 ~/.claude.json
chmod -R 755 ~/.gemini/

# Check SELinux (if applicable)
ls -Z ~/.claude.json
# If SELinux is causing issues:
sudo setsebool -P container_manage_cgroup 1
```

#### Mount Path Issues
Edit `docker-compose.yml` to use absolute paths:
```yaml
volumes:
  - /home/username/.claude.json:/mcp-configs/.claude.json:ro
  - /home/username/.gemini:/mcp-configs/.gemini:ro
```

### Problem: Workspace Files Not Accessible

**Symptoms:**
- Can't create/edit files in workspace
- "Permission denied" errors
- Tests fail due to file access

**Diagnosis:**
```bash
# Check workspace permissions
ls -la ./workspace/

# Test file creation in container
docker-compose exec mcp-debug-wizard touch /workspace/test.txt
docker-compose exec mcp-debug-wizard ls -la /workspace/
```

**Solutions:**
```bash
# Fix workspace permissions
sudo chown -R 1000:1000 ./workspace
chmod -R 755 ./workspace

# Create workspace if missing
mkdir -p ./workspace ./logs
```

## 🔄 MCP Communication

### Problem: MCP Servers Won't Start

**Symptoms:**
- Proxy Spy can't start MCP servers
- "Command not found" errors
- Process spawn failures

**Diagnosis:**
```bash
# Check if MCP tools are available in container
docker-compose exec mcp-debug-wizard which uvx
docker-compose exec mcp-debug-wizard uvx --version

# Test MCP server commands manually
docker-compose exec mcp-debug-wizard uvx mcp-server-filesystem --help
```

**Solutions:**

#### Missing MCP Tools
Add to `Dockerfile`:
```dockerfile
RUN pip install mcp
# or
RUN npm install -g @modelcontextprotocol/server-filesystem
```

#### Command Path Issues
```bash
# Check PATH in container
docker-compose exec mcp-debug-wizard echo $PATH

# Install missing tools
docker-compose exec mcp-debug-wizard pip install --user mcp-server-filesystem
```

### Problem: stdio Communication Failing

**Symptoms:**
- Proxy receives no response from MCP servers
- Timeout errors
- Broken pipe errors

**Diagnosis:**
```bash
# Test MCP server directly
echo '{"jsonrpc":"2.0","id":"1","method":"initialize","params":{}}' | uvx mcp-server-filesystem

# Check proxy logs
docker-compose logs mcp-proxy-spy | grep ERROR

# Test simple subprocess communication
docker-compose exec mcp-debug-wizard python -c "
import subprocess
proc = subprocess.Popen(['echo', 'test'], stdout=subprocess.PIPE)
print(proc.stdout.read())
"
```

**Solutions:**

#### Subprocess Issues
```bash
# Check container limits
docker stats

# Increase container resources in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 1G
      cpus: '0.5'
```

#### stdio Buffering
Add to Python code:
```python
proc = subprocess.Popen(
    command,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    bufsize=0,  # Unbuffered
    universal_newlines=False
)
```

## 🧞 Mock Server Issues

### Problem: Mock Responses Not Working

**Symptoms:**
- Mock server returns unexpected responses
- Tools not found errors
- JSON parsing errors

**Diagnosis:**
```bash
# Check mock server configuration
curl http://localhost:9091/debug/tools

# Test basic mock functionality
curl -X POST http://localhost:9091/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"test","method":"initialize"}'

# Check mock server logs
curl http://localhost:9091/debug/logs
```

**Solutions:**

#### Add Missing Mock Tools
```bash
# Add custom mock tool
curl -X POST http://localhost:9091/debug/tools \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test_tool",
    "description": "Test tool",
    "inputSchema": {"type": "object", "properties": {}}
  }'
```

#### Reset Mock Configuration
```bash
# Clear logs and restart
curl -X DELETE http://localhost:9091/debug/logs
docker-compose restart mcp-mock-genie
```

## 🔍 Advanced Debugging

### Enable Debug Logging

Edit `docker-compose.yml`:
```yaml
environment:
  - LOG_LEVEL=DEBUG
  - PYTHONUNBUFFERED=1
```

### Interactive Container Access

```bash
# Get shell access to debug
docker-compose exec mcp-debug-wizard bash

# Run Python interactively
docker-compose exec mcp-debug-wizard python

# Test components individually
docker-compose exec mcp-debug-wizard python mock_server.py
```

### Custom Debug Scripts

Create `debug.py`:
```python
#!/usr/bin/env python3
import requests
import json

# Test all endpoints
endpoints = [
    "http://localhost:9090/",
    "http://localhost:9091/", 
    "http://localhost:9092/"
]

for url in endpoints:
    try:
        r = requests.get(url, timeout=5)
        print(f"✅ {url}: {r.status_code}")
    except Exception as e:
        print(f"❌ {url}: {e}")
```

### Performance Debugging

```bash
# Monitor resource usage
docker stats

# Check service response times
time curl http://localhost:9090/api/discover-servers

# Monitor log file sizes
ls -lah ./logs/
```

## 🆘 When All Else Fails

### Nuclear Option: Complete Reset

```bash
# Stop everything
docker-compose down -v

# Remove all containers and images
docker system prune -a --volumes

# Remove project and re-clone
cd ..
rm -rf MCP_Testing_Tools
git clone https://github.com/llm-case-studies/MCP_Testing_Tools
cd MCP_Testing_Tools
./start.sh
```

### Minimal Test Setup

```bash
# Test with minimal configuration
echo '{"mcpServers":{}}' > ~/.claude.json
mkdir -p ./workspace ./logs

# Use alternative ports
sed -i 's/909/292/g' docker-compose.yml *.py start.sh

# Start with single service
docker-compose up mcp-debug-wizard
```

### Get Help

If you're still stuck:

1. **Check GitHub Issues**: [MCP Testing Tools Issues](https://github.com/llm-case-studies/MCP_Testing_Tools/issues)
2. **Create New Issue**: Include:
   - Operating system and Docker version
   - Complete error messages
   - Output of `docker-compose logs`
   - Steps to reproduce

3. **Community Discussion**: [GitHub Discussions](https://github.com/llm-case-studies/MCP_Testing_Tools/discussions)

---

**Remember**: The MCP Debug Wizard is here to help, not to cause stress! Most issues are simple configuration problems with easy fixes. 🧙‍♂️✨