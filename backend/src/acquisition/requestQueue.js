const PQueue = require('p-queue').default;
const settings = require('../config/settings');

/**
 * Global HTTP request queue — max 1 request per 3 seconds
 * Used for all Axios/Cheerio Tier 2 requests and Playwright requests.
 */
const httpQueue = new PQueue({
  concurrency: 1,
  interval: settings.scraping.globalRequestDelayMs,
  intervalCap: 1,
});

/**
 * Local embedding queue — no rate limits since we run the model locally/offline.
 * We keep concurrency at 1 to process them sequentially and prevent CPU spikes.
 */
const embeddingQueue = new PQueue({
  concurrency: 1,
});

/**
 * Wrap an async fn in the HTTP queue.
 * @param {Function} fn - async function to throttle
 */
function queueHttp(fn) {
  return httpQueue.add(fn);
}

/**
 * Wrap an async fn in the embedding queue.
 * @param {Function} fn - async function to throttle
 */
function queueEmbedding(fn) {
  return embeddingQueue.add(fn);
}

/**
 * Simple delay helper.
 */
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

module.exports = { queueHttp, queueEmbedding, sleep };
