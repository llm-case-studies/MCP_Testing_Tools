#!/usr/bin/env python3
"""
End-to-end tests for Learning Mode functionality
Tests the complete user journey through Learning Mode features
"""

import pytest
import asyncio
import json
from playwright.async_api import async_playwright, expect
import os
import signal
import subprocess
import time
from pathlib import Path

# Test configuration
TEST_PORT = 8099
TEST_URL = f"http://localhost:{TEST_PORT}"
LAUNCHER_PATH = Path(__file__).parent.parent / "launcher" / "main.py"

@pytest.fixture(scope="session")
async def launcher_server():
    """Start the launcher server for testing"""
    print(f"🚀 Starting launcher server on port {TEST_PORT}")
    
    # Start the launcher server
    process = subprocess.Popen([
        "python3", str(LAUNCHER_PATH), 
        "--port", str(TEST_PORT),
        "--no-auto-open"
    ], cwd=str(LAUNCHER_PATH.parent))
    
    # Wait for server to start
    max_wait = 30
    wait_time = 0
    while wait_time < max_wait:
        try:
            import requests
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

@pytest.fixture
async def browser_context():
    """Create a browser context for testing"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        yield context
        await browser.close()

class TestLearningModeE2E:
    """End-to-end tests for Learning Mode"""
    
    async def test_learning_mode_default_state(self, launcher_server, browser_context):
        """Test that Learning Mode is the default state"""
        page = await browser_context.new_page()
        await page.goto(launcher_server)
        
        # Wait for page to load
        await page.wait_for_selector('#learningModeBtn')
        
        # Check that Learning Mode is active by default
        learning_btn = page.locator('#learningModeBtn')
        await expect(learning_btn).to_have_class("active")
        
        # Check that Learning Mode tiles are visible
        learning_chooser = page.locator('#learningModeChooser')
        await expect(learning_chooser).to_be_visible()
        
        # Check that Pro Mode tiles are hidden
        pro_chooser = page.locator('#proModeChooser')
        await expect(pro_chooser).to_have_css('display', 'none')
    
    async def test_mode_switching(self, launcher_server, browser_context):
        """Test switching between Learning and Pro modes"""
        page = await browser_context.new_page()
        await page.goto(launcher_server)
        
        await page.wait_for_selector('#learningModeBtn')
        
        # Switch to Pro Mode
        await page.click('#proModeBtn')
        await page.wait_for_timeout(500)  # Wait for transition
        
        # Check Pro Mode is active
        pro_btn = page.locator('#proModeBtn')
        await expect(pro_btn).to_have_class('active')
        
        # Check Pro Mode tiles are visible
        pro_chooser = page.locator('#proModeChooser')
        await expect(pro_chooser).to_be_visible()
        
        # Check Learning Mode tiles are hidden
        learning_chooser = page.locator('#learningModeChooser')
        await expect(learning_chooser).to_have_css('display', 'none')
        
        # Switch back to Learning Mode
        await page.click('#learningModeBtn')
        await page.wait_for_timeout(500)
        
        # Check Learning Mode is active again
        learning_btn = page.locator('#learningModeBtn')
        await expect(learning_btn).to_have_class("active")
    
    async def test_mcp_basics_teaser_flow(self, launcher_server, browser_context):
        """Test the MCP Basics teaser modal flow"""
        page = await browser_context.new_page()
        await page.goto(launcher_server)
        
        await page.wait_for_selector('#learningModeChooser')
        
        # Click on MCP Basics tile
        mcp_basics_tile = page.locator('text=LEARN MCP BASICS').first()
        await mcp_basics_tile.click()
        
        # Wait for teaser modal to appear
        await page.wait_for_selector('#mcpBasicsTeaser', timeout=2000)
        teaser_modal = page.locator('#mcpBasicsTeaser')
        await expect(teaser_modal).to_be_visible()
        
        # Check teaser content
        await expect(page.locator('text=MCP = AI Superpowers!')).to_be_visible()
        await expect(page.locator("text=What you'll learn:")).to_be_visible()
        
        # Test "Let's Go!" button
        lets_go_btn = page.locator("text=🚀 Let's Go!")
        await expect(lets_go_btn).to_be_visible()
        await lets_go_btn.click()
        
        # Wait for "What is MCP?" modal to appear
        await page.wait_for_selector('#whatIsMCPModal', timeout=2000)
        what_is_mcp_modal = page.locator('#whatIsMCPModal')
        await expect(what_is_mcp_modal).to_be_visible()
        
        # Check educational content
        await expect(page.locator('text=What is MCP?')).to_be_visible()
        await expect(page.locator('text=Think of MCP like this')).to_be_visible()
    
    async def test_what_is_mcp_modal(self, launcher_server, browser_context):
        """Test the What is MCP? educational modal"""
        page = await browser_context.new_page()
        await page.goto(launcher_server)
        
        await page.wait_for_selector('#learningModeChooser')
        
        # Click "What is MCP?" button
        what_is_mcp_btn = page.locator('text=🤔 What is MCP?')
        await what_is_mcp_btn.click()
        
        # Wait for modal
        await page.wait_for_selector('#whatIsMCPModal')
        modal = page.locator('#whatIsMCPModal')
        await expect(modal).to_be_visible()
        
        # Check educational content sections
        await expect(page.locator('text=Without MCP')).to_be_visible()
        await expect(page.locator('text=With MCP')).to_be_visible()
        await expect(page.locator('text=Real Examples:')).to_be_visible()
        await expect(page.locator('text=Why Test MCP Tools?')).to_be_visible()
        
        # Test close button
        close_btn = page.locator('text=✕ Close')
        await close_btn.click()
        await page.wait_for_timeout(500)
        await expect(modal).to_have_css('display', 'none')
    
    async def test_guided_testing_teaser(self, launcher_server, browser_context):
        """Test the Guided Testing teaser modal"""
        page = await browser_context.new_page()
        await page.goto(launcher_server)
        
        await page.wait_for_selector('#learningModeChooser')
        
        # Click on Guided Testing tile
        guided_testing_tile = page.locator('text=GUIDED TESTING').first()
        await guided_testing_tile.click()
        
        # Wait for teaser modal
        await page.wait_for_selector('#guidedTestingTeaser', timeout=2000)
        teaser = page.locator('#guidedTestingTeaser')
        await expect(teaser).to_be_visible()
        
        # Check teaser content
        await expect(page.locator('text=Your First MCP Test!')).to_be_visible()
        await expect(page.locator('text=Interactive tool testing interface')).to_be_visible()
        
        # Test "Maybe Later" button
        maybe_later_btn = page.locator('#guidedTestingTeaser text=Maybe Later')
        await maybe_later_btn.click()
        await page.wait_for_timeout(500)
        
        # Teaser should be removed
        await expect(teaser).not_to_be_attached()
    
    async def test_explore_examples_teaser(self, launcher_server, browser_context):
        """Test the Explore Examples teaser modal"""
        page = await browser_context.new_page()
        await page.goto(launcher_server)
        
        await page.wait_for_selector('#learningModeChooser')
        
        # Click on Explore Examples tile
        examples_tile = page.locator('text=EXPLORE EXAMPLES').first()
        await examples_tile.click()
        
        # Wait for teaser modal
        await page.wait_for_selector('#exploreExamplesTeaser', timeout=2000)
        teaser = page.locator('#exploreExamplesTeaser')
        await expect(teaser).to_be_visible()
        
        # Check teaser content
        await expect(page.locator('text=Real-World Examples!')).to_be_visible()
        await expect(page.locator('text=Web scraping & search tools')).to_be_visible()
        await expect(page.locator('text=File system operations')).to_be_visible()
    
    async def test_troubleshooting_teaser(self, launcher_server, browser_context):
        """Test the Troubleshooting teaser modal"""
        page = await browser_context.new_page()
        await page.goto(launcher_server)
        
        await page.wait_for_selector('#learningModeChooser')
        
        # Click on Troubleshooting tile
        troubleshooting_tile = page.locator('text=TROUBLESHOOTING').first()
        await troubleshooting_tile.click()
        
        # Wait for teaser modal
        await page.wait_for_selector('#troubleshootingTeaser', timeout=2000)
        teaser = page.locator('#troubleshootingTeaser')
        await expect(teaser).to_be_visible()
        
        # Check teaser content
        await expect(page.locator('text=Troubleshooting Made Easy!')).to_be_visible()
        await expect(page.locator('text=Connection problems')).to_be_visible()
        await expect(page.locator('text=Configuration issues')).to_be_visible()
    
    async def test_learning_tiles_appearance(self, launcher_server, browser_context):
        """Test that all Learning Mode tiles appear correctly"""
        page = await browser_context.new_page()
        await page.goto(launcher_server)
        
        await page.wait_for_selector('#learningModeChooser')
        
        # Check all learning tiles are present
        tiles = [
            'LEARN MCP BASICS',
            'GUIDED TESTING',
            'EXPLORE EXAMPLES',
            'TROUBLESHOOTING'
        ]
        
        for tile_name in tiles:
            tile = page.locator(f'text={tile_name}').first()
            await expect(tile).to_be_visible()
        
        # Check learning-specific styling
        learning_tiles = page.locator('.learning-tile')
        await expect(learning_tiles).to_have_count(4)
        
        # Check progress indicators
        progress_indicators = page.locator('.learning-progress')
        await expect(progress_indicators).to_have_count(4)
    
    async def test_pro_mode_tiles_functionality(self, launcher_server, browser_context):
        """Test that Pro Mode tiles work correctly"""
        page = await browser_context.new_page()
        await page.goto(launcher_server)
        
        await page.wait_for_selector('#proModeBtn')
        
        # Switch to Pro Mode
        await page.click('#proModeBtn')
        await page.wait_for_timeout(500)
        
        # Check all pro tiles are present
        pro_tiles = [
            'INTERACTIVE',
            'API MODE',
            'MONITORING',
            'ENTERPRISE'
        ]
        
        for tile_name in pro_tiles:
            tile = page.locator(f'text={tile_name}').first()
            await expect(tile).to_be_visible()
        
        # Check demo links are present
        demo_links = page.locator('.tile-demo')
        await expect(demo_links).to_have_count(4)
    
    async def test_responsive_design(self, launcher_server, browser_context):
        """Test responsive design on different screen sizes"""
        page = await browser_context.new_page()
        
        # Test mobile viewport
        await page.set_viewport_size({"width": 375, "height": 667})
        await page.goto(launcher_server)
        
        await page.wait_for_selector('#learningModeChooser')
        
        # Check that tiles are still visible and functional
        learning_tiles = page.locator('.learning-tile')
        await expect(learning_tiles).to_have_count(4)
        
        # Check that mode toggle is visible
        mode_toggle = page.locator('.mode-toggle')
        await expect(mode_toggle).to_be_visible()
        
        # Test tablet viewport
        await page.set_viewport_size({"width": 768, "height": 1024})
        await page.wait_for_timeout(300)
        
        # Tiles should still be visible
        await expect(learning_tiles).to_have_count(4)
        
        # Test desktop viewport
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await page.wait_for_timeout(300)
        
        # All functionality should work
        await expect(learning_tiles).to_have_count(4)

# Run the tests
if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))