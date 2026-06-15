# AI Job Scraper — Personal Use

A local backend service that scrapes job listings from 11 major tech companies every 6 hours, matches them against your resume using semantic AI, and emails you the matches.

**No UI. Email-only. Runs on your PC.**

---

## Quick Start

```bat
:: 1. Run setup (installs everything)
backend\setup.bat

:: 2. Edit credentials
notepad backend\.env

:: 3. Upload your resume + set preferences (see API below)

:: 4. Start the server
cd backend
npm start
```

---

## Configuration (`.env`)

| Variable | Description |
|---|---|
| `EMAIL_USER` | Your Gmail address |
| `EMAIL_PASS` | Gmail App Password ([get one here](https://myaccount.google.com/apppasswords)) |
| `NOTIFY_EMAIL` | Where to send job digests (usually same as above) |
| `HF_API_KEY` | HuggingFace token (Required — free Read token from huggingface.co) |
| `MATCH_THRESHOLD` | Min match % to notify (default: 65) |
| `DATA_RETENTION_DAYS` | Days to keep job data (default: 3) |
| `SCRAPE_INTERVAL_HOURS` | How often to scrape (default: 6) |

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
    "matchThreshold": 65
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
| Google | Playwright (SPA) | India / Engineering | *(selector pending fix)* |
| Arista Networks | SmartRecruiters REST API | India | ~33 |
| Cisco Systems | Phenom People widgets API | India | ~150 |
| Qualcomm | Eightfold AI pcsx API | India | ~414 |
| AMD | Workday JSON POST | India + Remote | ~40 |
| Broadcom | Workday JSON POST | India + Remote | ~60 |
| Intel | Workday JSON POST | India + Remote | ~40 |
| Microsoft | Eightfold AI pcsx API | India | ~200 |
| IBM | IBM Search API | India / Software Engineering | ~362 |
| Ericsson | Eightfold AI pcsx API | India | ~121 |

---

## How It Works

```
Startup → Scrape all companies → Get job embeddings (HuggingFace)
       → Compare against your resume vector (cosine similarity)
       → Email matches ≥ 65% → Repeat every 6 hours
```

1. **Scraping**: Uses official ATS APIs where available, falls back to JSON-LD structured data
2. **Matching**: Your resume is converted to a 384-dim semantic vector once on upload. Each job gets its own vector at scrape time. Matching is pure math — no API calls
3. **Email**: Sent via Gmail SMTP. If it fails, the match is retried next cycle
4. **Storage**: Single SQLite file at `backend/data/jobs.db`. Jobs expire after 3 days automatically

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

**HuggingFace slow?**
- Free tier models "sleep" — first call may take 30s. Normal after warmup.
- Add a free HuggingFace token to `.env` as `HF_API_KEY` (required for API access)

**Resume skills seem wrong?**
- Re-upload with a cleaner PDF (avoid image-only/scanned resumes)
