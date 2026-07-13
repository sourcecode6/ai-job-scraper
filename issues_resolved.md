# Issues Resolved / Retrospective

## Version 8.0 (GitHub Actions Workflow Integration)

### 26. Scraper Resilience: Network Retries & Schema Keys
* **Issue**:
  - `Broadcom` / `IBM`: Failed with a `KeyError: 'careerUrl'` because the SQLite database schema returned `career_url` in snake_case, but the python adapters looked for camelCase.
  - `Microsoft`: Hit an HTTP `429 Too Many Requests` rate-limit block from Eightfold AI.
  - `Arm` / `IBM`: Experienced transient DNS `NameResolutionError` network blips (`[Errno 11001] getaddrinfo failed`).
* **Resolution**:
  - Fixed dictionary keys in `workday.py` and `ibm.py` to correctly reference `company['career_url']`.
  - Upgraded the central `queue_http` function in `utils.py` to implement robust retry logic (default `max_retries=3`). It now gracefully catches `requests.exceptions.RequestException` (like DNS failures) and applies exponential backoff delays automatically whenever an HTTP 429 rate limit is encountered, preventing premature scraper crashes.

### 25. Legacy HTTP Fallback in Resume Import
* **Issue**: The `import_resume.py` script was confusingly logging `"FastAPI server is not running. Falling back..."` when running via GitHub Actions. It was attempting a legacy HTTP POST request to the retired Node.js port (`3000`) before correctly falling back to local SQLite insertion.
* **Resolution**: Removed the unnecessary HTTP request entirely from `import_resume.py` so it directly interfaces with the database. Updated documentation (`architecture.md` and `implementation_plan.md`) to explicitly clarify the dual-execution gateways: `app.py` serves as the persistent local FastAPI web server on port `3000` (for backwards compatibility), while `workflow_runner.py` drives the serverless GitHub Actions pipeline.

### 24. Playwright Browser Binaries in GitHub Actions
* **Issue**: The Apple scraper uses Playwright to render the DOM, but GitHub Actions failed with `BrowserType.launch: Executable doesn't exist` because Playwright browser binaries were not installed.
* **Resolution**: Updated `.github/workflows/scrape_and_match.yml` to run `python -m playwright install chromium` immediately after `pip install` to ensure headless browsers are available to the pipeline.

### 23. Enhanced Error Checks & Resilience
* **Issue**: Various edge cases in the scraping pipeline (e.g., unexpected missing fields, timeout drops, or schema mismatches from newly added companies) caused occasional failures.
* **Resolution**: Implemented stronger error checking and data validation within the new `utils.py` and across the individual adapter scripts. Added defensive parsing to gracefully handle malformed job listings and safely fallback or skip corrupted entries without crashing the orchestration loop.

### 22. Codebase Modularization & Expanded Coverage (10 New Companies)
* **Issue**: The scraping logic was centralized in a single massive file (`scraper.py`), making it difficult to maintain, extend, and debug. The scraper also only supported 15 companies.
* **Resolution**:
  1. Refactored the architecture to be highly modular by extracting the scraping logic into individual, company-specific adapter modules (`backend/nlp_service/adapters/`).
  2. Created `utils.py` to house shared helper functions and core routines.
  3. Added 10 new companies to the scraping ecosystem (expanding the coverage to 25 total companies), updating `backend/companies_config.json` with their respective ATS configurations.

### 21. Missing Age Checks on Pending Matches
* **Issue**: Changing the `DATA_RETENTION_DAYS` limit (e.g. from 15 to 3) in `.env` did not stop previously matched jobs from being sent again in future email digests if their stored expiration date was set using the old limit.
* **Cause**: The query for `pending_matches` in `matcher.py` did not check the age of the job using the current retention settings, relying solely on `expires_at`.
* **Resolution**: Updated the query to `LEFT JOIN` the `jobs` table to retrieve `posted_date` and `scraped_at`, then ran `is_job_within_retention` on all pending matches to filter them against the active retention limit.

### 20. SQLite Datetime Comparison Format Mismatch
* **Issue**: Expired jobs were not being cleaned up by daily cleanup, and expired jobs were still matched and emailed.
* **Cause**: Dates are stored in SQLite as text. Python saved `expires_at` in ISO format (with 'T' and 'Z'), while SQLite's `datetime('now')` returned space-separated formats (without 'T'/'Z'). Since character `'T'` is lexicographically greater than `' '`, direct string comparisons failed.
* **Resolution**: Wrapped the `expires_at` column references in SQLite's `datetime()` function (e.g. `datetime(expires_at) > datetime('now')`) across `matcher.py` and `scraper.py` queries.

### 19. Relative Date Parsing Bug for plus signs (e.g. 15+ days ago)
* **Issue**: Jobs posted weeks ago (e.g., "15+ days ago" on Workday) were matching the current day and getting emailed.
* **Cause**: The relative date regex in `parse_relative_date` (`scraper.py`) and `is_job_within_retention` (`matcher.py`) did not expect a `+` symbol (like `15+ days ago` or `2+ weeks ago`). This caused the parser to fall back to `0` days ago (today), assigning a future `expires_at` date.
* **Resolution**: Updated the regexes to allow an optional `+` symbol (e.g. `r'(\d+)\+?\s+days?\s+ago'`), enabling correct parsing of relative ages.

