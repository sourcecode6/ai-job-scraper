const axios = require('axios');
const cheerio = require('cheerio');
const settings = require('../config/settings');
const logger = require('../logger');
const { queueHttp } = require('./requestQueue');

/**
 * Fetches the career page and extracts all JSON-LD JobPosting entries.
 *
 * @param {Object} company - Company config object
 * @returns {Array} Normalized job objects
 */
async function scrapeJsonLd(company) {
  const { name, careerUrl, filters } = company;

  // Build URL with optional query params
  let fetchUrl = careerUrl;
  if (filters?.urlParams && Object.keys(filters.urlParams).length > 0) {
    const params = new URLSearchParams(filters.urlParams);
    fetchUrl = `${careerUrl}?${params.toString()}`;
  }

  logger.info(`[${name}] JSON-LD fetch starting`, { url: fetchUrl });

  try {
    const html = await queueHttp(() =>
      axios.get(fetchUrl, {
        headers: {
          'User-Agent': settings.scraping.userAgent,
          'Accept': 'text/html,application/xhtml+xml',
          'Accept-Language': 'en-US,en;q=0.9',
        },
        timeout: 15000,
      }).then((r) => r.data)
    );

    const jobs = extractJobPostings(html, company);
    logger.info(`[${name}] JSON-LD scrape complete`, { totalJobs: jobs.length });
    return jobs;
  } catch (err) {
    const status = err?.response?.status;
    if (status === 429) {
      logger.error(`[${name}] Rate limited (429)`, { type: 'HTTP_429' });
    } else if (status === 403 || status === 401) {
      logger.error(`[${name}] Access denied (${status})`, { type: `HTTP_${status}` });
      throw Object.assign(err, { markDegraded: true });
    } else {
      logger.error(`[${name}] JSON-LD fetch error`, { message: err.message, status });
    }
    return [];
  }
}

/**
 * Parses all <script type="application/ld+json"> blocks from HTML
 * and returns normalized job objects for @type: "JobPosting" entries.
 */
function extractJobPostings(html, company) {
  const $ = cheerio.load(html);
  const jobs = [];

  $('script[type="application/ld+json"]').each((_, el) => {
    try {
      const raw = $(el).html();
      if (!raw) return;

      const parsed = JSON.parse(raw);

      // Handle both single objects and arrays
      const entries = Array.isArray(parsed) ? parsed : [parsed];

      for (const entry of entries) {
        if (entry['@type'] === 'JobPosting') {
          const job = normalizeJsonLdJob(entry, company);
          if (job) jobs.push(job);
        }
        // Some pages wrap in @graph
        if (entry['@graph']) {
          for (const graphEntry of entry['@graph']) {
            if (graphEntry['@type'] === 'JobPosting') {
              const job = normalizeJsonLdJob(graphEntry, company);
              if (job) jobs.push(job);
            }
          }
        }
      }
    } catch {
      // Silently skip malformed JSON-LD blocks
    }
  });

  return jobs;
}

function normalizeJsonLdJob(entry, company) {
  try {
    const jobId =
      entry?.identifier?.value ||
      entry?.identifier ||
      entry?.url?.split('/').filter(Boolean).pop() ||
      `${company.name}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

    const location =
      entry?.jobLocation?.address?.addressLocality ||
      entry?.jobLocation?.address?.addressRegion ||
      entry?.jobLocation?.address?.addressCountry ||
      (Array.isArray(entry?.jobLocation)
        ? entry.jobLocation.map((l) => l?.address?.addressLocality).filter(Boolean).join(', ')
        : '') ||
      '';

    return {
      companyName: company.name,
      jobId: String(jobId),
      jobTitle: entry?.title || entry?.name || 'Unknown Title',
      location,
      department: entry?.occupationalCategory || entry?.department || '',
      postedDate: entry?.datePosted || new Date().toISOString(),
      employmentType: entry?.employmentType || 'Full-time',
      jobDescription: stripHtml(entry?.description || ''),
      url: entry?.url || company.careerUrl,
      applyUrl: entry?.url || company.careerUrl,
    };
  } catch {
    return null;
  }
}

function stripHtml(html) {
  return html
    .replace(/<[^>]*>/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

module.exports = { scrapeJsonLd, extractJobPostings };
