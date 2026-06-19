# AI Job Scraper App — Implementation Plan (v8 — GitHub Actions Workflow Integration)

## Phase 4: GitHub Actions Workflow Integration

This phase outlines the integration of a GitHub Actions workflow to automate the scraping, matching, and emailing processes.

### User Review Required

> [!IMPORTANT]
> - **Secrets Configuration**: To send email digests, the following secrets must be configured in the GitHub repository (`Settings -> Secrets and variables -> Actions`):
>   - `EMAIL_USER`: The sender's Gmail address.
>   - `EMAIL_PASS`: The Gmail App Password.
>   - `NOTIFY_EMAIL`: The recipient's email address.
> - **Database Persistence & Tracking**:
>   - We will update the database/matching logic so that the `notified` column in `matched_jobs` acts as a counter. A job will be sent in email digests at most **2 times** (where `notified < 2`).
>   - The updated SQLite database (`jobs.db`) will be automatically committed and pushed back to the Git repository at the end of each GitHub Actions run. This ensures that the notification counter and historical scraping state are fully preserved across runs.

### Proposed Changes

#### [MODIFY] [matcher.py](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/nlp_service/matcher.py)
* Update `match_for_user_internal` to select pending matched jobs where `notified < 2` (instead of `notified = 0`).
* Increment the `notified` column by 1 upon a successful email dispatch instead of setting it to 1.

#### [NEW] [workflow_runner.py](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/nlp_service/workflow_runner.py)
* A standalone runner script to execute the database initialization, resume import, scraping, matching, and cleanup cycles sequentially in a single command.
* Runs the daily cleanup script to delete jobs out of the `DATA_RETENTION_DAYS` boundary.

#### [NEW] [scrape_and_match.yml](file:///c:/Users/saura/Desktop/Antigravity/Agent1/.github/workflows/scrape_and_match.yml)
* GitHub Actions workflow definition file.
* Runs on a cron schedule **every 6 hours** (`0 */6 * * *`) and supports manual triggering via `workflow_dispatch`.
* Configures Python, installs dependencies from `requirements.txt`, runs `workflow_runner.py`, and commits changes to `jobs.db` back to the repository.

### Verification Plan

#### Automated Tests
* Run `workflow_runner.py` locally to verify that it executes the full pipeline end-to-end:
  ```bash
  python backend/nlp_service/workflow_runner.py
  ```

---

## Phase 3: Python Scraping Service Migration

We are migrating all 11 scraping adapters, the global request queue, the robots.txt checker, and the scraper cron scheduling logic from Node.js to Python. This reduces JavaScript's footprint to ~25% of the codebase, leaving it responsible only for Express API endpoints, Nodemailer email digests, and triggering C++ matches.

### Proposed Changes

#### [NEW] [Python Scraper Service](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/scraper_service/orchestrator.py)
* Creates a standalone Python service under `backend/scraper_service`.
* Includes the following modules:
  - `orchestrator.py`: Orchestrates the scraping loop, reads active companies from `jobs.db`, respects the global rate limit (3s request gap, 10s company gap), and writes jobs directly to `jobs.db`.
  - `robots.py`: Compliant robots.txt parser and checker.
  - `adapters/`: Individual scraper modules for NVIDIA, Google, Arista, Cisco, Qualcomm, AMD, Broadcom, Intel, Microsoft, IBM, and Ericsson.
* Uses `requests` for Tier 2 APIs and `playwright-python` for Tier 3 fallbacks (Google).
* Loop schedule: Runs immediately on startup and every 6 hours.

#### [DELETE] [Node.js Scraping Code](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/acquisition/)
* Deletes the Node.js scraping adapters (`workday.js`, `cisco.js`, `eightfold.js`, `ibm.js`, `smartrecruiters.js`, `jsonld.js`, `playwright.js`, `robotsChecker.js`, `requestQueue.js`, `index.js`).

#### [MODIFY] [app.js](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/app.js) & [pythonService.js](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/services/pythonService.js)
* Updates Node.js process manager to automatically spawn the Python Scraper orchestrator in the background on startup, alongside the FastAPI embedding service.
* Node.js remains the host of the Express endpoints, Nodemailer email rendering/delivery, and the C++ vector math match loop.

#### [MODIFY] [setup.bat](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/setup.bat)
* Updates Python virtual environment setup to install new Python scraping libraries (`requests`, `beautifulsoup4`, `playwright`).

---

## Phase 2: Hybrid Python & C++ Architecture

We are migrating the heavy computational and NLP workloads from Node.js to specialized Python and C++ modules to optimize performance, leverage standard Python libraries, and execute similarity matches at native CPU speeds.

### User Review Required
> [!IMPORTANT]
> - **Python Requirement**: The user must have Python 3.10+ installed on their Windows PC and available in their system path (`python` command).
> - **C++ Compiler**: A pre-compiled `.node` binary will be provided for Windows x64. If recompiling is needed, the user must have MSVC Build Tools (`node-gyp` environment) set up.

### Proposed Changes

#### [NEW] [FastAPI Embeddings Service](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/nlp_service/app.py)
* Creates a Python FastAPI server running locally at `http://localhost:8000`.
* Loads the `sentence-transformers/all-MiniLM-L6-v2` model into memory on startup (using PyTorch).
* Exposes a `/embed` POST endpoint: accepts text, parses PDF text using `pypdf`, and returns the 384-dimensional floating point vector.

