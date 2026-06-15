const axios = require('axios');
const cheerio = require('cheerio');

async function testOldCisco() {
  const url = 'https://jobs.cisco.com/jobs/SearchJobs?location=India';
  try {
    const res = await axios.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      }
    });

    console.log('Status:', res.status);
    console.log('HTML length:', res.data.length);

    const $ = cheerio.load(res.data);
    
    // Check if there are tables or listings
    const tableRows = $('table tr').length;
    console.log('Table rows found:', tableRows);
    
    // Print first 500 chars of body
    console.log('HTML preview:', res.data.slice(0, 1000));

  } catch (err) {
    console.error('Error:', err.message);
  }
}

testOldCisco();
