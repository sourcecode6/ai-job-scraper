const axios = require('axios');
const cheerio = require('cheerio');
const logger = require('../logger');
const { queueHttp } = require('./requestQueue');
const settings = require('../config/settings');

/**
 * Fetches jobs from Eightfold AI-powered career sites.
 * Companies like Qualcomm, Ericsson, Microsoft use Eightfold's pcsx API.
 *
 * API:
 *   Search: GET {baseUrl}/api/pcsx/search?domain=...&location=...&query=...&start=...&num=...
 *   Detail: GET {baseUrl}/api/pcsx/position_details?position_id=...&domain=...&hl=en
 *
 * NOTE: Eightfold returns exactly 10 results per search page regardless of `num`.
 * Pagination is driven by `start < total`, NOT by `positions.length < pageSize`.
 *
 * NOTE: The detail API triggers bot-detection (403) if called in parallel or too
 * frequently. We use the search list data only (title, location, dept, date) and
 * skip individual detail fetches to keep the scraper reliable and polite.
 *
 * @param {Object} company - Company config object
 * @returns {Array} Normalized job objects
 */
async function scrapeEightfold(company) {
  const { name, eightfoldBaseUrl, eightfoldDomain, filters } = company;
  const searchUrl = `${eightfoldBaseUrl}/api/pcsx/search`;

  const jobs = [];
  let start = 0;
  const pageSize = 10; // Eightfold's fixed page size
  let total = null;

  logger.info(`[${name}] Eightfold fetch starting`, { domain: eightfoldDomain });

  while (true) {
    try {
      const response = await queueHttp(() =>
        axios.get(searchUrl, {
          params: {
            domain: eightfoldDomain,
            location: filters?.location || 'India',
            query: filters?.query || '',
            start,
            num: pageSize,
          },
          headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': `${eightfoldBaseUrl}/careers`,
            'Origin': eightfoldBaseUrl,
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
          },
          timeout: 15000,
        })
      );

      const positions = response.data?.data?.positions || [];
      total = response.data?.data?.count ?? total ?? 0;

      if (positions.length === 0) break;

      logger.info(`[${name}] Eightfold page fetched`, {
        start,
        total,
        fetched: positions.length,
      });

      for (const position of positions) {
        const job = normalizeEightfoldJob(position, company);
        if (job) jobs.push(job);
      }

      start += positions.length;
      if (start >= total) break;

    } catch (err) {
      const status = err?.response?.status;
      if (status === 429) {
        logger.error(`[${name}] Rate limited (429)`);
      } else if (status === 403 || status === 401) {
        logger.warn(`[${name}] Eightfold blocked at start=${start} (${status}) — saving ${jobs.length} jobs collected so far`);
        // Don't mark degraded — partial results are still useful
      } else {
        logger.error(`[${name}] Eightfold fetch error`, { message: err.message, status });
      }
      break;
    }
  }

  logger.info(`[${name}] Eightfold scrape complete`, { totalJobs: jobs.length });
  return jobs;
}

function normalizeEightfoldJob(position, company) {
  try {
    const jobId = position.atsJobId || String(position.id);
    const location = (position.locations || []).join(', ');
    const jobUrl = `${company.eightfoldBaseUrl}${position.positionUrl || '/careers'}`;

    return {
      companyName: company.name,
      jobId: String(jobId),
      jobTitle: position.name || 'Unknown Title',
      location,
      department: position.department || '',
      postedDate: position.postedTs
        ? new Date(position.postedTs * 1000).toISOString()
        : new Date().toISOString(),
      employmentType: 'Full-time',
      jobDescription: '', // Detail API triggers bot-detection; description not available from search
      url: jobUrl,
      applyUrl: jobUrl,
    };
  } catch {
    return null;
  }
}

module.exports = { scrapeEightfold };