### 18. Infinite Loop Bug in Eightfold and AMD Scrapers
* **Issue**: The scraper workflow would hang/get stuck indefinitely after processing Cisco Systems.
* **Cause**: In both `scrape_eightfold()` and `scrape_amd()` within [scraper.py](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/nlp_service/scraper.py), the `while True:` loop only indented the query parameter definition block, while the actual HTTP request, parsing logic, pagination increment, and break assertions were placed outside the `while True:` loop. This caused the loop to execute infinitely without ever calling the network or advancing.
* **Resolution**: Corrected the indentation of the entire network fetching, parsing, and pagination logic inside `scrape_eightfold()` and `scrape_amd()` to place them inside the `while True:` loop.

### 17. Location Filtering for ARM
* **Issue**: ARM's HTML scraper was retrieving all global job postings without applying any region/location filtering.
* **Resolution**: Added the standard list of location filters (India, UK, and European countries) to ARM's database initialization profile in [db_init.py](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/nlp_service/db_init.py) and updated the `scrape_arm` function in [scraper.py](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/nlp_service/scraper.py) to filter out jobs whose scraped location details do not match these criteria.

### 16. Python stdout buffering in background execution
* **Issue**: When `setup.bat` launched the FastAPI server process in the background, Python output buffering prevented Uvicorn startup logs from being written to the task log file immediately, making verification of startup status difficult.
* **Resolution**: Added the `-u` (unbuffered) flag to the Python execution command inside [setup.bat](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/setup.bat) so that all logs flush to standard output immediately.

### 15. Port Conflicts on Restarting setup.bat
* **Issue**: Running `setup.bat` multiple times would fail to start the FastAPI server due to `EADDRINUSE` port conflicts since the previous python Uvicorn instance was still listening on the port.
* **Resolution**: Added port-parsing logic to [setup.bat](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/setup.bat) to extract the active `PORT` from `.env` (defaulting to 3000) and automatically run `taskkill` to terminate any process listening on that port before launching setup or starting uvicorn. Standardized the loop command (`netstat -aon | findstr :%TARGET_PORT% | findstr LISTENING`) and removed parentheses inside the `for` loop body to avoid Command Prompt parser syntax breaks.

### 14. CPU Waste Skipping Arista Networks
* **Issue**: When `ALLOW_ARISTA_BYPASS=false` (default), the scraper would still execute a full initialization phase and evaluate robots.txt files for Arista Networks on every cycle, wasting CPU and network resources.
* **Resolution**: Implemented an early exit inside `scrape_company()` in [scraper.py](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/nlp_service/scraper.py) that detects Arista Networks and skips it immediately if `ALLOW_ARISTA_BYPASS` evaluates to false.

### 13. Log Timestamp Serialization Order
* **Issue**: The `"timestamp"` key in the JSON log entries of `error.log`, `nlp.log`, and `scrape.log` was serialized at the end of the line, making it hard to read and parse chronological entries.
* **Cause**: Python dictionary insertion order placed newly added fields (like timestamp) at the end.
* **Resolution**: Updated `write_log()` in [logger.py](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/nlp_service/logger.py) to explicitly reconstruct the logging dictionary with `"timestamp"` inserted as the first key.

### 12. Experience Match Indicator in Email Digests
* **Issue**: When a user met or exceeded the required Years of Experience (YoE) for a job, no positive visual indicator was rendered in the email digest layout.
* **Cause**: The email card template only evaluated the negative case (`requiredYoe > userYoe`) to show a warning badge.
* **Resolution**: Updated [emailService.js](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/services/emailService.js) to render a green `✅ Experience Match` badge in HTML (and text representation) when the required YoE is less than or equal to the user's configured YoE.

### 11. Fixed AMD Career Link and Scraper
* **Issue**: AMD's career site scraper was failing with 404 or 422 errors because their Workday tenant was decommissioned.
* **Cause**: AMD migrated to a new Attract/iCIMS portal at `careers.amd.com`.
* **Resolution**:
  1. Identified the new public job search API endpoint: `GET https://careers.amd.com/api/jobs`.
  2. Implemented a new custom scraper module [amd.js](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/acquisition/amd.js) supporting query filters and offset pagination via the new endpoint.
  3. Registered the new scraper in the orchestrator [index.js](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/acquisition/index.js) and updated the company definition in [companies.js](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/config/companies.js).
  4. Verified the new scraper successfully fetched 225 active jobs from the live AMD career site.

### 10. Removed Skills Cap from Database and Logging Layers
* **Issue**: Recognized skill tags in the database and execution logs were truncated to a maximum of 40 elements, preventing a full historic record of extracted technologies.
* **Cause**: `nlpService.js` applied a `.slice(0, 40)` limit on the canonical skills array returned from `extractSkills`.
* **Resolution**: Removed the `.slice(0, 40)` cap in `nlpService.js` to allow database tables (`jobs.skills_display`) and system logs to persist the full set of extracted keywords, while leaving the compact slicing logic (e.g. top 8) intact in `emailService.js` to keep email layout cards clean.

