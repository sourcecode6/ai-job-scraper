const axios = require('axios');
const logger = require('../logger');
const { queueHttp } = require('./requestQueue');
const settings = require('../config/settings');

/**
 * Fetches jobs from IBM's internal search API.
 *
 * API: POST https://www-api.ibm.com/search/api/v2
 * Uses Elasticsearch-style query DSL to filter by country and category.
 *
 * @param {Object} company - Company config object
 * @returns {Array} Normalized job objects
 */
async function scrapeIbm(company) {
  const { name, filters } = company;
  const apiUrl = 'https://www-api.ibm.com/search/api/v2';

  const jobs = [];
  let from = 0;
  const pageSize = 50;
  let hasMore = true;
  let totalExpected = null;

  logger.info(`[${name}] IBM API fetch starting`);

  while (hasMore) {
    try {
      const body = {
        appId: 'careers',
        scopes: ['careers2'],
        query: {
          bool: {
            must: [
              ...(filters?.country ? [{ match: { field_keyword_05: filters.country } }] : []),
              ...(filters?.category ? [{ match: { field_keyword_08: filters.category } }] : []),
            ],
          },
        },
        from,
        size: pageSize,
        lang: 'zz',
        _source: [
          '_id',
          'title',
          'url',
          'description',
          'language',
          'field_keyword_05',  // country
          'field_keyword_08',  // category
          'field_keyword_17',  // work mode
          'field_keyword_19',  // city
        ],
      };

      const response = await queueHttp(() =>
        axios.post(apiUrl, body, {
          headers: {
            'User-Agent': settings.scraping.userAgent,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
          timeout: 15000,
        })
      );

      const hits = response.data?.hits?.hits || [];
      const total = response.data?.hits?.total?.value || 0;

      if (totalExpected === null) {
        totalExpected = total;
        logger.info(`[${name}] IBM API total jobs found: ${total}`);
      }

      if (hits.length === 0) {
        hasMore = false;
        break;
      }

      for (const hit of hits) {
        const job = normalizeIbmJob(hit, company);
        if (job) jobs.push(job);
      }

      logger.info(`[${name}] IBM API page fetched`, {
        from,
        total,
        fetched: hits.length,
      });

      from += hits.length;
      if (from >= total || hits.length < pageSize) {
        hasMore = false;
      }
    } catch (err) {
      const status = err?.response?.status;
      if (status === 429) {
        logger.error(`[${name}] Rate limited (429)`);
      } else if (status === 403 || status === 401) {
        logger.error(`[${name}] Access denied (${status})`);
        throw Object.assign(err, { markDegraded: true });
      } else {
        logger.error(`[${name}] IBM API fetch error`, { message: err.message, status });
      }
      hasMore = false;
    }
  }

  logger.info(`[${name}] IBM API scrape complete`, { totalJobs: jobs.length });
  return jobs;
}

function normalizeIbmJob(hit, company) {
  try {
    const src = hit._source || {};
    // Extract a stable job ID from the URL (e.g. jobId=83003)
    const jobIdMatch = src.url?.match(/jobId=(\d+)/);
    const jobId = jobIdMatch ? jobIdMatch[1] : hit._id || String(Date.now());

    const location = src.field_keyword_19 || src.field_keyword_05 || '';
    const workMode = src.field_keyword_17 || '';

    return {
      companyName: company.name,
      jobId: String(jobId),
      jobTitle: src.title || 'Unknown Title',
      location,
      department: src.field_keyword_08 || '',
      postedDate: new Date().toISOString(),
      employmentType: workMode || 'Full-time',
      jobDescription: src.description || '',
      url: src.url || company.careerUrl,
      applyUrl: src.url || company.careerUrl,
    };
  } catch {
    return null;
  }
}

module.exports = { scrapeIbm };