#### [NEW] [C++ Cosine Similarity Node Addon](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/addon/similarity.cpp)
* Creates a native C++ addon using Node-API (`node-addon-api`).
* Implements the cosine similarity calculation using SIMD (Single Instruction Multiple Data) registers for high-performance array calculations.
* Exposes `calculateCosineSimilarity(vectorA, vectorB)` to JavaScript.

#### [MODIFY] [embeddingService.js](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/services/embeddingService.js)
* Redirects calls from the local `@xenova/transformers` library to the local Python FastAPI endpoint (`http://localhost:8000/embed`).

#### [MODIFY] [matchService.js](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/services/matchService.js)
* Replaces the pure-JavaScript cosine similarity calculation with calls to our compiled C++ Node-API addon.

#### [MODIFY] [setup.bat](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/setup.bat)
* Updates the installation workflow:
  1. Installs Node.js dependencies (`npm install`).
  2. Creates a Python virtual environment (`python -m venv venv_nlp`) inside `nlp_service`.
  3. Installs Python dependencies (`pip install fastapi uvicorn sentence-transformers pypdf`).
  4. Runs `npm run build-addon` to configure and compile the C++ addon.

### Verification Plan
* **Python Service Test**: Request a sample vector from the FastAPI endpoint and verify it returns a 384-length float array.
* **C++ Math Test**: Compare similarity scores between JS math and C++ math to ensure identical matching accuracy.

---

## Overview

A backend-only, email-notification-driven job scraping and matching system for **personal use**, running entirely on a local Windows PC:

- **Backend**: Node.js + Express REST API with scheduled data acquisition, semantic skill matching, and email notifications
- **Database**: SQLite (single `jobs.db` file — zero setup, no server)
- **Data Acquisition**: Legal-first, 3-tier approach with full ethical scraping compliance
- **NLP / Matching**: HuggingFace free Inference API for semantic embeddings + cosine similarity
- **UI**: **Email-only** — no web dashboard, no mobile app
- **Email**: Nodemailer + Gmail SMTP (App Password)
- **Scheduler**: node-cron — scrape on startup + every 6 hours, daily cleanup at 2 AM
- **Setup**: `setup.bat` one-command Windows script + `README.md`

---

## Confirmed Configuration

| Setting | Value |
|---|---|
| Companies | **11** (NVIDIA, Google, Arista, Cisco, Qualcomm, AMD, Broadcom, Intel, Microsoft, IBM, Ericsson) |
| Match Threshold | **65%** cosine similarity |
| Data Retention | **3 days** (jobs AND matched_jobs) |
| Resume Format | **PDF only** |
| Authentication | **None** — email is the only identifier (personal/local use) |
| NLP Engine | **HuggingFace free Inference API** (semantic embeddings) |
| UI | **Email digest only** — no frontend |
| Deployment | **Local Windows PC** |
| Scrape Frequency | **On startup + every 6 hours** |
| Location Filter | **India + Remote** (Workday companies) |
| Keyword Filter | **Any engineering/technical role** (Google) |

---

## What Was Removed vs Previous Plan

| Item | Previous Plan | Final Decision |
|---|---|---|
| Mobile App | React Native (Expo) | ❌ Removed — email-only |
| Docker | docker-compose.yml | ❌ Not needed (SQLite) |
| NLP | Jaccard + keyword vocab | ✅ Replaced with HuggingFace embeddings |
| Compression | gzip job descriptions | ❌ Removed — raw text is fine at this scale |
| Scheduler persistence | SQLite-stored next-run time | ✅ Simplified — always scrape on startup |

---

## Semantic Matching Architecture (HuggingFace)

### Why Embeddings Over Jaccard

Jaccard requires exact string matches — `"Python"` vs `"python programming"` scores 0. Embedding-based cosine similarity understands semantic meaning: `"Kubernetes"` is close to `"container orchestration"`, `"ML"` is close to `"machine learning"`.

### Model

**`sentence-transformers/all-MiniLM-L6-v2`** via HuggingFace free Inference API:
- Free, no API key required
- Returns 384-dimensional float vectors
- Endpoint: `https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2`
- Rate limit: ~10 req/min on free tier → handled by the embedding strategy below

### Embedding Strategy (Zero API Calls at Match Time)

```
RESUME UPLOAD:
  1. Extract text from PDF (pdf-parse)
  2. Call HuggingFace API → get 384-dim resume vector
  3. Store vector as JSON blob in users.resume_vector (SQLite TEXT)
  4. Done — no more API calls for this resume until re-upload

SCRAPE CYCLE (per new job):
  1. Acquire job data (Tier 2/3 pipeline)
  2. jobId already in DB? → skip entirely (no embedding call)
  3. Prepare embedding input: jobTitle + department + jobDescription (truncated to 512 tokens)
  4. Call HuggingFace API → get 384-dim job vector
  5. Store vector as JSON blob in jobs.embedding_vector
  6. Extract skill keywords for email display (local vocab match — no API)

MATCH CYCLE (runs after scrape, NO API calls):
  1. Load user.resume_vector from SQLite (pre-cached)
  2. Load all new jobs' embedding_vectors from SQLite (pre-cached)
  3. Compute cosine similarity in-memory (pure math, instant)
  4. Score >= 65% → record as match
```

### Rate Limit Management

HuggingFace free tier: ~10 req/min.
- 11 companies × ~20 new jobs each = ~220 new jobs per 6h cycle (worst case)
- Scraping is sequential with 10s gaps between companies → jobs are processed one-by-one
- A `p-queue` with concurrency=1 and `intervalCap=8, interval=60000` (8 embedding calls/min) ensures we never exceed the free limit
- If HuggingFace returns 503 (model loading) → wait 20s, retry once → if still fails, store job without vector and re-try embedding on next cycle

