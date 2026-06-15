const axios = require('axios');
const logger = require('../logger');
const { queueHttp } = require('./requestQueue');
const settings = require('../config/settings');

/**
 * Fetches jobs from Cisco's career site using their widgets API.
 *
 * The Cisco careers site (careers.cisco.com) uses a Play Framework backend.
 * Workflow:
 *   1. GET the search page to obtain session cookies + CSRF token from PLAY_SESSION JWT
 *   2. POST /widgets with ddoKey: 'refineSearch' and the correct country filter
 *
 * Key findings from API investigation:
 *  - ddoKey must be 'refineSearch' (not 'eagerLoadRefineSearchSession')
 *  - Location filter must use selected_fields.country (not .location)
 *  - country value must be the full name 'India' (not 'IN' or 'IND')
 *  - The API does NOT return totalHits — paginate until empty page
 *  - counts: false is needed to avoid empty facet responses
 *
 * @param {Object} company - Company config object
 * @returns {Array} Normalized job objects
 */
async function scrapeCisco(company) {
  const { name, filters } = company;
  const location = filters?.location || 'India';
  const keywords = filters?.keywords || 'engineer';

  logger.info(`[${name}] Cisco fetch starting`);

  const jobs = [];
  let from = 0;
  const pageSize = 25;

  try {
    // Step 1: GET the search page to obtain session cookies and CSRF token
    const { cookieHeader, csrfToken } = await getCiscoCsrf(name);

    // Step 2: Paginate through jobs
    while (true) {
      const body = {
        sortBy: '',
        subsearch: '',
        from,
        jobs: true,
        counts: false,
        all_fields: [],
        pageName: 'search-results',
        size: pageSize,
        clearAll: false,
        jdsource: 'facets',
        isSliderEnable: false,
        pageId: 'page4',
        siteType: 'external',
        keywords,
        global: true,
        selected_fields: {
          country: [location],  // IMPORTANT: use 'country', full name e.g. 'India'
        },
        lang: 'en_global',
        deviceType: 'desktop',
        country: 'global',
        refNum: 'CISCISGLOBAL',
        ddoKey: 'refineSearch',  // IMPORTANT: not 'eagerLoadRefineSearchSession'
      };

      const response = await queueHttp(() =>
        axios.post('https://careers.cisco.com/widgets', body, {
          headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://careers.cisco.com/global/en/search-results',
            'x-csrf-token': csrfToken,
            'Cookie': cookieHeader,
          },
          timeout: 20000,
        })
      );

      const result = response.data?.refineSearch;
      if (!result || result.status !== 200) {
        logger.warn(`[${name}] Cisco widgets returned unexpected status`, {
          status: result?.status,
          keys: result ? Object.keys(result) : [],
        });
        break;
      }

      const pageJobs = result.data?.jobs || [];

      if (pageJobs.length === 0) break;

      for (const j of pageJobs) {
        const job = normalizeCiscoJob(j, company);
        if (job) jobs.push(job);
      }

      logger.info(`[${name}] Cisco page fetched`, {
        from,
        fetched: pageJobs.length,
      });

      from += pageJobs.length;

      // Cisco doesn't return totalHits — stop when page is partial or empty
      if (pageJobs.length < pageSize) break;
    }

  } catch (err) {
    const status = err?.response?.status;
    if (status === 403 || status === 401) {
      logger.error(`[${name}] Access denied (${status})`);
      throw Object.assign(err, { markDegraded: true });
    }
    logger.error(`[${name}] Cisco fetch error`, { message: err.message, status });
  }

  logger.info(`[${name}] Cisco scrape complete`, { totalJobs: jobs.length });
  return jobs;
}

/**
 * GETs the Cisco search page to extract PLAY_SESSION cookie and CSRF token.
 */
async function getCiscoCsrf(name) {
  const pageRes = await axios.get('https://careers.cisco.com/global/en/search-results', {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9',
    },
    timeout: 20000,
  });

  const setCookies = pageRes.headers['set-cookie'] || [];
  const cookieHeader = setCookies.map((c) => c.split(';')[0]).join('; ');

  const playSessionEntry = setCookies.find((c) => c.startsWith('PLAY_SESSION='));
  if (!playSessionEntry) {
    throw new Error(`[${name}] PLAY_SESSION cookie not found`);
  }

  const playSession = playSessionEntry.split(';')[0].replace('PLAY_SESSION=', '').trim();
  const parts = playSession.split('.');
  if (parts.length < 2) {
    throw new Error(`[${name}] Invalid PLAY_SESSION JWT format`);
  }

  const payloadJson = JSON.parse(Buffer.from(parts[1], 'base64').toString('utf-8'));
  const csrfToken = payloadJson.data?.csrfToken;

  if (!csrfToken) {
    throw new Error(`[${name}] CSRF token not found in PLAY_SESSION`);
  }

  return { cookieHeader, csrfToken };
}

function normalizeCiscoJob(job, company) {
  try {
    const jobId = job.jobId || job.reqId || job.jobSeqNo || String(Date.now() + Math.random());
    const location = job.location || [job.city, job.state, job.country].filter(Boolean).join(', ');
    const jobUrl = job.applyUrl || `https://careers.cisco.com/global/en/job/${jobId}`;

    return {
      companyName: company.name,
      jobId: String(jobId),
      jobTitle: job.title || 'Unknown Title',
      location,
      department: job.category || job.department || '',
      postedDate: job.postedDate || job.dateCreated || new Date().toISOString(),
      employmentType: job.type || 'Full-time',
      jobDescription: job.descriptionTeaser || '',
      url: jobUrl,
      applyUrl: job.applyUrl || jobUrl,
    };
  } catch {
    return null;
  }
}

module.exports = { scrapeCisco };
