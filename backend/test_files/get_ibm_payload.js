const { chromium } = require('playwright');

async function getIBMPayload() {
  console.log('Navigating to IBM Careers to capture exact payload...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  page.on('request', request => {
    const url = request.url();
    if (url.includes('www-api.ibm.com/search/api/v2')) {
      console.log('--- IBM API REQUEST FOUND ---');
      console.log('URL:', url);
      console.log('Method:', request.method());
      console.log('Headers:', JSON.stringify(request.headers(), null, 2));
      console.log('Full Body:', request.postData());
    }
  });

  try {
    await page.goto('https://www.ibm.com/careers/search?country=IN&category=Software+Engineering', { waitUntil: 'networkidle' });
    await page.waitForTimeout(5000);
  } catch (err) {
    console.error('IBM Navigation error:', err.message);
  } finally {
    await browser.close();
  }
}

getIBMPayload();
