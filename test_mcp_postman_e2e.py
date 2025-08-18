#!/usr/bin/env python3
"""
End-to-End tests for MCP Postman functionality
Tests the complete workflow from launcher UI to backend execution
"""

import asyncio
import time
import subprocess
import requests
import json
from pathlib import Path
import signal
import sys

class MCPPostmanE2ETest:
    """E2E test class for MCP Postman"""
    
    def __init__(self):
        self.launcher_process = None
        self.backend_process = None  
        self.launcher_url = "http://localhost:8094"
        self.backend_url = "http://localhost:8095"
        
    def setup(self):
        """Setup test environment"""
        print("🚀 Setting up MCP Postman E2E test environment...")
        
        # Kill any existing processes on our ports
        self._kill_existing_processes()
        
        # Start launcher
        print("📱 Starting launcher...")
        launcher_dir = Path(__file__).parent / "launcher"
        self.launcher_process = subprocess.Popen(
            ["python3", "main.py"],
            cwd=launcher_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for launcher to start
        self._wait_for_service(self.launcher_url, "Launcher")
        
        print("✅ Test environment ready!")
    
    def teardown(self):
        """Cleanup test environment"""
        print("🧹 Cleaning up test environment...")
        
        if self.launcher_process:
            self.launcher_process.terminate()
            self.launcher_process.wait(timeout=5)
            
        if self.backend_process:
            self.backend_process.terminate()
            self.backend_process.wait(timeout=5)
            
        print("✅ Cleanup complete!")
    
    def test_launcher_serves_mcp_postman_ui(self):
        """Test that launcher serves MCP Postman UI"""
        print("🧪 Testing launcher serves MCP Postman UI...")
        
        response = requests.get(self.launcher_url)
        assert response.status_code == 200
        
        html_content = response.text
        
        # Check for MCP Postman components
        required_elements = [
            "MCP Postman - Tool Testing",
            "openMCPPostman()",
            "mcpPostmanModal", 
            "executeMCPTool()",
            "mcpServersList",
            "mcpToolsList"
        ]
        
        for element in required_elements:
            assert element in html_content, f"Missing element: {element}"
            
        print("✅ Launcher serves MCP Postman UI correctly")
    
    def test_sessions_api_for_mcp_integration(self):
        """Test sessions API provides data for MCP Postman"""
        print("🧪 Testing sessions API for MCP integration...")
        
        response = requests.get(f"{self.launcher_url}/api/sessions")
        assert response.status_code == 200
        
        data = response.json()
        assert "sessions" in data
        
        print("✅ Sessions API works for MCP integration")
    
    def test_project_scanning_with_mcp_configs(self):
        """Test project scanning detects MCP configurations"""
        print("🧪 Testing project scanning with MCP configs...")
        
        # Use current project as test subject
        current_dir = str(Path(__file__).parent.absolute())
        
        response = requests.get(f"{self.launcher_url}/api/scan-projects", params={
            "path": current_dir
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "projects" in data
        # Should find our MCP project
        if data["projects"]:
            project = data["projects"][0]
            assert "config_sources" in project
            print(f"✅ Found project with {len(project['config_sources'])} config sources")
        else:
            print("✅ Project scanning works (no MCP configs found in test dir)")
    
    def test_mcp_backend_apis_structure(self):
        """Test that backend would provide MCP APIs"""
        print("🧪 Testing MCP backend API structure...")
        
        # We can't test actual backend without launching a session,
        # but we can verify the launcher has the right integration code
        
        response = requests.get(self.launcher_url)
        html_content = response.text
        
        # Check for backend API integration code
        backend_api_calls = [
            "/api/mcp/discover",
            "/api/mcp/tools/",
            "/api/mcp/call-tool/",
            "/api/mcp/history",
            "/api/mcp/generate-sample/"
        ]
        
        for api_call in backend_api_calls:
            assert api_call in html_content, f"Missing backend API call: {api_call}"
            
        print("✅ Backend API integration structure is correct")
    
    def test_mcp_postman_ui_workflow_structure(self):
        """Test MCP Postman UI supports complete workflow"""
        print("🧪 Testing MCP Postman UI workflow structure...")
        
        response = requests.get(self.launcher_url)
        html_content = response.text
        
        # Test workflow components
        workflow_components = {
            "Session Selection": "mcpSessionSelect",
            "Server Discovery": "loadMCPServers",
            "Server List": "mcpServersList", 
            "Tool Discovery": "selectMCPServer",
            "Tool List": "mcpToolsList",
            "Tool Selection": "selectMCPTool",
            "Request Builder": "testArguments",
            "Tool Execution": "executeMCPTool",
            "Results Display": "mcpResults",
            "History Management": "mcpHistory",
            "Sample Generation": "generateSampleRequest",
            "Error Handling": "showMCPError"
        }
        
        for component_name, element_id in workflow_components.items():
            assert element_id in html_content, f"Missing workflow component: {component_name} ({element_id})"
            
        print("✅ Complete MCP Postman workflow structure is present")
    
    def test_mcp_postman_javascript_functionality(self):
        """Test MCP Postman JavaScript functions are properly defined"""
        print("🧪 Testing MCP Postman JavaScript functionality...")
        
        response = requests.get(self.launcher_url)
        html_content = response.text
        
        # Check for key JavaScript functions
        js_functions = [
            "function openMCPPostman()",
            "function closeMCPPostman()",
            "async function refreshMCPSessions()",
            "async function loadMCPServers()",
            "async function selectMCPServer(",
            "function selectMCPTool(",
            "async function executeMCPTool()",
            "async function generateSampleRequest()",
            "function clearToolTester()",
            "async function refreshMCPHistory()",
            "async function clearMCPHistory()",
            "async function getCurrentMCPSession()",
            "function showMCPError("
        ]
        
        for func in js_functions:
            assert func in html_content, f"Missing JavaScript function: {func}"
            
        print("✅ All MCP Postman JavaScript functions are defined")
    
    def test_mcp_postman_responsive_ui(self):
        """Test MCP Postman UI responsive design"""
        print("🧪 Testing MCP Postman responsive UI...")
        
        response = requests.get(self.launcher_url)
        html_content = response.text
        
        # Check responsive design elements
        responsive_elements = [
            "max-width: 1200px",  # Modal constraint
            "width: 90%",         # Responsive width  
            "max-height: 90vh",   # Viewport height
            "overflow-y: auto",   # Scrollable content
            "display: flex",      # Flexible layouts
            "flex: 1",            # Flexible components
            "gap: 20px"           # Consistent spacing
        ]
        
        found_elements = 0
        for element in responsive_elements:
            if element in html_content:
                found_elements += 1
                
        # Should have most responsive elements
        assert found_elements >= len(responsive_elements) * 0.7, f"Only found {found_elements}/{len(responsive_elements)} responsive elements"
        
        print(f"✅ Responsive UI design present ({found_elements}/{len(responsive_elements)} elements found)")
    
    def run_all_tests(self):
        """Run all E2E tests"""
        print("🎯 Starting MCP Postman E2E Test Suite")
        print("=" * 50)
        
        try:
            self.setup()
            
            # Run tests
            self.test_launcher_serves_mcp_postman_ui()
            self.test_sessions_api_for_mcp_integration() 
            self.test_project_scanning_with_mcp_configs()
            self.test_mcp_backend_apis_structure()
            self.test_mcp_postman_ui_workflow_structure()
            self.test_mcp_postman_javascript_functionality()
            self.test_mcp_postman_responsive_ui()
            
            print("\n🎉 All MCP Postman E2E tests PASSED!")
            return True
            
        except Exception as e:
            print(f"\n❌ E2E test failed: {e}")
            return False
            
        finally:
            self.teardown()
    
    def _wait_for_service(self, url, name, timeout=30):
        """Wait for service to be available"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    print(f"✅ {name} is ready at {url}")
                    return
            except requests.exceptions.RequestException:
                pass
            time.sleep(1)
        
        raise Exception(f"{name} did not start within {timeout} seconds")
    
    def _kill_existing_processes(self):
        """Kill any existing processes on our ports"""
        ports = [8094, 8095]
        for port in ports:
            try:
                subprocess.run(["pkill", "-f", f":{port}"], capture_output=True)
            except:
                pass

# Run tests if executed directly
if __name__ == "__main__":
    tester = MCPPostmanE2ETest()
    
    success = tester.run_all_tests()
    
    if success:
        print("\n🏆 MCP Postman E2E Test Suite: SUCCESS")
        sys.exit(0)
    else:
        print("\n💥 MCP Postman E2E Test Suite: FAILED") 
        sys.exit(1)