# AI Job Scraper — Build Tasks

## Phase 1: Project Scaffold
- [x] Create task.md
- [x] Initialize backend npm project
- [x] Install all dependencies
- [x] Create folder structure

## Phase 2: Config & Database
- [x] backend/src/config/settings.js
- [x] backend/src/config/companies.js (11 companies)
- [x] backend/db/schema.sql (managed in db.js)
- [x] backend/src/config/db.js (SQLite init + schema migration)

## Phase 3: Acquisition Pipeline
- [x] backend/src/acquisition/requestQueue.js (p-queue throttler)
- [x] backend/src/acquisition/robotsChecker.js
- [x] backend/src/acquisition/workday.js (Workday JSON POST)
- [x] backend/src/acquisition/jsonld.js (Cheerio JSON-LD extractor)
- [x] backend/src/acquisition/playwright.js (Google + fallback)
- [x] backend/src/acquisition/index.js (orchestrator)

## Phase 4: Services
- [x] backend/src/services/embeddingService.js (HuggingFace API)
- [x] backend/src/services/resumeService.js (PDF → text → vector)
- [x] backend/src/services/matchService.js (cosine similarity)
- [x] backend/src/services/emailService.js (Nodemailer HTML digest)
- [x] backend/src/services/cleanupService.js (3-day expiry)

## Phase 5: Scheduler
- [x] backend/src/schedulers/index.js (startup scrape + 6h cron + 2am cleanup)

## Phase 6: Routes & App
- [x] backend/src/routes/resume.js
- [x] backend/src/routes/users.js
- [x] backend/src/routes/companies.js
- [x] backend/src/routes/admin.js
- [x] backend/src/logger.js (Winston)
- [x] backend/src/app.js (Express entry point)

## Phase 7: Data & Setup
- [x] backend/data/skills_vocab.json (500+ skills)
- [x] backend/.env.example
- [x] backend/setup.bat
- [x] backend/README.md
- [x] backend/package.json scripts

## Phase 8: Hybrid Python & C++ Migration
- [x] Create Python FastAPI service (`backend/nlp_service/app.py` and `requirements.txt`)
- [x] Create C++ Node-API native addon (`backend/src/addon/similarity.cpp` and `binding.gyp`)
- [x] Integrate Python FastAPI in `embeddingService.js`
- [x] Integrate C++ native addon in `matchService.js`
- [x] Update `setup.bat` to configure Python venv and C++ addon
- [x] Verify hybrid setup via automated test runs

## Phase 9: 100% Python Native Migration
- [x] Migrate Node.js API endpoints and database logic to FastAPI
- [x] Migrate Nodemailer email digest to Python `email` module
- [x] Migrate matching and NumPy cosine calculations to Python
- [x] Remove C++ addon and Node.js backend files entirely
- [x] Add port conflict resolution and unbuffered logs in `setup.bat`
- [x] Update project documentation (README, architecture, audit, walkthrough) to represent 100% Python codebase


