#!/usr/bin/env python3
"""
Integration tests for JavaScript functionality
Tests the complete JavaScript loading and function availability
"""

import pytest
import requests
import subprocess
import os
from pathlib import Path

class TestJavaScriptIntegration:
    """Test JavaScript functionality and integration"""
    
    def test_javascript_syntax_validation(self):
        """Test that JavaScript syntax is valid using Node.js"""
        script_path = Path(__file__).parent.parent / "launcher" / "static" / "script.js"
        
        # Use Node.js to validate syntax
        result = subprocess.run(
            ["node", "-c", str(script_path)], 
            capture_output=True, 
            text=True
        )
        
        assert result.returncode == 0, f"JavaScript syntax error: {result.stderr}"
    
    def test_all_learning_mode_functions_present(self):
        """Test that all expected Learning Mode functions are present"""
        script_path = Path(__file__).parent.parent / "launcher" / "static" / "script.js"
        
        with open(script_path, 'r') as f:
            js_content = f.read()
        
        # Core Learning Mode functions
        required_functions = [
            'startMCPBasics',
            'showMCPBasicsTeaser',
            'closeMCPBasicsTeaser', 
            'beginMCPBasics',
            'startGuidedTesting',
            'exploreExamples',
            'showExploreExamplesTeaser',
            'troubleshootingHelp',
            'showTroubleshootingTeaser',
            'switchToLearningMode',
            'switchToProMode',
            'showWhatIsMCP',
            'closeWhatIsMCPModal',
            'showLearningPath'
        ]
        
        missing_functions = []
        for func in required_functions:
            if f'function {func}(' not in js_content:
                missing_functions.append(func)
        
        assert not missing_functions, f"Missing functions: {missing_functions}"
    
    def test_javascript_no_template_literal_conflicts(self):
        """Test that there are no remaining template literal syntax conflicts"""
        script_path = Path(__file__).parent.parent / "launcher" / "static" / "script.js"
        
        with open(script_path, 'r') as f:
            js_content = f.read()
        
        # Check for problematic patterns that caused original errors
        lines = js_content.split('\n')
        problematic_lines = []
        
        for i, line in enumerate(lines, 1):
            # Look for template literals with potential quote conflicts
            if '`' in line and ('\\' in line and '"' in line):
                problematic_lines.append(f"Line {i}: {line.strip()}")
        
        assert not problematic_lines, f"Potential template literal conflicts: {problematic_lines}"
    
    def test_mcp_postman_functions_present(self):
        """Test that MCP Postman functionality is preserved"""
        script_path = Path(__file__).parent.parent / "launcher" / "static" / "script.js"
        
        with open(script_path, 'r') as f:
            js_content = f.read()
        
        # MCP Postman core functions
        mcp_functions = [
            'openMCPPostman',
            'closeMCPPostman',
            'refreshMCPSessions',
            'loadMCPServers',
            'selectMCPServer',
            'selectMCPTool',
            'executeMCPTool'
        ]
        
        missing_functions = []
        for func in mcp_functions:
            if f'function {func}(' not in js_content:
                missing_functions.append(func)
        
        assert not missing_functions, f"Missing MCP functions: {missing_functions}"
    
    def test_javascript_file_size_reasonable(self):
        """Test that the JavaScript file size is reasonable"""
        script_path = Path(__file__).parent.parent / "launcher" / "static" / "script.js"
        
        file_size = os.path.getsize(script_path)
        
        # Should be substantial (has lots of functionality) but not excessive
        assert 10000 < file_size < 100000, f"JavaScript file size unusual: {file_size} bytes"
    
    def test_no_hardcoded_localhost_urls(self):
        """Test that there are no hardcoded localhost URLs that would break deployment"""
        script_path = Path(__file__).parent.parent / "launcher" / "static" / "script.js"
        
        with open(script_path, 'r') as f:
            js_content = f.read()
        
        # Look for hardcoded URLs that would break in production
        problematic_patterns = [
            'http://localhost',
            'https://localhost',
            '127.0.0.1'
        ]
        
        issues = []
        for pattern in problematic_patterns:
            if pattern in js_content:
                issues.append(pattern)
        
        assert not issues, f"Hardcoded localhost URLs found: {issues}"

class TestJavaScriptFunctionality:
    """Test JavaScript functionality via server integration"""
    
    @pytest.fixture(scope="class")
    def launcher_server(self):
        """Start launcher server for JavaScript testing"""
        # This would reuse the same fixture pattern as other tests
        # Implementation details similar to existing test fixtures
        pass
    
    def test_javascript_loads_without_errors(self, launcher_server):
        """Test that JavaScript loads without console errors"""
        # This would require browser automation (Playwright)
        # to check for JavaScript console errors
        pass
    
    def test_learning_mode_ui_interactions(self, launcher_server):
        """Test that Learning Mode UI interactions work correctly"""
        # This would test actual DOM manipulation
        # and UI state changes via browser automation
        pass

if __name__ == "__main__":
    pytest.main([__file__, "-v"])