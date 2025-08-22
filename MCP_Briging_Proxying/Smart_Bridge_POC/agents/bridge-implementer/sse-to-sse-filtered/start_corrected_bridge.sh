#!/bin/bash
"""
Startup script for the corrected filtered bridge implementation
Uses the working simple_bridge.py architecture with content filtering enhancements
"""

set -e

# Default configuration
DEFAULT_PORT=8100
DEFAULT_CMD="python3 -m mcp_server_echo"
DEFAULT_LOG_LEVEL="INFO"
DEFAULT_LOG_LOCATION="../../../Smart_Bridge_Logs"
DEFAULT_FILTER_CONFIG="config/default_filters.json"

# Parse command line arguments
PORT=${1:-$DEFAULT_PORT}
CMD=${2:-$DEFAULT_CMD}
LOG_LEVEL=${3:-$DEFAULT_LOG_LEVEL}
LOG_LOCATION=${4:-$DEFAULT_LOG_LOCATION}
FILTER_CONFIG=${5:-$DEFAULT_FILTER_CONFIG}

echo "🔧 Starting Corrected Filtered Bridge"
echo "=================================="
echo "Port: $PORT"
echo "Command: $CMD"
echo "Log Level: $LOG_LEVEL"
echo "Log Location: $LOG_LOCATION"
echo "Filter Config: $FILTER_CONFIG"
echo "=================================="

# Ensure log directory exists
mkdir -p "$LOG_LOCATION"

# Ensure filter config exists
if [ ! -f "$FILTER_CONFIG" ]; then
    echo "⚠️  Filter config not found at $FILTER_CONFIG, using defaults"
    FILTER_CONFIG=""
fi

# Start the corrected filtered bridge
python3 filtered_simple_bridge.py \
    --port "$PORT" \
    --host "localhost" \
    --cmd "$CMD" \
    --log_level "$LOG_LEVEL" \
    --log_location "$LOG_LOCATION" \
    --filter_config "$FILTER_CONFIG" \
    --log_pattern "filtered_bridge_{server}_{port}.log"

echo "🏁 Filtered bridge stopped"