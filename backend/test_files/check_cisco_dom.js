const { chromium } = require('playwright');

async function checkDOM() {
  console.log('Checking Cisco DOM...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    await page.goto('https://careers.cisco.com/global/en/search-results?q=engineer&location=India', {
      waitUntil: 'networkidle',
      timeout: 30000
    });

    console.log('Page loaded.');
    await page.waitForTimeout(5000);

    const bodyText = await page.innerText('body');
    console.log('Body text length:', bodyText.length);
    console.log('Includes engineer?', bodyText.toLowerCase().includes('engineer'));
    console.log('Includes Software?', bodyText.toLowerCase().includes('software'));

    // Print all headers or specific elements
    const jobTitles = await page.evaluate(() => {
      const titles = Array.from(document.querySelectorAll('[class*="job-title"], [class*="jobTitle"], [data-ph-id*="job-title"]'));
      return titles.map(el => el.innerText.trim()).filter(Boolean);
    });

    console.log('Found job titles in DOM:', jobTitles);

    // Print all links
    const links = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('a'))
        .map(a => ({ text: a.innerText.trim(), href: a.href }))
        .filter(link => link.href.includes('/job/') || link.href.includes('/jobs/'));
    });
    console.log('Found job links:', links.slice(0, 10));

  } catch (err) {
    console.error('Error:', err.message);
  } finally {
    await browser.close();
  }
}

checkDOM();
