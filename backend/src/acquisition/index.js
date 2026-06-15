const { scrapeWorkday } = require('./workday');
const { scrapeJsonLd } = require('./jsonld');
const { scrapePlaywright } = require('./playwright');
const { scrapeSmartRecruiters } = require('./smartrecruiters');
const { scrapeEightfold } = require('./eightfold');
const { scrapeIbm } = require('./ibm');
const { scrapeCisco } = require('./cisco');
const { scrapeAmd } = require('./amd');
const { isAllowed } = require('./robotsChecker');
const { sleep } = require('./requestQueue');
const { db } = require('../config/db');
const embeddingService = require('../services/embeddingService');
const nlpService = require('../services/nlpService');
const settings = require('../config/settings');
const logger = require('../logger');

/**
 * Runs the full acquisition cycle for all active companies.
 * Called on startup and every 6 hours.
 */
async function runAcquisitionCycle() {
  logger.info('=== Acquisition cycle started ===');

  const companies = db.prepare("SELECT * FROM companies WHERE status = 'active'").all();

  for (let i = 0; i < companies.length; i++) {
    const company = companies[i];
    const companyConfig = getCompanyConfig(company.name);

    if (i > 0) {
      logger.info(`Waiting ${settings.scraping.betweenCompaniesDelayMs / 1000}s before next company...`);
      await sleep(settings.scraping.betweenCompaniesDelayMs);
    }

    await scrapeCompany(company, companyConfig);
  }

  // Retry any jobs that failed embedding
  await retryFailedEmbeddings();

  logger.info('=== Acquisition cycle complete ===');
}

async function scrapeCompany(company, companyConfig) {
  const startTime = Date.now();
  logger.info(`[${company.name}] Starting acquisition`, { ats: company.ats, tier: company.tier });

  try {
    // Check robots.txt for Tier 2/3 (not needed for Tier 1 ATS APIs)
    if (company.tier >= 2 && company.ats !== 'workday') {
      const allowed = await isAllowed(company.career_url);
      if (!allowed) {
        logger.warn(`[${company.name}] Blocked by robots.txt — skipping`);
        return;
      }
    }

    let rawJobs = [];

    if (company.ats === 'workday') {
      rawJobs = await scrapeWorkday(companyConfig);
    } else if (company.ats === 'playwright') {
      rawJobs = await scrapePlaywright(companyConfig);
    } else if (company.ats === 'smartrecruiters') {
      rawJobs = await scrapeSmartRecruiters(companyConfig);
    } else if (company.ats === 'eightfold') {
      rawJobs = await scrapeEightfold(companyConfig);
    } else if (company.ats === 'ibm') {
      rawJobs = await scrapeIbm(companyConfig);
    } else if (company.ats === 'cisco') {
      rawJobs = await scrapeCisco(companyConfig);
    } else if (company.ats === 'amd') {
      rawJobs = await scrapeAmd(companyConfig);
    } else {
      rawJobs = await scrapeJsonLd(companyConfig);
    }

    // Process and store each job
    let newCount = 0;
    let skipCount = 0;

    for (const job of rawJobs) {
      const isNew = await processJob(job, company.name);
      if (isNew) newCount++;
      else skipCount++;
    }

    // Update last_scraped_at
    db.prepare("UPDATE companies SET last_scraped_at = ? WHERE name = ?")
      .run(new Date().toISOString(), company.name);

    logger.info(`[${company.name}] Acquisition done`, {
      logType: 'scrape',
      company: company.name,
      status: 'success',
      jobsFound: rawJobs.length,
      jobsNew: newCount,
      jobsSkipped: skipCount,
      durationMs: Date.now() - startTime,
    });

  } catch (err) {
    if (err.markDegraded) {
      db.prepare("UPDATE companies SET status = 'degraded', degraded_reason = ? WHERE name = ?")
        .run(err.message, company.name);
      logger.error(`[${company.name}] Marked as degraded`, { reason: err.message });
    } else {
      logger.error(`[${company.name}] Acquisition error`, { message: err.message });
    }
  }
}

/**
 * Inserts a job if it doesn't exist. Queues embedding if new.
 * Returns true if job was new, false if duplicate.
 */
