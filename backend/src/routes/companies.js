const express = require('express');
const { db } = require('../config/db');

const router = express.Router();

/**
 * GET /api/companies
 * Returns all companies with their current status.
 */
router.get('/', (req, res) => {
  const companies = db.prepare(
    'SELECT name, ats, tier, career_url, status, last_scraped_at, degraded_reason FROM companies ORDER BY name'
  ).all();
  res.json(companies);
});

/**
 * GET /api/jobs?company=X
 * Returns all active jobs for a company.
 */
router.get('/jobs', (req, res) => {
  const { company } = req.query;
  if (!company) return res.status(400).json({ error: 'company query param required' });

  const jobs = db.prepare(`
    SELECT job_id, job_title, location, department, posted_date, employment_type,
           apply_url, skills_display, embedding_status, scraped_at
    FROM jobs
    WHERE company_name = ? AND expires_at > datetime('now')
    ORDER BY scraped_at DESC
  `).all(company);

  res.json({ company, count: jobs.length, jobs });
});

/**
 * GET /api/matches?email=X
 * Returns all matched jobs for a user.
 */
router.get('/matches', (req, res) => {
  const { email } = req.query;
  if (!email) return res.status(400).json({ error: 'email query param required' });

  const matches = db.prepare(`
    SELECT company_name, job_id, job_title, location, match_score,
           apply_url, skills_display, notified, notified_at, expires_at
    FROM matched_jobs
    WHERE email = ? AND expires_at > datetime('now')
    ORDER BY match_score DESC
  `).all(email);

  res.json({ email, count: matches.length, matches });
});

module.exports = router;
