/**
 * Master list of supported companies.
 * Each entry defines how jobs are acquired for that company.
 *
 * tier:
 *   1 = Official ATS public API (Greenhouse/Lever)
 *   2 = Workday internal JSON POST or JSON-LD via Cheerio
 *   3 = Playwright HTML scraper (fallback)
 *
 * ats:
 *   'workday'    → Workday internal JSON POST
 *   'jsonld'     → Cheerio + JSON-LD extraction
 *   'playwright' → Google hybrid (Playwright list + Cheerio detail)
 *
 * filters:
 *   locations    → passed to Workday JSON POST body
 *   searchText   → passed to Workday JSON POST body
 *   urlParams    → appended to JSON-LD career page URL as query params
 */
module.exports = [
  {
    name: 'NVIDIA',
    ats: 'workday',
    tier: 2,
    careerUrl: 'https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite',
    workdayTenant: 'nvidia',
    workdaySite: 'NVIDIAExternalCareerSite',
    workdaySubdomain: 'nvidia.wd5',
    filters: {
      locations: ['India', 'Remote'],
      searchText: '',
      limit: 20,
    },
  },
  //  {
  //    name: 'Google',
  //    ats: 'playwright',
  //    tier: 3,
  //    careerUrl: 'https://careers.google.com/jobs/results',
  //    filters: {
  //      category: 'ENGINEERING_AND_TECHNOLOGY',
  //      location: 'India',
  //      keywords: 'engineer',
  //    },
  //  },
  {
    name: 'Arista Networks',
    ats: 'smartrecruiters',
    tier: 2,
    careerUrl: 'https://jobs.smartrecruiters.com/AristaNetworks',
    smartRecruitersId: 'AristaNetworks',
    filters: {
      country: 'in', // ISO 3166-1 alpha-2 country code
    },
  },
  {
    name: 'Cisco Systems',
    ats: 'cisco',
    tier: 2,
    careerUrl: 'https://careers.cisco.com/global/en/search-results',
    filters: {
      keywords: 'engineer',
      location: 'India',
    },
  },
  {
    name: 'Qualcomm',
    ats: 'eightfold',
    tier: 2,
    careerUrl: 'https://careers.qualcomm.com',
    eightfoldBaseUrl: 'https://careers.qualcomm.com',
    eightfoldDomain: 'qualcomm.com',
    filters: {
      location: 'India',
      query: '',
    },
  },
  {
    name: 'AMD',
    ats: 'amd',
    tier: 2,
    careerUrl: 'https://careers.amd.com/careers-home/jobs',
    filters: {
      location: 'India',
      keywords: '',
    },
  },
  {
    name: 'Broadcom',
    ats: 'workday',
    tier: 2,
    careerUrl: 'https://broadcom.wd1.myworkdayjobs.com/External_Career',
    workdayTenant: 'broadcom',
    workdaySite: 'External_Career',
    workdaySubdomain: 'broadcom.wd1',
    filters: {
      locations: ['India', 'Remote'],
      searchText: '',
      limit: 20,
    },
  },
  {
    name: 'Intel',
    ats: 'workday',
    tier: 2,
    careerUrl: 'https://intel.wd1.myworkdayjobs.com/en-US/External',
    workdayTenant: 'intel',
    workdaySite: 'External',
    workdaySubdomain: 'intel.wd1',
    filters: {
      locations: ['India', 'Remote'],
      searchText: '',
      limit: 20,
    },
  },
  {
    name: 'Microsoft',
    ats: 'eightfold',
    tier: 2,
    careerUrl: 'https://careers.microsoft.com',
    eightfoldBaseUrl: 'https://apply.careers.microsoft.com',
    eightfoldDomain: 'microsoft.com',
    filters: {
      location: 'India',
      query: '',
    },
  },
  {
    name: 'IBM',
    ats: 'ibm',
    tier: 2,
    careerUrl: 'https://careers.ibm.com/careers/search',
    filters: {
      country: 'India',
      category: 'Software Engineering',
    },
  },
  {
    name: 'Ericsson',
    ats: 'eightfold',
    tier: 2,
    careerUrl: 'https://jobs.ericsson.com',
    eightfoldBaseUrl: 'https://jobs.ericsson.com',
    eightfoldDomain: 'ericsson.com',
    filters: {
      location: 'India',
      query: '',
    },
  },
];
