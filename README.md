# AI Job Scraper — Personal Use

A local backend service that scrapes job listings from 11 major tech companies every 6 hours, matches them against your resume using semantic AI, and emails you the matches.

**No UI. Email-only. Runs on your PC.**

---

## Quick Start

```bat
:: 1. Run setup (installs environment, imports resume, and starts the FastAPI server)
backend\setup.bat

:: 2. Edit credentials in .env if needed
notepad backend\.env

:: 3. To restart the server later:
backend\setup.bat
```

---

## Configuration (`.env`)

| Variable | Description |
|---|---|
| `EMAIL_USER` | Your Gmail address |
| `EMAIL_PASS` | Gmail App Password ([get one here](https://myaccount.google.com/apppasswords)) |
| `NOTIFY_EMAIL` | Where to send job digests (usually same as above) |
| `MATCH_THRESHOLD` | Min match % to notify (default: 30) |
| `DATA_RETENTION_DAYS` | Days to keep job data (default: 3) |
| `SCRAPE_INTERVAL_HOURS` | How often to scrape (default: 6) |
| `USER_YOE` | Your Years of Experience (default: 4) |

---

## API Reference (use curl or Postman)

### 1. Upload your Resume

```bash
curl -X POST http://localhost:3000/api/resume/upload \
  -F "email=you@gmail.com" \
  -F "resume=@/path/to/resume.pdf"
```

### 2. Set Company Preferences

```bash
curl -X POST http://localhost:3000/api/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "you@gmail.com",
    "selectedCompanies": ["NVIDIA", "Google", "Intel", "Microsoft"],
    "matchThreshold": 30
  }'
```

### 3. Manually Trigger a Scrape

```bash
curl -X POST http://localhost:3000/api/admin/scrape
```

### 4. Manually Trigger Matching for Your Email

```bash
curl -X POST "http://localhost:3000/api/admin/match?email=you@gmail.com"
```

### 5. Check System Status

```bash
curl http://localhost:3000/api/admin/status
```

### 6. View Your Matched Jobs

```bash
curl "http://localhost:3000/api/matches?email=you@gmail.com"
```

### 7. Reactivate a Degraded Company

```bash
curl -X POST "http://localhost:3000/api/admin/activate?company=NVIDIA"
```

---

## Supported Companies

| Company | ATS / Method | Location Filter | Expected Jobs |
|---|---|---|---|
| NVIDIA | Workday JSON POST | India + Remote | ~40 |
| Google | Playwright (SPA) | India / Engineering | ~10-20 |
| Arista Networks | SmartRecruiters REST API | India | ~33 |
| Cisco Systems | Phenom People widgets API | India | ~150 |
| Qualcomm | Eightfold AI pcsx API | India | ~414 |
| AMD | iCIMS/Attract GET API | India | ~225 |
| Broadcom | Workday JSON POST | India + Remote | ~60 |
| Intel | Workday JSON POST | India + Remote | ~40 |
| Microsoft | Eightfold AI pcsx API | India | ~200 |
| IBM | IBM Search API | India / Software Engineering | ~362 |
| Ericsson | Eightfold AI pcsx API | India | ~121 |

---

## How It Works

```
Startup → Scrape all companies → Local Job Embeddings (offline model)
       → Compare against your resume vector (cosine similarity)
       → Email matches ≥ threshold % → Repeat every 6 hours
```

1. **Scraping**: Uses official ATS APIs where available, falls back to JSON-LD structured data or clean widget POST requests.
2. **Local AI Matching**: Your resume is converted to a 384-dimensional semantic vector once on upload. Each job gets its own vector at scrape time using a local, offline `sentence-transformers` `all-MiniLM-L6-v2` model. Matching is pure in-memory math using NumPy with no external API calls or rate limits.
3. **Email**: Sent via Gmail SMTP. If it fails, the matches are retried on the next cycle.
4. **Storage**: Single SQLite file at `backend/data/jobs.db` using Python's native `sqlite3`. Jobs and matches expire after 3 days automatically.

---

## Logs

| File | Contents |
|---|---|
| `backend/logs/scrape.log` | Per-company scrape results |
| `backend/logs/error.log` | HTTP errors, degraded companies |
| `backend/logs/nlp.log` | Embedding events |

---

## Troubleshooting

**Email not sending?**
- Make sure you're using a Gmail App Password, not your regular password
- Enable 2-Step Verification first: [myaccount.google.com/security](https://myaccount.google.com/security)

**No jobs found?**
- Check `logs/scrape.log` for per-company errors
- Some companies may be marked `degraded` — use `/api/admin/activate`

**Resume skills seem wrong?**
- Re-upload with a cleaner PDF (avoid image-only/scanned resumes)