async function processJob(job, companyName) {
  const now = new Date();
  let expiresAt = new Date(now.getTime() + settings.dataRetentionDays * 24 * 60 * 60 * 1000);

  if (job.postedDate) {
    const postedMs = Date.parse(job.postedDate);
    if (!isNaN(postedMs)) {
      expiresAt = new Date(postedMs + settings.dataRetentionDays * 24 * 60 * 60 * 1000);
    } else {
      const lowercasePosted = job.postedDate.toLowerCase();
      let daysAgo = 0;
      if (lowercasePosted.includes('yesterday')) {
        daysAgo = 1;
      } else if (lowercasePosted.includes('today')) {
        daysAgo = 0;
      } else {
        const daysMatch = lowercasePosted.match(/(\d+)\s+days?\s+ago/);
        if (daysMatch) {
          daysAgo = parseInt(daysMatch[1], 10);
        } else {
          const weeksMatch = lowercasePosted.match(/(\d+)\s+weeks?\s+ago/);
          if (weeksMatch) {
            daysAgo = parseInt(weeksMatch[1], 10) * 7;
          } else if (lowercasePosted.includes('month') || lowercasePosted.includes('year') || lowercasePosted.includes('30+ days')) {
            daysAgo = 30;
          }
        }
      }
      if (daysAgo > 0) {
        expiresAt = new Date(now.getTime() - (daysAgo - settings.dataRetentionDays) * 24 * 60 * 60 * 1000);
      }
    }
  }

  // Extract display skills using local vocab (fast, no API)
  const skillsDisplay = nlpService.extractSkills(
    `${job.jobTitle} ${job.department} ${job.jobDescription}`
  );

  const requiredYoe = extractYoE(job.jobDescription);

  try {
    db.prepare(`
      INSERT INTO jobs (
        company_name, job_id, job_title, location, department,
        posted_date, employment_type, job_description, url, apply_url,
        skills_display, required_yoe, embedding_status, scraped_at, expires_at
      ) VALUES (
        @companyName, @jobId, @jobTitle, @location, @department,
        @postedDate, @employmentType, @jobDescription, @url, @applyUrl,
        @skillsDisplay, @requiredYoe, 'pending', @scrapedAt, @expiresAt
      )
    `).run({
      companyName: job.companyName,
      jobId: job.jobId,
      jobTitle: job.jobTitle,
      location: job.location || '',
      department: job.department || '',
      postedDate: job.postedDate || now.toISOString(),
      employmentType: job.employmentType || 'Full-time',
      jobDescription: job.jobDescription || '',
      url: job.url || '',
      applyUrl: job.applyUrl || '',
      skillsDisplay: JSON.stringify(skillsDisplay),
      requiredYoe: requiredYoe,
      scrapedAt: now.toISOString(),
      expiresAt: expiresAt.toISOString(),
    });

    // Queue embedding (rate-limited)
    embeddingService.queueJobEmbedding(job.jobId, companyName);

    return true; // new job
  } catch (err) {
    if (err.message?.includes('UNIQUE constraint failed')) {
      return false; // duplicate
    }
    logger.error(`Failed to insert job`, { jobId: job.jobId, error: err.message });
    return false;
  }
}

async function retryFailedEmbeddings() {
  const failed = db.prepare(`
    SELECT job_id, company_name, job_title, job_description, department
    FROM jobs
    WHERE embedding_status = 'failed'
    AND expires_at > datetime('now')
    LIMIT 20
  `).all();

  if (failed.length === 0) return;

  logger.info(`Retrying ${failed.length} failed embeddings`);
  for (const job of failed) {
    embeddingService.queueJobEmbedding(job.job_id, job.company_name);
  }
}

function getCompanyConfig(name) {
  // Merges DB company row with full config from companies.js
  const configs = require('../config/companies');
  return configs.find((c) => c.name === name) || {};
}

/**
 * Extracts required Years of Experience (YoE) from a job description text using heuristics.
 *
 * @param {string} text - Raw job description
 * @returns {number|null} Experience required in years, or null if not found
 */
function extractYoE(text) {
  if (!text) return null;

  const regex = /(?:minimum\s+(?:of\s+)?|min\s+)?(\d+)(?:\s*(?:-|to)\s*(\d+))?\s*\+?\s*years?/gi;
  let match;
  const matches = [];

  while ((match = regex.exec(text)) !== null) {
    const minVal = parseInt(match[1], 10);
    
    // Get context around the match to look for keywords like total, overall, minimum
    const matchIndex = match.index;
    const contextStart = Math.max(0, matchIndex - 60);
    const contextEnd = Math.min(text.length, matchIndex + match[0].length + 40);
    const context = text.slice(contextStart, contextEnd).toLowerCase();

    const isOverall = /total|overall|minimum|min|at least/i.test(context);
    
    matches.push({
      minVal,
      isOverall
    });
  }

  if (matches.length === 0) return null;

  // Search for the overall/total/minimum requirement first
  const overallMatch = matches.find(m => m.isOverall);
  if (overallMatch) {
    return overallMatch.minVal;
  }

  // Fallback to the first/lowest number found (ignoring unrealistic numbers like > 15)
  const reasonableMatches = matches.filter(m => m.minVal <= 15);
  if (reasonableMatches.length > 0) {
    return reasonableMatches[0].minVal;
  }

  return null;
}

module.exports = { runAcquisitionCycle, extractYoE };
