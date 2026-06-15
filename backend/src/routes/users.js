const express = require('express');
const { db } = require('../config/db');
const logger = require('../logger');

const router = express.Router();

/**
 * POST /api/users
 * Creates or updates a user profile.
 * Body: { email, selectedCompanies: [...], matchThreshold: 65 }
 */
router.post('/', (req, res) => {
  const { email, selectedCompanies, matchThreshold } = req.body;
  if (!email) return res.status(400).json({ error: 'email is required' });

  const now = new Date().toISOString();
  const companies = Array.isArray(selectedCompanies) ? selectedCompanies : [];

  db.prepare(`
    INSERT INTO users (email, selected_companies, match_threshold, created_at)
    VALUES (@email, @companies, @threshold, @now)
    ON CONFLICT(email) DO UPDATE SET
      selected_companies = excluded.selected_companies,
      match_threshold    = excluded.match_threshold
  `).run({
    email,
    companies: JSON.stringify(companies),
    threshold: matchThreshold || 65,
    now,
  });

  logger.info('User created/updated', { email, companies, threshold: matchThreshold });
  res.json({ success: true, email, selectedCompanies: companies, matchThreshold: matchThreshold || 65 });
});

/**
 * GET /api/users?email=X
 * Returns user profile.
 */
router.get('/', (req, res) => {
  const { email } = req.query;
  if (!email) return res.status(400).json({ error: 'email query param required' });

  const user = db.prepare('SELECT * FROM users WHERE email = ?').get(email);
  if (!user) return res.status(404).json({ error: 'User not found' });

  res.json({
    email: user.email,
    selectedCompanies: JSON.parse(user.selected_companies || '[]'),
    resumeSkills: JSON.parse(user.resume_skills || '[]'),
    matchThreshold: user.match_threshold,
    resumeUploadedAt: user.resume_uploaded_at,
    lastNotifiedAt: user.last_notified_at,
    hasResume: !!user.resume_vector,
  });
});

/**
 * PUT /api/users/:email/companies
 * Updates selected companies list.
 */
router.put('/:email/companies', (req, res) => {
  const { email } = req.params;
  const { selectedCompanies } = req.body;
  if (!Array.isArray(selectedCompanies)) return res.status(400).json({ error: 'selectedCompanies must be an array' });

  db.prepare('UPDATE users SET selected_companies = ? WHERE email = ?')
    .run(JSON.stringify(selectedCompanies), email);

  res.json({ success: true, email, selectedCompanies });
});

module.exports = router;