### Cosine Similarity (in-memory, no library needed)

```js
function cosineSimilarity(vecA, vecB) {
  const dot = vecA.reduce((sum, a, i) => sum + a * vecB[i], 0);
  const magA = Math.sqrt(vecA.reduce((sum, a) => sum + a * a, 0));
  const magB = Math.sqrt(vecB.reduce((sum, b) => sum + b * b, 0));
  return dot / (magA * magB); // returns -1 to 1, multiply by 100 for %
}
```

---

## Legal-First Data Acquisition Strategy

> [!IMPORTANT]
> Data is acquired through a **prioritized 3-tier pipeline**. We always attempt the most legal and reliable method first before falling back.

### Guiding Principles
- **Target company sites directly** — never LinkedIn, Indeed, or aggregators
- **No logins** — publicly accessible pages only; login-required pages are skipped
- **robots.txt compliance** — checked before every Tier 2/3 request
- **Transparent bot identity** — `User-Agent: AIJobScraperBot/1.0 (Personal use; not commercial)`

---

### Tier 1 — Official ATS Public APIs
Fully documented public JSON APIs (Greenhouse, Lever). No robots.txt check needed (third-party domain).
> None of the current 11 companies use Tier 1 — reserved for future additions.

### Tier 2 — Structured Data (JSON-LD + Workday Internal JSON)

**Workday Internal JSON** (NVIDIA, Qualcomm, Broadcom, Intel):
```
POST https://{tenant}.wd5.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
Body: {
  "limit": 20,
  "offset": 0,
  "searchText": "",
  "locations": ["India", "Remote"]    ← India + Remote filter
}
```
Publicly accessible, no auth, same endpoint the career page's JS uses.

**iCIMS/Attract GET API** (AMD):
```
GET https://careers.amd.com/api/jobs?page={page}&limit={limit}&location={location}
```
Publicly accessible REST API endpoint, respects standard rate-limits via `requestQueue.js`, relies on honest User-Agent headers, and runs full dynamic `robots.txt` checks with zero bypasses.

**JSON-LD Extraction** (Arista, Cisco, Microsoft, IBM, Ericsson):
```
1. GET https://company.com/careers  (axios, no JS render)
2. Extract <script type="application/ld+json"> blocks
3. Filter for @type: "JobPosting"
4. Map schema.org fields → our schema
```

**Google Hybrid** (Tier 2/3):
```
1. Playwright: load careers.google.com/jobs/results
   → filter: category=ENGINEERING, location=India|Remote
2. Extract job listing URLs from rendered DOM
3. For each URL: axios GET → Cheerio extract JSON-LD → parse JobPosting
```

### Tier 3 — Playwright HTML Scraper (fallback only)
Used when Tier 2 fails. Single page, `slowMo: 200ms`, realistic viewport, honest User-Agent.

---

### robots.txt Compliance
- Fetched once per company per cycle (cached in memory for that cycle)
- `Disallow:` on careers path → skip company entirely
- `Crawl-delay:` → honor strictly (default 5s if not specified)
- Workday endpoint companies → robots.txt of `myworkdayjobs.com` is checked (not company domain, since the API call goes there)

### Rate Limiting
- Global: max 1 HTTP request per 3 seconds (`p-queue`, concurrency=1)
- Between companies: 10s gap
- HuggingFace embedding calls: max 8/min (`p-queue` with intervalCap)

### Error Handling
```
HTTP 200     → process normally
HTTP 429     → log "rate limited", skip company this cycle
HTTP 403/401 → log "access denied", mark company status='degraded', skip next 3 cycles
HTTP 404     → log "endpoint gone", mark status='degraded', manual review needed
HTTP 5xx     → log "server error", retry once after 30s, then skip
Network err  → log "connection failed", skip this cycle
HF API 503   → wait 20s, retry once, store job without vector if still fails
```

**Degraded company behavior:**
- `companies.status` field: `'active'` | `'degraded'`
- When degraded: skipped in scrape cycle + logged
- Must be manually re-activated via SQLite (set `status='active'`)
- A log entry is written to `logs/scrape.log` with timestamp and reason

---

## Company List

| # | Company | ATS | Tier | Career URL | Filter |
|---|---|---|---|---|---|
| 1 | **NVIDIA** | Workday | 2 — Workday JSON POST | `nvidia.wd5.myworkdayjobs.com` | India + Remote |
| 2 | **Google** | Custom | 2/3 hybrid | `careers.google.com` | Engineering + India/Remote |
| 3 | **Arista Networks** | SmartRecruiters | 2 — JSON-LD | `smartrecruiters.com/ArNetworks` | All public listings |
| 4 | **Cisco Systems** | Avature | 2 — JSON-LD | `jobs.cisco.com` | All public listings |
| 5 | **Qualcomm** | Workday | 2 — Workday JSON POST | `qualcomm.wd5.myworkdayjobs.com` | India + Remote |
| 6 | **AMD** | iCIMS/Attract | 2 — GET JSON API | `careers.amd.com` | India |
| 7 | **Broadcom** | Workday | 2 — Workday JSON POST | `broadcom.wd1.myworkdayjobs.com` | India + Remote |
| 8 | **Intel** | Workday | 2 — Workday JSON POST | `intel.wd1.myworkdayjobs.com` | India + Remote |
| 9 | **Microsoft** | Eightfold AI | 2 — JSON-LD | `jobs.careers.microsoft.com` | All public listings |
| 10 | **IBM** | Kenexa BrassRing | 2 — JSON-LD | `ibm.com/careers` | India + Engineering/technical roles |
| 11 | **Ericsson** | Eightfold AI | 2 — JSON-LD | `jobs.ericsson.com` | All public listings |

