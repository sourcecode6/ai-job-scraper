const { chromium } = require('playwright');

async function compare() {
  console.log('Comparing tokens...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  let csrfHeader = '';

  page.on('request', request => {
    const url = request.url();
    if (url.includes('careers.cisco.com/widgets')) {
      const headers = request.headers();
      if (headers['x-csrf-token']) {
        csrfHeader = headers['x-csrf-token'];
        console.log('Intercepted x-csrf-token header:', csrfHeader);
      }
    }
  });

  try {
    await page.goto('https://careers.cisco.com/global/en/search-results?q=engineer&location=India', { waitUntil: 'networkidle' });
    
    // Get cookies
    const cookies = await context.cookies();
    const playSessionCookie = cookies.find(c => c.name === 'PLAY_SESSION');
    if (playSessionCookie) {
      console.log('PLAY_SESSION Cookie value:', playSessionCookie.value);
      const parts = playSessionCookie.value.split('.');
      const payloadBuf = Buffer.from(parts[1], 'base64');
      const payloadJson = JSON.parse(payloadBuf.toString('utf-8'));
      console.log('Decoded JSESSIONID:', payloadJson.data?.JSESSIONID);
      console.log('Decoded csrfToken:', payloadJson.data?.csrfToken);
      console.log('Are they equal?', payloadJson.data?.csrfToken === csrfHeader);
    } else {
      console.log('No PLAY_SESSION cookie found!');
    }
  } catch (err) {
    console.error(err);
  } finally {
    await browser.close();
  }
}

compare();
