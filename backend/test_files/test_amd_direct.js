const axios = require('axios');

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

async function run() {
  console.log('--- Fetching careers.amd.com/careers-home/jobs ---');
  try {
    const pageRes = await axios.get('https://careers.amd.com/careers-home/jobs', {
      headers: {
        'User-Agent': UA,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
      },
      timeout: 15000,
    });
    const setCookies = pageRes.headers['set-cookie'] || [];
    const cookieHeader = setCookies.map(c => c.split(';')[0]).join('; ');
    console.log('Got Cookies:', cookieHeader);

    console.log('--- Calling widgets endpoint ---');
    const body = {
      sortBy: '',
      subsearch: '',
      from: 0,
      jobs: true,
      counts: false,
      all_fields: [],
      pageName: 'search-results',
      size: 10,
      clearAll: false,
      jdsource: 'facets',
      isSliderEnable: false,
      pageId: 'page20',
      siteType: 'external',
      keywords: '',
      global: true,
      lang: 'en-US',
      deviceType: 'desktop',
      country: 'US',
      refNum: 'AMDA005GLOBAL',
      ddoKey: 'refineSearch'
    };

    const res = await axios.post('https://careers.amd.com/widgets', body, {
      headers: {
        'User-Agent': UA,
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://careers.amd.com/careers-home/jobs',
        'Cookie': cookieHeader,
      },
      timeout: 15000,
    });

    console.log('Widgets status:', res.status);
    console.log('Keys:', Object.keys(res.data));
    const r = res.data.refineSearch;
    console.log('refineSearch status:', r?.status);
    console.log('totalHits:', r?.data?.totalHits);
    console.log('jobs length:', r?.data?.jobs?.length);
    if (r?.data?.jobs?.[0]) {
      console.log('Sample job:', JSON.stringify(r.data.jobs[0], null, 2));
    }
  } catch (e) {
    console.error('Failed:', e.message);
    if (e.response) {
      console.error('Response Status:', e.response.status);
      console.error('Response Data:', e.response.data);
    }
  }
}

run();
