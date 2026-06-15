const axios = require('axios');

async function testCiscoAPI() {
  console.log('Testing Cisco widgets API...');
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

  try {
    const res = await axios.post(url, body, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Content-Type': 'application/json',
        'Referer': 'https://careers.cisco.com/global/en/search-results?q=engineer&location=India'
      }
    });

    console.log('Cisco Status:', res.status);
    console.log('Keys:', Object.keys(res.data));
    const eagerLoad = res.data.eagerLoadRefineSearchSession;
    if (eagerLoad) {
      console.log('eagerLoad Keys:', Object.keys(eagerLoad));
      console.log('Status inside:', eagerLoad.status);
      const data = eagerLoad.data;
      if (data) {
        console.log('Data keys:', Object.keys(data));
        console.log('Total jobs found:', data.totalHits || data.hits);
        if (data.jobs && data.jobs.length > 0) {
          console.log('First job snippet:', JSON.stringify(data.jobs[0], null, 2).slice(0, 800));
        } else {
          console.log('No jobs in response, data preview:', JSON.stringify(data, null, 2).slice(0, 1000));
        }
      }
    } else {
      console.log('Full response preview:', JSON.stringify(res.data, null, 2).slice(0, 1000));
    }
  } catch (err) {
    console.error('Error fetching Cisco:', err.message);
    if (err.response) {
      console.error('Response data:', err.response.data);
    }
  }
}

testCiscoAPI();
