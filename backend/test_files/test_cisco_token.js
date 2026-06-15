const axios = require('axios');
const cheerio = require('cheerio');

async function checkCiscoHTML() {
  const url = 'https://careers.cisco.com/global/en/search-results?q=engineer&location=India';
  try {
    const res = await axios.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      }
    });

    console.log('Cisco page loaded. Status:', res.status);
    console.log('Headers:', res.headers);
    const cookies = res.headers['set-cookie'] || [];
    console.log('Cookies:', cookies);

    const $ = cheerio.load(res.data);
    
    // Look for meta tags with csrf
    $('meta').each((_, el) => {
      const name = $(el).attr('name');
      const content = $(el).attr('content');
      if (name && name.toLowerCase().includes('csrf')) {
        console.log(`Found meta: ${name} = ${content}`);
      }
    });

    // Search script tags for csrf
    $('script').each((_, el) => {
      const html = $(el).html() || '';
      if (html.includes('csrf') || html.includes('ph-token') || html.includes('CISCISGLOBAL')) {
        console.log(`Found in script:`, html.slice(0, 500));
      }
    });

  } catch (err) {
    console.error('Error:', err.message);
  }
}

checkCiscoHTML();
