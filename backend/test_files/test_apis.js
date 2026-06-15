const axios = require('axios');

async function testArista() {
  console.log('Testing Arista Networks via SmartRecruiters API...');
  try {
    const listUrl = "https://api.smartrecruiters.com/v1/companies/AristaNetworks/postings";
    const res = await axios.get(listUrl, { headers: { 'User-Agent': 'Mozilla/5.0' } });
    console.log(`Arista: Found ${res.data.content?.length || 0} postings`);
    if (res.data.content && res.data.content.length > 0) {
      console.log('Sample posting:', JSON.stringify(res.data.content[0], null, 2));
      const detailUrl = `https://api.smartrecruiters.com/v1/companies/AristaNetworks/postings/${res.data.content[0].id}`;
      const detailRes = await axios.get(detailUrl, { headers: { 'User-Agent': 'Mozilla/5.0' } });
      console.log('Sample detail:', JSON.stringify(detailRes.data, null, 2).slice(0, 500));
    }
  } catch (err) {
    console.error('Arista error:', err.message);
  }
}

async function testQualcomm() {
  console.log('\nTesting Qualcomm PCSX API...');
  try {
    const searchUrl = "https://careers.qualcomm.com/api/pcsx/search";
    const body = {
      "query": "engineer",
      "location": "India",
      "limit": 20,
      "offset": 0
    };
    const res = await axios.post(searchUrl, body, {
      headers: {
        'User-Agent': 'Mozilla/5.0',
        'Content-Type': 'application/json'
      }
    });
    console.log(`Qualcomm status: ${res.status}`);
    console.log('Qualcomm keys:', Object.keys(res.data));
    if (res.data.positions && res.data.positions.length > 0) {
      console.log(`Qualcomm positions found: ${res.data.positions.length}`);
      console.log('Sample Qualcomm position:', JSON.stringify(res.data.positions[0], null, 2));
    } else {
      console.log('Sample full Qualcomm response:', JSON.stringify(res.data, null, 2).slice(0, 1000));
    }
  } catch (err) {
    console.error('Qualcomm error:', err.message);
    if (err.response) {
      console.error('Qualcomm status:', err.response.status, err.response.data);
    }
  }
}

async function testCisco() {
  console.log('\nTesting Cisco Systems...');
  try {
    // Let's test the search-results URL
    const baseUrl = "https://careers.cisco.com/global/en/search-results";
    const res = await axios.get(baseUrl, {
      params: {
        q: 'engineer',
        location: 'India',
        from: 0,
        s: 1
      },
      headers: { 'User-Agent': 'Mozilla/5.0' }
    });
    console.log(`Cisco status: ${res.status}`);
    console.log('Cisco preview:', typeof res.data === 'object' ? JSON.stringify(res.data, null, 2).slice(0, 1000) : String(res.data).slice(0, 1000));
  } catch (err) {
    console.error('Cisco error:', err.message);
  }
}

async function runAll() {
  await testArista();
  await testQualcomm();
  await testCisco();
}

runAll();
