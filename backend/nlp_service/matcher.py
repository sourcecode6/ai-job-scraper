from backend.nlp_service.config import get_db_path, load_settings
import os
import re
import json
import sqlite3
import numpy as np
from datetime import datetime, timedelta
from backend.nlp_service import email_sender
from backend.nlp_service.scraper import get_db_path, load_settings

def compute_similarity(vec_a, vec_b):
    if vec_a is None or vec_b is None or len(vec_a) != len(vec_b):
        return 0.0
    arr_a = np.array(vec_a, dtype=np.float32)
    arr_b = np.array(vec_b, dtype=np.float32)
    dot = np.dot(arr_a, arr_b)
    norm_a = np.linalg.norm(arr_a)
    norm_b = np.linalg.norm(arr_b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot / (norm_a * norm_b))

def get_location_priority_rank(location):
    if not location:
        return 3
    loc = location.lower()
    # Check India
    if 'india' in loc or ', in' in loc or loc.endswith(' in') or re.search(r'\bin\b', loc) is not None:
        return 0
    # Check UK
    if 'united kingdom' in loc or ' u.k.' in loc or '\buk\b' in loc or ', uk' in loc or 'great britain' in loc or 'england' in loc or 'scotland' in loc or 'wales' in loc or 'london' in loc:
        return 1
    # Check Europe
    european_keywords = [
        'europe', 'germany', 'france', 'italy', 'spain', 'poland', 'netherlands', 'belgium',
        'austria', 'switzerland', 'sweden', 'norway', 'denmark', 'finland', 'ireland', 'portugal',
        'greece', 'czech republic', 'hungary', 'romania', 'bulgaria', 'slovakia', 'croatia',
        'lithuania', 'latvia', 'estonia', 'slovenia', 'luxembourg', 'malta', 'cyprus',
        'munich', 'berlin', 'paris', 'amsterdam', 'dublin', 'gdansk', 'warsaw', 'regensburg'
    ]
    if any(kw in loc for kw in european_keywords):
        return 1
    # Check remote
    if 'remote' in loc:
        return 2
    return 3

def is_job_within_retention(job_posted_date, job_scraped_at, retention_days):
    now = datetime.utcnow()
    cutoff = now - timedelta(days=retention_days)

    # 1. Try parsing posted_date
    if job_posted_date:
        try:
            # Try ISO date parsing
            s = job_posted_date.rstrip('Z')
            s = re.sub(r'([+-]\d{2})(\d{2})$', r'\1:\2', s)
            posted_dt = datetime.fromisoformat(s)
            if posted_dt.tzinfo is not None:
                posted_dt = posted_dt.replace(tzinfo=None)
            return posted_dt >= cutoff
        except ValueError:
            pass

        # Parse relative date
        lowercase_posted = job_posted_date.lower()
        if 'today' in lowercase_posted:
            return True
        if 'yesterday' in lowercase_posted:
            return retention_days >= 1

        days_match = re.search(r'(\d+)\+?\s+days?\s+(ago|back)', lowercase_posted)
        if days_match:
            days_ago = int(days_match.group(1))
            return days_ago <= retention_days
 
        weeks_match = re.search(r'(\d+)\+?\s+weeks?\s+(ago|back)', lowercase_posted)
        if weeks_match:
            weeks_ago = int(weeks_match.group(1))
            return (weeks_ago * 7) <= retention_days

        if any(w in lowercase_posted for w in ['month', 'year', '30+ days']):
            return False

    # 2. Fallback to scraped_at
    if job_scraped_at:
        try:
            s = job_scraped_at.rstrip('Z')
            s = re.sub(r'([+-]\d{2})(\d{2})$', r'\1:\2', s)
            scraped_dt = datetime.fromisoformat(s)
            if scraped_dt.tzinfo is not None:
                scraped_dt = scraped_dt.replace(tzinfo=None)
            return scraped_dt >= cutoff
        except ValueError:
            pass

    return True

def run_match_cycle():
    print("=== Python Match cycle started ===")
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print("Database not found. Skipping match cycle.")
        return

    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE resume_vector IS NOT NULL")
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not users:
        print("No users with resume vectors — skipping match cycle")
        return

    for user in users:
        try:
            match_for_user_internal(user)
        except Exception as e:
            print(f"Error matching for user {user['email']}: {e}")

    print("=== Python Match cycle complete ===")

def match_for_user(email):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        print(f"User {email} not found.")
        return
    if not user['resume_vector']:
        print(f"User {email} has no resume vector.")
        return

    match_for_user_internal(dict(user))

def match_for_user_internal(user):
    email = user['email']
    resume_vector = np.frombuffer(user['resume_vector'], dtype=np.float32)
    selected_companies = json.loads(user['selected_companies'] or '[]')
    resume_skills = json.loads(user.get('resume_skills') or '[]')
    
    settings = load_settings()
    threshold = settings['matchThreshold']
    retention_days = settings['dataRetentionDays']
    user_yoe = int(os.environ.get('USER_YOE', '0'))

    db_path = get_db_path()
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if not selected_companies:
        cursor.execute("SELECT name FROM companies WHERE status = 'active'")
        selected_companies = [row['name'] for row in cursor.fetchall()]

    if not selected_companies:
        print(f"No active companies found for matching user {email}")
        conn.close()
        return

    # 1. Fetch eligible jobs
    jobs = _fetch_eligible_jobs(cursor, selected_companies)

    # 2. Calculate matches
    new_matches = _calculate_matches(jobs, resume_vector, threshold, retention_days, email, cursor)

    # 3. Save new matches
    _save_new_matches(cursor, email, new_matches)

    # 4. Fetch pending matches
    all_matches = _combine_pending_matches(cursor, email, new_matches, retention_days)

    if not all_matches:
        print(f"No new matches found for user {email}")
        conn.close()
        return

    print(f"Found {len(all_matches)} matches for user {email}")

    # 5. Send notifications
    _send_notifications_and_update(cursor, conn, email, all_matches, user_yoe, resume_skills=resume_skills)

    conn.close()

