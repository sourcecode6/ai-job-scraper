# AI Job Scraper App — Implementation Plan (v10 — Scraper Parallelization & DNS Mitigations)

## Phase 6: Scraper Parallelization & DNS Mitigations (Completed)
- **Parallel Scraper Orchestration:** Refactored `scraper.py` to run company acquisitions concurrently using a thread pool executor (`ThreadPoolExecutor`). Added configurable `MAX_CONCURRENT_COMPANIES` (default `3`).
- **Concurrently Optimized Thread Locking:** Integrated a global `db_lock` around SQLite database transactions. Reorganized scraping steps so that the lock is released during network HTTP fetches and GPU/CPU-bound SentenceTransformer model embedding generation to prevent database locks and maximize speed.
- **Deduplication & Unique Constraint Fix:** Resolved `UNIQUE constraint failed: jobs.company_name, jobs.job_id` errors by adding an in-memory `seen_job_ids` tracking set per scraper batch, and changing the database insert operation to use `INSERT OR IGNORE` combined with `cursor.rowcount` tracking.
- **Windows DNS Lookup Fix:** Forced `urllib3`'s socket connection builder in `utils.py` to resolve only IPv4 addresses (`socket.AF_INET`), completely bypassing dual-stack IPv4/IPv6 lookup failures (`NameResolutionError`) on Windows for **Arm** and **IBM** portals.
- **Scraper Auto-Recovery:** Updated the SQL scraper query to select status `IN ('active', 'degraded')` so that degraded scrapers will automatically retry on the next execution loop and recover their status to active.

## Phase 5: Configuration & Error Reporting (Completed)
- Extracted hardcoded company list to `backend/companies_config.json`.
- Updated `db_init.py` to sync configuration to `jobs.db` on run.
- Updated `matcher.py` and `email_sender.py` to fetch and embed scraper errors into email digests.

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
* Uploads log files (`backend/logs/*`) as a workflow run artifact (`scraper-logs`) for easy debugging access.


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

A backend-only, email-notification-driven job scraping and matching system for **personal use**, running entirely on a local Windows PC or via GitHub Actions:

- **Backend**: Python workflow scripts with scheduled data acquisition, semantic skill matching, and email notifications
- **Database**: SQLite (single `jobs.db` file — zero setup, no server)
- **Data Acquisition**: Legal-first, modular Python adapters (Requests, BeautifulSoup, Playwright)
- **NLP / Matching**: Local PyTorch offline SentenceTransformer for semantic embeddings + numpy cosine similarity
- **UI**: **Email-only** — no web dashboard, no mobile app
- **Email**: Python `smtplib` + Gmail SMTP (App Password)
- **Scheduler**: GitHub Actions Workflow (cron) — scrape every 6 hours and auto-commit db
- **Setup**: `setup.bat` local execution script + `README.md`

---

## Confirmed Configuration

| Setting | Value |
|---|---|
| Companies | **25** (NVIDIA, Google, Meta, Microsoft, Apple, Amazon, AMD, Broadcom, Arista Networks, Qualcomm, Cloudflare, Cisco, ARM, Intel, Cerebras, Groq, Juniper, NetApp, HPE, Samsung Research, NXP, Ericsson, Nokia, Tenstorrent, Graphcore) |
| Match Threshold | **30%** cosine similarity |
| Data Retention | **3 days** (jobs AND matched_jobs) |
| Resume Format | **PDF only** |
| Authentication | **None** — email is the only identifier (personal/local use) |
| NLP Engine | **HuggingFace free Inference API** (semantic embeddings) |
| UI | **Email digest only** — no frontend |
| Deployment | **Local Windows PC** |
| Scrape Frequency | **On startup + every 6 hours** |
| Location Filter | **India, United Kingdom, Europe + Remote** |
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

## Semantic Matching Architecture (Local Offline)

### Why Embeddings Over Jaccard

Jaccard requires exact string matches — `"Python"` vs `"python programming"` scores 0. Embedding-based cosine similarity understands semantic meaning: `"Kubernetes"` is close to `"container orchestration"`, `"ML"` is close to `"machine learning"`.

### Model

**`sentence-transformers/all-MiniLM-L6-v2`** via Local Python Execution:
- 100% Free and Private, runs locally on your PC.
- No API key required, zero network dependencies.
- Returns 384-dimensional float vectors.
- No rate limits (runs as fast as your CPU allows).

