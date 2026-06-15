const { chromium } = require('playwright');

const IGNORE_EXTS = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.css', '.js', '.woff', '.woff2', '.ttf', '.ico', '.jsonld', 'google-analytics', 'doubleclick', 'facebook.com', 'linkedin.com', 'hotjar'];

function shouldLog(url) {
  const lowercase = url.toLowerCase();
  for (const ext of IGNORE_EXTS) {
    if (lowercase.includes(ext)) return false;
  }
  return true;
}

async function inspectSite(name, url) {
  console.log(`\n=================== Inspecting ${name} ===================`);
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  });
  const page = await context.newPage();

  page.on('request', request => {
    const reqUrl = request.url();
    if (shouldLog(reqUrl)) {
      console.log(`[${name} REQ] ${request.method()} ${reqUrl}`);
      try {
        const postData = request.postData();
        if (postData) {
          console.log(`  Body: ${postData.slice(0, 500)}`);
        }
      } catch (e) {}
    }
  });

  page.on('response', async response => {
    const resUrl = response.url();
    if (shouldLog(resUrl)) {
      console.log(`[${name} RES] ${response.status()} ${resUrl}`);
      try {
        const text = await response.text();
        console.log(`  Response Preview: ${text.slice(0, 400)}`);
      } catch (e) {}
    }
  });

  try {
    await page.goto(url, { waitUntil: 'load', timeout: 30000 });
    console.log(`[${name}] Navigated, waiting 8 seconds for dynamic calls...`);
    await page.waitForTimeout(8000);
  } catch (err) {
    console.error(`[${name}] Navigation error:`, err.message);
  } finally {
    await browser.close();
  }
}

async function run() {
  await inspectSite('Microsoft', 'https://jobs.careers.microsoft.com/global/en/search?lc=India&l=en_us&pg=1&pgSz=20');
  await inspectSite('IBM', 'https://www.ibm.com/careers/search?country=IN&category=Software+Engineering');
  await inspectSite('Ericsson', 'https://jobs.ericsson.com/careers?location=India');
  await inspectSite('Cisco', 'https://careers.cisco.com/global/en/search-results?q=engineer&location=India');
}

run();
