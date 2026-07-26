import os
import time
import re
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from utils import get_db_path, load_settings, extract_skills, extract_yoe, is_allowed, get_crawl_delay_ms, COMPANY_CONFIGS
from logger import log_scrape_info, log_scrape_error, log_nlp_event

# Thread lock for SQLite database writes/reads
db_lock = threading.Lock()


# Import adapters
from adapters.workday import scrape_workday
from adapters.smartrecruiters import scrape_smartrecruiters
from adapters.cisco import scrape_cisco
from adapters.eightfold import scrape_eightfold
from adapters.eightfold_v2 import scrape_eightfold_v2
from adapters.ashbyhq import scrape_ashbyhq
from adapters.apple import scrape_apple
from adapters.amd import scrape_amd
from adapters.ibm import scrape_ibm
from adapters.arm import scrape_arm
from adapters.greenhouse import scrape_greenhouse

# --- Main orchestrator ---

def parse_relative_date(date_str, retention_days):
    now = datetime.utcnow()
    expires_at = now + timedelta(days=retention_days)

    if not date_str:
        return now.isoformat() + 'Z', expires_at.isoformat() + 'Z'

    # Try ISO or standard datetime parse
    try:
        # standard ISO parsing
        # Remove trailing Z if present for python < 3.11 compatibility
        s = date_str.rstrip('Z')
        s = re.sub(r'([+-]\d{2})(\d{2})$', r'\1:\2', s)
        parsed = datetime.fromisoformat(s)
        if parsed.tzinfo is not None:
            # Convert to UTC and strip tzinfo so we only append Z
            from datetime import timezone
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return date_str, (parsed + timedelta(days=retention_days)).isoformat() + 'Z'
    except ValueError:
        pass

    # Handle relative date strings
    lower = date_str.lower()
    days_ago = 0
    if 'yesterday' in lower:
        days_ago = 1
    elif 'today' in lower:
        days_ago = 0
    else:
        days_match = re.search(r'(\d+)\+?\s+days?\s+(ago|back)', lower)
        if days_match:
            days_ago = int(days_match.group(1))
        else:
            weeks_match = re.search(r'(\d+)\+?\s+weeks?\s+(ago|back)', lower)
            if weeks_match:
                days_ago = int(weeks_match.group(1)) * 7
            elif 'month' in lower or 'year' in lower or '30+ days' in lower:
                days_ago = 30

    if days_ago > 0:
        posted_date = now - timedelta(days=days_ago)
        expires_at = now - timedelta(days=days_ago - retention_days)
        return posted_date.isoformat() + 'Z', expires_at.isoformat() + 'Z'

    return date_str, expires_at.isoformat() + 'Z'