---

## Architecture

```
┌─────────────────────────────────────────────┐
│             Node.js + Express Backend         │
│                                               │
│  ┌─────────────────────────────────────────┐ │
│  │   Data Acquisition Pipeline              │ │
│  │   Workday JSON POST (5 companies)        │ │
│  │   JSON-LD Cheerio  (5 companies)         │ │
│  │   Playwright hybrid (Google)             │ │
│  │   robots.txt checker + p-queue throttle  │ │
│  └──────────────────┬──────────────────────┘ │
│                     │ new jobs                │
│  ┌──────────────────▼──────────────────────┐ │
│  │   HuggingFace Embedding Service          │ │
│  │   POST all-MiniLM-L6-v2                  │ │
│  │   → 384-dim vector per job               │ │
│  │   Rate-limited: 8 calls/min              │ │
│  └──────────────────┬──────────────────────┘ │
│                     │ vectors                 │
│  ┌──────────────────▼──────────────────────┐ │
│  │   SQLite  (jobs.db)                      │ │
│  │   companies · jobs · users · matched_jobs│ │
│  └──────────────────┬──────────────────────┘ │
│                     │                         │
│  ┌──────────────────▼──────────────────────┐ │
│  │   Match Engine (cosine similarity)        │ │
│  │   resume_vector ↔ job embedding_vector   │ │
│  │   threshold: 65% · zero API calls        │ │
│  └──────────────────┬──────────────────────┘ │
│                     │ matches                 │
│  ┌──────────────────▼────────┐ ┌───────────┐ │
│  │  node-cron Scheduler       │ │ Nodemailer│ │
│  │  Startup + every 6h        │ │ Gmail SMTP│ │
│  │  Daily cleanup at 2 AM     │ └───────────┘ │
│  └────────────────────────────┘               │
│                                               │
│  ┌─────────────────────────────────────────┐ │
│  │  Observability Logs (logs/ directory)    │ │
│  │  scrape.log · error.log · nlp.log        │ │
│  └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘

  ↑ REST API (for resume upload + config only)
  └── curl / Postman (no frontend)

  ↓ Email digest → Gmail inbox
```

---

## Project Structure

```
Agent1/
├── backend/
│   ├── src/
│   │   ├── config/
│   │   │   ├── db.js                  # SQLite init + schema migration
│   │   │   ├── companies.js           # 11 companies config (tier, URL, filters)
│   │   │   └── settings.js            # .env loader + constants
│   │   ├── db/
│   │   │   └── schema.sql             # SQLite CREATE TABLE statements
│   │   ├── acquisition/
│   │   │   ├── index.js               # Orchestrator: selects tier per company
│   │   │   ├── robotsChecker.js       # robots.txt fetch + parse (cache per cycle)
│   │   │   ├── requestQueue.js        # p-queue: global 1req/3s + HF 8req/min
│   │   │   ├── workday.js             # Workday internal JSON POST client
│   │   │   ├── jsonld.js              # Cheerio JSON-LD extractor
│   │   │   └── playwright.js          # Ethical Playwright scraper (Google + fallback)
│   │   ├── services/
│   │   │   ├── embeddingService.js    # HuggingFace API calls + retry logic
│   │   │   ├── resumeService.js       # PDF → text (pdf-parse) → embedding
│   │   │   ├── matchService.js        # Cosine similarity, threshold filter
│   │   │   ├── emailService.js        # Nodemailer HTML digest + retry logic
│   │   │   └── cleanupService.js      # DELETE expired jobs + matched_jobs
│   │   ├── routes/
│   │   │   ├── resume.js              # POST /api/resume/upload
│   │   │   ├── users.js               # POST /api/users  GET /api/users?email=X
│   │   │   ├── companies.js           # GET /api/companies
│   │   │   └── admin.js               # POST /api/admin/scrape  GET /api/admin/status
│   │   ├── schedulers/
│   │   │   └── index.js               # Startup scrape + 6h cron + 2am cleanup
│   │   ├── logger.js                  # Winston logger → logs/ directory
│   │   └── app.js                     # Express entry point
│   ├── data/
│   │   ├── jobs.db                    # SQLite database
│   │   └── skills_vocab.json          # 500+ skills for email display tags only
│   ├── logs/
│   │   ├── scrape.log                 # Per-company scrape results
│   │   ├── error.log                  # HTTP errors, degraded companies
│   │   └── nlp.log                    # Embedding quality + skill extraction
│   ├── uploads/                       # Temp PDF (deleted after parse)
│   ├── .env.example
│   ├── .env                           # Created by setup.bat
│   ├── setup.bat                      # One-command Windows setup script
│   ├── README.md
│   └── package.json
```

---

## SQLite Database Schema

