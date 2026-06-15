/**
 * Quick smoke test for all new scrapers.
 * Run: node backend/src/scripts/test_new_scrapers.js
 */
process.chdir(require('path').join(__dirname, '../..'));

const { scrapeSmartRecruiters } = require('../acquisition/smartrecruiters');
const { scrapeEightfold } = require('../acquisition/eightfold');
const { scrapeIbm } = require('../acquisition/ibm');

// Minimal company configs for testing (no DB needed)
const aristaConfig = {
  name: 'Arista Networks',
  ats: 'smartrecruiters',
  careerUrl: 'https://jobs.smartrecruiters.com/AristaNetworks',
  smartRecruitersId: 'AristaNetworks',
  filters: { country: 'in' },
};

const qualcommConfig = {
  name: 'Qualcomm',
  ats: 'eightfold',
  careerUrl: 'https://careers.qualcomm.com',
  eightfoldBaseUrl: 'https://careers.qualcomm.com',
  eightfoldDomain: 'qualcomm.com',
  filters: { location: 'India', query: '' },
};

const ericssonConfig = {
  name: 'Ericsson',
  ats: 'eightfold',
  careerUrl: 'https://jobs.ericsson.com',
  eightfoldBaseUrl: 'https://jobs.ericsson.com',
  eightfoldDomain: 'ericsson.com',
  filters: { location: 'India', query: '' },
};

const ibmConfig = {
  name: 'IBM',
  ats: 'ibm',
  careerUrl: 'https://careers.ibm.com/careers/search',
  filters: { country: 'India', category: 'Software Engineering' },
};

async function run() {
  console.log('\n=== Testing Arista (SmartRecruiters API) ===');
  try {
    const jobs = await scrapeSmartRecruiters(aristaConfig);
    console.log(`✅ Arista: ${jobs.length} jobs fetched`);
    if (jobs.length > 0) {
      const j = jobs[0];
      console.log(`   Sample: "${j.jobTitle}" at ${j.location}`);
    }
  } catch (e) { console.error('❌ Arista error:', e.message); }

  console.log('\n=== Testing Qualcomm (Eightfold API) ===');
  try {
    const jobs = await scrapeEightfold(qualcommConfig);
    console.log(`✅ Qualcomm: ${jobs.length} jobs fetched`);
    if (jobs.length > 0) {
      const j = jobs[0];
      console.log(`   Sample: "${j.jobTitle}" at ${j.location}`);
    }
  } catch (e) { console.error('❌ Qualcomm error:', e.message); }

  console.log('\n=== Testing Ericsson (Eightfold API) ===');
  try {
    const jobs = await scrapeEightfold(ericssonConfig);
    console.log(`✅ Ericsson: ${jobs.length} jobs fetched`);
    if (jobs.length > 0) {
      const j = jobs[0];
      console.log(`   Sample: "${j.jobTitle}" at ${j.location}`);
    }
  } catch (e) { console.error('❌ Ericsson error:', e.message); }

  console.log('\n=== Testing IBM (IBM Search API) ===');
  try {
    // Just fetch 1 page to keep it fast
    const jobs = await scrapeIbm({ ...ibmConfig, _testLimit: true });
    console.log(`✅ IBM: ${jobs.length} jobs fetched (first page)`);
    if (jobs.length > 0) {
      const j = jobs[0];
      console.log(`   Sample: "${j.jobTitle}" at ${j.location}`);
    }
  } catch (e) { console.error('❌ IBM error:', e.message); }

  console.log('\nDone.');
}

run().catch(console.error);
