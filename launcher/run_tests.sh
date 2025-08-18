#!/bin/bash
# Test runner for MCP Launcher V2

echo "🧪 Running MCP Launcher V2 Test Suite"
echo "======================================"

# Install test dependencies
echo "📦 Installing test dependencies..."
pip3 install -r tests/requirements.txt -q

# Run unit tests
echo ""
echo "🔬 Running Unit Tests..."
python3 -m pytest tests/test_project_scanner.py tests/test_session_manager.py -v

# Run API tests  
echo ""
echo "🌐 Running API Tests..."
python3 -m pytest tests/test_api.py -v

# Run full suite
echo ""
echo "🎯 Running Full Test Suite..."
python3 -m pytest tests/ --tb=short

echo ""
echo "✅ Test suite completed!"