```sql
-- Companies master list
CREATE TABLE companies (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  name            TEXT NOT NULL UNIQUE,
  slug            TEXT NOT NULL,
  ats             TEXT NOT NULL,       -- 'workday' | 'jsonld' | 'playwright'
  tier            INTEGER NOT NULL,    -- 1, 2, or 3
  career_url      TEXT NOT NULL,
  filters         TEXT,               -- JSON: {"locations":["India","Remote"],"category":"ENGINEERING"}
  status          TEXT DEFAULT 'active', -- 'active' | 'degraded'
  last_scraped_at TEXT,               -- ISO timestamp
  degraded_reason TEXT                -- reason if status='degraded'
);

-- Jobs (all companies, with expiry)
CREATE TABLE jobs (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  company_name     TEXT NOT NULL,
  job_id           TEXT NOT NULL,
  job_title        TEXT NOT NULL,
  location         TEXT,
  department       TEXT,
  posted_date      TEXT,
  employment_type  TEXT,
  job_description  TEXT,              -- raw text, uncompressed
  url              TEXT,
  apply_url        TEXT,
  skills_display   TEXT,              -- JSON array, local vocab match (for email tags)
  embedding_vector TEXT,              -- JSON array of 384 floats (backward compatibility)
  title_vector     TEXT,              -- JSON array of 384 floats (Job Title embedding)
  description_vector TEXT,            -- JSON array of 384 floats (Job Description embedding)
  required_yoe     INTEGER,           -- parsed required Years of Experience (YoE)
  embedding_status TEXT DEFAULT 'pending', -- 'pending' | 'done' | 'failed'
  scraped_at       TEXT NOT NULL,
  expires_at       TEXT NOT NULL,     -- scraped_at + 3 days
  UNIQUE(company_name, job_id)
);

-- Users (email as identifier, no password)
CREATE TABLE users (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  email               TEXT NOT NULL UNIQUE,
  resume_text         TEXT,
  resume_vector       TEXT,           -- JSON array of 384 floats
  resume_skills       TEXT,           -- JSON array (local vocab match, for display)
  selected_companies  TEXT,           -- JSON array of company names
  match_threshold     REAL DEFAULT 65.0,
  resume_uploaded_at  TEXT,
  last_notified_at    TEXT,
  created_at          TEXT NOT NULL
);

-- Deduplication + matched job log
CREATE TABLE matched_jobs (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  email        TEXT NOT NULL,
  job_id       TEXT NOT NULL,
  company_name TEXT NOT NULL,
  match_score  REAL NOT NULL,
  job_title    TEXT,
  location     TEXT,
  apply_url    TEXT,
  skills_display TEXT,
  required_yoe INTEGER,               -- required YoE for the job
  notified     INTEGER DEFAULT 0,     -- 0=pending, 1=email sent successfully
  notified_at  TEXT,                  -- set when email confirmed sent
  expires_at   TEXT NOT NULL,         -- same as job expires_at (3 days)
  UNIQUE(email, company_name, job_id)
);

-- Indexes
CREATE INDEX idx_jobs_company    ON jobs(company_name);
CREATE INDEX idx_jobs_expires    ON jobs(expires_at);
CREATE INDEX idx_jobs_embedding  ON jobs(embedding_status);
CREATE INDEX idx_matched_email   ON matched_jobs(email);
CREATE INDEX idx_matched_notified ON matched_jobs(notified);
```

---

## Scheduler Behavior

### On Startup (runs immediately when `npm start` executes)
```
1. Initialize SQLite schema (CREATE TABLE IF NOT EXISTS)
2. Seed companies table from companies.js config
3. Trigger full scrape cycle immediately (regardless of lastScrapedAt)
4. Register 6h cron for subsequent cycles
5. Register 2am daily cleanup cron
```

### Every 6 Hours: Scrape + Embed + Match + Notify
```
For each company (sequentially, 10s gap, skip if status='degraded'):
  1. Check robots.txt (cache result for this cycle)
  2. Call acquisition tier → get raw job list
  3. For each job:
     a. UNIQUE(company_name, job_id) conflict? → skip
     b. INSERT job with embedding_status='pending'
     c. Queue HuggingFace embedding call (rate-limited)
     d. On success: UPDATE embedding_vector, embedding_status='done'
     e. On failure after retry: embedding_status='failed' (matched next cycle)
  4. UPDATE companies.last_scraped_at = now

Embedding retry sweep (after all companies):
  - SELECT jobs WHERE embedding_status='failed' AND scraped_at > now-3days
  - Re-attempt HuggingFace call for each
  - Update status accordingly

For each registered user:
  5. SELECT jobs WHERE:
       company_name IN user.selected_companies
       AND scraped_at > user.last_notified_at
       AND embedding_status = 'done'
  6. Load user.resume_vector from SQLite
  7. For each job: cosine_similarity(resume_vector, embedding_vector) × 100
  8. Filter: score >= user.match_threshold
             AND NOT EXISTS in matched_jobs for this user+job
  9. INSERT into matched_jobs (notified=0) for each match
  10. If any matches: attempt email send
      → Success: UPDATE matched_jobs SET notified=1, notified_at=now
                 UPDATE users.last_notified_at=now
      → Failure:  leave notified=0, log error, retry next cycle
                  (jobs are NOT marked notified — will retry)
```

### Daily at 2 AM: Cleanup
```sql
DELETE FROM jobs         WHERE expires_at < datetime('now');
DELETE FROM matched_jobs WHERE expires_at < datetime('now');
```

### On Resume Re-Upload
```
1. Extract text from PDF
2. Call HuggingFace → get resume_vector
3. Extract display skills (local vocab)
4. UPDATE users SET resume_text, resume_vector, resume_skills, resume_uploaded_at
5. DELETE FROM matched_jobs
   WHERE email = user.email
   AND expires_at > datetime('now')    ← only clear still-valid entries
6. Re-run match cycle immediately for this user against all jobs with embedding_status='done'
7. Send fresh email digest if any new matches found
```

