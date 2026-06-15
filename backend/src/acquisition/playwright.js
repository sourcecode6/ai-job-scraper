const { chromium } = require('playwright');
const settings = require('../config/settings');
const logger = require('../logger');
const { extractJobPostings } = require('./jsonld');
const { sleep } = require('./requestQueue');
const axios = require('axios');

/**
 * Google careers hybrid scraper:
 * 1. Playwright renders the SPA job listing page
 * 2. Tries multiple CSS selector strategies to find job links
 *    (Google has changed their DOM structure several times)
 * 3. For each detail URL: plain HTTP GET + Cheerio JSON-LD extraction
 *
 * @param {Object} company - Company config object
 * @returns {Array} Normalized job objects
 */
async function scrapePlaywright(company) {
  const { name, careerUrl, filters } = company;
  logger.info(`[${name}] Playwright fetch starting`);

  let browser = null;
  const jobs = [];

  try {
    browser = await chromium.launch({
      headless: true,
      slowMo: settings.scraping.playwrightSlowMo,
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });

    const context = await browser.newContext({
      // Use a real browser UA — Google blocks bot UAs
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      viewport: { width: 1280, height: 900 },
      locale: 'en-US',
    });

    const page = await context.newPage();

    // Build search URL
    const params = new URLSearchParams({
      q: filters.keywords || 'engineer',
      location: filters.location || 'India',
    });
    if (filters.category) params.set('jc', filters.category);

    const searchUrl = `${careerUrl}?${params.toString()}`;
    logger.info(`[${name}] Navigating to: ${searchUrl}`);

    await page.goto(searchUrl, { waitUntil: 'networkidle', timeout: 45000 });
    await sleep(3000); // Extra wait for SPA hydration

    // Try multiple selector strategies in priority order (Google changes these often)
    const jobLinks = await page.evaluate(() => {
      const seen = new Set();
      const links = [];

      // Strategy 1: Direct job result links (current format as of 2025)
      document.querySelectorAll('a[href*="/jobs/results/"]').forEach(a => {
        if (a.href && !seen.has(a.href)) { seen.add(a.href); links.push(a.href); }
      });

      // Strategy 2: Job cards with data attributes
      document.querySelectorAll('[data-job-id] a, [data-jobid] a').forEach(a => {
        if (a.href && !seen.has(a.href)) { seen.add(a.href); links.push(a.href); }
      });

      // Strategy 3: li elements with job links
      document.querySelectorAll('li a[href*="careers.google.com"]').forEach(a => {
        if (a.href && !seen.has(a.href)) { seen.add(a.href); links.push(a.href); }
      });

      // Strategy 4: Any anchor that looks like a job detail page
      document.querySelectorAll('a[href]').forEach(a => {
        if (
          a.href &&
          a.href.includes('careers.google.com') &&
          (a.href.includes('/jobs/') || a.href.includes('/results/')) &&
          !seen.has(a.href)
        ) {
          seen.add(a.href);
          links.push(a.href);
        }
      });

      return links.slice(0, 30);
    });

    logger.info(`[${name}] Found ${jobLinks.length} job links via Playwright`);

    // Log page title to help diagnose future selector breakage
    const title = await page.title().catch(() => 'unknown');
    logger.info(`[${name}] Page title: "${title}"`);

    if (jobLinks.length === 0) {
      // Capture the actual DOM structure to help debug next time
      const bodySnippet = await page.evaluate(() =>
        document.body?.innerHTML?.slice(0, 500) ?? ''
      );
      logger.warn(`[${name}] No job links found. Body snippet: ${bodySnippet.replace(/\s+/g, ' ')}`);
    }

    await browser.close();
    browser = null;

    // Fetch job descriptions via JSON-LD from each detail page
    for (const jobUrl of jobLinks) {
      try {
        await sleep(settings.scraping.crawlDelayDefaultMs);
        const html = await axios.get(jobUrl, {
          headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
          },
          timeout: 10000,
        }).then((r) => r.data);

        const extracted = extractJobPostings(html, company);
        if (extracted.length > 0) {
          jobs.push({ ...extracted[0], url: jobUrl, applyUrl: jobUrl });
        }
      } catch (err) {
        logger.warn(`[${name}] Failed to fetch job detail: ${jobUrl}`, { message: err.message });
      }
    }

    logger.info(`[${name}] Playwright scrape complete`, { totalJobs: jobs.length });
  } catch (err) {
    if (browser) await browser.close();
    logger.error(`[${name}] Playwright error`, { message: err.message });
  }

  return jobs;
}

module.exports = { scrapePlaywright };
