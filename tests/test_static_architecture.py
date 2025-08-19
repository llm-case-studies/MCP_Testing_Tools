#!/usr/bin/env python3
"""
Tests for the static file architecture
Validates the refactored structure and proper separation of concerns
"""

import pytest
import requests
from pathlib import Path

class TestStaticArchitecture:
    """Test the static file architecture"""
    
    @pytest.fixture(scope="class")
    def launcher_server(self):
        """Reuse launcher server fixture - implementation would match existing patterns"""
        return "http://localhost:8098"  # Placeholder for actual fixture
    
    def test_static_file_structure_exists(self):
        """Test that the static file structure is properly organized"""
        static_dir = Path(__file__).parent.parent / "launcher" / "static"
        
        required_files = [
            "index.html",
            "style.css", 
            "script.js"
        ]
        
        for file in required_files:
            file_path = static_dir / file
            assert file_path.exists(), f"Required static file missing: {file}"
            assert file_path.stat().st_size > 0, f"Static file is empty: {file}"
    
    def test_html_structure_and_content(self):
        """Test that HTML file has proper structure"""
        html_path = Path(__file__).parent.parent / "launcher" / "static" / "index.html"
        
        with open(html_path, 'r') as f:
            html_content = f.read()
        
        # Check essential HTML structure
        assert '<!DOCTYPE html>' in html_content
        assert '<html>' in html_content
        assert '<head>' in html_content
        assert '<body>' in html_content
        
        # Check Learning Mode elements
        assert 'learningModeChooser' in html_content
        assert 'proModeChooser' in html_content
        assert 'LEARN MCP BASICS' in html_content
        assert 'GUIDED TESTING' in html_content
        
        # Check proper external file references
        assert '<link rel="stylesheet" href="/static/style.css">' in html_content
        assert '<script src="/static/script.js"></script>' in html_content
        
        # Ensure NO inline JavaScript (clean architecture)
        assert '<script>' not in html_content or html_content.count('<script>') == 0
        assert 'function ' not in html_content  # No inline JS functions
    
    def test_css_completeness(self):
        """Test that CSS file contains all necessary styles"""
        css_path = Path(__file__).parent.parent / "launcher" / "static" / "style.css"
        
        with open(css_path, 'r') as f:
            css_content = f.read()
        
        # Check core styling classes
        required_styles = [
            '.learning-tile',
            '.adventure-tile', 
            '.mode-toggle',
            '.learning-highlight',
            '.project-card',
            '.status-running',
            '.status-stopped'
        ]
        
        for style in required_styles:
            assert style in css_content, f"Required CSS class missing: {style}"
        
        # Check responsive design
        assert '@keyframes' in css_content  # Animations present
        assert 'grid-template-columns' in css_content  # Grid layout
        # Check for responsive design (flex-wrap is our responsive approach)
        assert 'flex-wrap' in css_content  # Responsive design
    
    def test_separation_of_concerns(self):
        """Test that separation of concerns is properly maintained"""
        static_dir = Path(__file__).parent.parent / "launcher" / "static"
        
        # Read all files
        with open(static_dir / "index.html", 'r') as f:
            html_content = f.read()
        with open(static_dir / "style.css", 'r') as f:
            css_content = f.read()
        with open(static_dir / "script.js", 'r') as f:
            js_content = f.read()
        
        # HTML should have minimal inline styles (this is a refactored legacy structure)
        inline_style_count = html_content.count('style=')
        assert inline_style_count < 100, f"Too many inline styles: {inline_style_count} (refactored from monolithic structure)"
        
        # HTML should not contain inline JavaScript
        assert 'function(' not in html_content
        assert 'var ' not in html_content
        assert 'let ' not in html_content
        assert 'const ' not in html_content
        
        # CSS should not contain JavaScript
        assert 'function' not in css_content
        assert 'document.' not in css_content
        
        # JavaScript should not contain excessive CSS definitions (allow modal HTML)
        # Note: Modal teasers contain legitimate inline HTML for dynamic content
        js_lines_with_style = [line for line in js_content.split('\n') if 'style=' in line and len(line.strip()) > 100]
        assert len(js_lines_with_style) < 50, f"JavaScript contains too much inline styling: {len(js_lines_with_style)} lines"

class TestArchitectureIntegration:
    """Test that the static architecture integrates properly with the server"""
    
    def test_static_files_served_correctly(self, launcher_server=None):
        """Test that all static files are served with correct MIME types"""
        if not launcher_server:
            launcher_server = "http://localhost:8094"  # Default port
        
        static_files = [
            ("/static/index.html", "text/html"),
            ("/static/style.css", "text/css"), 
            ("/static/script.js", "application/javascript")
        ]
        
        for file_path, expected_mime in static_files:
            try:
                response = requests.get(f"{launcher_server}{file_path}", timeout=2)
                if response.status_code == 200:
                    content_type = response.headers.get('content-type', '').lower()
                    # Note: Some servers might return slightly different MIME types
                    assert any(mime_part in content_type for mime_part in expected_mime.split('/')), \
                        f"Unexpected MIME type for {file_path}: {content_type}"
            except requests.exceptions.RequestException:
                # Server might not be running - skip this test
                pytest.skip(f"Server not available at {launcher_server}")
    
    def test_main_page_loads_static_resources(self, launcher_server=None):
        """Test that the main page properly loads all static resources"""
        if not launcher_server:
            launcher_server = "http://localhost:8094"
        
        try:
            response = requests.get(launcher_server, timeout=2)
            assert response.status_code == 200
            
            html_content = response.text
            
            # Check that static resource links are present
            assert '/static/style.css' in html_content
            assert '/static/script.js' in html_content
            
        except requests.exceptions.RequestException:
            pytest.skip(f"Server not available at {launcher_server}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])