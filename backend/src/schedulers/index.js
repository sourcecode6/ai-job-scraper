const cron = require('node-cron');
const { runAcquisitionCycle } = require('../acquisition');
const { runMatchCycle } = require('../services/matchService');
const { runCleanup } = require('../services/cleanupService');
const { clearCache } = require('../acquisition/robotsChecker');
const settings = require('../config/settings');
const logger = require('../logger');

let scrapeTask = null;
let cleanupTask = null;

/**
 * Initializes the scheduler:
 * 1. Immediately runs a full scrape+match cycle on startup
 * 2. Registers 6-hour cron for subsequent scrape+match cycles
 * 3. Registers 2 AM daily cron for cleanup
 */
async function initScheduler() {
  logger.info('Scheduler initializing...');

  // === Startup: run immediately ===
  logger.info('Running startup scrape cycle...');
  await runFullCycle();

  // === Every 6 hours: scrape + match ===
  const cronExpr = `0 */${settings.scrapeIntervalHours} * * *`;
  scrapeTask = cron.schedule(cronExpr, async () => {
    logger.info(`Cron triggered (every ${settings.scrapeIntervalHours}h)`);
    await runFullCycle();
  });

  // === Daily at 2 AM: cleanup expired data ===
  cleanupTask = cron.schedule('0 2 * * *', () => {
    runCleanup();
  });

  logger.info(`Scheduler ready — scrape every ${settings.scrapeIntervalHours}h, cleanup at 2 AM daily`);
}

async function runFullCycle() {
  try {
    clearCache(); // Reset robots.txt cache at start of each cycle
    await runAcquisitionCycle();
    await runMatchCycle();
  } catch (err) {
    logger.error('Full cycle error', { message: err.message, stack: err.stack });
  }
}

function getStatus() {
  const companies = require('../config/db').db
    .prepare('SELECT name, status, last_scraped_at, degraded_reason FROM companies')
    .all();

  return {
    scrapeIntervalHours: settings.scrapeIntervalHours,
    companies,
    cronActive: !!scrapeTask,
    nextScrapeApprox: scrapeTask ? `every ${settings.scrapeIntervalHours}h from startup` : 'not running',
  };
}

module.exports = { initScheduler, getStatus };
