/**
 * Deep investigation of Cisco's widgets API.
 * Tests multiple ddoKeys and request variations to find what actually returns jobs.
 */
const axios = require('axios');

async function parseCsrf(pageUrl) {
  const res = await axios.get(pageUrl, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9',
    },
    timeout: 20000,
  });
  const setCookies = res.headers['set-cookie'] || [];
  const cookieHeader = setCookies.map(c => c.split(';')[0]).join('; ');
  const playEntry = setCookies.find(c => c.startsWith('PLAY_SESSION='));
  if (!playEntry) throw new Error('No PLAY_SESSION');
  const token = playEntry.split(';')[0].replace('PLAY_SESSION=', '').trim();
  const parts = token.split('.');
  const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString('utf-8'));
  return { cookieHeader, csrfToken: payload.data?.csrfToken };
}

async function tryWidgets(pageUrl, cookieHeader, csrfToken, ddoKey, extraBody = {}) {
  const body = {
    sortBy: '', subsearch: '', from: 0, jobs: true, counts: true,
    all_fields: ['category', 'country', 'state', 'city', 'type', 'RemoteType'],
    pageName: 'search-results', size: 10, clearAll: false,
    jdsource: 'facets', isSliderEnable: false, pageId: 'page4',
    siteType: 'external', keywords: 'engineer', global: true,
    selected_fields: { location: ['India'] },
    lang: 'en_global', deviceType: 'desktop', country: 'global',
    refNum: 'CISCISGLOBAL', ddoKey,
    ...extraBody,
  };

  const res = await axios.post('https://careers.cisco.com/widgets', body, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'Content-Type': 'application/json',
      'Accept': 'application/json, text/plain, */*',
      'Accept-Language': 'en-US,en;q=0.9',
      'Referer': pageUrl,
      'x-csrf-token': csrfToken,
      'Cookie': cookieHeader,
    },
    timeout: 20000,
  });

  const data = res.data;
  const keys = Object.keys(data);
  console.log(`\n[ddoKey=${ddoKey}] Response keys:`, keys);

  for (const key of keys) {
    const val = data[key];
    if (typeof val === 'object' && val !== null) {
      console.log(`  ${key}.status:`, val.status);
      if (val.data) {
        console.log(`  ${key}.data.totalHits:`, val.data.totalHits);
        console.log(`  ${key}.data.jobs count:`, val.data.jobs?.length ?? 'N/A');
        if (val.data.jobs?.[0]) {
          console.log(`  First job title:`, val.data.jobs[0].title);
        }
      } else {
        console.log(`  ${key} (no .data):`, JSON.stringify(val).slice(0, 200));
      }
    }
  }
  return data;
}

async function run() {
  const pageUrl = 'https://careers.cisco.com/global/en/search-results?q=engineer&location=India';
  console.log('Step 1: Getting CSRF token...');
  const { cookieHeader, csrfToken } = await parseCsrf(pageUrl);
  console.log('CSRF token:', csrfToken);

  // Test every known ddoKey variation
  const ddoKeys = [
    'eagerLoadRefineSearchSession',
    'refineSearch',
    'searchResults',
    'jobSearch',
    'searchPage',
  ];

  for (const key of ddoKeys) {
    try {
      await tryWidgets(pageUrl, cookieHeader, csrfToken, key);
    } catch (e) {
      console.log(`[ddoKey=${key}] ERROR:`, e.message, e.response?.status);
    }
  }

  // Also try without selected_fields (no location filter)
  console.log('\n--- Trying without location filter ---');
  try {
    const res = await axios.post('https://careers.cisco.com/widgets', {
      sortBy: '', subsearch: '', from: 0, jobs: true, counts: true,
      all_fields: ['category', 'country', 'city'],
      pageName: 'search-results', size: 10, clearAll: false,
      jdsource: 'facets', isSliderEnable: false, pageId: 'page4',
      siteType: 'external', keywords: 'software engineer', global: true,
      lang: 'en_global', deviceType: 'desktop', country: 'global',
      refNum: 'CISCISGLOBAL', ddoKey: 'refineSearch',
    }, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/plain, */*',
        'Referer': pageUrl,
        'x-csrf-token': csrfToken,
        'Cookie': cookieHeader,
      },
      timeout: 20000,
    });
    const data = res.data;
    console.log('Keys:', Object.keys(data));
    const r = data.refineSearch;
    if (r) {
      console.log('status:', r.status);
      console.log('totalHits:', r.data?.totalHits);
      console.log('jobs count:', r.data?.jobs?.length);
      if (r.data?.jobs?.[0]) console.log('First job:', JSON.stringify(r.data.jobs[0]).slice(0, 300));
    }
  } catch(e) {
    console.log('No-filter error:', e.message);
  }
}

run().catch(e => console.error('Fatal:', e.message));
