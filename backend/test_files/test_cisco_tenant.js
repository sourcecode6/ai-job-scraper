const axios = require('axios');
async function test() {
  // Cisco uses Phenom People ATS with tenant CISCISGLOBAL
  // Try various phenom API patterns
  const tenantId = 'CISCISGLOBAL';
  
  const attempts = [
    // Standard Phenom People jobs API
    {
      url: 'https://careers.cisco.com/api/apply/v2/jobs',
      params: { limit: 5, offset: 0, searchText: 'engineer', location: 'India' },
      headers: {
        'Accept': 'application/json',
        'x-ph-api-version': '3',
        'x-ph-origin-host': 'careers.cisco.com',
        'x-ph-referer': 'https://careers.cisco.com/global/en/search-results',
        'x-ph-tenant-id': tenantId,
        'User-Agent': 'Mozilla/5.0',
      }
    },
    // Try phenom CDN API
    {
      url: `https://cdn.phenompeople.com/CareerConnectResources/${tenantId}/api/jobs`,
      params: { limit: 5, searchText: 'engineer', location: 'India' },
      headers: { 'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0' }
    }
  ];
  
  for (const attempt of attempts) {
    try {
      const res = await axios.get(attempt.url, {
        params: attempt.params,
        headers: attempt.headers,
        timeout: 10000
      });
      console.log('URL:', attempt.url.slice(0,80));
      console.log('Status:', res.status);
      console.log('Type:', typeof res.data);
      if (typeof res.data === 'object') console.log('Data:', JSON.stringify(res.data).slice(0, 600));
    } catch(e) {
      console.log('URL:', attempt.url.slice(0,80));
      console.log('Failed:', e.message, 'status:', e.response?.status);
      if (e.response?.data) console.log('Error data:', JSON.stringify(e.response.data).slice(0,200));
    }
    console.log('---');
  }
}
test().catch(e => console.error(e.message));
