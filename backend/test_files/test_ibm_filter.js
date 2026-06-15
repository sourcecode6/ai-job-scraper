const axios = require('axios');

async function testFilter() {
  const url = 'https://www-api.ibm.com/search/api/v2';
  const body = {
    appId: "careers",
    scopes: ["careers2"],
    query: {
      bool: {
        must: [
          { match: { field_keyword_05: "India" } },
          { match: { field_keyword_08: "Software Engineering" } }
        ]
      }
    },
    size: 50,
    lang: "zz",
    _source: [
      "_id", "title", "url", "description", "language", "field_keyword_17", "field_keyword_08", "field_keyword_05", "field_keyword_19"
    ]
  };

  try {
    const res = await axios.post(url, body, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Content-Type': 'application/json'
      }
    });

    console.log('IBM Filtered Total:', res.data.hits?.total?.value);
    if (res.data.hits?.hits) {
      console.log(`Retrieved ${res.data.hits.hits.length} jobs.`);
      res.data.hits.hits.slice(0, 3).forEach((h, i) => {
        console.log(`Hit ${i + 1}:`, JSON.stringify(h._source, null, 2));
      });
    }
  } catch (err) {
    console.error('IBM filter query error:', err.message);
  }
}

testFilter();
