const { DatabaseSync } = require('node:sqlite');
const path = require('path');
const fs = require('fs');
const logger = require('../logger');
const companiesConfig = require('./companies');

const DB_PATH = path.join(__dirname, '../../data/jobs.db');

// Ensure data directory exists
const dataDir = path.dirname(DB_PATH);
if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });

const db = new DatabaseSync(DB_PATH);

// Simple compatibility wrappers for better-sqlite3 API
db.pragma = function(cmd) {
  return db.exec(`PRAGMA ${cmd};`);
};

// Enable WAL mode for better concurrent read performance
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

// Transaction support wrapper
db.transaction = function(fn) {
  return function(...args) {
    db.exec('BEGIN TRANSACTION');
    try {
      const result = fn(...args);
      db.exec('COMMIT');
      return result;
    } catch (err) {
      db.exec('ROLLBACK');
      throw err;
    }
  };
};

// Wrap db.prepare to allow bare named parameters like better-sqlite3
const originalPrepare = db.prepare.bind(db);
db.prepare = function(sql) {
  const stmt = originalPrepare(sql);
  if (typeof stmt.setAllowBareNamedParameters === 'function') {
    stmt.setAllowBareNamedParameters(true);
  }
  return stmt;
};

function initSchema() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS companies (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      name            TEXT NOT NULL UNIQUE,
      ats             TEXT NOT NULL,
      tier            INTEGER NOT NULL,
      career_url      TEXT NOT NULL,
      filters         TEXT,
      status          TEXT DEFAULT 'active',
      last_scraped_at TEXT,
      degraded_reason TEXT
    );

    CREATE TABLE IF NOT EXISTS jobs (
      id               INTEGER PRIMARY KEY AUTOINCREMENT,
      company_name     TEXT NOT NULL,
      job_id           TEXT NOT NULL,
      job_title        TEXT NOT NULL,
      location         TEXT,
      department       TEXT,
      posted_date      TEXT,
      employment_type  TEXT,
      job_description  TEXT,
      url              TEXT,
      apply_url        TEXT,
      skills_display   TEXT,
      embedding_vector TEXT,
      title_vector     TEXT,
      description_vector TEXT,
      required_yoe     INTEGER DEFAULT NULL,
      embedding_status TEXT DEFAULT 'pending',
      scraped_at       TEXT NOT NULL,
      expires_at       TEXT NOT NULL,
      UNIQUE(company_name, job_id)
    );

    CREATE TABLE IF NOT EXISTS users (
      id                  INTEGER PRIMARY KEY AUTOINCREMENT,
      email               TEXT NOT NULL UNIQUE,
      resume_text         TEXT,
      resume_vector       TEXT,
      resume_skills       TEXT,
      selected_companies  TEXT,
      match_threshold     REAL DEFAULT 65.0,
      resume_uploaded_at  TEXT,
      last_notified_at    TEXT,
      created_at          TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS matched_jobs (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      email        TEXT NOT NULL,
      job_id       TEXT NOT NULL,
      company_name TEXT NOT NULL,
      match_score  REAL NOT NULL,
      job_title    TEXT,
      location     TEXT,
      apply_url    TEXT,
      skills_display TEXT,
      required_yoe INTEGER DEFAULT NULL,
      notified     INTEGER DEFAULT 0,
      notified_at  TEXT,
      expires_at   TEXT NOT NULL,
      UNIQUE(email, company_name, job_id)
    );

    CREATE INDEX IF NOT EXISTS idx_jobs_company     ON jobs(company_name);
    CREATE INDEX IF NOT EXISTS idx_jobs_expires     ON jobs(expires_at);
    CREATE INDEX IF NOT EXISTS idx_jobs_embedding   ON jobs(embedding_status);
    CREATE INDEX IF NOT EXISTS idx_matched_email    ON matched_jobs(email);
    CREATE INDEX IF NOT EXISTS idx_matched_notified ON matched_jobs(notified);
  `);

  // Migrations for existing databases
  try {
    db.exec("ALTER TABLE jobs ADD COLUMN title_vector TEXT;");
  } catch (e) {}
  try {
    db.exec("ALTER TABLE jobs ADD COLUMN description_vector TEXT;");
  } catch (e) {}
  try {
    db.exec("ALTER TABLE jobs ADD COLUMN required_yoe INTEGER DEFAULT NULL;");
  } catch (e) {}
  try {
    db.exec("ALTER TABLE matched_jobs ADD COLUMN required_yoe INTEGER DEFAULT NULL;");
  } catch (e) {}
}

function seedCompanies() {
  const insert = db.prepare(`
    INSERT INTO companies (name, ats, tier, career_url, filters, status)
    VALUES (@name, @ats, @tier, @career_url, @filters, 'active')
    ON CONFLICT(name) DO UPDATE SET
      ats = excluded.ats,
      tier = excluded.tier,
      career_url = excluded.career_url,
      filters = excluded.filters
  `);

  const insertMany = db.transaction((companies) => {
    for (const c of companies) {
      insert.run({
        name: c.name,
        ats: c.ats,
        tier: c.tier,
        career_url: c.careerUrl,
        filters: JSON.stringify(c.filters || {}),
      });
    }
  });

  insertMany(companiesConfig);
  logger.info(`Seeded ${companiesConfig.length} companies into DB`);
}

function init() {
  initSchema();
  seedCompanies();
  logger.info(`SQLite database ready at ${DB_PATH}`);
}

module.exports = { db, init };
