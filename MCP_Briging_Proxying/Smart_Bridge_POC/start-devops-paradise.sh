#!/bin/bash
# DevOps Paradise - One-Command Client Setup
# Provisions complete quality assurance environment for development teams

set -e

# ============================================================================
# Configuration & Defaults
# ============================================================================

CLIENT_NAME=${1:-"$(whoami)-$(date +%s)"}
WORKSPACE=${2:-"$(pwd)"}
QUALITY_PROFILE=${3:-"comprehensive"}
BRIDGE_HOST=${BRIDGE_HOST:-"localhost"}
BRIDGE_PORT=${BRIDGE_PORT:-"8100"}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ============================================================================
# Helper Functions
# ============================================================================

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

progress() {
    echo -e "${BLUE}🔄 $1${NC}"
}

banner() {
    echo -e "${PURPLE}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                           🌉 DevOps Paradise Bridge 🚀                       ║"
    echo "║                     Complete Quality & Testing Platform                      ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_requirements() {
    log "Checking system requirements..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is required but not installed. Please install Docker first."
    fi
    
    # Check curl for API calls
    if ! command -v curl &> /dev/null; then
        error "curl is required but not installed."
    fi
    
    # Check jq for JSON parsing
    if ! command -v jq &> /dev/null; then
        warning "jq not found - will use basic JSON parsing"
        JQ_AVAILABLE=false
    else
        JQ_AVAILABLE=true
    fi
    
    success "System requirements check passed"
}

validate_workspace() {
    log "Validating workspace: $WORKSPACE"
    
    # Check if directory exists
    if [[ ! -d "$WORKSPACE" ]]; then
        error "Workspace directory does not exist: $WORKSPACE"
    fi
    
    # Check if directory is readable/writable
    if [[ ! -r "$WORKSPACE" ]] || [[ ! -w "$WORKSPACE" ]]; then
        error "Workspace directory is not readable/writable: $WORKSPACE"
    fi
    
    # Convert to absolute path
    WORKSPACE=$(realpath "$WORKSPACE")
    
    success "Workspace validated: $WORKSPACE"
}

check_bridge_health() {
    log "Checking DevOps Paradise Bridge health..."
    
    local max_attempts=5
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -s -f "http://$BRIDGE_HOST:$BRIDGE_PORT/health" > /dev/null 2>&1; then
            success "Bridge is healthy and ready"
            return 0
        fi
        
        progress "Attempt $attempt/$max_attempts - Bridge not ready, waiting..."
        sleep 2
        ((attempt++))
    done
    
    error "Bridge health check failed after $max_attempts attempts"
}

register_client() {
    log "Registering client with DevOps Paradise Bridge..."
    
    # Prepare registration payload
    local payload=$(cat <<EOF
{
    "client_id": "$CLIENT_NAME",
    "workspace_path": "$WORKSPACE",
    "quality_profile": "$QUALITY_PROFILE"
}
EOF
)
    
    # Make registration request
    local response
    if ! response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "http://$BRIDGE_HOST:$BRIDGE_PORT/clients/register" 2>/dev/null); then
        error "Failed to connect to DevOps Paradise Bridge"
    fi
    
    # Parse response
    if [[ $JQ_AVAILABLE == true ]]; then
        CLIENT_ID=$(echo "$response" | jq -r '.client_id')
        BRIDGE_CLIENT_PORT=$(echo "$response" | jq -r '.bridge_port')
        DASHBOARD_PORT=$(echo "$response" | jq -r '.dashboard_port')
        DASHBOARD_URL=$(echo "$response" | jq -r '.dashboard_url')
        MCP_SSE_URL=$(echo "$response" | jq -r '.mcp_sse_url')
        STATUS=$(echo "$response" | jq -r '.status')
    else
        # Basic JSON parsing without jq
        CLIENT_ID=$(echo "$response" | grep -o '"client_id":"[^"]*"' | cut -d'"' -f4)
        BRIDGE_CLIENT_PORT=$(echo "$response" | grep -o '"bridge_port":[0-9]*' | cut -d':' -f2)
        DASHBOARD_PORT=$(echo "$response" | grep -o '"dashboard_port":[0-9]*' | cut -d':' -f2)
        STATUS=$(echo "$response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        DASHBOARD_URL="http://localhost:$DASHBOARD_PORT/dashboard"
        MCP_SSE_URL="http://localhost:$BRIDGE_CLIENT_PORT/sse"
    fi
    
    if [[ "$STATUS" != "ready" ]]; then
        error "Client registration failed: $response"
    fi
    
    success "Client registered successfully"
    log "Client ID: $CLIENT_ID"
    log "Bridge Port: $BRIDGE_CLIENT_PORT"
    log "Dashboard Port: $DASHBOARD_PORT"
}

