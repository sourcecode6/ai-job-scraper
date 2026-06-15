const { chromium } = require('playwright');

async function interceptQualcomm() {
  console.log('--- Intercepting Qualcomm ---');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Listen to all network requests
  page.on('request', request => {
    const url = request.url();
    if (url.includes('/api/')) {
      console.log(`[QUALCOMM REQ] ${request.method()} ${url}`);
      try {
        const postData = request.postData();
        if (postData) {
          console.log(`  Body: ${postData}`);
        }
      } catch (e) {}
      console.log('  Headers:', JSON.stringify(request.headers(), null, 2));
    }
  });

  page.on('response', async response => {
    const url = response.url();
    if (url.includes('/api/')) {
      console.log(`[QUALCOMM RES] ${response.status()} ${url}`);
      try {
        const text = await response.text();
        console.log(`  Response Preview: ${text.slice(0, 300)}`);
      } catch (e) {}
    }
  });

  try {
    // Go to Qualcomm careers search page
    await page.goto('https://careers.qualcomm.com/careers', { waitUntil: 'networkidle' });
    // Let's type 'engineer' in the search bar or wait for some search request to happen
    console.log('Navigated to Qualcomm careers');
    await page.waitForTimeout(5000);
  } catch (err) {
    console.error('Qualcomm navigation error:', err.message);
  } finally {
    await browser.close();
  }
}

async function interceptCisco() {
  console.log('\n--- Intercepting Cisco ---');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  page.on('request', request => {
    const url = request.url();
    if (url.includes('/search') || url.includes('/api/')) {
      console.log(`[CISCO REQ] ${request.method()} ${url}`);
      try {
        const postData = request.postData();
        if (postData) {
          console.log(`  Body: ${postData}`);
        }
      } catch (e) {}
      console.log('  Headers:', JSON.stringify(request.headers(), null, 2));
    }
  });

  page.on('response', async response => {
    const url = response.url();
    if (url.includes('/search') || url.includes('/api/')) {
      console.log(`[CISCO RES] ${response.status()} ${url}`);
      try {
        const text = await response.text();
        console.log(`  Response Preview: ${text.slice(0, 300)}`);
      } catch (e) {}
    }
  });

  try {
    await page.goto('https://careers.cisco.com/global/en/search-results', { waitUntil: 'networkidle' });
    console.log('Navigated to Cisco search-results');
    await page.waitForTimeout(5000);
  } catch (err) {
    console.error('Cisco navigation error:', err.message);
  } finally {
    await browser.close();
  }
}

async function run() {
  await interceptQualcomm();
  await interceptCisco();
}

run();
