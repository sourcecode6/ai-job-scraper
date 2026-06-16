# AI Job Scraper — Code Review & Compliance Audit

This document summarizes the compliance audit of the implemented codebase, verifying the system's alignment with python-native architectures and legal scraping guidelines.

---

## 1. Plan Compliance & Alignment

| Feature / Phase | Planned Approach | Actual Implementation | Status |
| :--- | :--- | :--- | :---: |
| **Backend Runtime** | Python FastAPI Web Server | Single FastAPI process in [app.py](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/nlp_service/app.py) | **Fully Compliant** |
| **Database** | SQLite database (zero-setup file) | SQLite using native python `sqlite3` driver | **Fully Compliant** |
| **NLP Engine** | Offline sentence-transformers | **Local `sentence-transformers`** (all-MiniLM-L6-v2) | **Fully Compliant** |
| **Acquisition** | robots.txt compliant + prioritized 3-tier | Global rate limiter, robots checker, and fallback chain | **Fully Compliant** |
| **Matching** | Cosine similarity in-memory | Weighted title & description math using NumPy | **Fully Compliant** |
| **UI** | Email digest only (HTML) | SMTP client in [email_sender.py](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/nlp_service/email_sender.py) | **Fully Compliant** |
| **Setup** | `setup.bat` start script | Python virtual environment setup + startup launcher | **Fully Compliant** |

---

## 2. Key Adaptations & Technical Improvements

### 🧠 NumPy-Based Semantic Match Engine
* Vector similarity calculations (cosine similarity) are executed at native CPU speed using **NumPy** array operations. This replaces pure-JavaScript loops or complex Node-API addons.

### 🌐 Compliance & Robots.txt Handling
* **Robots.txt parsing**: Obeying robots.txt rules is managed directly in Python using standard parsing libraries in [scraper.py](file:///c:/Users/saura/Desktop/Antigravity/Agent1/backend/nlp_service/scraper.py).
* **Early bypass skipping**: If `ALLOW_ARISTA_BYPASS=false`, Arista Networks is skipped immediately without making any outbound requests, preventing CPU/network waste on disallowed crawls.

### 🔒 Rate Limiting & Politeness
* Outbound requests are rate-limited with cooperative delays:
  - 3-second delay between individual job endpoint queries.
  - 10-second pause before moving to the next company.
  - A transparent User-Agent string is sent to indicate bot identity: `AIJobScraperBot/1.0 (Personal use job tracker; not for commercial use)`.
