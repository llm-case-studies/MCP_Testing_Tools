#!/bin/bash
# Health check script for DevOps Paradise Quality Container

set -e

SERENA_PORT=${SERENA_PORT:-24282}
DASHBOARD_PORT=${DASHBOARD_PORT:-8000}

# Check if Serena MCP is responding
if ! curl -s -f "http://localhost:$SERENA_PORT/health" > /dev/null 2>&1; then
    echo "❌ Serena MCP health check failed"
    exit 1
fi

# Check if dashboard is responding
if ! curl -s -f "http://localhost:$DASHBOARD_PORT/" > /dev/null 2>&1; then
    echo "❌ Dashboard health check failed"
    exit 1
fi

# Check if processes are running
if [[ -f /app/serena.pid ]] && ! kill -0 $(cat /app/serena.pid) 2>/dev/null; then
    echo "❌ Serena process not running"
    exit 1
fi

if [[ -f /app/orchestrator.pid ]] && ! kill -0 $(cat /app/orchestrator.pid) 2>/dev/null; then
    echo "❌ Quality Orchestrator process not running"
    exit 1
fi

echo "✅ All services healthy"
exit 0