### Embedding Strategy (Optimized Chunking)

```
RESUME UPLOAD:
  1. Extract text from PDF (PyPDF2)
  2. Split resume into overlapping chunks (2000 chars, 200 char overlap)
  3. Call local SentenceTransformer model → get 384-dim vector for each chunk
  4. Average the vectors to create a single comprehensive resume vector
  5. Store vector as JSON blob in users.resume_vector (SQLite TEXT)

SCRAPE CYCLE (per new job):
  1. Acquire job data (Tier 2/3 pipeline)
  2. jobId already in DB? → skip entirely
  3. Prepare embedding input: jobTitle + department + jobDescription
  4. Call local SentenceTransformer model → get 384-dim job vector
  5. Store vector as JSON blob in jobs.embedding_vector
  6. Extract skill keywords for email display (local vocab match)

MATCH CYCLE (runs after scrape):
  1. Load user.resume_vector from SQLite (pre-cached)
  2. Load all new jobs' embedding_vectors from SQLite (pre-cached)
  3. Compute cosine similarity in-memory using Python numpy (instant)
  4. Score >= 30% → record as match
```

### Rate Limit Management

Because we run the model locally offline via PyTorch, there are no artificial API rate limits. Jobs are embedded sequentially as fast as the local CPU can process them.

### Cosine Similarity (in-memory, no library needed)

```python
import numpy as np

def compute_cosine_similarity(vec_a, vec_b):
    a = np.array(vec_a)
    b = np.array(vec_b)
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return (dot_product / (norm_a * norm_b)) * 100
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
  "locations": ["India", "Remote", "United Kingdom", "Germany", "France", "Poland", "Netherlands", "Sweden", "Switzerland", "Ireland", "Italy", "Spain"]
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
    → filter: category=ENGINEERING, locations=India|Remote|UK|Europe
2. Extract job listing URLs from rendered DOM
3. For each URL: axios GET → Cheerio extract JSON-LD → parse JobPosting
```

### Tier 3 — Playwright HTML Scraper (fallback only)
Used when APIs or static HTML aren't viable due to advanced anti-bot protections, CSRF, or single-page React apps.
- **Apple**: Loads `jobs.apple.com` via headless Chromium. Bypasses undocumented API tokens. Injects `AIJobScraperBot/1.0` User-Agent and runs JavaScript `page.evaluate()` to harvest DOM URLs.
- **Google**: (Hybrid) Playwright loads `careers.google.com/jobs/results`, then standard Axios parses JSON-LD from individual pages.

### Tier 4 — Specialty APIs (AshbyHQ, Greenhouse)
- **Cerebras**: Fetches from `api.ashbyhq.com/posting-api/job-board/cerebras` natively.

---

### robots.txt Compliance
- Fetched once per company per cycle (cached in memory for that cycle)
- `Disallow:` on careers path → skip company entirely
- `Crawl-delay:` → honor strictly (default 5s if not specified)
- Workday endpoint companies → robots.txt of `myworkdayjobs.com` is checked (not company domain, since the API call goes there)

### Rate Limiting
- Global: max 1 HTTP request per 3 seconds (`time.sleep`)
- Between companies: 10s gap
- **Note:** Because the local offline PyTorch model is used for embeddings, there are zero NLP API rate limits. 

### Error Handling
```text
HTTP 200     → process normally
HTTP 429     → log "rate limited", skip company this cycle
HTTP 403/401 → log "access denied", mark company status='degraded', skip next 3 cycles
HTTP 404     → log "endpoint gone", mark status='degraded', manual review needed
HTTP 5xx     → log "server error", retry once after 30s, then skip
Network err  → log "connection failed", skip this cycle
```

**Degraded company behavior:**
- `companies.status` field: `'active'` | `'degraded'`
- When degraded: skipped in scrape cycle + logged
- Must be manually re-activated via SQLite (set `status='active'`)
- A log entry is written to `logs/scrape.log` with timestamp and reason

---

## Company List (25 Companies)

