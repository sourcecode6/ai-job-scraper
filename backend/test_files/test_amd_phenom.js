const axios = require('axios');

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

async function run() {
  console.log('--- Testing AMD Phenom API endpoints ---');
  
  // Try Approach 1: /api/apply/v2/jobs
  try {
    const res = await axios.get('https://careers.amd.com/api/apply/v2/jobs', {
      params: { limit: 5, offset: 0, searchText: 'engineer', location: 'India', lang: 'en_global' },
      headers: {
        'User-Agent': UA,
        'Accept': 'application/json',
      },
      timeout: 10000,
    });
    console.log('Endpoint v2/jobs status:', res.status);
    console.log('Keys:', Object.keys(res.data));
    console.log('Data sample:', JSON.stringify(res.data).slice(0, 300));
  } catch (e) {
    console.log('Endpoint v2/jobs failed:', e.message, e.response?.status);
  }

  // Try Approach 2: Get base page session, then call widgets
  try {
    console.log('\n--- Fetching careers.amd.com/careers-home/jobs to get session ---');
    const pageRes = await axios.get('https://careers.amd.com/careers-home/jobs', {
      headers: { 'User-Agent': UA, 'Accept': 'text/html' },
      timeout: 15000,
    });
    const setCookies = pageRes.headers['set-cookie'] || [];
    const cookieHeader = setCookies.map(c => c.split(';')[0]).join('; ');
    const playEntry = setCookies.find(c => c.startsWith('PLAY_SESSION='));
    
    console.log('Cookies:', cookieHeader);
    
    if (playEntry) {
      const token = playEntry.split(';')[0].replace('PLAY_SESSION=', '').trim();
      const parts = token.split('.');
      if (parts[1]) {
        const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString('utf-8'));
        const csrf = payload.data?.csrfToken;
        console.log('CSRF Token:', csrf);
        
        console.log('\n--- Calling POST /widgets ---');
        const widRes = await axios.post('https://careers.amd.com/widgets', {
          sortBy: '', subsearch: '', from: 0, jobs: true, counts: false,
          all_fields: [], pageName: 'search-results', size: 10, clearAll: false,
          jdsource: 'facets', isSliderEnable: false, pageId: 'page4',
          siteType: 'external', keywords: '', global: true,
          lang: 'en_global', deviceType: 'desktop', country: 'global',
          ddoKey: 'refineSearch',
        }, {
          headers: {
            'User-Agent': UA,
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://careers.amd.com/careers-home/jobs',
            'x-csrf-token': csrf,
            'Cookie': cookieHeader,
          },
          timeout: 15000,
        });
        
        console.log('Widgets status:', widRes.status);
        console.log('Keys:', Object.keys(widRes.data));
        const r = widRes.data.refineSearch;
        console.log('refineSearch status:', r?.status);
        console.log('totalHits:', r?.data?.totalHits);
        console.log('jobs length:', r?.data?.jobs?.length);
        if (r?.data?.jobs?.[0]) {
          console.log('Sample job:', JSON.stringify(r.data.jobs[0]).slice(0, 400));
        }
      }
    } else {
      console.log('No PLAY_SESSION cookie found.');
    }
  } catch (e) {
    console.log('Widgets approach failed:', e.message, e.response?.status, e.response?.data);
  }
}

run().catch(console.error);
