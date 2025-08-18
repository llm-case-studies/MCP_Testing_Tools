const { test, expect } = require('@playwright/test');

test('verify Playwright functionality', async ({ page }) => {
  console.log('🎭 Testing Playwright standalone functionality...');
  
  // Navigate to example.com
  await page.goto('https://example.com');
  
  // Verify page title
  await expect(page).toHaveTitle(/Example/);
  
  // Verify specific content
  const heading = page.locator('h1');
  await expect(heading).toContainText('Example Domain');
  
  // Take screenshot for verification
  await page.screenshot({ path: 'playwright-test-result.png' });
  
  console.log('✅ Playwright standalone test completed successfully!');
});