---

## Email Failure Handling

The `notified` flag in `matched_jobs` is the key mechanism:

```
notified = 0  →  match found but email not yet confirmed sent
notified = 1  →  email successfully sent for this match
```

On each scrape cycle, before inserting new matches, the system also:
```sql
SELECT * FROM matched_jobs
WHERE email = ? AND notified = 0 AND expires_at > datetime('now')
```
These pending (unsent) matches are **included in the next email digest**, effectively retrying until success.

---

## Observability — Log Files

All logs written via **Winston** to `backend/logs/`:

### `scrape.log`
```json
{
  "timestamp": "2026-06-13T11:00:00Z",
  "company": "NVIDIA",
  "status": "success",
  "jobsFound": 47,
  "jobsNew": 3,
  "jobsSkipped": 44,
  "durationMs": 2341
}
```

### `error.log`
```json
{
  "timestamp": "2026-06-13T11:00:05Z",
  "company": "Qualcomm",
  "type": "HTTP_429",
  "message": "Rate limited by Workday endpoint",
  "action": "skipped_this_cycle"
}
```

### `nlp.log`
```json
{
  "timestamp": "2026-06-13T10:45:00Z",
  "event": "resume_upload",
  "email": "user@gmail.com",
  "skillsExtracted": ["Python", "Docker", "AWS", "React"],
  "vectorDimensions": 384,
  "huggingFaceStatus": "success",
  "durationMs": 1230
}
```

---

## Email Digest Format

**Subject**: `🎯 4 New Job Matches — June 13, 2026`

**Body** (HTML):

```
Hi! We found 4 new job matches since your last update.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Senior Software Engineer @ NVIDIA
  📍 Bengaluru, India  •  Full-time
  🎯 Match Score: 82%
  ✅ Skills: Python, CUDA, C++, Docker
  📅 Posted: June 12, 2026
  👉 Apply Now → https://nvidia.wd5...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Staff Engineer — Networking @ Cisco
  📍 Remote  •  Full-time
  🎯 Match Score: 71%
  ✅ Skills: Go, Kubernetes, REST APIs
  📅 Posted: June 13, 2026
  👉 Apply Now → https://jobs.cisco...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This email was generated by your local AI Job Scraper.
Next check: ~6 hours from now.
```

---

## API Endpoints (curl / Postman only — no frontend)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/resume/upload` | Upload PDF → extract text → get embedding → store |
| `POST` | `/api/users` | Create/update user (email + company selection + threshold) |
| `GET` | `/api/users?email=X` | Get user profile + resume skills |
| `GET` | `/api/companies` | List all companies + status |
| `GET` | `/api/admin/status` | Scheduler status, last run times, pending embeddings |
| `POST` | `/api/admin/scrape` | Manually trigger full scrape cycle |
| `POST` | `/api/admin/match?email=X` | Manually trigger match + email for one user |
| `POST` | `/api/admin/activate?company=X` | Set company status back to 'active' |

---

## Setup (`setup.bat`)

```bat
@echo off
echo === AI Job Scraper Setup ===

echo Installing dependencies...
cd backend
npm install

echo Creating .env from template...
if not exist .env (
  copy .env.example .env
  echo  → .env created. Please fill in EMAIL_USER and EMAIL_PASS.
) else (
  echo  → .env already exists, skipping.
)

echo Creating data directory...
if not exist data mkdir data

echo Creating logs directory...
if not exist logs mkdir logs

echo.
echo Setup complete!
echo  1. Edit backend\.env with your Gmail credentials
echo  2. Run: cd backend ^& npm start
echo.
pause
```

`.env.example`:
```
# Gmail SMTP (use an App Password — not your Gmail password)
EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your_16_char_app_password

# HuggingFace (no key needed for free Inference API — leave blank)
HF_API_KEY=

# App settings
PORT=3000
MATCH_THRESHOLD=65
DATA_RETENTION_DAYS=3
SCRAPE_INTERVAL_HOURS=6
USER_YOE=4

# Your email (where digests are sent)
NOTIFY_EMAIL=your_email@gmail.com
```

---

## Technology Stack

| Layer | Technology | Reason |
|---|---|---|
| Backend | Node.js + Express | Fast, great npm ecosystem |
| Database | SQLite (`better-sqlite3`) | Zero server, single file, perfect for personal use |
| Data Acquisition | Axios + Cheerio + Playwright | Tier 2 (lightweight HTTP), Tier 3 (JS render fallback) |
| robots.txt | `robots-parser` | Parse Disallow + Crawl-delay |
| Rate Limiting | `p-queue` | Concurrency + interval caps for both HTTP and HF API |
| Embeddings | HuggingFace free Inference API | Free, no key, semantic understanding |
| PDF Parsing | `pdf-parse` | Lightweight, no external deps |
| Similarity | Pure JS cosine similarity | No library needed, instant in-memory |
| Email | Nodemailer (Gmail SMTP) | Free, no third-party service |
| Logging | Winston | Structured JSON logs to files |
| Scheduler | `node-cron` | In-process, no Redis/queue needed |
| Setup | `setup.bat` + `README.md` | One-command Windows setup |

---

## Verification Plan

