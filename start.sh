#!/bin/bash
# MCP Testing Suite Startup Script

set -e

echo "🚀 Starting MCP Testing Suite..."

# Create necessary directories
mkdir -p workspace logs

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not available"
    echo "Please install Docker and try again"
    exit 1
fi

# Check if docker compose is available
if ! docker compose version &> /dev/null; then
    echo "❌ docker compose is not installed or not available"
    echo "Please install docker compose and try again"
    exit 1
fi

# Build the container
echo "🔨 Building MCP Testing container..."
docker compose build

# Start the services
echo "🏃 Starting MCP Testing services..."
docker compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Health check
echo "🔍 Checking service health..."
services=("http://localhost:8094" "http://localhost:8095" "http://localhost:8096")

for service in "${services[@]}"; do
    if curl -f "$service" > /dev/null 2>&1; then
        echo "✅ $service is healthy"
    else
        echo "⚠️  $service is not responding"
    fi
done

echo ""
echo "🎉 MCP Debug Wizard is ready! 🧙‍♂️✨"
echo ""
echo "📱 Web Portal:    http://localhost:8094"
echo "🧞 Mock Genie:    http://localhost:8095" 
echo "🕵️ Proxy Spy:     http://localhost:8096"
echo ""
echo "📁 Workspace:     ./workspace"
echo "📊 Logs:          ./logs"
echo ""
echo "To stop: docker compose down"
echo "To view logs: docker compose logs -f"
echo ""

# Test config discovery
echo "🔍 Testing configuration discovery..."
docker compose exec -T mcp-debug-wizard python config_discovery.py || echo "⚠️  Config discovery test failed"