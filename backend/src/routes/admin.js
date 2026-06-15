const express = require('express');
const axios = require('axios');
const { runMatchCycle, matchForUser } = require('../services/matchService');
const { runCleanup } = require('../services/cleanupService');
const { db } = require('../config/db');
const logger = require('../logger');

const router = express.Router();

// Python service endpoint base
const PYTHON_SERVICE_URL = 'http://127.0.0.1:8000';

/**
 * GET /api/admin/status
 * Returns combined status from Node.js and Python FastAPI service.
 */
router.get('/status', async (req, res) => {
  try {
    const pyRes = await axios.get(`${PYTHON_SERVICE_URL}/status`, { timeout: 5000 });
    const pyStatus = pyRes.data;
    
    res.json({
      node_status: {
        db_path: 'backend/data/jobs.db',
        cleanup_schedule: '2 AM daily',
      },
      python_status: pyStatus
    });
  } catch (err) {
    res.json({
      node_status: {
        db_path: 'backend/data/jobs.db',
        cleanup_schedule: '2 AM daily',
      },
      python_status: {
        error: 'Failed to reach Python service',
        message: err.message
      }
    });
  }
});

/**
 * POST /api/admin/scrape
 * Proxy manual trigger to Python FastAPI scraper.
 */
router.post('/scrape', async (req, res) => {
  try {
    const pyRes = await axios.post(`${PYTHON_SERVICE_URL}/scrape`, {}, { timeout: 5000 });
    res.json(pyRes.data);
  } catch (err) {
    logger.error('Failed to trigger manual scrape on Python service', { error: err.message });
    res.status(500).json({ error: 'Failed to contact Python scraping service', details: err.message });
  }
});

/**
 * POST /api/admin/match-all
 * Triggers match + email for all users. Called by Python scraper on completion.
 */
router.post('/match-all', async (req, res) => {
  res.json({ success: true, message: 'Match cycle triggered for all users' });
  runMatchCycle().catch((err) =>
    logger.error('Match all error', { error: err.message })
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