def scrape_company(company_row, model):
    start_time = time.time()
    company = dict(company_row)
    name = company['name']
    if name in COMPANY_CONFIGS:
        company.update(COMPANY_CONFIGS[name])

    ats = company['ats']
    tier = company['tier']
    career_url = company['career_url']
    filters = json.loads(company['filters'] or '{}')



    log_scrape_info(f"[{name}] Starting acquisition (ats={ats}, tier={tier})")

    # Determine the target endpoint URL to check against robots.txt
    target_url = career_url
    if ats == 'eightfold':
        target_url = f"{company['eightfoldBaseUrl']}/api/pcsx/search"
    elif ats == 'eightfold_v2':
        target_url = f"{company['eightfoldBaseUrl']}/api/apply/v2/jobs"
    elif ats == 'ashbyhq':
        target_url = f"https://api.ashbyhq.com/posting-api/job-board/{company['board_token']}"
    elif ats == 'smartrecruiters':
        target_url = f"https://api.smartrecruiters.com/v1/companies/{company['smartRecruitersId']}/postings"
    elif ats == 'apple':
        target_url = "https://jobs.apple.com/en-us/search"
    elif ats == 'cisco':
        target_url = "https://careers.cisco.com/widgets"
    elif ats == 'amd':
        target_url = "https://careers.amd.com/api/jobs"
    elif ats == 'ibm':
        target_url = "https://www-api.ibm.com/search/api/v2"
    elif ats == 'arm':
        target_url = "https://careers.arm.com/search-jobs"
    elif ats == 'greenhouse':
        target_url = f"https://boards-api.greenhouse.io/v1/boards/{company.get('board_token', 'unknown')}/jobs"

    # Check robots.txt compliance
    if tier >= 2 and ats != 'workday':
        if not is_allowed(target_url):
            log_scrape_error(f"[{name}] Blocked by robots.txt — skipping (target_url={target_url})")
            return

    try:
        raw_jobs = []
        if ats == 'workday':
            raw_jobs = scrape_workday(company, filters)
        elif ats == 'smartrecruiters':
            raw_jobs = scrape_smartrecruiters(company, filters)
        elif ats == 'cisco':
            raw_jobs = scrape_cisco(company, filters)
        elif ats == 'eightfold':
            raw_jobs = scrape_eightfold(company, filters)
        elif ats == 'eightfold_v2':
            raw_jobs = scrape_eightfold_v2(company, filters)
        elif ats == 'ashbyhq':
            raw_jobs = scrape_ashbyhq(company, filters)
        elif ats == 'apple':
            raw_jobs = scrape_apple(company, filters)
        elif ats == 'amd':
            raw_jobs = scrape_amd(company, filters)
        elif ats == 'ibm':
            raw_jobs = scrape_ibm(company, filters)
        elif ats == 'arm':
            raw_jobs = scrape_arm(company, filters)
        elif ats == 'greenhouse':
            raw_jobs = scrape_greenhouse(company, filters)
        else:
            # Fallback (Google is commented out, so we don't expect other types)
            log_scrape_error(f"[{name}] ATS type {ats} not fully implemented in python. Skipping.")
            return

        new_count = 0
        skip_count = 0
        settings = load_settings()
        retention = settings['dataRetentionDays']

        # 1. Filter out duplicate jobs under lock
        db_path = get_db_path()
        new_jobs = []
        seen_job_ids = set()
        with db_lock:
            conn = sqlite3.connect(db_path, timeout=30.0)
            cursor = conn.cursor()
            for job in raw_jobs:
                jid = job['jobId']
                if jid in seen_job_ids:
                    skip_count += 1
                    continue
                seen_job_ids.add(jid)

                cursor.execute("SELECT 1 FROM jobs WHERE company_name = ? AND job_id = ?", (name, jid))
                if cursor.fetchone():
                    skip_count += 1
                else:
                    new_jobs.append(job)
            conn.close()

        # 2. Extract features and generate embeddings (No lock here to avoid blocking other threads)
        jobs_to_insert = []
        for job in new_jobs:
            posted_date_str, expires_at_str = parse_relative_date(job['postedDate'], retention)
            skills = extract_skills(f"{job['jobTitle']} {job['department']} {job['jobDescription']}")
            yoe = extract_yoe(job['jobDescription'])

            title_vec_str = None
            desc_vec_str = None
            status = 'pending'

            if model:
                try:
                    # Title Embedding
                    title_vector = model.encode([job['jobTitle']])[0].tolist()
                    title_vec_str = json.dumps(title_vector)

                    # Description/Combined Embedding (with chunking)
                    desc_text = f"{job['jobTitle']} {job['department']} {job['jobDescription']}"
                    chunk_size = 2000
                    overlap = 200
                    chunks = []
                    i = 0
                    while i < len(desc_text):
                        chunk = desc_text[i:i + chunk_size].strip()
                        if chunk:
                            chunks.append(chunk)
                        if i + chunk_size >= len(desc_text):
                            break
                        i += (chunk_size - overlap)

                    if chunks:
                        chunk_embeddings = model.encode(chunks)
                        import numpy as np
                        avg_embedding = np.mean(chunk_embeddings, axis=0)
                        norm = np.linalg.norm(avg_embedding)
                        if norm > 0:
                            avg_embedding = avg_embedding / norm
                        desc_vec_str = json.dumps(avg_embedding.tolist())
                        status = 'done'
                        log_nlp_event(
                            message="Job embeddings stored",
                            event="job_embedding",
                            extra={
                                "company": name,
                                "jobId": job['jobId'],
                                "titleVectorDimensions": 384,
                                "descVectorDimensions": 384
                            }
                        )
                except Exception as embed_err:
                    log_scrape_error(f"[{name}] Embedding generation failed for job {job['jobId']}: {embed_err}")
                    status = 'failed'

            jobs_to_insert.append((posted_date_str, expires_at_str, skills, yoe, title_vec_str, desc_vec_str, status, job))

        # 3. Insert jobs and update company status under lock
        with db_lock:
            conn = sqlite3.connect(db_path, timeout=30.0)
            cursor = conn.cursor()
            for posted_date_str, expires_at_str, skills, yoe, title_vec_str, desc_vec_str, status, job in jobs_to_insert:
                cursor.execute("""
                    INSERT OR IGNORE INTO jobs (
                        company_name, job_id, job_title, location, department,
                        posted_date, employment_type, job_description, url, apply_url,
                        skills_display, required_yoe, embedding_status, scraped_at, expires_at,
                        title_vector, description_vector, embedding_vector
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    name, job['jobId'], job['jobTitle'], job['location'], job['department'],
                    posted_date_str, job['employmentType'], job['jobDescription'], job['url'], job['applyUrl'],
                    json.dumps(skills), yoe, status, datetime.utcnow().isoformat() + 'Z', expires_at_str,
                    title_vec_str, desc_vec_str, desc_vec_str
                ))
                new_count += cursor.rowcount

            cursor.execute("UPDATE companies SET last_scraped_at = ?, status = 'active', degraded_reason = NULL WHERE name = ?", 
                           (datetime.utcnow().isoformat() + 'Z', name))
            conn.commit()
            conn.close()

        # Log completion log structure
        log_entry = {
            "company": name,
            "status": "success",
            "jobsFound": len(raw_jobs),
            "jobsNew": new_count,
            "jobsSkipped": skip_count,
            "durationMs": int((time.time() - start_time) * 1000)
        }
        log_scrape_info(f"[{name}] Scraping success", log_entry)

    except Exception as e:
        log_scrape_error(f"[{name}] Acquisition error: {e}")
        db_path = get_db_path()
        with db_lock:
            conn = sqlite3.connect(db_path, timeout=30.0)
            cursor = conn.cursor()
            # Mark degraded
            cursor.execute("UPDATE companies SET status = 'degraded', degraded_reason = ? WHERE name = ?", (str(e), name))
            conn.commit()
            conn.close()


def run_acquisition_cycle(model):
    print("=== Python Acquisition cycle started ===")
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"Database file not found at {db_path}. Waiting for schema initialization.")
        return

    conn = sqlite3.connect(db_path, timeout=30.0)
    # Return dictionary rows
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM companies WHERE status IN ('active', 'degraded')")
    companies = cursor.fetchall()
    conn.close()

    settings = load_settings()
    max_workers = settings.get('maxConcurrentCompanies', 3)
    print(f"Starting parallel acquisition with {max_workers} workers...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scrape_company, company, model): company['name'] for company in companies}
        for future in futures:
            company_name = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"Fatal error scraping company {company_name}: {e}")

    print("=== Python Acquisition cycle complete ===")

def run_cleanup():
    print("=== Python daily cleanup started ===")
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM jobs WHERE datetime(expires_at) < datetime('now')")
        jobs_deleted = cursor.rowcount
        
        cursor.execute("DELETE FROM matched_jobs WHERE datetime(expires_at) < datetime('now')")
        matched_deleted = cursor.rowcount
        
        conn.commit()
        print(f"Python daily cleanup complete: {jobs_deleted} jobs deleted, {matched_deleted} matched_jobs deleted")
        
        # Reclaim storage space and shrink database file size
        print("Vacuuming database...")
        cursor.execute("VACUUM")
        conn.close()
    except Exception as e:
        print(f"Error in python daily cleanup: {e}")
