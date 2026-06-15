const axios = require('axios');
const logger = require('../logger');
const { queueHttp } = require('./requestQueue');
const settings = require('../config/settings');

/**
 * Fetches jobs from AMD's career site using their new Attract/iCIMS API.
 *
 * API: GET https://careers.amd.com/api/jobs
 * Parameters:
 *   - page: page number (1-based)
 *   - limit: page size (e.g. 50)
 *   - location: e.g. "India"
 *   - keywords: search text (optional)
 *
 * @param {Object} company - Company config object
 * @returns {Array} Normalized job objects
 */
async function scrapeAmd(company) {
  const { name, filters } = company;
  const location = filters?.location || 'India';
  const keywords = filters?.keywords || '';

  logger.info(`[${name}] AMD API fetch starting`, { location, keywords });

  const jobs = [];
  let page = 1;
  const limit = 50;
  let hasMore = true;

  while (hasMore) {
    try {
      const params = new URLSearchParams({
        page: String(page),
        limit: String(limit),
        sortBy: 'relevance',
        descending: 'false',
        internal: 'false'
      });

      if (location) params.append('location', location);
      if (keywords) params.append('keywords', keywords);

      const apiUrl = `https://careers.amd.com/api/jobs?${params.toString()}`;

      const response = await queueHttp(() =>
        axios.get(apiUrl, {
          headers: {
            'User-Agent': settings.scraping.userAgent || 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
          },
          timeout: 15000,
        })
      );

      const pageJobs = response.data?.jobs || [];

      if (pageJobs.length === 0) {
        hasMore = false;
        break;
      }

      for (const j of pageJobs) {
        const job = normalizeAmdJob(j, company);
        if (job) jobs.push(job);
      }

      logger.info(`[${name}] AMD API page ${page} fetched`, {
        fetched: pageJobs.length,
      });

      if (pageJobs.length < limit) {
        hasMore = false;
      } else {
        page++;
      }
    } catch (err) {
      const status = err?.response?.status;
      if (status === 403 || status === 401) {
        logger.error(`[${name}] Access denied (${status})`);
        throw Object.assign(err, { markDegraded: true });
      }
      logger.error(`[${name}] AMD API fetch error`, { message: err.message, status });
      hasMore = false;
    }
  }

  logger.info(`[${name}] AMD API scrape complete`, { totalJobs: jobs.length });
  return jobs;
}

function normalizeAmdJob(item, company) {
  try {
    const job = item.data;
    if (!job) return null;

    const jobId = job.req_id || job.slug || String(Date.now() + Math.random());
    const location = job.full_location || job.short_location || [job.city, job.state, job.country].filter(Boolean).join(', ');
    const jobUrl = job.meta_data?.canonical_url || job.apply_url || `https://careers.amd.com/jobs/${jobId}`;

    return {
      companyName: company.name,
      jobId: String(jobId),
      jobTitle: job.title || 'Unknown Title',
      location,
      department: (job.category && job.category[0]) || (job.categories && job.categories[0]) || '',
      postedDate: job.posted_date || job.create_date || new Date().toISOString(),
      employmentType: job.employment_type || 'Full-time',
      jobDescription: job.description || '',
      url: jobUrl,
      applyUrl: job.apply_url || jobUrl,
    };
  } catch {
    return null;
  }
}

module.exports = { scrapeAmd };
