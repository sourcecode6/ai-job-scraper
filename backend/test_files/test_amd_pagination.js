const axios = require('axios');

async function testPagination() {
  const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';
  
  // Try limit or size parameters
  const urls = [
    'https://careers.amd.com/api/jobs?page=1&limit=50&location=India',
    'https://careers.amd.com/api/jobs?page=1&size=50&location=India',
    'https://careers.amd.com/api/jobs?page=1&pageSize=50&location=India',
    'https://careers.amd.com/api/jobs?page=2&location=India',
  ];

  for (const url of urls) {
    try {
      const res = await axios.get(url, { headers: { 'User-Agent': UA }, timeout: 10000 });
      console.log(`URL: ${url}`);
      console.log(`Jobs length: ${res.data?.jobs?.length}`);
      if (res.data?.jobs?.[0]) {
        console.log(`First job ID: ${res.data.jobs[0].id}`);
      }
    } catch (e) {
      console.error(`Error for ${url}:`, e.message);
    }
  }
}

testPagination();