wait_for_services() {
    log "Waiting for services to initialize..."
    
    local max_wait=120  # 2 minutes
    local wait_time=0
    
    progress "Waiting for Serena quality container to be ready..."
    
    while [[ $wait_time -lt $max_wait ]]; do
        # Check if dashboard is responding
        if curl -s -f "$DASHBOARD_URL" > /dev/null 2>&1; then
            success "Services are ready!"
            return 0
        fi
        
        sleep 5
        wait_time=$((wait_time + 5))
        progress "Still waiting... (${wait_time}s/${max_wait}s)"
    done
    
    warning "Services took longer than expected to start, but continuing..."
}

generate_mcp_config() {
    log "Generating MCP configuration..."
    
    # Create comprehensive MCP configuration
    cat > ".devops-paradise-config.json" <<EOF
{
    "client_info": {
        "client_name": "$CLIENT_NAME",
        "workspace": "$WORKSPACE",
        "quality_profile": "$QUALITY_PROFILE",
        "registered_at": "$(date -Iseconds)"
    },
    "endpoints": {
        "bridge_port": $BRIDGE_CLIENT_PORT,
        "dashboard_port": $DASHBOARD_PORT,
        "dashboard_url": "$DASHBOARD_URL",
        "mcp_sse_url": "$MCP_SSE_URL"
    },
    "mcp_config": {
        "mcpServers": {
            "devops-paradise": {
                "type": "sse",
                "url": "$MCP_SSE_URL",
                "description": "🌉 DevOps Paradise - Complete quality assurance and testing platform with semantic code analysis",
                "capabilities": [
                    "semantic_code_analysis",
                    "automated_testing",
                    "quality_assurance",
                    "performance_analysis",
                    "security_scanning",
                    "e2e_testing",
                    "api_testing",
                    "linting_integration",
                    "coverage_reporting",
                    "quality_trends",
                    "intelligent_orchestration"
                ],
                "use_cases": [
                    "Run comprehensive code quality analysis across multiple languages",
                    "Execute intelligent testing pipeline: unit → integration → e2e → api tests",
                    "Generate security vulnerability reports for dependencies and code",
                    "Perform automated performance analysis with Lighthouse and custom metrics",
                    "Create quality trend reports and AI-powered recommendations",
                    "Integrate with CI/CD pipelines for quality gates and automation",
                    "Provide real-time quality feedback during development",
                    "Generate compliance reports for code quality standards",
                    "Optimize test execution with semantic change detection"
                ],
                "testing_capabilities": [
                    "Unit testing with pytest, jest, mocha",
                    "E2E testing with Playwright (headless browsers)",
                    "API testing with Newman/Postman collections",
                    "Visual regression testing with screenshot comparison",
                    "Performance testing with Lighthouse and custom metrics",
                    "Load testing integration with autocannon and clinic.js"
                ],
                "quality_tools": [
                    "ESLint, Pylint, TSLint for static analysis",
                    "Black, Prettier for code formatting",
                    "Bandit, Safety for security scanning",
                    "Coverage.py, Istanbul for coverage reporting",
                    "Lighthouse for performance auditing",
                    "Serena semantic analysis for intelligent code insights"
                ],
                "best_for": "When you need enterprise-grade automated quality assurance, intelligent testing orchestration, or comprehensive code analysis across multiple languages and frameworks"
            }
        }
    },
    "quick_start": {
        "claude_code_integration": [
            "1. Copy the 'mcp_config' section above",
            "2. Add it to your Claude Code MCP settings",
            "3. Restart Claude Code",
            "4. Access tools via: mcp__devops_paradise__*"
        ],
        "dashboard_access": "Open $DASHBOARD_URL in your browser",
        "api_access": "Use bridge management API at http://$BRIDGE_HOST:$BRIDGE_PORT"
    }
}
EOF
    
    success "MCP configuration saved to: .devops-paradise-config.json"
}