def _fetch_eligible_jobs(cursor, selected_companies):
    placeholders = ",".join(["?"] * len(selected_companies))
    query = f"""
        SELECT * FROM jobs
        WHERE company_name IN ({placeholders})
        AND embedding_status = 'done'
        AND (embedding_vector IS NOT NULL OR (title_vector IS NOT NULL AND description_vector IS NOT NULL))
        AND datetime(expires_at) > datetime('now')
    """
    cursor.execute(query, selected_companies)
    return [dict(row) for row in cursor.fetchall()]

def _calculate_matches(jobs, resume_vector, threshold, retention_days, email, cursor):
    new_matches = []
    for job in jobs:
        if not is_job_within_retention(job['posted_date'], job['scraped_at'], retention_days):
            continue

        score = 0.0
        if job['title_vector'] and job['description_vector']:
            title_vec = np.frombuffer(job['title_vector'], dtype=np.float32)
            desc_vec = np.frombuffer(job['description_vector'], dtype=np.float32)
            title_score = compute_similarity(resume_vector, title_vec) * 100
            desc_score = compute_similarity(resume_vector, desc_vec) * 100
            score = (title_score * 0.5) + (desc_score * 0.5)
        else:
            job_vector = np.frombuffer(job['embedding_vector'], dtype=np.float32)
            score = compute_similarity(resume_vector, job_vector) * 100

        if score >= threshold:
            cursor.execute("""
                SELECT id FROM matched_jobs
                WHERE email = ? AND company_name = ? AND job_id = ?
            """, (email, job['company_name'], job['job_id']))
            
            if not cursor.fetchone():
                rounded_score = round(score, 1)
                new_matches.append({
                    "job_id": job['job_id'],
                    "company_name": job['company_name'],
                    "job_title": job['job_title'],
                    "location": job['location'],
                    "apply_url": job['apply_url'],
                    "skills_display": job['skills_display'],
                    "required_yoe": job['required_yoe'],
                    "match_score": rounded_score,
                    "posted_date": job['posted_date'],
                    "expires_at": job['expires_at']
                })
    return new_matches

def _save_new_matches(cursor, email, new_matches):
    for job in new_matches:
        cursor.execute("""
            INSERT OR IGNORE INTO matched_jobs
                (email, job_id, company_name, match_score, job_title, location, apply_url, skills_display, required_yoe, notified, expires_at)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """, (
            email, job['job_id'], job['company_name'], job['match_score'], job['job_title'],
            job['location'], job['apply_url'], job['skills_display'], job['required_yoe'],
            job['expires_at']
        ))

def _combine_pending_matches(cursor, email, new_matches, retention_days):
    cursor.execute("""
        SELECT mj.*, j.posted_date, j.scraped_at
        FROM matched_jobs mj
        LEFT JOIN jobs j ON mj.company_name = j.company_name AND mj.job_id = j.job_id
        WHERE mj.email = ? AND mj.notified < 2 AND datetime(mj.expires_at) > datetime('now')
    """, (email,))
    pending_matches = [dict(row) for row in cursor.fetchall()]

    all_matches = []
    seen_ids = set()
    
    for m in new_matches:
        key = (m['company_name'], m['job_id'])
        if key not in seen_ids:
            seen_ids.add(key)
            all_matches.append(m)
            
    for m in pending_matches:
        if m['posted_date'] or m['scraped_at']:
            if not is_job_within_retention(m['posted_date'], m['scraped_at'], retention_days):
                continue
        key = (m['company_name'], m['job_id'])
        if key not in seen_ids:
            seen_ids.add(key)
            all_matches.append(m)

    def sort_key(m):
        loc = m.get('location', '')
        score = m.get('match_score') or 0.0
        return (get_location_priority_rank(loc), -score)

    all_matches.sort(key=sort_key)
    return all_matches

def _send_notifications_and_update(cursor, conn, email, all_matches, user_yoe, resume_skills=None):
    from backend.nlp_service.db_init import load_companies_config
    configs = {c['name']: c for c in load_companies_config()}
    
    cursor.execute("SELECT name, degraded_reason FROM companies WHERE status = 'degraded'")
    errors = []
    for r in cursor.fetchall():
        if configs.get(r["name"], {}).get("enabled", True):
            errors.append({"name": r["name"], "reason": r["degraded_reason"]})

    from backend.nlp_service import email_sender
    sent = email_sender.send_job_digest(email, all_matches, user_yoe, errors, resume_skills=resume_skills)

    if sent:
        now_iso = datetime.utcnow().isoformat() + 'Z'
        for m in all_matches:
            cursor.execute("""
                UPDATE matched_jobs SET notified = notified + 1, notified_at = ?
                WHERE email = ? AND company_name = ? AND job_id = ?
            """, (now_iso, email, m['company_name'], m['job_id']))
        
        cursor.execute("UPDATE users SET last_notified_at = ? WHERE email = ?", (now_iso, email))
        conn.commit()
        print(f"Email digest sent and matches marked notified (incremented) for {email}")
    else:
        print(f"Email send failed — matches left as pending for {email}")
