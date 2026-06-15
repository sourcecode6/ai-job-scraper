const axios = require('axios');

const USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

async function testEightfold(name, searchUrl, domain, location) {
  console.log(`\nTesting Eightfold for ${name}...`);
  try {
    const res = await axios.get(searchUrl, {
      params: {
        domain: domain,
        location: location,
        query: 'engineer',
        start: 0,
        num: 5
      },
      headers: {
        'User-Agent': USER_AGENT,
        'Accept': 'application/json, text/plain, */*'
      }
    });

    console.log(`${name} status: ${res.status}`);
    const positions = res.data.data?.positions || [];
    console.log(`${name} found ${positions.length} positions.`);
    if (positions.length > 0) {
      console.log('Sample Position:', JSON.stringify(positions[0], null, 2));
      // Test details
      const detailUrl = searchUrl.replace('/search', '/position_details');
      const detailRes = await axios.get(detailUrl, {
        params: {
          position_id: positions[0].id,
          domain: domain,
          hl: 'en'
        },
        headers: {
          'User-Agent': USER_AGENT,
          'Accept': 'application/json, text/plain, */*'
        }
      });
      console.log(`${name} Detail status: ${detailRes.status}`);
      const jobDesc = detailRes.data.data?.jobDescription || '';
      console.log(`${name} Description length:`, jobDesc.length);
      console.log(`${name} Description snippet:`, jobDesc.slice(0, 200));
    }
  } catch (err) {
    console.error(`${name} error:`, err.message);
  }
}

async function run() {
  await testEightfold(
    'Microsoft',
    'https://apply.careers.microsoft.com/api/pcsx/search',
    'microsoft.com',
    'India'
  );
  await testEightfold(
    'Qualcomm',
    'https://careers.qualcomm.com/api/pcsx/search',
    'qualcomm.com',
    'India'
  );
  await testEightfold(
    'Ericsson',
    'https://jobs.ericsson.com/api/pcsx/search',
    'ericsson.com',
    'India'
  );
}

run();
