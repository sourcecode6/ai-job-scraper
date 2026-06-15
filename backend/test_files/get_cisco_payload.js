const { chromium } = require('playwright');

async function getCiscoPayload() {
  console.log('Navigating to Cisco Careers to capture widgets payloads...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  page.on('request', request => {
    const url = request.url();
    if (url.includes('careers.cisco.com/widgets')) {
      console.log(`\n--- CISCO REQ ---`);
      console.log('Method:', request.method());
      console.log('Headers:', JSON.stringify(request.headers(), null, 2));
      console.log('Body:', request.postData());
    }
  });

  page.on('response', async response => {
    const url = response.url();
    if (url.includes('careers.cisco.com/widgets')) {
      console.log(`--- CISCO RES (${response.status()}) ---`);
      try {
        const text = await response.text();
        console.log('Response:', text.slice(0, 1000));
      } catch (e) {
        console.log('Could not get response body:', e.message);
      }
    }
  });

  try {
    await page.goto('https://careers.cisco.com/global/en/search-results?q=engineer&location=India', { waitUntil: 'networkidle' });
    await page.waitForTimeout(10000);
  } catch (err) {
    console.error('Cisco Navigation error:', err.message);
  } finally {
    await browser.close();
  }
}

getCiscoPayload();
