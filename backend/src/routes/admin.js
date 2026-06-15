const express = require('express');
const { runAcquisitionCycle } = require('../acquisition');
const { matchForUser } = require('../services/matchService');
const { runCleanup } = require('../services/cleanupService');
const { getStatus } = require('../schedulers');
const { db } = require('../config/db');
const logger = require('../logger');

const router = express.Router();

/**
 * GET /api/admin/status
 * Returns scheduler status and company last-scraped timestamps.
 */
router.get('/status', (req, res) => {
  res.json(getStatus());
});

/**
 * POST /api/admin/scrape
 * Manually triggers the full acquisition cycle.
 */
router.post('/scrape', async (req, res) => {
  res.json({ success: true, message: 'Scrape cycle triggered — check logs/scrape.log' });
  // Run async after responding
  runAcquisitionCycle().catch((err) =>
    logger.error('Manual scrape error', { error: err.message })
  );
});

/**
 * POST /api/admin/match?email=X
 * Manually triggers match + email for one user.
 */
router.post('/match', async (req, res) => {
  const { email } = req.query;
  if (!email) return res.status(400).json({ error: 'email query param required' });

  res.json({ success: true, message: `Match cycle triggered for ${email} — check your inbox` });
  matchForUser(email).catch((err) =>
    logger.error('Manual match error', { email, error: err.message })
  );
});

/**
 * POST /api/admin/reset?email=X
 * Resets the matching history (clears matched_jobs and sets last_notified_at to NULL) for a user.
 */
router.post('/reset', (req, res) => {
  const { email } = req.query;
  if (!email) return res.status(400).json({ error: 'email query param required' });

  db.prepare("UPDATE users SET last_notified_at = NULL WHERE email = ?").run(email);
  db.prepare("DELETE FROM matched_jobs WHERE email = ?").run(email);

  logger.info(`Reset match history for user`, { email });
  res.json({ success: true, message: `Match history and last_notified_at reset for ${email}.` });
});

/**
 * POST /api/admin/activate?company=X
 * Re-activates a degraded company.
 */
router.post('/activate', (req, res) => {
  const { company } = req.query;
  if (!company) return res.status(400).json({ error: 'company query param required' });

  const result = db.prepare(
    "UPDATE companies SET status = 'active', degraded_reason = NULL WHERE name = ?"
  ).run(company);

  if (result.changes === 0) return res.status(404).json({ error: 'Company not found' });

  logger.info(`Company re-activated`, { company });
  res.json({ success: true, company, status: 'active' });
});

/**
 * POST /api/admin/cleanup
 * Manually triggers the cleanup job.
 */
router.post('/cleanup', (req, res) => {
  runCleanup();
  res.json({ success: true, message: 'Cleanup complete — check logs/scrape.log' });
});

module.exports = router;
