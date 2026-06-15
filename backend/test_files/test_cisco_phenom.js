/**
 * Tests Cisco via Phenom People API (their actual ATS backend).
 * Cisco uses Phenom People with tenant CISCISGLOBAL.
 */
const axios = require('axios');

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

async function test() {
  // Approach 1: Phenom API with correct host header
  console.log('\n=== Approach 1: Phenom API with Host header ===');
  try {
    const res = await axios.get('https://careers.cisco.com/api/apply/v2/jobs', {
      params: { limit: 10, offset: 0, searchText: 'engineer', location: 'India', lang: 'en_global' },
      headers: {
        'User-Agent': UA,
        'Accept': 'application/json',
        'Host': 'careers.cisco.com',
        'Referer': 'https://careers.cisco.com/global/en/search-results',
        'Origin': 'https://careers.cisco.com',
      },
      timeout: 15000,
    });
    console.log('Status:', res.status, '| Data:', JSON.stringify(res.data).slice(0, 400));
  } catch (e) { console.log('Error:', e.message, e.response?.status); }

  // Approach 2: Try the Phenom search API with tenantKey
  console.log('\n=== Approach 2: Phenom with tenantKey param ===');
  try {
    const res = await axios.get('https://careers.cisco.com/api/apply/v2/jobs', {
      params: { limit: 10, offset: 0, searchText: 'engineer', location: 'India', tenantKey: 'CISCISGLOBAL', lang: 'en_global' },
      headers: { 'User-Agent': UA, 'Accept': 'application/json' },
      timeout: 15000,
    });
    console.log('Status:', res.status, '| Data:', JSON.stringify(res.data).slice(0, 400));
  } catch (e) { console.log('Error:', e.message, e.response?.status); }

  // Approach 3: Try direct Phenom infrastructure API
  console.log('\n=== Approach 3: Direct Phenom CDN API ===');
  const phenomApis = [
    'https://careers.cisco.com/api/apply/v3/jobs?limit=5&offset=0&searchText=engineer&location=India',
    'https://careers.cisco.com/api/apply/v1/jobs?limit=5&offset=0&searchText=engineer&location=India',
    'https://careers.cisco.com/en/api/apply/v2/jobs?limit=5&offset=0&searchText=engineer&location=India',
    'https://careers.cisco.com/global/en/api/apply/v2/jobs?limit=5&offset=0',
  ];
  for (const url of phenomApis) {
    try {
      const res = await axios.get(url, {
        headers: { 'User-Agent': UA, 'Accept': 'application/json', 'Referer': 'https://careers.cisco.com/' },
        timeout: 10000,
      });
      if (typeof res.data === 'object') {
        console.log('URL:', url.slice(35));
        console.log('  Status:', res.status, '| Keys:', Object.keys(res.data));
        console.log('  Data:', JSON.stringify(res.data).slice(0, 300));
      }
    } catch (e) { console.log('URL:', url.slice(35), '| Error:', e.message, e.response?.status); }
  }

  // Approach 4: Playwright-style — simulate what the browser does to get a valid session
  // After a page load the JS calls /widgets with a properly initialized session.
  // Try fetching the page first, then calling widgets
  console.log('\n=== Approach 4: Fresh session then widgets ===');
  try {
    // GET base page first
    const pageRes = await axios.get('https://careers.cisco.com/global/en/search-results', {
      headers: { 'User-Agent': UA, 'Accept': 'text/html' },
      timeout: 20000,
    });
    const setCookies = pageRes.headers['set-cookie'] || [];
    const cookieHeader = setCookies.map(c => c.split(';')[0]).join('; ');
    const playEntry = setCookies.find(c => c.startsWith('PLAY_SESSION='));
    if (!playEntry) { console.log('No PLAY_SESSION'); return; }
    const token = playEntry.split(';')[0].replace('PLAY_SESSION=', '').trim();
    const parts = token.split('.');
    const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString('utf-8'));
    const csrf = payload.data?.csrfToken;

    // POST /widgets with a simple body — no location filter first
    const widRes = await axios.post('https://careers.cisco.com/widgets', {
      sortBy: '', subsearch: '', from: 0, jobs: true, counts: false,
      all_fields: [], pageName: 'search-results', size: 5, clearAll: false,
      jdsource: 'facets', isSliderEnable: false, pageId: 'page4',
      siteType: 'external', keywords: 'software', global: true,
      lang: 'en_global', deviceType: 'desktop', country: 'global',
      refNum: 'CISCISGLOBAL', ddoKey: 'refineSearch',
    }, {
      headers: {
        'User-Agent': UA,
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://careers.cisco.com/global/en/search-results',
        'x-csrf-token': csrf,
        'Cookie': cookieHeader,
      },
      timeout: 20000,
    });
    console.log('Widgets keys:', Object.keys(widRes.data));
    const r = widRes.data.refineSearch;
    console.log('refineSearch.status:', r?.status);
    console.log('totalHits:', r?.data?.totalHits);
    console.log('jobs:', r?.data?.jobs?.length, '| facets:', r?.data?.facets ? Object.keys(r.data.facets) : 'none');
    if (r?.data?.jobs?.[0]) console.log('First job:', JSON.stringify(r.data.jobs[0]).slice(0, 300));
  } catch (e) { console.log('Error:', e.message, e.response?.status); }
}

test().catch(e => console.error('Fatal:', e.message));
