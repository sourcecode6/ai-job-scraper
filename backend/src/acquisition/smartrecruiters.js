const axios = require('axios');
const logger = require('../logger');
const { queueHttp } = require('./requestQueue');

/**
 * Fetches jobs from SmartRecruiters public REST API.
 * Used for companies like Arista Networks that post on SmartRecruiters.
 *
 * API: GET https://api.smartrecruiters.com/v1/companies/{companyId}/postings
 *
 * @param {Object} company - Company config object
 * @returns {Array} Normalized job objects
 */
async function scrapeSmartRecruiters(company) {
  const { name, smartRecruitersId, filters } = company;
  const baseUrl = `https://api.smartrecruiters.com/v1/companies/${smartRecruitersId}/postings`;

  const jobs = [];
  let offset = 0;
  const limit = 100;
  let hasMore = true;

  logger.info(`[${name}] SmartRecruiters fetch starting`, { companyId: smartRecruitersId });

  while (hasMore) {
    try {
      const params = {
        limit,
        offset,
      };

      // Apply optional country filter
      if (filters?.country) {
        params.country = filters.country;
      }

      const response = await queueHttp(() =>
        axios.get(baseUrl, {
          params,
          headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
          },
          timeout: 15000,
        })
      );

      const data = response.data;
      const postings = data?.content || [];
      const total = data?.totalFound || 0;

      if (postings.length === 0) {
        hasMore = false;
        break;
      }

      for (const posting of postings) {
        const job = normalizeSmartRecruitersJob(posting, company);
        if (job) jobs.push(job);
      }

      offset += postings.length;

      logger.info(`[${name}] SmartRecruiters page fetched`, {
        offset,
        total,
        fetched: postings.length,
      });

      if (offset >= total || postings.length < limit) {
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
        logger.error(`[${name}] SmartRecruiters fetch error`, { message: err.message, status });
      }
      hasMore = false;
    }
  }

  logger.info(`[${name}] SmartRecruiters scrape complete`, { totalJobs: jobs.length });
  return jobs;
}

function normalizeSmartRecruitersJob(posting, company) {
  try {
    const jobId = posting.refNumber || posting.id || String(Date.now());
    const location = [posting.location?.city, posting.location?.region, posting.location?.country]
      .filter(Boolean)
      .join(', ');

    const jobUrl = `https://jobs.smartrecruiters.com/${company.smartRecruitersId}/${posting.id}`;

    return {
      companyName: company.name,
      jobId: String(jobId),
      jobTitle: posting.name || 'Unknown Title',
      location,
      department: posting.department?.label || '',
      postedDate: posting.releasedDate || new Date().toISOString(),
      employmentType: posting.typeOfEmployment?.label || 'Full-time',
      jobDescription: posting.customField?.description || '',
      url: jobUrl,
      applyUrl: jobUrl,
    };
  } catch {
    return null;
  }
}

module.exports = { scrapeSmartRecruiters };
