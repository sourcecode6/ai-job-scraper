# AI Job Scraper — Walkthrough

We have successfully migrated the codebase from the initial Node.js implementation to a **100% Python-native architecture** using FastAPI, SentenceTransformers, and SQLite.

## Summary of Accomplishments

### 1. 100% Python Core Migration
- **FastAPI Gateway**: Implemented the REST API gateway under [app.py](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/nlp_service/app.py) exposing endpoints for resume uploading, profile management, and manual scraping/matching triggers.
- **Acquisition Engine**: Migrated the 11 company scraper adapters (NVIDIA, Google, Arista Networks, Cisco Systems, Qualcomm, AMD, Broadcom, Intel, Microsoft, IBM, Ericsson) to [scraper.py](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/nlp_service/scraper.py) using `requests` and Python-native structured parsing.
- **Match Engine**: Replaced C++/Node vector similarity logic with highly optimized **NumPy** array operations in [matcher.py](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/nlp_service/matcher.py) to perform AVX/SSE-speed similarity math natively in python.
- **Storage & Seeding**: Relational operations run on python's built-in `sqlite3` driver via [db_init.py](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/nlp_service/db_init.py) with structured tables and constraint indexes.

### 2. Log Serialization & Order
- **Issue**: The `"timestamp"` key in JSON logs was appended at the end of dictionary entries, making parsing harder.
- **Resolution**: Updated `write_log()` in [logger.py](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/nlp_service/logger.py) to explicitly construct the dictionary inserting `'timestamp'` first.

### 3. CPU/Network Optimization for Arista Networks
- **Issue**: When `ALLOW_ARISTA_BYPASS=false` (default), the scraper spent CPU cycles looking up `robots.txt` for Arista only to skip it anyway.
- **Resolution**: Implemented early bypass checks in `scraper.py` to immediately skip Arista Networks without starting any network lookups if `ALLOW_ARISTA_BYPASS` is false.

### 4. Port Conflict Resolution
- **Issue**: Re-running `setup.bat` failed due to port conflicts with existing running Python instances.
- **Resolution**: Added port detection logic parsing `PORT` from `.env` (default 3000) and automatically executing `taskkill` to clean up old processes on that port.

---

## Instructions for Running the App

1. **Initialize Environment Variables**:
   Copy `backend\.env.example` to `backend\.env` and configure your credentials.

2. **Run the Script**:
   Execute the Windows startup script:
   ```cmd
   backend\setup.bat
   ```
   This compiles/updates requirements, imports your resume, terminates conflicting processes, and launches the FastAPI background worker.
