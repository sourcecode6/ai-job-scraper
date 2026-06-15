const { extractYoE } = require('../acquisition');
const nlpService = require('../services/nlpService');
const { init: initDb, db } = require('../config/db');
const embeddingService = require('../services/embeddingService');
const matchService = require('../services/matchService');

// Initialize DB first
initDb();

// 1. Test YoE Extraction Heuristics
console.log('--- Testing YoE Heuristic Extraction ---');
const testCases = [
  { text: 'Requires 5+ years of experience in wireless development', expected: 5 },
  { text: 'Looking for a Senior Developer with 5 to 8 years experience overall. 10+ years in industry is a plus.', expected: 5 },
  { text: 'Minimum of 3 years experience. 5 years total preferred.', expected: 3 }, // 3 is the minimum required
  { text: 'Entry level role, experience with Python is good.', expected: null }
];

for (const tc of testCases) {
  const got = extractYoE(tc.text);
  console.log(`Text: "${tc.text}" -> Got: ${got} (Expected: ${tc.expected})`);
}

// 2. Insert a test job to verify schema and embedding queue
async function runEmbeddingAndMatchTest() {
  console.log('\n--- Testing Embedding Generation and Match Scoring ---');
  
  // Clean existing test jobs first
  db.prepare("DELETE FROM jobs WHERE job_id = 'test-yoe-123'").run();
  db.prepare("DELETE FROM matched_jobs").run(); // Clear all matched jobs to avoid pending matches

  // Make sure test user exists with a low threshold so they match the test job
  db.prepare(`
    INSERT INTO users (email, match_threshold, created_at)
    VALUES ('mssurashe42@gmail.com', 10.0, datetime('now'))
    ON CONFLICT(email) DO UPDATE SET match_threshold = 10.0
  `).run();

  const now = new Date();
  const expiresAt = new Date(now.getTime() + 3 * 24 * 60 * 60 * 1000);

  // Insert mock job
  db.prepare(`
    INSERT INTO jobs (
      company_name, job_id, job_title, location, department,
      posted_date, employment_type, job_description, url, apply_url,
      skills_display, required_yoe, embedding_status, scraped_at, expires_at
    ) VALUES (
      'NVIDIA', 'test-yoe-123', 'Senior Firmware Engineer (C++)', 'India', 'Engineering',
      ?, 'Full-time', 'Requires minimum 6 years of experience in RTOS and C++ firmware development.',
      'https://nvidia.com/test', 'https://nvidia.com/test',
      '[]', 6, 'pending', ?, ?
    )
  `).run(now.toISOString(), now.toISOString(), expiresAt.toISOString());

  console.log('Seeded test job "test-yoe-123" with required_yoe=6');

  // Trigger embedding generation
  console.log('Generating embeddings...');
  // Force run the queued embedding immediately by calling the function
  await new Promise((resolve) => {
    embeddingService.queueJobEmbedding('test-yoe-123', 'NVIDIA');
    // Wait a moment for async execution
    setTimeout(resolve, 3000);
  });

  const job = db.prepare("SELECT * FROM jobs WHERE job_id = 'test-yoe-123'").get();
  console.log('Job embedding status:', job.embedding_status);
  console.log('Has title_vector?', !!job.title_vector);
  console.log('Has description_vector?', !!job.description_vector);

  if (job.title_vector && job.description_vector) {
    // Run match for user
    const email = 'mssurashe42@gmail.com';
    // Update user's last notified at to 10 seconds ago so we only catch this newly seeded job
    const tenSecondsAgo = new Date(Date.now() - 10000).toISOString();
    db.prepare("UPDATE users SET last_notified_at = ? WHERE email = ?").run(tenSecondsAgo, email);
    
    await matchService.matchForUser(email);
    
    const match = db.prepare("SELECT * FROM matched_jobs WHERE job_id = 'test-yoe-123'").get();
    if (match) {
      console.log('✅ Job Matched successfully!');
      console.log(`Match Score: ${match.match_score}%`);
      console.log(`Required YoE stored: ${match.required_yoe}`);
    } else {
      console.log('❌ Job did not match (check threshold).');
    }
  }

  // Clean up
  db.prepare("DELETE FROM jobs WHERE job_id = 'test-yoe-123'").run();
  db.prepare("DELETE FROM matched_jobs WHERE job_id = 'test-yoe-123'").run();
  console.log('Cleanup completed.');
}

runEmbeddingAndMatchTest().catch(console.error);
