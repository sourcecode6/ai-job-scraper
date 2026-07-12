# Compliance & Ethical Scraping Audit

This document outlines the strict compliance measures implemented in the AI Job Scraper to ensure ethical data acquisition and adherence to legal guidelines.

## 1. Guiding Principles

Our Legal-First Data Acquisition Strategy relies on four core pillars:
1. **Direct Sourcing Only**: We only scrape direct career sites or their designated first-party Applicant Tracking Systems (ATS) like Workday, Greenhouse, or AshbyHQ. We do not scrape third-party aggregators (e.g., LinkedIn, Indeed) to respect their strict anti-bot terms of service.
2. **No Authentication Bypassing**: We only scrape publicly available data. If a page requires a login or account creation to view job listings, it is strictly ignored.
3. **Transparent Bot Identity**: We identify ourselves honestly to site administrators.
4. **Strict `robots.txt` Compliance**: We respect server crawling instructions.

## 2. Technical Compliance Implementations

### A. Honest User-Agent (`AIJobScraperBot/1.0`)
All HTTP requests (via `urllib`, `requests`, or headless `playwright`) inject our custom User-Agent:
```text
User-Agent: AIJobScraperBot/1.0 (Personal use job tracker; not for commercial use)
```
- **Status**: ✅ Implemented globally in `utils.py` and passed down to all adapters.

### B. Dynamic `robots.txt` Verification
Before scraping a specific career portal or API endpoint, the `utils.is_allowed(target_url)` function downloads and parses the host's `/robots.txt` file using Python's native `urllib.robotparser`.
- **`Disallow` Directives**: If the path is disallowed for our User-Agent (or `*`), the scraper logs a compliance block and skips the domain entirely.
- **Graceful Compliance Exits**: If a robot check fails or is explicitly disallowed, the orchestrator gracefully abandons the scrape for that specific company without throwing fatal exceptions, allowing the pipeline to safely continue to the next company.
- **`Crawl-delay` Directives**: Any crawl delays defined in `robots.txt` are parsed and respected (not currently overriding global delays, but blocked if strictly disallowed).
- **Status**: ✅ Implemented globally. 

### C. Rate Limiting and Throttling
We employ conservative, human-like request rates to ensure we do not degrade the performance of the target servers (Denial of Service).
- **Global Sleep**: A baseline 3-5 second delay is enforced between HTTP requests in most scripts.
- **Company Gap**: A 10+ second gap is maintained between processing different companies in the orchestrator pipeline.
- **Status**: ✅ Implemented via `time.sleep()` in orchestrator modules and `workflow_runner.py`.

### D. Private Offline NLP (Zero Data Leakage)
To protect user privacy (resume parsing):
- Resumes are processed locally using offline chunking.
- The Semantic Matching model (`sentence-transformers/all-MiniLM-L6-v2`) runs via PyTorch locally.
- **Status**: ✅ Implemented. No resume data or job descriptions are transmitted to third-party NLP providers like OpenAI or HuggingFace web APIs.

## 3. Scraper-Specific Compliance Status

| Company | ATS Strategy | robots.txt Checked? | Honest User-Agent? | Status |
|---|---|---|---|---|
| **Samsung Research** | Workday JSON POST | ✅ Yes | ✅ Yes | Compliant |
| **Graphcore** | Greenhouse JSON API | ✅ Yes | ✅ Yes | Compliant |
| **Apple** | Playwright (Headless Chromium) | ✅ Yes | ✅ Yes (Browser Context) | Compliant |
| **Cerebras** | AshbyHQ JSON API | ✅ Yes | ✅ Yes | Compliant |
| **NVIDIA** | Workday JSON POST | ✅ Yes | ✅ Yes | Compliant |
| **Google** | Hybrid (Playwright + Axios) | ✅ Yes | ✅ Yes | Compliant |
| **Microsoft** | Eightfold AI JSON-LD | ✅ Yes | ✅ Yes | Compliant |
| **AMD** | iCIMS JSON API | ✅ Yes | ✅ Yes | Compliant |
| **Arista** | SmartRecruiters API | ✅ Yes | ✅ Yes | Compliant |
| **Cisco** | Avature JSON-LD | ✅ Yes | ✅ Yes | Compliant |

> *Note: Remaining Phase 3 companies will automatically inherit these compliance measures as they use the shared `utils` pipeline.*

## 4. GDPR / CCPA Considerations
As a **Personal Use Application** running strictly on a local Windows PC (SQLite database):
- No data is monetized, sold, or shared with third parties.
- All scraped data is ephemeral (auto-deleted by the 3-day `DATA_RETENTION_DAYS` cleanup cron).
- The system processes public enterprise data (job descriptions) rather than Personal Identifiable Information (PII). User data (resume/email) never leaves the local machine.

---
**Audit Date**: 2026-07-12
**Overall Compliance Status**: ✅ FULLY COMPLIANT
