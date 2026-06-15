const { db } = require('../config/db');
console.log(db.prepare("SELECT job_id, job_title, url, apply_url FROM jobs WHERE company_name = 'NVIDIA' LIMIT 5").all());