show_summary() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                          🎉 DevOps Paradise Ready! 🚀                        ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}📊 Quality Dashboard:${NC} $DASHBOARD_URL"
    echo -e "${CYAN}🌉 MCP Bridge:${NC} $MCP_SSE_URL"
    echo -e "${CYAN}📋 Configuration:${NC} .devops-paradise-config.json"
    echo -e "${CYAN}👤 Client ID:${NC} $CLIENT_ID"
    echo ""
    echo -e "${YELLOW}🔧 To use with Claude Code:${NC}"
    echo "1. Copy the MCP configuration from .devops-paradise-config.json"
    echo "2. Add it to your Claude Code MCP settings"
    echo "3. Restart Claude Code"
    echo "4. Start using quality tools: mcp__devops_paradise__*"
    echo ""
    echo -e "${YELLOW}🎯 Available Capabilities:${NC}"
    echo "• Semantic code analysis with Serena intelligence"
    echo "• Comprehensive testing: Unit, Integration, E2E, API"
    echo "• Security scanning and vulnerability assessment"
    echo "• Performance analysis with Lighthouse"
    echo "• Quality trends and AI-powered recommendations"
    echo "• Intelligent test orchestration based on code changes"
    echo ""
    echo -e "${YELLOW}📈 Management Commands:${NC}"
    echo "• View client status: curl http://$BRIDGE_HOST:$BRIDGE_PORT/clients/$CLIENT_ID/status"
    echo "• List all clients: curl http://$BRIDGE_HOST:$BRIDGE_PORT/clients"
    echo "• Unregister client: curl -X DELETE http://$BRIDGE_HOST:$BRIDGE_PORT/clients/$CLIENT_ID"
    echo ""
    echo -e "${GREEN}Happy coding in your DevOps Paradise! 🌴✨${NC}"
}

cleanup_on_error() {
    if [[ -n "$CLIENT_ID" ]]; then
        warning "Cleaning up due to error..."
        curl -s -X DELETE "http://$BRIDGE_HOST:$BRIDGE_PORT/clients/$CLIENT_ID" > /dev/null 2>&1 || true
    fi
}

# ============================================================================
# Main Execution
# ============================================================================

main() {
    # Set up error handling
    trap cleanup_on_error ERR
    
    # Show banner
    banner
    
    log "Starting DevOps Paradise setup for client: $CLIENT_NAME"
    log "Workspace: $WORKSPACE"
    log "Quality Profile: $QUALITY_PROFILE"
    log "Bridge: $BRIDGE_HOST:$BRIDGE_PORT"
    
    # Pre-flight checks
    check_requirements
    validate_workspace
    check_bridge_health
    
    # Register with bridge
    register_client
    
    # Wait for services
    wait_for_services
    
    # Generate configuration
    generate_mcp_config
    
    # Show summary
    show_summary
    
    success "DevOps Paradise setup completed successfully!"
}

# ============================================================================
# Script Entry Point
# ============================================================================

# Check for help flag
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    echo "DevOps Paradise - One-Command Setup"
    echo ""
    echo "Usage: $0 [CLIENT_NAME] [WORKSPACE] [QUALITY_PROFILE]"
    echo ""
    echo "Arguments:"
    echo "  CLIENT_NAME      Unique identifier for this client (default: auto-generated)"
    echo "  WORKSPACE        Path to project workspace (default: current directory)"
    echo "  QUALITY_PROFILE  Quality analysis profile (default: comprehensive)"
    echo ""
    echo "Environment Variables:"
    echo "  BRIDGE_HOST      Bridge server host (default: localhost)"
    echo "  BRIDGE_PORT      Bridge server port (default: 8100)"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Use defaults"
    echo "  $0 my-project                        # Custom client name"
    echo "  $0 my-project /path/to/workspace     # Custom workspace"
    echo "  $0 team-alpha ./project comprehensive # Full customization"
    echo ""
    echo "For more information, visit: https://github.com/your-org/devops-paradise"
    exit 0
fi

# Run main function
main "$@"