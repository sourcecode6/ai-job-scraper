require('dotenv').config();
const express = require('express');
const path = require('path');
const logger = require('./logger');
const { init: initDb } = require('./config/db');
const { startPythonService } = require('./services/pythonService');
const { initScheduler } = require('./schedulers');

const app = express();

// ── Middleware ────────────────────────────────────────────────────────────
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Request logger (brief)
app.use((req, _res, next) => {
  logger.info(`${req.method} ${req.path}`);
  next();
});

// ── Routes ────────────────────────────────────────────────────────────────
app.use('/api/resume',    require('./routes/resume'));
app.use('/api/users',     require('./routes/users'));
app.use('/api',           require('./routes/companies'));   // /api/companies, /api/jobs, /api/matches
app.use('/api/admin',     require('./routes/admin'));

// Health check
app.get('/', (req, res) => {
  res.json({
    service: 'AI Job Scraper Backend',
    status: 'running',
    version: '1.0.0',
    docs: 'See README.md for API usage with curl',
  });
});

// ── Error handler ─────────────────────────────────────────────────────────
app.use((err, req, res, _next) => {
  logger.error('Unhandled route error', { message: err.message, path: req.path });
  res.status(err.status || 500).json({ error: err.message || 'Internal server error' });
});

// ── Start ─────────────────────────────────────────────────────────────────
const PORT = process.env.PORT || 3000;

async function start() {
  try {
    // 1. Initialize database
    initDb();

    // 1.5. Start local Python FastAPI NLP service
    startPythonService();

    // 2. Start Express server
    app.listen(PORT, () => {
      logger.info(`✅ Server running at http://localhost:${PORT}`);
    });

    // 3. Start scheduler (runs startup scrape immediately)
    await initScheduler();
  } catch (err) {
    logger.error('Failed to start server', { message: err.message });
    process.exit(1);
  }
}

start();