| # | Company | ATS | Tier | Career URL |
|---|---|---|---|---|
| 1 | **NVIDIA** | Workday | 2 | `nvidia.wd5.myworkdayjobs.com` |
| 2 | **Google** | Custom | 3 | `careers.google.com` |
| 3 | **Meta** | Unknown | 3 | `metacareers.com` |
| 4 | **Microsoft** | Eightfold AI | 2 | `jobs.careers.microsoft.com` |
| 5 | **Apple** | Playwright (Custom) | 3 | `jobs.apple.com` |
| 6 | **Amazon (AWS)** | Unknown | 3 | `amazon.jobs` |
| 7 | **AMD** | iCIMS/Attract | 2 | `careers.amd.com` |
| 8 | **Broadcom** | Workday | 2 | `broadcom.wd1.myworkdayjobs.com` |
| 9 | **Arista Networks** | SmartRecruiters | 2 | `jobs.smartrecruiters.com/AristaNetworks` |
| 10 | **Qualcomm** | Eightfold AI | 2 | `careers.qualcomm.com` |
| 11 | **Cloudflare** | Greenhouse | 4 | `careers.cloudflare.com` |
| 12 | **Cisco** | Avature | 2 | `jobs.cisco.com` |
| 13 | **ARM** | Custom HTML | 2 | `careers.arm.com` |
| 14 | **Intel** | Workday | 2 | `intel.wd1.myworkdayjobs.com` |
| 15 | **Cerebras Systems** | AshbyHQ | 4 | `cerebras.ai/careers` |
| 16 | **Groq** | Unknown | 3 | `groq.com/careers` |
| 17 | **Juniper Networks** | Workday | 2 | `careers.juniper.net` |
| 18 | **NetApp** | Eightfold AI | 2 | `careers.netapp.com` |
| 19 | **Hewlett Packard Enterprise** | Workday | 2 | `careers.hpe.com` |
| 20 | **Samsung Research** | Unknown | 3 | `research.samsung.com/careers` |
| 21 | **NXP Semiconductors** | Workday | 2 | `careers.nxp.com` |
| 22 | **Ericsson** | Eightfold AI | 2 | `jobs.ericsson.com` |
| 23 | **Nokia** | Unknown | 3 | `careers.nokia.com` |
| 24 | **Tenstorrent** | Unknown | 3 | `tenstorrent.com/careers` |
| 25 | **Graphcore** | Unknown | 3 | `graphcore.ai/careers` |


---

## Architecture

```
┌─────────────────────────────────────────────┐
│             Python Automation Workflow        │
│                                               │
│  ┌─────────────────────────────────────────┐ │
│  │   Data Acquisition Pipeline (Python)     │ │
│  │   13 Adapters (Workday, Eightfold, etc.) │ │
│  │   robots.txt checker + global throttle   │ │
│  └──────────────────┬──────────────────────┘ │
│                     │ new jobs                │
│  ┌──────────────────▼──────────────────────┐ │
│  │   Local SentenceTransformer Model        │ │
│  │   all-MiniLM-L6-v2 (offline PyTorch)     │ │
│  │   → 384-dim vector per job               │ │
│  └──────────────────┬──────────────────────┘ │
│                     │ vectors                 │
│  ┌──────────────────▼──────────────────────┐ │
│  │   SQLite  (jobs.db)                      │ │
│  │   companies · jobs · users · matched_jobs│ │
│  └──────────────────┬──────────────────────┘ │
│                     │                         │
│  ┌──────────────────▼──────────────────────┐ │
│  │   Match Engine (Python Numpy)             │ │
│  │   resume_vector ↔ job embedding_vector   │ │
│  │   threshold: 30% · instant memory array  │ │
│  └──────────────────┬──────────────────────┘ │
│                     │ matches                 │
│  ┌──────────────────▼────────┐ ┌───────────┐ │
│  │  GitHub Actions Cron       │ │ Python SMTP │ │
│  │  Every 6 hours             │ │ Email Digest│ │
│  └────────────────────────────┘ └───────────┘ │
│                                               │
│  ┌─────────────────────────────────────────┐ │
│  │  Observability Logs                      │ │
│  │  Uploaded as GitHub Workflow Artifacts   │ │
│  └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘

  ↓ Email digest → Gmail inbox
```

---

## Project Structure