### 9. Sort Matches by Country (India First, then UK/Europe, then Remote, then others) and Match Percentage
* **Issue**: It was hard to find the best match because the jobs in the email were in arbitrary database order.
* **Resolution**: Added sorting logic in `matcher.py` to order matches first by location priority (India: Rank 0, UK/Europe: Rank 1, Remote: Rank 2, Others: Rank 3) and then by match score in descending order before sending them to the email generator.

### 8. Jobs Older than DATA_RETENTION_DAYS Getting Matched
* **Issue**: Jobs posted weeks ago (like Arista jobs from May) were still getting matched even though the `DATA_RETENTION_DAYS` limit was set to 3.
* **Cause**:
  1. The expiration date (`expires_at`) was set based on the `scraped_at` timestamp (`scraped_at + DATA_RETENTION_DAYS`) rather than the actual job creation/posted date.
  2. There was no age verification during the matching cycle.
* **Resolution**:
  1. Updated `matchService.js` to run an in-memory age check (`isJobWithinRetention`) parsing absolute/relative dates against the user's `DATA_RETENTION_DAYS`.
  2. Updated `processJob` in `index.js` to calculate `expires_at` based on the actual job `posted_date` so that older jobs expire instantly and are cleaned up.

### 7. Relative Date Formatting Bug in Email Digests
* **Issue**: NVIDIA jobs did not display their posted dates in the email digest.
* **Cause**: NVIDIA stores relative date strings (like `"Posted Today"` or `"Posted Yesterday"`). The email generator was trying to parse these using JS `Date` objects, resulting in `"Invalid Date"`.
* **Resolution**: Added a `formatPostedDate` helper in [emailService.js](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/services/emailService.js) to detect and skip parsing for relative strings, outputting them directly in the template.

### 6. Matching Cycle Ignoring Existing Active Jobs
* **Issue**: Changing user settings (like lowering `MATCH_THRESHOLD` or uploading a new resume) did not match older, existing jobs in the database.
* **Cause**: The matching query in `matchService.js` had a `scraped_at > user.last_notified_at` constraint. Once `last_notified_at` was updated after a successful run, older jobs were permanently ignored in subsequent matching cycles.
* **Resolution**: Removed the `scraped_at > user.last_notified_at` constraint from the matching SQL query. The query now pulls all unexpired jobs (`expires_at > datetime('now')`), and duplicate prevention is correctly managed via deduplication checks on the `matched_jobs` table.

### 5. Match Threshold Changes in .env Ignored
* **Issue**: Changing `MATCH_THRESHOLD` in `.env` did not affect matching because the user's profile in the database defaulted to `65` (which was overriding the environment setting).
* **Cause**: `matchService.js` prioritized the user's database `match_threshold` column over the global `settings.matchThreshold` config value.
* **Resolution**: Updated [matchService.js](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/services/matchService.js) to always use the global `settings.matchThreshold` config (derived directly from `.env`), serving as the single source of truth for the local personal job tracker.

### 4. Broken Workday URLs & Lack of Job ID in Emails
* **Issue**:
  1. Scraped Workday job URLs returned 404 or redirected because they lacked the `/en-US/{siteName}` prefix (Workday requires the site prefix to load the correct layout).
  2. It was hard to search for jobs directly without their Job ID displayed in the email digest.
* **Resolution**:
  1. Updated `normalizeWorkdayJob` in [workday.js](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/acquisition/workday.js) to detect if `externalPath` starts with `/job/` and prepend it with `/en-US/${company.workdaySite}`.
  2. Updated [emailService.js](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/src/services/emailService.js) to display the Job ID badge next to the company name in the HTML layout, and inside parentheses in the text-only layout.

### 3. Artificial Rate-Limiting Throttling for Local Offline Embeddings
* **Issue**: Job embedding generation suffered from major delays (a 60-second delay/pause occurred after every 8 embedded jobs).
* **Cause**: `requestQueue.js` still enforced the old Hugging Face free API tier rate limit (capping at 8 calls per 60 seconds) even though the project was upgraded to use a local, offline SentenceTransformer model (`@xenova/transformers`).
* **Resolution**: Removed the `interval` and `intervalCap` constraints from the `embeddingQueue` in `requestQueue.js`, keeping only sequential concurrency (`concurrency: 1`) to run local embeddings as fast as possible without causing CPU usage spikes.

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

### 1. Partial Resume Scanning due to Character Truncation
* **Issue**: The embedding model only checked the skills/summary section at the top of the resume and missed keywords/skills in later project or experience sections.
* **Cause**: `getEmbedding` in `embeddingService.js` truncated the resume to 2000 characters to avoid model input sequence limits.
* **Resolution**: Replaced truncation with an overlapping chunking algorithm. The text is split into chunks of 2000 characters with 200 character overlap. Each chunk is embedded separately using the local SentenceTransformer model, and the resulting vectors are averaged and re-normalized.
