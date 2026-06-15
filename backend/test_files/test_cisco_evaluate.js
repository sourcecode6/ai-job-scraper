const { chromium } = require('playwright');

async function testCiscoEvaluate() {
  console.log('Testing Cisco widgets query inside browser context...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  let csrfToken = '';

  // Intercept requests to get the CSRF token from the headers
  page.on('request', request => {
    if (request.url().includes('careers.cisco.com/widgets')) {
      const token = request.headers()['x-csrf-token'];
      if (token) {
        csrfToken = token;
      }
    }
  });

  try {
    await page.goto('https://careers.cisco.com/global/en/search-results?q=engineer&location=India', {
      waitUntil: 'networkidle',
      timeout: 30000
    });

    if (!csrfToken) {
      throw new Error('Could not capture CSRF token from widgets request');
    }

    console.log('Captured CSRF Token:', csrfToken);

    // Call widgets search inside the page context
    const jobsData = await page.evaluate(async ({ csrfToken }) => {
      const url = 'https://careers.cisco.com/widgets';
      const body = {
        sortBy: "",
        subsearch: "",
        from: 0,
        jobs: true,
        counts: true,
        all_fields: ["category", "raasJobRequisitionType", "country", "state", "city", "type", "RemoteType"],
        pageName: "search-results",
        size: 20,
        clearAll: false,
        jdsource: "facets",
        isSliderEnable: false,
        pageId: "page4",
        siteType: "external",
        keywords: "engineer",
        global: true,
        selected_fields: {
          location: ["India"]
        },
        lang: "en_global",
        deviceType: "desktop",
        country: "global",
        refNum: "CISCISGLOBAL",
        ddoKey: "eagerLoadRefineSearchSession"
      };

      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-csrf-token': csrfToken
        },
        body: JSON.stringify(body)
      });

      return res.json();
    }, { csrfToken });

    const eagerLoad = jobsData.eagerLoadRefineSearchSession;
    if (eagerLoad) {
      console.log('eagerLoad Status:', eagerLoad.status);
      const data = eagerLoad.data;
      if (data) {
        console.log('Total jobs found:', data.totalHits || data.hits);
        if (data.jobs && data.jobs.length > 0) {
          console.log(`Successfully retrieved ${data.jobs.length} jobs!`);
          console.log('Sample Job:', JSON.stringify(data.jobs[0], null, 2).slice(0, 1000));
        }
      }
    } else {
      console.log('Response:', JSON.stringify(jobsData, null, 2));
    }

  } catch (err) {
    console.error('Error:', err.message);
  } finally {
    await browser.close();
  }
}

testCiscoEvaluate();