```text
Agent1/
├── .github/
│   └── workflows/
│       └── scrape_and_match.yml       # GitHub Actions Cron
├── backend/
│   ├── nlp_service/
│   │   ├── adapters/                  # Python Scraper Adapters
│   │   │   ├── amd.py, apple.py, workday.py, eightfold.py, etc.
│   │   ├── workflow_runner.py         # Main execution pipeline
│   │   ├── scraper.py                 # Core scraping orchestrator
│   │   ├── utils.py                   # Shared helper functions & validation
│   │   ├── matcher.py                 # Numpy Cosine Similarity match logic
│   │   ├── email_sender.py            # SMTP HTML digest generator
│   │   ├── db_init.py                 # SQLite migration & config seeding
│   │   └── requirements.txt           # Python dependencies
│   ├── companies_config.json          # 25 companies config list
│   ├── data/
│   │   ├── jobs.db                    # SQLite database
│   │   └── skills_vocab.json          # Dictionary for skill extraction
│   └── setup.bat                      # Windows local setup
└── README.md
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
  filters         TEXT,               -- JSON: {"locations":["India","United Kingdom","Germany","France","Poland","Netherlands","Ireland","Italy","Spain","Sweden","Switzerland"],"category":"ENGINEERING"}
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

## Pipeline Behavior

The entire system runs sequentially as a single pipeline whenever `workflow_runner.py` is triggered (either manually locally, or via the 6-hour GitHub Actions cron). However, if you are running the system via the local `app.py` FastAPI server, a dedicated asynchronous loop triggers a separate cleanup cycle daily at 2 AM.

### Daily at 2 AM: Local Cleanup Loop (app.py only)
```sql
-- Deletes jobs that have aged past the DATA_RETENTION_DAYS boundary
DELETE FROM jobs WHERE datetime(expires_at) < datetime('now');
DELETE FROM matched_jobs WHERE datetime(expires_at) < datetime('now');
```

### Pipeline Execution (workflow_runner.py)
```text
1. Initialize Database
   - Initialize SQLite schema (CREATE TABLE IF NOT EXISTS)
   - Seed/sync companies table from companies_config.json

2. Import / Process Resume
   - Look for PDF files in `backend/uploads/`
   - Extract text → Call Local PyTorch Model → store resume_vector
   - Delete PDF file to protect privacy

3. Data Acquisition (Scrape)
   - For each company (sequentially, respect crawl-delay, skip if degraded):
     a. Check robots.txt (cache result for this cycle)
     b. Call specific Python adapter → get raw job list
     c. For each job:
        - UNIQUE(company_name, job_id) conflict? → skip
        - Call Local PyTorch Model → get embedding_vector (instant)
        - INSERT job with embedding_status='done'
     d. UPDATE companies.last_scraped_at = now

4. Match & Notify
   - For each registered user:
     a. SELECT jobs WHERE scraped_at > user.last_notified_at
     b. Load user.resume_vector from SQLite
     c. For each job: numpy cosine_similarity(resume_vector, embedding_vector) × 100
     d. Filter: score >= user.match_threshold AND NOT EXISTS in matched_jobs
     e. INSERT into matched_jobs (notified=0) for each match
     f. Attempt email send via smtplib
        → Success: UPDATE matched_jobs SET notified=notified+1
        → Failure: leave as is, will retry next cycle

5. Cleanup Phase
   - Runs at the end of the pipeline execution (or at 2 AM via app.py background loop)
   - Executes the SQL DELETE routines to drop expired jobs/matched_jobs based on DATA_RETENTION_DAYS.
```

### On Resume Re-Upload (During Pipeline Initialization)
```text
1. Extract text from PDF
2. Call Local PyTorch Model → get resume_vector
3. Extract display skills (local vocab)
4. UPDATE users SET resume_text, resume_vector, resume_skills, resume_uploaded_at
5. DELETE FROM matched_jobs
   WHERE email = user.email
   AND datetime(expires_at) > datetime('now')    ← only clear still-valid entries
6. Match cycle will run normally at step 5 of the pipeline.
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

All logs written via standard Python **logging** to `backend/logs/`:

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
  "localModelStatus": "success",
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

## Execution Modes & API

The system provides two execution methods: a serverless pipeline, and a persistent background API server.

### 1. Serverless Pipeline (Recommended for GitHub Actions)
Runs the entire process synchronously from start to finish.
| Mode | Command | Description |
|---|---|---|
| **Local Terminal** | `python backend/nlp_service/workflow_runner.py` | Runs the full pipeline manually |
| **GitHub Actions** | `.github/workflows/scrape_and_match.yml` | Scheduled cron execution every 6 hours |

