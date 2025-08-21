#!/bin/bash
# DevOps Paradise - Serena Quality Container Startup Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log() {
    echo -e "${CYAN}[$(date +'%H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

banner() {
    echo -e "${PURPLE}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                    🌉 DevOps Paradise - Serena Quality 🚀                    ║"
    echo "║                   Semantic Analysis + Quality Assurance                     ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Display banner
banner

# Validate required environment variables
log "Validating environment configuration..."

if [[ -z "$CLIENT_ID" ]]; then
    error "CLIENT_ID environment variable is required"
fi

if [[ -z "$WORKSPACE_PATH" ]]; then
    error "WORKSPACE_PATH environment variable is required"
fi

if [[ ! -d "$WORKSPACE_PATH" ]]; then
    error "Workspace directory does not exist: $WORKSPACE_PATH"
fi

SERENA_PORT=${SERENA_PORT:-24282}
DASHBOARD_PORT=${DASHBOARD_PORT:-8000}
QUALITY_PROFILE=${QUALITY_PROFILE:-comprehensive}

success "Environment validation passed"
log "Client ID: $CLIENT_ID"
log "Workspace: $WORKSPACE_PATH"
log "Quality Profile: $QUALITY_PROFILE"
log "Serena Port: $SERENA_PORT"
log "Dashboard Port: $DASHBOARD_PORT"

# Create client-specific directories
log "Setting up client workspace..."
mkdir -p /app/reports/$CLIENT_ID
mkdir -p /app/logs/$CLIENT_ID
mkdir -p /app/configs/$CLIENT_ID

# Generate client-specific configuration
log "Generating client configuration..."
cat > /app/configs/$CLIENT_ID/serena_config.json <<EOF
{
    "client_id": "$CLIENT_ID",
    "workspace_path": "$WORKSPACE_PATH",
    "quality_profile": "$QUALITY_PROFILE",
    "ports": {
        "serena": $SERENA_PORT,
        "dashboard": $DASHBOARD_PORT
    },
    "analysis": {
        "semantic_analysis": true,
        "code_quality": true,
        "security_scanning": true,
        "performance_testing": true,
        "test_coverage": true
    },
    "tools": {
        "python": {
            "linting": ["pylint", "flake8"],
            "formatting": ["black", "isort"],
            "testing": ["pytest"],
            "type_checking": ["mypy"],
            "security": ["bandit", "safety"]
        },
        "javascript": {
            "linting": ["eslint"],
            "formatting": ["prettier"],
            "testing": ["jest", "playwright"],
            "performance": ["lighthouse", "clinic"]
        },
        "api_testing": ["newman"],
        "browsers": ["chromium", "firefox", "webkit"]
    }
}
EOF

success "Client configuration generated"

# Start Serena MCP server
log "Starting Serena MCP server..."

# Export Serena configuration
export SERENA_CONFIG_PATH="/app/configs/$CLIENT_ID/serena_config.json"
export SERENA_WORKSPACE="$WORKSPACE_PATH"
export SERENA_CLIENT_ID="$CLIENT_ID"

# Start Serena in background
uvx --python python3.11 run serena \
    --port $SERENA_PORT \
    --workspace "$WORKSPACE_PATH" \
    --host 0.0.0.0 \
    --log-level INFO \
    --enable-dashboard \
    --dashboard-port $DASHBOARD_PORT &

SERENA_PID=$!
echo $SERENA_PID > /app/serena.pid

# Wait for Serena to start
log "Waiting for Serena to initialize..."
max_attempts=30
attempt=1

while [[ $attempt -le $max_attempts ]]; do
    if curl -s -f "http://localhost:$SERENA_PORT/health" > /dev/null 2>&1; then
        success "Serena MCP server is ready"
        break
    fi
    
    if ! kill -0 $SERENA_PID 2>/dev/null; then
        error "Serena process died during startup"
    fi
    
    log "Attempt $attempt/$max_attempts - Serena not ready, waiting..."
    sleep 2
    ((attempt++))
done

if [[ $attempt -gt $max_attempts ]]; then
    error "Serena failed to start after $max_attempts attempts"
fi

# Start Quality Orchestrator
log "Starting Quality Orchestrator..."
python3 /app/quality_orchestrator.py \
    --client-id "$CLIENT_ID" \
    --workspace "$WORKSPACE_PATH" \
    --config "/app/configs/$CLIENT_ID/serena_config.json" \
    --log-level INFO &

ORCHESTRATOR_PID=$!
echo $ORCHESTRATOR_PID > /app/orchestrator.pid

# Wait for Quality Orchestrator to be ready
log "Waiting for Quality Orchestrator..."
sleep 5

if ! kill -0 $ORCHESTRATOR_PID 2>/dev/null; then
    error "Quality Orchestrator failed to start"
fi

success "Quality Orchestrator is ready"

# Display startup summary
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    🎉 DevOps Paradise Quality Ready! 🚀                     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}🔍 Serena MCP:${NC} http://localhost:$SERENA_PORT"
echo -e "${CYAN}📊 Dashboard:${NC} http://localhost:$DASHBOARD_PORT"
echo -e "${CYAN}👤 Client ID:${NC} $CLIENT_ID"
echo -e "${CYAN}📁 Workspace:${NC} $WORKSPACE_PATH"
echo -e "${CYAN}🎯 Profile:${NC} $QUALITY_PROFILE"
echo ""
echo -e "${YELLOW}Available Quality Tools:${NC}"
echo "• Semantic code analysis with Serena intelligence"
echo "• Python: pylint, flake8, black, isort, pytest, mypy, bandit"
echo "• JavaScript: eslint, prettier, jest, playwright, lighthouse"
echo "• API testing with Newman/Postman collections"
echo "• Performance analysis and optimization"
echo "• Security vulnerability scanning"
echo "• Comprehensive test coverage reporting"
echo ""

# Monitor processes and handle shutdown gracefully
cleanup() {
    log "Shutting down services..."
    
    if [[ -f /app/orchestrator.pid ]]; then
        kill $(cat /app/orchestrator.pid) 2>/dev/null || true
        rm -f /app/orchestrator.pid
    fi
    
    if [[ -f /app/serena.pid ]]; then
        kill $(cat /app/serena.pid) 2>/dev/null || true
        rm -f /app/serena.pid
    fi
    
    success "Services stopped"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Keep the container running and monitor processes
log "DevOps Paradise Quality container is running..."
log "Press Ctrl+C to stop"

while true; do
    # Check if Serena is still running
    if ! kill -0 $SERENA_PID 2>/dev/null; then
        warning "Serena process died, attempting restart..."
        
        uvx --python python3.11 run serena \
            --port $SERENA_PORT \
            --workspace "$WORKSPACE_PATH" \
            --host 0.0.0.0 \
            --log-level INFO \
            --enable-dashboard \
            --dashboard-port $DASHBOARD_PORT &
        
        SERENA_PID=$!
        echo $SERENA_PID > /app/serena.pid
    fi
    
    # Check if Quality Orchestrator is still running
    if ! kill -0 $ORCHESTRATOR_PID 2>/dev/null; then
        warning "Quality Orchestrator died, attempting restart..."
        
        python3 /app/quality_orchestrator.py \
            --client-id "$CLIENT_ID" \
            --workspace "$WORKSPACE_PATH" \
            --config "/app/configs/$CLIENT_ID/serena_config.json" \
            --log-level INFO &
        
        ORCHESTRATOR_PID=$!
        echo $ORCHESTRATOR_PID > /app/orchestrator.pid
    fi
    
    sleep 30
done