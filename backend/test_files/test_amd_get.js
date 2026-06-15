const axios = require('axios');

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

async function run() {
  console.log('--- Testing AMD API GET endpoint ---');
  try {
    const urls = [
      'https://careers.amd.com/api/jobs?page=1&sortBy=relevance&descending=false&internal=false',
      'https://careers.amd.com/api/jobs?page=1&sortBy=relevance&descending=false&internal=false&keywords=engineer',
      'https://careers.amd.com/api/jobs?page=1&sortBy=relevance&descending=false&internal=false&location=India',
      'https://careers.amd.com/api/jobs?page=1&sortBy=relevance&descending=false&internal=false&country=IN',
      'https://careers.amd.com/api/jobs?page=1&sortBy=relevance&descending=false&internal=false&location=Bengaluru',
    ];

    for (const url of urls) {
      console.log(`\nFetching: ${url}`);
      const res = await axios.get(url, {
        headers: {
          'User-Agent': UA,
          'Accept': 'application/json',
        },
        timeout: 10000,
      });
      console.log('Status:', res.status);
      console.log('Total jobs found/returned:', res.data?.jobs?.length);
      console.log('Pagination info:', {
        total: res.data?.total,
        pages: res.data?.pages,
        limit: res.data?.limit,
        page: res.data?.page,
      });
      if (res.data?.jobs?.[0]) {
        const first = res.data.jobs[0].data;
        console.log('Sample job properties:', {
          title: first.title,
          req_id: first.req_id,
          location: first.location,
          locations: first.locations,
          locations_alt: first.locations_alt,
          country: first.country,
          city: first.city,
          primary_location: first.primary_location,
        });
      }
    }
  } catch (e) {
    console.error('Failed:', e.message);
  }
}

run();
