from backend.nlp_service.config import get_db_path, load_settings
import os
import time
import re
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from backend.nlp_service.utils import extract_skills, extract_yoe, is_allowed, get_crawl_delay_ms
from backend.nlp_service.config import load_settings, get_db_path
from backend.nlp_service.logger import log_scrape_info, log_scrape_error, log_nlp_event

# Import adapters
from backend.nlp_service.adapters.registry import get_target_url, run_adapter

# --- Main orchestrator ---

def parse_relative_date(date_str, retention_days):
    now = datetime.utcnow()
    expires_at = now + timedelta(days=retention_days)

    if not date_str:
        return now.isoformat() + 'Z', expires_at.isoformat() + 'Z'

    try:
        s = date_str.rstrip('Z')
        s = re.sub(r'([+-]\d{2})(\d{2})$', r'\1:\2', s)
        parsed = datetime.fromisoformat(s)
        if parsed.tzinfo is not None:
            from datetime import timezone
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return date_str, (parsed + timedelta(days=retention_days)).isoformat() + 'Z'
    except ValueError:
        pass

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

def scrape_company(company_row):
    start_time = time.time()
    company = dict(company_row)
    name = company['name']
    # (COMPANY_CONFIGS moved to json)


    ats = company['ats']
    tier = company['tier']
    filters = json.loads(company['filters'] or '{}')

    log_scrape_info(f"[{name}] Starting acquisition (ats={ats}, tier={tier})")

    target_url = get_target_url(ats, company)

    # Check robots.txt compliance
    if tier >= 2 and ats != 'workday':
        if not is_allowed(target_url):
            log_scrape_error(f"[{name}] Blocked by robots.txt — skipping (target_url={target_url})")
            return {"name": name, "status": "degraded", "error": "Blocked by robots.txt", "raw_jobs": []}

    try:
        raw_jobs = run_adapter(ats, company, filters)
        return {
            "name": name, 
            "status": "active", 
            "error": None, 
            "raw_jobs": raw_jobs, 
            "start_time": start_time
        }
    except Exception as e:
        error_type = "Adapter Error" if type(e).__name__ == "AdapterError" else "Acquisition error"
        log_scrape_error(f"[{name}] {error_type}: {e}")
        return {"name": name, "status": "degraded", "error": str(e), "raw_jobs": []}


def run_acquisition_cycle():
    print("=== Python Acquisition cycle started ===")
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"Database file not found at {db_path}. Waiting for schema initialization.")
        return

    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM companies WHERE status IN ('active', 'degraded')")
    db_companies = cursor.fetchall()
    conn.close()

    from backend.nlp_service.db_init import load_companies_config
    config_list = load_companies_config()
    config_lookup = {c['name']: c for c in config_list}

    companies = []
    for db_c in db_companies:
        c_dict = dict(db_c)
        if c_dict['name'] in config_lookup:
            config = config_lookup[c_dict['name']]
            if not config.get('enabled', True):
                continue
            for k, v in config.items():
                if k not in c_dict:
                    c_dict[k] = v
        companies.append(c_dict)

    settings = load_settings()
    max_workers = settings.get('maxConcurrentCompanies', 3)
    retention = settings['dataRetentionDays']
    print(f"Starting parallel acquisition with {max_workers} workers...")

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scrape_company, company): company['name'] for company in companies}
        for future in futures:
            company_name = futures[future]
            try:
                res = future.result()
                if res:
                    results.append(res)
            except Exception as e:
                print(f"Fatal error scraping company {company_name}: {e}")

    # Centralized DB Insert
    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()

    for result in results:
        name = result['name']
        status = result['status']
        error = result['error']
        raw_jobs = result['raw_jobs']

        if status == 'degraded':
            cursor.execute("UPDATE companies SET status = 'degraded', degraded_reason = ? WHERE name = ?", (error, name))
            continue

        skip_count = 0
        new_count = 0
        seen_job_ids = set()
        jobs_to_insert = []
        
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
                posted_date_str, expires_at_str = parse_relative_date(job['postedDate'], retention)
                skills = extract_skills(f"{job['jobTitle']} {job['department']} {job['jobDescription']}")
                yoe = extract_yoe(job['jobDescription'])
                jobs_to_insert.append((
                    name, job['jobId'], job['jobTitle'], job['location'], job['department'],
                    posted_date_str, job['employmentType'], job['jobDescription'], job['url'], job['applyUrl'],
                    json.dumps(skills), yoe, 'pending', datetime.utcnow().isoformat() + 'Z', expires_at_str,
                    None, None, None
                ))

        if jobs_to_insert:
            cursor.executemany("""
                INSERT OR IGNORE INTO jobs (
                    company_name, job_id, job_title, location, department,
                    posted_date, employment_type, job_description, url, apply_url,
                    skills_display, required_yoe, embedding_status, scraped_at, expires_at,
                    title_vector, description_vector, embedding_vector
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, jobs_to_insert)
            new_count += cursor.rowcount

        cursor.execute("UPDATE companies SET last_scraped_at = ?, status = 'active', degraded_reason = NULL WHERE name = ?", 
                       (datetime.utcnow().isoformat() + 'Z', name))
                       
        log_entry = {
            "company": name,
            "status": "success",
            "jobsFound": len(raw_jobs),
            "jobsNew": new_count,
            "jobsSkipped": skip_count,
            "durationMs": int((time.time() - result['start_time']) * 1000)
        }
        log_scrape_info(f"[{name}] Scraping success", log_entry)

    conn.commit()
    conn.close()

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
        
        print("Vacuuming database...")
        cursor.execute("VACUUM")
        conn.close()
    except Exception as e:
        print(f"Error in python daily cleanup: {e}")
