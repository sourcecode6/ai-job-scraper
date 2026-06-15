const { chromium } = require('playwright');

async function interceptAmd() {
  console.log('--- Intercepting AMD ---');
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-setuid-sandbox'] });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 800 }
  });
  const page = await context.newPage();

  // Listen to all network requests
  page.on('request', request => {
    const url = request.url();
    // Log any request that has /api/, /jobs, /widgets, or seems to be a data fetch
    if (url.includes('api') || url.includes('jobs') || url.includes('search') || url.includes('widget')) {
      console.log(`[AMD REQ] ${request.method()} ${url}`);
      try {
        const postData = request.postData();
        if (postData) {
          console.log(`  Body: ${postData}`);
        }
      } catch (e) {}
    }
  });

  page.on('response', async response => {
    const url = response.url();
    if (url.includes('api') || url.includes('jobs') || url.includes('search') || url.includes('widget')) {
      console.log(`[AMD RES] ${response.status()} ${url}`);
      try {
        const text = await response.text();
        console.log(`  Response Preview: ${text.slice(0, 400)}`);
      } catch (e) {}
    }
  });

  try {
    // Navigate to AMD careers page
    await page.goto('https://careers.amd.com/careers-home/jobs', { waitUntil: 'networkidle' });
    console.log('Navigated to AMD careers');
    await page.waitForTimeout(7000);
  } catch (err) {
    console.error('AMD navigation error:', err.message);
  } finally {
    await browser.close();
  }
}

interceptAmd().catch(console.error);
