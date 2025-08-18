// Simple Playwright test to verify functionality
const { test, expect } = require('@playwright/test');

test('basic Playwright functionality test', async ({ page }) => {
  // Navigate to a simple page
  await page.goto('https://example.com');
  
  // Check the title
  await expect(page).toHaveTitle(/Example/);
  
  // Take a screenshot
  await page.screenshot({ path: 'test-screenshot.png' });
  
  console.log('✅ Playwright standalone test passed!');
});