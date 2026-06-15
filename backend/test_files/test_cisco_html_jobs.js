const axios = require('axios');
const fs = require('fs');

async function searchHTML() {
  const url = 'https://jobs.cisco.com/jobs/SearchJobs?location=India';
  try {
    const res = await axios.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      }
    });

    console.log('Fetched HTML length:', res.data.length);
    
    // Save to a file so we can analyze it
    fs.writeFileSync('cisco_raw.html', res.data);
    console.log('Saved to cisco_raw.html');

    // Search for keywords
    const keywords = ['jobSeqNo', 'eagerLoad', 'jobs', 'position', 'title', 'refineSearch'];
    for (const kw of keywords) {
      const idx = res.data.indexOf(kw);
      console.log(`Keyword "${kw}" found at index:`, idx);
    }

  } catch (err) {
    console.error('Error:', err.message);
  }
}

searchHTML();
