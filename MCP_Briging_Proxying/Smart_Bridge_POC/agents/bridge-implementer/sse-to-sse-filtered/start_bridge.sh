#!/bin/bash
# Startup script for Filtered SSE-to-SSE MCP Bridge

set -e

# Configuration
DEFAULT_SSE_URL="http://localhost:3000/sse"
DEFAULT_PORT=8201
DEFAULT_CONFIG="config/default_filters.json"
DEFAULT_LOG_LEVEL="INFO"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_usage() {
    cat << EOF
Filtered SSE-to-SSE MCP Bridge Startup Script

Usage: $0 [options]

Options:
    --sse_url URL       Upstream SSE MCP server URL (default: $DEFAULT_SSE_URL)
    --api_key KEY       API key for upstream server
    --port PORT         Port to run on (default: $DEFAULT_PORT)
    --config FILE       Filter configuration file (default: $DEFAULT_CONFIG)
    --log_level LEVEL   Log level: DEBUG, INFO, WARNING, ERROR (default: $DEFAULT_LOG_LEVEL)
    --log_location DIR  Directory for log files (optional)
    --strict            Use strict filtering configuration
    --permissive        Use permissive filtering configuration
    --help              Show this help message

Examples:
    # Basic startup with Firecrawl
    $0 --api_key fc-your-key

    # Strict filtering mode
    $0 --api_key fc-your-key --strict

    # Custom configuration
    $0 --sse_url http://remote:3000/sse --config my_filters.json

    # Debug mode with logging
    $0 --api_key fc-your-key --log_level DEBUG --log_location ./logs

Environment Variables:
    FIRECRAWL_API_KEY   Default API key if --api_key not provided
    BRIDGE_AUTH_MODE    Authentication mode (none, bearer, apikey)
    BRIDGE_AUTH_SECRET  Authentication secret
EOF
}

check_dependencies() {
    log_info "Checking dependencies..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required but not installed"
        exit 1
    fi
    
    # Check required Python packages
    python3 -c "import fastapi, aiohttp, uvicorn" 2>/dev/null || {
        log_error "Required Python packages not installed. Run: pip install -r requirements.txt"
        exit 1
    }
    
    log_info "✓ Dependencies check passed"
}

check_upstream_server() {
    local sse_url="$1"
    log_info "Checking upstream SSE server at $sse_url..."
    
    # Extract base URL for health check
    local base_url=$(echo "$sse_url" | sed 's|/sse$||')
    
    # Try to connect to the server
    if curl -s --connect-timeout 5 "$base_url" > /dev/null 2>&1; then
        log_info "✓ Upstream server is reachable"
    else
        log_warn "⚠ Cannot reach upstream server at $base_url"
        log_warn "Make sure the upstream SSE MCP server is running"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

start_firecrawl_instructions() {
    cat << EOF

${YELLOW}To start Firecrawl in SSE mode:${NC}

1. In a separate terminal, run:
   ${GREEN}SSE_LOCAL=true FIRECRAWL_API_KEY=fc-your-key npx -y firecrawl-mcp${NC}

2. Wait for it to show "SSE server started on port 3000"

3. Then run this script again with your API key:
   ${GREEN}$0 --api_key fc-your-key${NC}

EOF
}

# Parse command line arguments
SSE_URL="$DEFAULT_SSE_URL"
API_KEY=""
PORT="$DEFAULT_PORT"
CONFIG_FILE="$DEFAULT_CONFIG"
LOG_LEVEL="$DEFAULT_LOG_LEVEL"
LOG_LOCATION=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --sse_url)
            SSE_URL="$2"
            shift 2
            ;;
        --api_key)
            API_KEY="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --log_level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        --log_location)
            LOG_LOCATION="$2"
            shift 2
            ;;
        --strict)
            CONFIG_FILE="config/strict_filters.json"
            shift
            ;;
        --permissive)
            CONFIG_FILE="config/permissive_filters.json"
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Use environment variable if API key not provided
if [[ -z "$API_KEY" && -n "$FIRECRAWL_API_KEY" ]]; then
    API_KEY="$FIRECRAWL_API_KEY"
fi

# Check if we're in the right directory
if [[ ! -f "src/filtered_bridge.py" ]]; then
    log_error "Please run this script from the sse-to-sse-filtered directory"
    exit 1
fi

# Main execution
log_info "Starting Filtered SSE-to-SSE MCP Bridge"
log_info "Configuration:"
log_info "  SSE URL: $SSE_URL"
log_info "  Port: $PORT"
log_info "  Config: $CONFIG_FILE"
log_info "  Log Level: $LOG_LEVEL"

# Check dependencies
check_dependencies

# Check if configuration file exists
if [[ ! -f "$CONFIG_FILE" ]]; then
    log_error "Configuration file not found: $CONFIG_FILE"
    log_info "Available configurations:"
    ls -la config/*.json 2>/dev/null || log_info "  No configuration files found in config/"
    exit 1
fi

# Check upstream server
check_upstream_server "$SSE_URL"

# Check if port is available
if netstat -an 2>/dev/null | grep -q ":$PORT "; then
    log_error "Port $PORT is already in use"
    log_info "Check if another bridge is running: ps aux | grep filtered_bridge"
    exit 1
fi

# Prepare command
CMD="PYTHONPATH=src python3 src/filtered_bridge.py --sse_url $SSE_URL --port $PORT --filter_config $CONFIG_FILE --log_level $LOG_LEVEL"

if [[ -n "$API_KEY" ]]; then
    CMD="$CMD --api_key $API_KEY"
fi

if [[ -n "$LOG_LOCATION" ]]; then
    CMD="$CMD --log_location $LOG_LOCATION"
    mkdir -p "$LOG_LOCATION"
fi

# Show startup information
log_info "Bridge will be available at: http://localhost:$PORT"
log_info "Health endpoint: http://localhost:$PORT/health"
log_info "SSE endpoint: http://localhost:$PORT/sse"

# Check for API key
if [[ -z "$API_KEY" && "$SSE_URL" == *"localhost"* ]]; then
    log_warn "No API key provided. If using Firecrawl, you may need --api_key"
fi

log_info "Starting bridge..."
log_info "Command: $CMD"

# Start the bridge
export PYTHONPATH=src
exec python3 src/filtered_bridge.py --sse_url "$SSE_URL" --port "$PORT" --filter_config "$CONFIG_FILE" --log_level "$LOG_LEVEL" ${API_KEY:+--api_key "$API_KEY"} ${LOG_LOCATION:+--log_location "$LOG_LOCATION"} ${LOG_PATTERN:+--log_pattern "$LOG_PATTERN"}