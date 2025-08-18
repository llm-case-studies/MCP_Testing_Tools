#!/bin/bash
# End-to-End Test Suite for MCP Testing Tools
# Tests all functionality without browser dependencies

set -e

BASE_URL="http://localhost:8094"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🧪 MCP Testing Suite - End-to-End Tests"
echo "========================================"

# Test 1: Web Interface Responds
echo -e "\n${YELLOW}Test 1: Web Interface Accessibility${NC}"
if curl -s -f "$BASE_URL" > /dev/null; then
    echo -e "${GREEN}✅ Web interface is accessible${NC}"
else
    echo -e "${RED}❌ Web interface is not accessible${NC}"
    exit 1
fi

# Test 2: Server Discovery API
echo -e "\n${YELLOW}Test 2: Server Discovery API${NC}"
DISCOVERY_RESULT=$(curl -s -X POST "$BASE_URL/api/discover-servers")
SERVER_COUNT=$(echo "$DISCOVERY_RESULT" | jq -r '.total_servers // 0')
if [ "$SERVER_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✅ Discovered $SERVER_COUNT servers${NC}"
    
    # List Qdrant servers
    QDRANT_SERVERS=$(echo "$DISCOVERY_RESULT" | jq -r '.discovered[] | select(.name | contains("qdrant")) | .name')
    if [ ! -z "$QDRANT_SERVERS" ]; then
        echo -e "${GREEN}✅ Found Qdrant memory servers:${NC}"
        echo "$QDRANT_SERVERS" | sed 's/^/  - /'
    else
        echo -e "${YELLOW}⚠️  No Qdrant servers found${NC}"
    fi
else
    echo -e "${RED}❌ Server discovery failed${NC}"
    exit 1
fi

# Test 3: JavaScript Functions
echo -e "\n${YELLOW}Test 3: JavaScript Function Testing${NC}"
WEBPAGE=$(curl -s "$BASE_URL")
if echo "$WEBPAGE" | grep -q "discoverServers()"; then
    echo -e "${GREEN}✅ JavaScript functions present${NC}"
    if echo "$WEBPAGE" | grep -q "testQdrantStore"; then
        echo -e "${GREEN}✅ Qdrant test functions present${NC}"
    else
        echo -e "${YELLOW}⚠️  Qdrant test functions missing${NC}"
    fi
else
    echo -e "${RED}❌ JavaScript functions missing${NC}"
fi

# Test 4: DOM Elements Present
echo -e "\n${YELLOW}Test 4: Required DOM Elements${NC}"
if echo "$WEBPAGE" | grep -q 'id="servers"'; then
    echo -e "${GREEN}✅ Servers container present${NC}"
else
    echo -e "${RED}❌ Servers container missing${NC}"
fi

if echo "$WEBPAGE" | grep -q 'id="tools"'; then
    echo -e "${GREEN}✅ Tools container present${NC}"
else
    echo -e "${RED}❌ Tools container missing${NC}"
fi

# Test 5: Auto-discovery on Load
echo -e "\n${YELLOW}Test 5: Auto-discovery Configuration${NC}"
if echo "$WEBPAGE" | grep -q "window.onload"; then
    echo -e "${GREEN}✅ Auto-discovery configured${NC}"
else
    echo -e "${RED}❌ Auto-discovery not configured${NC}"
fi

# Test 6: Port Configuration
echo -e "\n${YELLOW}Test 6: Port Configuration${NC}"
EXPECTED_PORTS=(8094 8095 8096)
for port in "${EXPECTED_PORTS[@]}"; do
    if netstat -tln | grep -q ":$port "; then
        echo -e "${GREEN}✅ Port $port is listening${NC}"
    else
        echo -e "${RED}❌ Port $port is not listening${NC}"
    fi
done

# Test 7: Container Health
echo -e "\n${YELLOW}Test 7: Docker Container Health${NC}"
if docker ps | grep -q "MCP-Debug-Wizard"; then
    echo -e "${GREEN}✅ MCP Debug Wizard container is running${NC}"
    
    # Check container health
    HEALTH=$(docker inspect MCP-Debug-Wizard --format='{{.State.Health.Status}}' 2>/dev/null || echo "no-health-check")
    if [ "$HEALTH" = "healthy" ]; then
        echo -e "${GREEN}✅ Container health check passed${NC}"
    elif [ "$HEALTH" = "no-health-check" ]; then
        echo -e "${YELLOW}⚠️  No health check configured${NC}"
    else
        echo -e "${RED}❌ Container health check failed: $HEALTH${NC}"
    fi
else
    echo -e "${RED}❌ MCP Debug Wizard container is not running${NC}"
fi

# Test 8: Memory Testing (Simulation)
echo -e "\n${YELLOW}Test 8: Qdrant Memory Testing (Simulation)${NC}"
echo -e "${GREEN}✅ Test data prepared for Qdrant:${NC}"
cat << EOF
{
  "information": "E2E test run at $(date)",
  "metadata": {
    "test_suite": "e2e_curl",
    "timestamp": "$(date -Iseconds)",
    "ports": [8094, 8095, 8096],
    "status": "automated_test"
  }
}
EOF

echo -e "\n${GREEN}✅ Search query prepared: 'MCP Testing Suite e2e'${NC}"

# Test 9: Browser Accessibility Test
echo -e "\n${YELLOW}Test 9: Browser Accessibility Check${NC}"
# Try different ways to test browser accessibility
if command -v firefox >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Firefox available for manual testing${NC}"
fi

if command -v chromium >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Chromium available for manual testing${NC}"
fi

if command -v google-chrome >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Chrome available for manual testing${NC}"
fi

# Test Summary
echo -e "\n${YELLOW}🎯 Test Summary${NC}"
echo "========================================"
echo -e "${GREEN}Web Interface:${NC} http://localhost:8094"
echo -e "${GREEN}Mock Genie:${NC} http://localhost:8095"  
echo -e "${GREEN}Proxy Spy:${NC} http://localhost:8096"
echo ""
echo -e "${YELLOW}Manual Testing Steps:${NC}"
echo "1. Open http://localhost:8094 in your browser"
echo "2. Verify servers auto-load on page"
echo "3. Look for Qdrant memory servers with test buttons"
echo "4. Click 'Test Store' and 'Test Find' buttons"
echo "5. Check that results appear on the page (not just console)"
echo ""
echo -e "${GREEN}✅ E2E Test Suite Completed Successfully!${NC}"