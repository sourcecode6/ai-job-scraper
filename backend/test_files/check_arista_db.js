const { DatabaseSync } = require('node:sqlite');
const path = require('path');
const db = new DatabaseSync(path.join('backend', 'data', 'jobs.db'));
db.prepare('PRAGMA journal_mode = WAL;').get();

// Check Arista jobs count
const count = db.prepare("SELECT COUNT(*) as cnt FROM jobs WHERE company_name = 'Arista Networks'").get();
console.log('Arista jobs in DB:', count.cnt);

// Check sample job to see what data looks like
const sample = db.prepare("SELECT job_id, job_title, location, url, job_description, skills_display, embedding_status, expires_at FROM jobs WHERE company_name = 'Arista Networks' LIMIT 3").all();
console.log('Sample Arista jobs:', JSON.stringify(sample, null, 2));

// Check companies table for Arista
const co = db.prepare("SELECT * FROM companies WHERE name = 'Arista Networks'").get();
console.log('Arista in companies table:', JSON.stringify(co, null, 2));

// Check all companies job counts
const allCo = db.prepare("SELECT company_name, COUNT(*) as cnt FROM jobs GROUP BY company_name ORDER BY cnt DESC").all();
console.log('\nAll company job counts:');
allCo.forEach(r => console.log(`  ${r.company_name}: ${r.cnt}`));
