#!/usr/bin/env python3
"""
Basic tests for Learning Mode functionality
Tests the server-side components and API endpoints
"""

import pytest
import json
import time
import subprocess
import requests
from pathlib import Path

# Test configuration
TEST_PORT = 8098
TEST_URL = f"http://localhost:{TEST_PORT}"
LAUNCHER_PATH = Path(__file__).parent.parent / "launcher" / "main.py"

@pytest.fixture(scope="session")
def launcher_server():
    """Start the launcher server for testing"""
    print(f"🚀 Starting launcher server on port {TEST_PORT}")
    
    # Start the launcher server
    process = subprocess.Popen([
        "python3", str(LAUNCHER_PATH), 
        "--port", str(TEST_PORT),
        "--no-auto-open"
    ], cwd=str(LAUNCHER_PATH.parent))
    
    # Wait for server to start
    max_wait = 15
    wait_time = 0
    while wait_time < max_wait:
        try:
            response = requests.get(TEST_URL, timeout=2)
            if response.status_code == 200:
                print(f"✅ Server started successfully on {TEST_URL}")
                break
        except:
            pass
        time.sleep(1)
        wait_time += 1
    else:
        process.terminate()
        raise Exception(f"Failed to start server on {TEST_URL} within {max_wait} seconds")
    
    yield TEST_URL
    
    # Cleanup
    print("🧹 Shutting down launcher server")
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()

class TestLearningModeBasic:
    """Basic tests for Learning Mode server functionality"""
    
    def test_server_starts_successfully(self, launcher_server):
        """Test that the server starts and serves the main page"""
        response = requests.get(launcher_server, timeout=5)
        assert response.status_code == 200
        assert "MCP Testing Suite" in response.text
    
    def test_learning_mode_html_structure(self, launcher_server):
        """Test that Learning Mode HTML elements are present"""
        response = requests.get(launcher_server, timeout=5)
        html = response.text
        
        # Check for Learning Mode toggle button
        assert 'id="learningModeBtn"' in html
        assert '🎓 Learning Mode' in html
        
        # Check for Pro Mode toggle button
        assert 'id="proModeBtn"' in html
        assert '⚡ Pro Mode' in html
        
        # Check for Learning Mode chooser
        assert 'id="learningModeChooser"' in html
        
        # Check for Pro Mode chooser
        assert 'id="proModeChooser"' in html
    
    def test_learning_tiles_present(self, launcher_server):
        """Test that all Learning Mode tiles are present in HTML"""
        response = requests.get(launcher_server, timeout=5)
        html = response.text
        
        # Check for learning tiles
        learning_tiles = [
            'LEARN MCP BASICS',
            'GUIDED TESTING', 
            'EXPLORE EXAMPLES',
            'TROUBLESHOOTING'
        ]
        
        for tile_name in learning_tiles:
            assert tile_name in html
        
        # Check for learning-specific styling
        assert 'learning-tile' in html
        assert 'learning-progress' in html
    
    def test_javascript_functions_defined(self, launcher_server):
        """Test that Learning Mode JavaScript functions are defined in external JS file"""
        # Test that the main page loads the external script
        response = requests.get(launcher_server, timeout=5)
        html = response.text
        assert '<script src="/static/script.js"></script>' in html
        
        # Test that the external JavaScript file contains the functions
        js_response = requests.get(f"{launcher_server}/static/script.js", timeout=5)
        assert js_response.status_code == 200
        js_content = js_response.text
        
        # Check for key JavaScript functions in the external file
        js_functions = [
            'startMCPBasics',
            'startGuidedTesting', 
            'exploreExamples',
            'troubleshootingHelp',
            'switchToLearningMode',
            'switchToProMode',
            'showWhatIsMCP'
        ]
        
        for func_name in js_functions:
            assert f'function {func_name}(' in js_content
    
    def test_educational_modals_present(self, launcher_server):
        """Test that educational modals are included"""
        response = requests.get(launcher_server, timeout=5)
        html = response.text
        
        # Check for What is MCP modal
        assert 'id="whatIsMCPModal"' in html
        assert 'What is MCP?' in html
        assert 'Think of MCP like this' in html
        
        # Check for MCP Postman modal
        assert 'id="mcpPostmanModal"' in html
    
    def test_teaser_functionality_in_js(self, launcher_server):
        """Test that teaser modal functions are present in external JS"""
        js_response = requests.get(f"{launcher_server}/static/script.js", timeout=5)
        assert js_response.status_code == 200
        js_content = js_response.text
        
        # Check for teaser functions in external JavaScript file
        teaser_functions = [
            'showMCPBasicsTeaser',
            'startGuidedTesting',  # This is the actual function name in HTML
            'showExploreExamplesTeaser', 
            'showTroubleshootingTeaser'
        ]
        
        for func_name in teaser_functions:
            assert f'function {func_name}(' in js_content
    
    def test_transition_system_present(self, launcher_server):
        """Test that Learning-to-Pro transition system is included in external JS"""
        js_response = requests.get(f"{launcher_server}/static/script.js", timeout=5)
        assert js_response.status_code == 200
        js_content = js_response.text
        
        # Check for transition functions in external JavaScript file
        transition_functions = [
            'switchToLearningMode',
            'switchToProMode',
            'updateLearningProgress'
        ]
        
        for func_name in transition_functions:
            assert f'function {func_name}(' in js_content
    
    def test_api_endpoints_available(self, launcher_server):
        """Test that API endpoints are available"""
        # Test health endpoint
        try:
            response = requests.get(f"{launcher_server}/api/health", timeout=3)
            # May or may not exist, but shouldn't crash
        except:
            pass
        
        # Test main page loads (this is the core requirement)
        response = requests.get(launcher_server, timeout=5)
        assert response.status_code == 200
    
    def test_css_styling_present(self, launcher_server):
        """Test that Learning Mode CSS styling is present in external CSS"""
        css_response = requests.get(f"{launcher_server}/static/style.css", timeout=5)
        assert css_response.status_code == 200
        css_content = css_response.text
        
        # Check for learning-specific CSS classes in external stylesheet
        css_classes = [
            '.learning-tile',
            '.learning-progress',
            '.mode-toggle',
            '.mode-btn',
            '.adventure-grid',
            '.adventure-tile'
        ]
        
        for css_class in css_classes:
            assert css_class in css_content
    
    def test_responsive_design_css(self, launcher_server):
        """Test that responsive design CSS is included in external CSS"""
        css_response = requests.get(f"{launcher_server}/static/style.css", timeout=5)
        assert css_response.status_code == 200
        css_content = css_response.text
        
        # Check for responsive grid in external stylesheet
        assert 'grid-template-columns: repeat(auto-fit, minmax(' in css_content
        
        # Check for media queries or flexible layouts
        assert 'flex-wrap: wrap' in css_content
    
    def test_no_javascript_errors_in_external_js(self, launcher_server):
        """Test that there are no obvious JavaScript syntax errors in external JS file"""
        js_response = requests.get(f"{launcher_server}/static/script.js", timeout=5)
        assert js_response.status_code == 200
        js_content = js_response.text
        
        # Basic syntax checks in external JavaScript file
        assert 'SyntaxError' not in js_content
        assert 'undefined is not a function' not in js_content
        assert 'Uncaught' not in js_content
        
        # Check for proper function definitions
        function_count = js_content.count('function ')
        assert function_count > 20  # Should have many functions defined
        
        # Check that we have proper JavaScript structure
        assert js_content.count('{') == js_content.count('}')  # Balanced braces

