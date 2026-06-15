const axios = require('axios');
const settings = require('../config/settings');
const logger = require('../logger');
const { queueHttp } = require('./requestQueue');

/**
 * Fetches jobs from a Workday career site using the internal JSON POST endpoint.
 * This endpoint is publicly accessible (same one the Workday SPA uses internally).
 *
 * @param {Object} company - Company config object
 * @returns {Array} Normalized job objects
 */
async function scrapeWorkday(company) {
  const { name, workdaySubdomain, workdayTenant, workdaySite, filters } = company;
  const endpoint = `https://${workdaySubdomain}.myworkdayjobs.com/wday/cxs/${workdayTenant}/${workdaySite}/jobs`;

  const jobs = [];
  let offset = 0;
  const limit = filters.limit || 20;
  let hasMore = true;

  logger.info(`[${name}] Workday fetch starting`, { endpoint });

  while (hasMore) {
    const body = {
      limit,
      offset,
      searchText: filters.searchText || '',
      locations: filters.locations || [],
    };

    try {
      const response = await queueHttp(() =>
        axios.post(endpoint, body, {
          headers: {
            'Content-Type': 'application/json',
            'User-Agent': settings.scraping.userAgent,
            'Accept': 'application/json',
          },
          timeout: 15000,
        })
      );

      const data = response.data;
      const postings = data?.jobPostings || [];

      if (postings.length === 0) {
        hasMore = false;
        break;
      }

      for (const posting of postings) {
        jobs.push(normalizeWorkdayJob(posting, company));
      }

      // Workday typically returns total count
      const total = data?.total || 0;
      offset += postings.length;

      if (offset >= total || postings.length < limit) {
        hasMore = false;
      }

      logger.info(`[${name}] Workday page fetched`, {
        offset,
        total,
        fetched: postings.length,
      });
    } catch (err) {
      handleHttpError(name, err);
      hasMore = false;
    }
  }

  logger.info(`[${name}] Workday scrape complete`, { totalJobs: jobs.length });
  return jobs;
}

function normalizeWorkdayJob(posting, company) {
  // Workday API response fields
  let externalPath = posting.externalPath || '';
  if (externalPath.startsWith('/job/')) {
    externalPath = `/en-US/${company.workdaySite}${externalPath}`;
  }
  const baseUrl = `https://${company.workdaySubdomain}.myworkdayjobs.com`;
  const jobUrl = externalPath ? `${baseUrl}${externalPath}` : company.careerUrl;

  return {
    companyName: company.name,
    jobId: posting.bulletFields?.[0] || posting.title?.replace(/\s+/g, '-').toLowerCase() + '-' + Date.now(),
    jobTitle: posting.title || 'Unknown Title',
    location: posting.locationsText || '',
    department: posting.jobCategories?.[0]?.value || '',
    postedDate: posting.postedOn || new Date().toISOString(),
    employmentType: posting.timeType || 'Full-time',
    jobDescription: posting.jobDescription?.trim() || '',
    url: jobUrl,
    applyUrl: jobUrl,
  };
}

function handleHttpError(companyName, err) {
  const status = err?.response?.status;
  if (status === 429) {
    logger.error(`[${companyName}] Rate limited (429)`, { type: 'HTTP_429', action: 'skipped_this_cycle' });
  } else if (status === 403 || status === 401) {
    logger.error(`[${companyName}] Access denied (${status})`, { type: `HTTP_${status}`, action: 'mark_degraded' });
    throw Object.assign(err, { markDegraded: true });
  } else if (status === 404) {
    logger.error(`[${companyName}] Endpoint not found (404)`, { type: 'HTTP_404', action: 'mark_degraded' });
    throw Object.assign(err, { markDegraded: true });
  } else {
    logger.error(`[${companyName}] HTTP error`, { status, message: err.message });
  }
}

module.exports = { scrapeWorkday };
