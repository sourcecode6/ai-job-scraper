const pdfParse = require('pdf-parse');
const fs = require('fs');
const { db } = require('../config/db');
const embeddingService = require('./embeddingService');
const nlpService = require('./nlpService');
const logger = require('../logger');

/**
 * Processes an uploaded PDF resume:
 * 1. Extracts raw text via pdf-parse
 * 2. Extracts display skills via local NLP vocab
 * 3. Gets semantic embedding via HuggingFace
 * 4. Stores everything in the users table
 * 5. Clears matched_jobs within 3-day window (for fresh re-match)
 *
 * @param {string} email
 * @param {string} pdfFilePath - Temp file path of uploaded PDF
 * @returns {Object} { resumeSkills, vectorDimensions }
 */
async function processResume(email, pdfFilePath) {
  logger.info('Processing resume', { email });

  // 1. Extract text from PDF
  const pdfBuffer = fs.readFileSync(pdfFilePath);
  let resumeText = '';
  try {
    const parsed = await pdfParse(pdfBuffer);
    resumeText = parsed.text?.trim() || '';
  } catch (err) {
    throw new Error(`PDF parsing failed: ${err.message}`);
  } finally {
    // Clean up temp file
    fs.unlink(pdfFilePath, () => {});
  }

  if (!resumeText) {
    throw new Error('Could not extract text from PDF. Ensure the PDF is not image-only/scanned.');
  }

  // 2. Extract display skills
  const resumeSkills = nlpService.extractSkills(resumeText);

  // 3. Get semantic embedding
  const vector = await embeddingService.embedResume(email, resumeText);

  logger.info('Resume processed', {
    logType: 'nlp',
    event: 'resume_processed',
    email,
    skillsExtracted: resumeSkills,
    vectorDimensions: vector?.length || 0,
  });

  const now = new Date().toISOString();

  // 4. Upsert user record (defaulting to all active companies for new users)
  const allCompanyNames = require('../config/companies').map(c => c.name);

  db.prepare(`
    INSERT INTO users (email, resume_text, resume_vector, resume_skills, selected_companies, resume_uploaded_at, created_at)
    VALUES (@email, @resumeText, @resumeVector, @resumeSkills, @selectedCompanies, @now, @now)
    ON CONFLICT(email) DO UPDATE SET
      resume_text = excluded.resume_text,
      resume_vector = excluded.resume_vector,
      resume_skills = excluded.resume_skills,
      resume_uploaded_at = excluded.resume_uploaded_at
  `).run({
    email,
    resumeText,
    resumeVector: vector ? JSON.stringify(vector) : null,
    resumeSkills: JSON.stringify(resumeSkills),
    selectedCompanies: JSON.stringify(allCompanyNames),
    now,
  });

  // 5. Clear matched_jobs that are still within the 3-day window
  //    so fresh re-matching runs against all current jobs
  const cleared = db.prepare(`
    DELETE FROM matched_jobs
    WHERE email = ? AND expires_at > datetime('now')
  `).run(email);

  logger.info('Cleared matched_jobs for re-match', {
    email,
    clearedCount: cleared.changes,
  });

  return { resumeSkills, vectorDimensions: vector?.length || 0 };
}

module.exports = { processResume };