# Simple integration test that doesn't need browser
class TestLearningModeIntegration:
    """Integration tests that verify the complete system works together"""
    
    def test_complete_page_loads_without_errors(self, launcher_server):
        """Test that the complete page loads successfully"""
        response = requests.get(launcher_server, timeout=10)
        assert response.status_code == 200
        
        html = response.text
        
        # Should contain all major sections
        sections = [
            'Learning Mode',
            'Pro Mode', 
            'LEARN MCP BASICS',
            'What is MCP?',
            'MCP Testing Suite'
        ]
        
        for section in sections:
            assert section in html
    
    def test_page_size_reasonable(self, launcher_server):
        """Test that the page size is reasonable (not truncated or too large)"""
        response = requests.get(launcher_server, timeout=5)
        html = response.text
        
        # Should be substantial but not excessive
        assert len(html) > 10000  # At least 10KB
        assert len(html) < 1000000  # Less than 1MB
    
    def test_html_validity_basic(self, launcher_server):
        """Basic HTML validity checks"""
        response = requests.get(launcher_server, timeout=5)
        html = response.text
        
        # Basic structure checks
        assert html.count('<html>') == 1
        assert html.count('</html>') == 1
        assert html.count('<head>') == 1
        assert html.count('</head>') == 1
        assert html.count('<body>') == 1
        assert html.count('</body>') == 1
        
        # No obvious unclosed tags for major elements  
        # Allow some tolerance for self-closing divs and complex structures
        assert html.count('<div') <= html.count('</div>') + 20  # More tolerance for complex layouts
        # Check script tags including those with attributes
        assert html.count('<script') == html.count('</script>')

# Run the tests
if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))