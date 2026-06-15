const axios = require('axios');
const robotsParser = require('robots-parser');
const settings = require('../config/settings');
const logger = require('../logger');

// Cache robots.txt per domain for the duration of one scrape cycle
const cache = new Map();

/**
 * Clears the in-memory cache. Call at start of each scrape cycle.
 */
function clearCache() {
  cache.clear();
}

/**
 * Fetches and parses robots.txt for a given URL's domain.
 * Returns a parsed robots object (robots-parser instance).
 */
async function fetchRobots(careerUrl) {
  try {
    const url = new URL(careerUrl);
    const robotsUrl = `${url.protocol}//${url.host}/robots.txt`;

    if (cache.has(robotsUrl)) {
      return cache.get(robotsUrl);
    }

    const response = await axios.get(robotsUrl, {
      timeout: 8000,
      headers: { 'User-Agent': settings.scraping.userAgent },
    });

    const robots = robotsParser(robotsUrl, response.data);
    cache.set(robotsUrl, robots);
    return robots;
  } catch {
    // If robots.txt can't be fetched, assume allowed (conservative approach)
    return null;
  }
}

/**
 * Returns true if scraping the given URL is allowed by robots.txt.
 * Returns true by default if robots.txt is unavailable.
 */
async function isAllowed(careerUrl) {
  const robots = await fetchRobots(careerUrl);
  if (!robots) return true;

  const allowed = robots.isAllowed(careerUrl, settings.scraping.userAgent);
  if (!allowed) {
    logger.warn(`robots.txt disallows scraping: ${careerUrl}`);
  }
  return allowed !== false;
}

/**
 * Returns the crawl delay in ms for this domain.
 * Falls back to the configured default if not specified in robots.txt.
 */
async function getCrawlDelayMs(careerUrl) {
  const robots = await fetchRobots(careerUrl);
  if (!robots) return settings.scraping.crawlDelayDefaultMs;

  const delaySec = robots.getCrawlDelay(settings.scraping.userAgent)
    || robots.getCrawlDelay('*');

  if (delaySec) {
    return delaySec * 1000;
  }
  return settings.scraping.crawlDelayDefaultMs;
}

module.exports = { isAllowed, getCrawlDelayMs, clearCache };