### 2. FastAPI Background Server (Local PC)
Runs a persistent local server (`python backend/nlp_service/app.py`) at `http://127.0.0.1:3000` with background scrape/cleanup loops and REST endpoints.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/resume/upload` | Upload PDF → extract text → get embedding → store |
| `POST` | `/api/users` | Create/update user profile |
| `GET` | `/api/users` | Get user profile + resume skills |
| `GET` | `/api/companies` | List all companies + status |
| `GET` | `/api/jobs` | View scraped jobs |
| `GET` | `/api/matches` | View matched jobs |
| `GET` | `/api/admin/status` | System status, last run times, background loops |
| `POST` | `/api/admin/scrape` | Manually trigger full scrape cycle in background |
| `POST` | `/api/admin/match` | Manually trigger match + email cycle in background |
| `POST` | `/api/admin/cleanup` | Manually trigger database cleanup |
| `POST` | `/api/admin/activate` | Set company status back to 'active' |

---

## Setup (`setup.bat`)

```bat
@echo off
echo === AI Job Scraper Setup ===

echo Installing dependencies...
cd backend/nlp_service
pip install -r requirements.txt
cd ../..

echo Creating .env from template...
if not exist backend\.env (
  copy backend\.env.example backend\.env
  echo  → .env created. Please fill in EMAIL_USER and EMAIL_PASS.
) else (
  echo  → .env already exists, skipping.
)

echo Creating data directory...
if not exist backend\data mkdir backend\data

echo Creating logs directory...
if not exist backend\logs mkdir backend\logs

echo.
echo Setup complete!
echo  1. Edit backend\.env with your Gmail credentials
echo  2. Run: python backend/nlp_service/workflow_runner.py
echo.
pause
```

`.env.example`:
```
# Gmail SMTP (use an App Password — not your Gmail password)
EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your_16_char_app_password

# App settings
MATCH_THRESHOLD=30
DATA_RETENTION_DAYS=3
USER_YOE=4

# Your email (where digests are sent)
NOTIFY_EMAIL=your_email@gmail.com
```

---

## Technology Stack

| Layer | Technology | Reason |
|---|---|---|
| Backend | Python 3.10+ | Robust, great data science ecosystem |
| Database | SQLite (`sqlite3`) | Zero server, single file, perfect for personal use |
| Data Acquisition | `requests` + `beautifulsoup4` + `playwright` | Modular parsing and JS render fallback |
| robots.txt | `urllib.robotparser` | Built-in Python library for compliance |
| Rate Limiting | `time.sleep` | Simple, sequential processing without queue overhead |
| Embeddings | `sentence-transformers` | Free, local, offline PyTorch semantic understanding |
| PDF Parsing | `PyPDF2` | Lightweight local extraction |
| Similarity | `numpy` cosine similarity | High-speed array operations |
| Email | `smtplib` (Gmail SMTP) | Built-in Python library, free delivery |
| Logging | `logging` | Standard Python logging to files |
| Scheduler | GitHub Actions | Zero-maintenance cron execution on the cloud |
| Setup | `setup.bat` + `README.md` | One-command Windows setup |

---

## Verification Plan

1. Run `setup.bat` → confirm `data/` and `logs/` created
2. Fill in `.env` with Gmail App Password
3. Run `python backend/nlp_service/workflow_runner.py`
4. Confirm logs appear in `backend/logs/scraper.log`
5. Place a resume PDF (e.g. `resume.pdf`) inside `backend/uploads/`
6. Re-run `workflow_runner.py` → confirm skills and vector stored in DB
7. Confirm email received in Gmail inbox
8. Repeat step 6 → confirm **same jobs not re-sent** (deduplication via `notified=1`)
9. Simulate email failure: wrong SMTP password → confirm `notified=0` persists, re-sent next cycle
10. Manually set `expires_at` to past in SQLite → run pipeline → confirm rows deleted

---

## Open Questions / Post-Build Decisions

> [!NOTE]
> These are minor items that can be decided during or after build:
> 1. **HuggingFace model warm-up**: Free tier models "sleep" — first call may take 20–30s. The retry logic handles this, but first run after long idle will be slow.
> 2. **Google Playwright stability**: careers.google.com may require specific wait-for-selector logic that needs tuning against the live page.
> 3. **IBM filtering**: `ibm.com/careers` is filtered by **countries=[India, UK, Germany, France, etc.]** and **category=Engineering/Technical** at fetch time — this significantly reduces volume to a manageable set per cycle.

