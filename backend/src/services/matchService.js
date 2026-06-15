const { db } = require('../config/db');
const { cosineSimilarity } = require('./embeddingService');
const emailService = require('./emailService');
const settings = require('../config/settings');
const logger = require('../logger');

function isJobWithinRetention(job, retentionDays) {
  const cutoff = Date.now() - retentionDays * 24 * 60 * 60 * 1000;
  
  if (job.posted_date) {
    const postedMs = Date.parse(job.posted_date);
    if (!isNaN(postedMs)) {
      return postedMs >= cutoff;
    }
    
    // Relative string parsing
    const lowercasePosted = job.posted_date.toLowerCase();
    if (lowercasePosted.includes('today')) return true;
    if (lowercasePosted.includes('yesterday')) return retentionDays >= 1;
    
    const daysMatch = lowercasePosted.match(/(\d+)\s+days?\s+ago/);
    if (daysMatch) {
      const daysAgo = parseInt(daysMatch[1], 10);
      return daysAgo <= retentionDays;
    }
    
    const weeksMatch = lowercasePosted.match(/(\d+)\s+weeks?\s+ago/);
    if (weeksMatch) {
      const weeksAgo = parseInt(weeksMatch[1], 10);
      return (weeksAgo * 7) <= retentionDays;
    }
    
    if (lowercasePosted.includes('month') || lowercasePosted.includes('year') || lowercasePosted.includes('30+ days')) {
      return false;
    }
  }
  
  // Fallback to scraped_at
  if (job.scraped_at) {
    const scrapedMs = Date.parse(job.scraped_at);
    if (!isNaN(scrapedMs)) {
      return scrapedMs >= cutoff;
    }
  }
  
  return true;
}

function isIndia(location) {
  if (!location) return false;
  const loc = location.toLowerCase();
  return loc.includes('india') || 
         loc.includes(', in') || 
         loc.endsWith(' in') || 
         /\bin\b/.test(loc);
}

/**
 * Runs the full match cycle for all registered users.
 * For each user:
 *   1. Finds new jobs (since last_notified_at) with completed embeddings
 *   2. Computes cosine similarity against resume vector
 *   3. Records matches above threshold (deduplication via matched_jobs)
 *   4. Also retries previously unnotified matches (email failed earlier)
 *   5. Sends a combined email digest
 */
async function runMatchCycle() {
  const users = db.prepare('SELECT * FROM users WHERE resume_vector IS NOT NULL').all();

  if (users.length === 0) {
    logger.info('No users with resume vectors — skipping match cycle');
    return;
  }

  for (const user of users) {
    await matchForUser(user);
  }
}

/**
 * Runs match cycle for a single user. Also used by admin/manual trigger.
 * @param {Object|string} userOrEmail - user row or email string
 */
