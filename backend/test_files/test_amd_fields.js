const axios = require('axios');

async function run() {
  const url = 'https://careers.amd.com/api/jobs?page=1&limit=2&location=India';
  const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';
  
  try {
    const res = await axios.get(url, { headers: { 'User-Agent': UA } });
    if (res.data?.jobs) {
      console.log('Number of jobs:', res.data.jobs.length);
      const job = res.data.jobs[0];
      console.log('Job root keys:', Object.keys(job));
      if (job.data) {
        console.log('Job data keys:', Object.keys(job.data));
        console.log('Job ID from data.req_id:', job.data.req_id);
        console.log('Job ID from data.slug:', job.data.slug);
        console.log('Job title:', job.data.title);
        console.log('Job country:', job.data.country);
        console.log('Job city:', job.data.city);
        console.log('Job full_location:', job.data.full_location);
        console.log('Job short_location:', job.data.short_location);
        console.log('Job categories:', job.data.category);
        console.log('Job posted_date:', job.data.posted_date);
        console.log('Job apply_url:', job.data.apply_url);
        console.log('Job canonical_url:', job.data.meta_data?.canonical_url);
      }
    }
  } catch (e) {
    console.error('Error:', e.message);
  }
}

run();
