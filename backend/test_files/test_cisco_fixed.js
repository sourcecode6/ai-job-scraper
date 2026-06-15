/**
 * Quick end-to-end test of the fixed Cisco scraper.
 * Run: node backend/src/scripts/test_cisco_fixed.js
 */
process.chdir(require('path').join(__dirname, '../..'));

const { scrapeCisco } = require('../acquisition/cisco');

const ciscoConfig = {
  name: 'Cisco Systems',
  ats: 'cisco',
  careerUrl: 'https://careers.cisco.com/global/en/search-results',
  filters: {
    keywords: 'engineer',
    location: 'India',
  },
};

async function run() {
  console.log('Testing Cisco scraper...\n');
  const jobs = await scrapeCisco(ciscoConfig);
  console.log(`\n✅ Cisco: ${jobs.length} jobs fetched`);
  if (jobs.length > 0) {
    const j = jobs[0];
    console.log('Sample job:');
    console.log('  Title:', j.jobTitle);
    console.log('  Location:', j.location);
    console.log('  Department:', j.department);
    console.log('  Type:', j.employmentType);
    console.log('  URL:', j.url);
    console.log('  Description snippet:', j.jobDescription?.slice(0, 150));
  }
}

run().catch(e => console.error('Fatal:', e.message));
