/**
 * Quick smoke test for AMD scraper.
 * Run: node backend/src/scripts/test_amd_scraper.js
 */
process.chdir(require('path').join(__dirname, '../..'));

const { scrapeAmd } = require('../acquisition/amd');

const amdConfig = {
  name: 'AMD',
  ats: 'amd',
  careerUrl: 'https://careers.amd.com/careers-home/jobs',
  filters: {
    location: 'India',
    keywords: '',
  },
};

async function run() {
  console.log('=== Testing AMD Scraper ===');
  try {
    const jobs = await scrapeAmd(amdConfig);
    console.log(`✅ AMD: ${jobs.length} jobs fetched`);
    if (jobs.length > 0) {
      const j = jobs[0];
      console.log('Sample Job details:', {
        companyName: j.companyName,
        jobId: j.jobId,
        jobTitle: j.jobTitle,
        location: j.location,
        department: j.department,
        postedDate: j.postedDate,
        employmentType: j.employmentType,
        url: j.url,
        applyUrl: j.applyUrl,
        descSnippet: j.jobDescription ? j.jobDescription.slice(0, 100) + '...' : ''
      });
    }
  } catch (e) {
    console.error('❌ AMD error:', e);
  }
}

run();
