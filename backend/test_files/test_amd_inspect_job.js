const axios = require('axios');

async function run() {
  const url = 'https://careers.amd.com/api/jobs?page=1&sortBy=relevance&descending=false&internal=false&location=India';
  const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';
  
  try {
    const res = await axios.get(url, {
      headers: { 'User-Agent': UA },
      timeout: 10000,
    });
    
    if (res.data?.jobs?.[0]) {
      console.log('Keys of job:', Object.keys(res.data.jobs[0]));
      console.log('Keys of job.data:', Object.keys(res.data.jobs[0].data));
      console.log('Full job object:', JSON.stringify(res.data.jobs[0], null, 2));
    } else {
      console.log('No jobs found.');
    }
  } catch (e) {
    console.error('Error:', e.message);
  }
}

run();
