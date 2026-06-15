const fs = require('fs');
const path = require('path');

// Load environment variables explicitly from backend/.env
require('dotenv').config({ path: path.resolve(__dirname, '../../.env') });

const { init: initDb } = require('../config/db');
const resumeService = require('../services/resumeService');
const logger = require('../logger');

async function run() {
  try {
    // 1. Initialize database first
    initDb();

    // 2. Get email from .env
    const email = process.env.NOTIFY_EMAIL || process.env.EMAIL_USER;
    if (!email) {
      console.error('❌ Error: NOTIFY_EMAIL or EMAIL_USER must be set in backend/.env');
      process.exit(1);
    }

    // 3. Scan directories for PDF files
    // Check root workspace (../../..) first, then backend (../..)
    const searchDirs = [
      path.resolve(__dirname, '../../..'),
      path.resolve(__dirname, '../..')
    ];

    let foundPdfPath = null;
    let foundPdfName = null;

    for (const dir of searchDirs) {
      if (!fs.existsSync(dir)) continue;
      const files = fs.readdirSync(dir);
      
      // Look for saurabh_surashe.pdf specifically first
      const specificPdf = files.find(f => f.toLowerCase() === 'saurabh_surashe.pdf');
      if (specificPdf) {
        foundPdfName = specificPdf;
        foundPdfPath = path.join(dir, specificPdf);
        break;
      }

      // Otherwise look for any PDF file
      const anyPdf = files.find(f => f.toLowerCase().endsWith('.pdf'));
      if (anyPdf) {
        foundPdfName = anyPdf;
        foundPdfPath = path.join(dir, anyPdf);
        break;
      }
    }

    if (!foundPdfPath) {
      console.error('❌ Error: No PDF resume found in root workspace or backend folder.');
      process.exit(1);
    }

    console.log(`\n📄 Found resume PDF: ${foundPdfName} at ${foundPdfPath}`);

    // Create a temporary copy in the uploads folder to prevent original from being deleted
    const uploadsDir = path.resolve(__dirname, '../../uploads');
    if (!fs.existsSync(uploadsDir)) {
      fs.mkdirSync(uploadsDir, { recursive: true });
    }
    const tempPdfPath = path.join(uploadsDir, `temp_import_${Date.now()}_${foundPdfName}`);
    fs.copyFileSync(foundPdfPath, tempPdfPath);

    console.log(`⚙️ Processing resume for ${email}...`);
    const result = await resumeService.processResume(email, tempPdfPath);

    console.log(`✅ Resume processed successfully!`);
    console.log(`   Skills Extracted (${result.resumeSkills?.length || 0}):`, result.resumeSkills.join(', '));
  } catch (err) {
    console.error('❌ Failed to import resume:', err.message);
    process.exit(1);
  }
}

run();