1. Run `setup.bat` → confirm `node_modules`, `data/`, `logs/` created
2. Fill in `.env` with Gmail App Password
3. `npm start` → confirm startup scrape triggers, logs appear in `logs/scrape.log`
4. `GET /api/admin/status` → all 11 companies shown, `lastScrapedAt` populated
5. `POST /api/resume/upload` with a PDF → confirm skills and vector stored in DB
6. `POST /api/users` with email + company selections
7. `POST /api/admin/match?email=X` → confirm email received in Gmail inbox
8. Repeat step 7 → confirm **same jobs not re-sent** (deduplication via `notified=1`)
9. Simulate email failure: wrong SMTP password → confirm `notified=0` persists, re-sent next cycle
10. Manually set `expires_at` to past in SQLite → run cleanup → confirm rows deleted
11. Re-upload resume → confirm `matched_jobs` (within 3-day window) cleared → fresh match email arrives

---

## Open Questions / Post-Build Decisions

> [!NOTE]
> These are minor items that can be decided during or after build:
> 1. **HuggingFace model warm-up**: Free tier models "sleep" — first call may take 20–30s. The retry logic handles this, but first run after long idle will be slow.
> 2. **Google Playwright stability**: careers.google.com may require specific wait-for-selector logic that needs tuning against the live page.
> 3. **IBM filtering**: `ibm.com/careers` is filtered by **location=India** and **category=Engineering/Technical** at fetch time via URL query params — this significantly reduces volume to a manageable set per cycle.

---

## Issues Resolved / Retrospective

### 1. Partial Resume Scanning due to Character Truncation
* **Issue**: The embedding model only checked the skills/summary section at the top of the resume and missed keywords/skills in later project or experience sections.
* **Cause**: `getEmbedding` in `embeddingService.js` truncated the resume to 2000 characters to avoid model input sequence limits.
* **Resolution**: Replaced truncation with an overlapping chunking algorithm. The text is split into chunks of 2000 characters with 200 character overlap. Each chunk is embedded separately using the local SentenceTransformer model, and the resulting vectors are averaged and re-normalized.

### 2. Missing Tech Keywords & Regex Boundary Limitations
* **Issue**: Skills containing special characters (like `C++`, `L2/L3`, etc.) and telecommunication/low-level debugging terms (like `NB-IoT`, `4G`, `Real-Time Systems`, `NTN`, `GDB`, `SQL`, `VTune`, and `MAC Scheduler`) were not extracted.
* **Cause**:
  1. Standard regex word boundaries (`\b`) do not work on terms ending/starting with non-alphanumeric characters (like `++` or `/`).
  2. The terms were missing from `skills_vocab.json`.
  3. Extracted display skills were capped at 20.
* **Resolution**:
  1. Updated `nlpService.js` to use custom lookahead and lookbehind assertions (`(?<![a-zA-Z0-9_])` and `(?![a-zA-Z0-9_])`) to match word boundaries correctly for both word and non-word characters.
  2. Added the missing skills and aliases to `skills_vocab.json`.
  3. Increased the displayed skills cap to 40.

### 3. Artificial Rate-Limiting Throttling for Local Offline Embeddings
* **Issue**: Job embedding generation suffered from major delays (a 60-second delay/pause occurred after every 8 embedded jobs).
* **Cause**: `requestQueue.js` still enforced the old Hugging Face free API tier rate limit (capping at 8 calls per 60 seconds) even though the project was upgraded to use a local, offline SentenceTransformer model (`@xenova/transformers`).
* **Resolution**: Removed the `interval` and `intervalCap` constraints from the `embeddingQueue` in `requestQueue.js`, keeping only sequential concurrency (`concurrency: 1`) to run local embeddings as fast as possible without causing CPU usage spikes.

### 4. Broken Workday URLs & Lack of Job ID in Emails
* **Issue**:
  1. Scraped Workday job URLs returned 404 or redirected because they lacked the `/en-US/{siteName}` prefix (Workday requires the site prefix to load the correct layout).
  2. It was hard to search for jobs directly without their Job ID displayed in the email digest.
* **Resolution**:
  1. Updated `normalizeWorkdayJob` in [workday.js](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/acquisition/workday.js) to detect if `externalPath` starts with `/job/` and prepend it with `/en-US/${company.workdaySite}`.
  2. Updated [emailService.js](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/services/emailService.js) to display the Job ID badge next to the company name in the HTML layout, and inside parentheses in the text-only layout.

### 5. Match Threshold Changes in .env Ignored
* **Issue**: Changing `MATCH_THRESHOLD` in `.env` did not affect matching because the user's profile in the database defaulted to `65` (which was overriding the environment setting).
* **Cause**: `matchService.js` prioritized the user's database `match_threshold` column over the global `settings.matchThreshold` config value.
* **Resolution**: Updated [matchService.js](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/services/matchService.js) to always use the global `settings.matchThreshold` config (derived directly from `.env`), serving as the single source of truth for the local personal job tracker.

### 6. Matching Cycle Ignoring Existing Active Jobs
* **Issue**: Changing user settings (like lowering `MATCH_THRESHOLD` or uploading a new resume) did not match older, existing jobs in the database.
* **Cause**: The matching query in `matchService.js` had a `scraped_at > user.last_notified_at` constraint. Once `last_notified_at` was updated after a successful run, older jobs were permanently ignored in subsequent matching cycles.
* **Resolution**: Removed the `scraped_at > user.last_notified_at` constraint from the matching SQL query. The query now pulls all unexpired jobs (`expires_at > datetime('now')`), and duplicate prevention is correctly managed via deduplication checks on the `matched_jobs` table.