async function matchForUser(userOrEmail) {
  const user = typeof userOrEmail === 'string'
    ? db.prepare('SELECT * FROM users WHERE email = ?').get(userOrEmail)
    : userOrEmail;

  if (!user || !user.resume_vector) {
    logger.warn('Match requested but no resume vector found', { email: user?.email });
    return;
  }

  const resumeVector = JSON.parse(user.resume_vector);
  let selectedCompanies = JSON.parse(user.selected_companies || '[]');
  const threshold = settings.matchThreshold;

  if (selectedCompanies.length === 0) {
    const activeCompanies = db.prepare("SELECT name FROM companies WHERE status = 'active'").all();
    selectedCompanies = activeCompanies.map(c => c.name);
  }

  if (selectedCompanies.length === 0) {
    logger.warn('No active companies found in database for match cycle', { email: user.email });
    return;
  }

  // Fetch jobs for matching (filtering only by selected companies and active status)
  const placeholders = selectedCompanies.map(() => '?').join(',');

  const newJobs = db.prepare(`
    SELECT * FROM jobs
    WHERE company_name IN (${placeholders})
    AND embedding_status = 'done'
    AND (embedding_vector IS NOT NULL OR (title_vector IS NOT NULL AND description_vector IS NOT NULL))
    AND expires_at > datetime('now')
  `).all(...selectedCompanies);

  // Score each job
  const newMatches = [];
  for (const job of newJobs) {
    // Skip if job is older than settings.dataRetentionDays
    if (!isJobWithinRetention(job, settings.dataRetentionDays)) {
      continue;
    }

    let score;
    if (job.title_vector && job.description_vector) {
      const titleVec = JSON.parse(job.title_vector);
      const descVec = JSON.parse(job.description_vector);
      const titleScore = cosineSimilarity(resumeVector, titleVec) * 100;
      const descScore = cosineSimilarity(resumeVector, descVec) * 100;
      score = (titleScore * 0.5) + (descScore * 0.5);
    } else {
      const jobVector = JSON.parse(job.embedding_vector);
      score = cosineSimilarity(resumeVector, jobVector) * 100;
    }

    if (score >= threshold) {
      // Deduplication check
      const existing = db.prepare(`
        SELECT id FROM matched_jobs
        WHERE email = ? AND company_name = ? AND job_id = ?
      `).get(user.email, job.company_name, job.job_id);

      if (!existing) {
        const expiresAt = job.expires_at;
        db.prepare(`
          INSERT OR IGNORE INTO matched_jobs
            (email, job_id, company_name, match_score, job_title, location, apply_url, skills_display, required_yoe, notified, expires_at)
          VALUES
            (@email, @jobId, @companyName, @score, @jobTitle, @location, @applyUrl, @skillsDisplay, @requiredYoe, 0, @expiresAt)
        `).run({
          email: user.email,
          jobId: job.job_id,
          companyName: job.company_name,
          score: Math.round(score * 10) / 10,
          jobTitle: job.job_title,
          location: job.location,
          applyUrl: job.apply_url,
          skillsDisplay: job.skills_display,
          requiredYoe: job.required_yoe,
          expiresAt,
        });

        newMatches.push({ ...job, matchScore: Math.round(score * 10) / 10, required_yoe: job.required_yoe });
      }
    }
  }

  // Also fetch previously unnotified matches (email failed earlier)
  const pendingMatches = db.prepare(`
    SELECT * FROM matched_jobs
    WHERE email = ? AND notified = 0 AND expires_at > datetime('now')
  `).all(user.email);

  const allMatchesToSend = [
    ...newMatches,
    ...pendingMatches.filter(
      (p) => !newMatches.find((m) => m.job_id === p.job_id && m.company_name === p.company_name)
    ),
  ];

  // Sort matches first by country (India first) and then by match percentage (descending)
  allMatchesToSend.sort((a, b) => {
    const locA = a.location || '';
    const locB = b.location || '';
    const isIndiaA = isIndia(locA);
    const isIndiaB = isIndia(locB);

    if (isIndiaA && !isIndiaB) return -1;
    if (!isIndiaA && isIndiaB) return 1;

    // Both are India or both are not India — sort by match score descending
    const scoreA = a.matchScore || a.match_score || 0;
    const scoreB = b.matchScore || b.match_score || 0;
    return scoreB - scoreA;
  });

  if (allMatchesToSend.length === 0) {
    logger.info('No new matches for user', { email: user.email });
    return;
  }

  logger.info(`Found ${allMatchesToSend.length} matches for user`, { email: user.email });

  // Attempt email send
  const sent = await emailService.sendJobDigest(user.email, allMatchesToSend);

  if (sent) {
    // Mark all as notified
    const now = new Date().toISOString();
    for (const match of allMatchesToSend) {
      db.prepare(`
        UPDATE matched_jobs SET notified = 1, notified_at = ?
        WHERE email = ? AND company_name = ? AND job_id = ?
      `).run(now, user.email, match.company_name || match.companyName, match.job_id || match.jobId);
    }
    db.prepare('UPDATE users SET last_notified_at = ? WHERE email = ?')
      .run(now, user.email);
    logger.info('Email digest sent and matches marked notified', { email: user.email, count: allMatchesToSend.length });
  } else {
    // Leave notified=0 — will retry next cycle
    logger.error('Email send failed — matches left as pending for retry', { email: user.email });
  }
}

module.exports = { runMatchCycle, matchForUser };
