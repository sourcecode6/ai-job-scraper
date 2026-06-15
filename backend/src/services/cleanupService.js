const { db } = require('../config/db');
const logger = require('../logger');

/**
 * Deletes expired jobs and matched_jobs records.
 * Run daily at 2 AM.
 */
function runCleanup() {
  logger.info('=== Daily cleanup started ===');

  const jobsResult = db.prepare(
    "DELETE FROM jobs WHERE expires_at < datetime('now')"
  ).run();

  const matchedResult = db.prepare(
    "DELETE FROM matched_jobs WHERE expires_at < datetime('now')"
  ).run();

  logger.info('Daily cleanup complete', {
    logType: 'scrape',
    event: 'cleanup',
    jobsDeleted: jobsResult.changes,
    matchedJobsDeleted: matchedResult.changes,
  });
}

module.exports = { runCleanup };
