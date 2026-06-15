const cron = require('node-cron');
const { runCleanup } = require('../services/cleanupService');
const logger = require('../logger');

let cleanupTask = null;

/**
 * Initializes the Node-side scheduler:
 * Registers 2 AM daily cron for data cleanup.
 * Scraping scheduler is managed entirely by the Python FastAPI service.
 */
async function initScheduler() {
  logger.info('Scheduler initializing...');

  // === Daily at 2 AM: cleanup expired data ===
  cleanupTask = cron.schedule('0 2 * * *', () => {
    logger.info('Running daily database cleanup...');
    runCleanup();
  });

  logger.info('Node scheduler ready — cleanup at 2 AM daily');
}

module.exports = { initScheduler };