### 7. Relative Date Formatting Bug in Email Digests
* **Issue**: NVIDIA jobs did not display their posted dates in the email digest.
* **Cause**: NVIDIA stores relative date strings (like `"Posted Today"` or `"Posted Yesterday"`). The email generator was trying to parse these using JS `Date` objects, resulting in `"Invalid Date"`.
* **Resolution**: Added a `formatPostedDate` helper in [emailService.js](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/services/emailService.js) to detect and skip parsing for relative strings, outputting them directly in the template.

### 8. Jobs Older than DATA_RETENTION_DAYS Getting Matched
* **Issue**: Jobs posted weeks ago (like Arista jobs from May) were still getting matched even though the `DATA_RETENTION_DAYS` limit was set to 3.
* **Cause**:
  1. The expiration date (`expires_at`) was set based on the `scraped_at` timestamp (`scraped_at + DATA_RETENTION_DAYS`) rather than the actual job creation/posted date.
  2. There was no age verification during the matching cycle.
* **Resolution**:
  1. Updated `matchService.js` to run an in-memory age check (`isJobWithinRetention`) parsing absolute/relative dates against the user's `DATA_RETENTION_DAYS`.
  2. Updated `processJob` in `index.js` to calculate `expires_at` based on the actual job `posted_date` so that older jobs expire instantly and are cleaned up.

### 9. Sort Matches by Country (India First) and Match Percentage
* **Issue**: It was hard to find the best match because the jobs in the email were in arbitrary database order.
* **Resolution**: Added sorting logic in `matchService.js` to order matches first by location (placing jobs located in India at the top) and then by match score in descending order before sending them to the email generator.

### 10. Removed Skills Cap from Database and Logging Layers
* **Issue**: Recognized skill tags in the database and execution logs were truncated to a maximum of 40 elements, preventing a full historic record of extracted technologies.
* **Cause**: `nlpService.js` applied a `.slice(0, 40)` limit on the canonical skills array returned from `extractSkills`.
* **Resolution**: Removed the `.slice(0, 40)` cap in `nlpService.js` to allow database tables (`jobs.skills_display`) and system logs to persist the full set of extracted keywords, while leaving the compact slicing logic (e.g. top 8) intact in `emailService.js` to keep email layout cards clean.

### 11. Fixed AMD Career Link and Scraper
* **Issue**: AMD's career site scraper was failing with 404 or 422 errors because their Workday tenant was decommissioned.
* **Cause**: AMD migrated to a new Attract/iCIMS portal at `careers.amd.com`.
* **Resolution**:
  1. Identified the new public job search API endpoint: `GET https://careers.amd.com/api/jobs`.
  2. Implemented a new custom scraper module [amd.js](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/acquisition/amd.js) supporting query filters and offset pagination via the new endpoint.
  3. Registered the new scraper in the orchestrator [index.js](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/acquisition/index.js) and updated the company definition in [companies.js](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/config/companies.js).
  4. Verified the new scraper successfully fetched 225 active jobs from the live AMD career site.

### 12. Experience Match Indicator in Email Digests
* **Issue**: When a user met or exceeded the required Years of Experience (YoE) for a job, no positive visual indicator was rendered in the email digest layout.
* **Cause**: The email card template only evaluated the negative case (`requiredYoe > userYoe`) to show a warning badge.
* **Resolution**: Updated [emailService.js](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/services/emailService.js) to render a green `✅ Experience Match` badge in HTML (and text representation) when the required YoE is less than or equal to the user's configured YoE.

### 13. Log Timestamp Serialization Order
* **Issue**: The `"timestamp"` key in the JSON log entries of `error.log`, `nlp.log`, and `scrape.log` was serialized at the end of the line, making it hard to read and parse chronological entries.
* **Cause**: Python dictionary insertion order placed newly added fields (like timestamp) at the end.
* **Resolution**: Updated `write_log()` in [logger.py](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/nlp_service/logger.py) to explicitly reconstruct the logging dictionary with `"timestamp"` inserted as the first key.

### 14. CPU Waste Skipping Arista Networks
* **Issue**: When `ALLOW_ARISTA_BYPASS=false` (default), the scraper would still execute a full initialization phase and evaluate robots.txt files for Arista Networks on every cycle, wasting CPU and network resources.
* **Resolution**: Implemented an early exit inside `scrape_company()` in [scraper.py](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/nlp_service/scraper.py) that detects Arista Networks and skips it immediately if `ALLOW_ARISTA_BYPASS` evaluates to false.

### 15. Port Conflicts on Restarting setup.bat
* **Issue**: Running `setup.bat` multiple times would fail to start the FastAPI server due to `EADDRINUSE` port conflicts since the previous python Uvicorn instance was still listening on the port.
* **Resolution**: Added port-parsing logic to [setup.bat](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/setup.bat) to extract the active `PORT` from `.env` (defaulting to 3000) and automatically run `taskkill` to terminate any process listening on that port before launching setup or starting uvicorn. Standardized the loop command (`netstat -aon | findstr :%TARGET_PORT% | findstr LISTENING`) and removed parentheses inside the `for` loop body to avoid Command Prompt parser syntax breaks.

### 16. Python stdout buffering in background execution
* **Issue**: When `setup.bat` launched the FastAPI server process in the background, Python output buffering prevented Uvicorn startup logs from being written to the task log file immediately, making verification of startup status difficult.
* **Resolution**: Added the `-u` (unbuffered) flag to the Python execution command inside [setup.bat](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/setup.bat) so that all logs flush to standard output immediately.





