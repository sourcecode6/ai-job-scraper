const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const resumeService = require('../services/resumeService');
const matchService = require('../services/matchService');
const logger = require('../logger');

const router = express.Router();

// Configure multer for PDF uploads
const uploadsDir = path.join(__dirname, '../../uploads');
if (!fs.existsSync(uploadsDir)) fs.mkdirSync(uploadsDir, { recursive: true });

const upload = multer({
  dest: uploadsDir,
  limits: { fileSize: 10 * 1024 * 1024 }, // 10 MB max
  fileFilter: (req, file, cb) => {
    if (file.mimetype === 'application/pdf') {
      cb(null, true);
    } else {
      cb(new Error('Only PDF files are accepted'));
    }
  },
});

/**
 * POST /api/resume/upload
 * Body: multipart/form-data with fields: email (string), resume (file)
 */
router.post('/upload', upload.single('resume'), async (req, res) => {
  const { email } = req.body;

  if (!email) return res.status(400).json({ error: 'email is required' });
  if (!req.file) return res.status(400).json({ error: 'PDF resume file is required' });

  try {
    const result = await resumeService.processResume(email, req.file.path);

    logger.info('Resume uploaded and processed', { email });

    // Trigger immediate match cycle for this user
    matchService.matchForUser(email).catch((err) =>
      logger.error('Post-upload match cycle error', { email, error: err.message })
    );

    res.json({
      success: true,
      email,
      skillsExtracted: result.resumeSkills,
      skillsCount: result.resumeSkills.length,
      vectorDimensions: result.vectorDimensions,
      message: 'Resume processed. Matching is running in background — check your email.',
    });
  } catch (err) {
    logger.error('Resume upload error', { email, error: err.message });
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
