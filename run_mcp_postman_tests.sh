#!/bin/bash
# Comprehensive test runner for MCP Postman functionality

echo "🧪 MCP Postman Test Suite"
echo "=========================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAILED_TESTS=0
TOTAL_TESTS=0

# Function to run a test and report results
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -e "${YELLOW}🔬 Running: $test_name${NC}"
    echo "Command: $test_command"
    echo ""
    
    if eval "$test_command"; then
        echo -e "${GREEN}✅ PASSED: $test_name${NC}"
    else
        echo -e "${RED}❌ FAILED: $test_name${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo ""
    echo "----------------------------------------"
    echo ""
}

echo "Installing test dependencies..."
pip3 install pytest requests fastapi httpx pytest-asyncio

echo ""
echo "Starting MCP Postman test execution..."
echo ""

# 1. Backend API Unit Tests
run_test "Backend API Unit Tests" "python3 -m pytest tests/test_mcp_postman_api.py -v"

# 2. Launcher Integration Tests  
run_test "Launcher Integration Tests" "python3 -m pytest launcher/tests/test_mcp_postman_integration.py -v"

# 3. E2E Tests
run_test "End-to-End Workflow Tests" "python3 test_mcp_postman_e2e.py"

# 4. Existing Launcher Tests (ensure we didn't break anything)
run_test "Existing Launcher Tests" "cd launcher && python3 -m pytest tests/ -v"

# Summary
echo "=========================================="
echo "🏁 MCP Postman Test Suite Complete"
echo "=========================================="
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL TESTS PASSED! ($TOTAL_TESTS/$TOTAL_TESTS)${NC}"
    echo ""
    echo "✅ MCP Postman functionality is ready for production!"
    echo ""
    echo "📋 Test Coverage:"
    echo "  • Backend API endpoints"
    echo "  • Request/response handling"  
    echo "  • History and collections management"
    echo "  • Launcher UI integration"
    echo "  • JavaScript functionality"
    echo "  • End-to-end workflow"
    echo "  • Error handling"
    echo "  • Responsive design"
    echo ""
    exit 0
else
    echo -e "${RED}💥 $FAILED_TESTS out of $TOTAL_TESTS tests FAILED${NC}"
    echo ""
    echo "❗ Please fix failing tests before deploying MCP Postman"
    echo ""
    echo "🔍 Common issues to check:"
    echo "  • Import paths and dependencies"
    echo "  • Port conflicts (8094, 8095)"
    echo "  • Missing test fixtures"
    echo "  • API endpoint changes"
    echo "  • JavaScript syntax errors"
    echo ""
    exit 1
fi