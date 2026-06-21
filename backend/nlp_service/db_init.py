import os
import json
import sqlite3
from datetime import datetime

DEFAULT_COMPANIES = [
    {
        'name': 'NVIDIA',
        'ats': 'workday',
        'tier': 2,
        'careerUrl': 'https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite',
        'filters': {
            'locations': ['India', 'Remote', 'United Kingdom', 'Germany', 'France', 'Poland', 'Netherlands', 'Sweden', 'Switzerland', 'Ireland', 'Italy', 'Spain'],
            'searchText': '',
            'limit': 20,
        }
    },
    {
        'name': 'Arista Networks',
        'ats': 'smartrecruiters',
        'tier': 2,
        'careerUrl': 'https://jobs.smartrecruiters.com/AristaNetworks',
        'filters': {
            'countries': ['in', 'gb', 'de', 'fr', 'pl', 'nl', 'ie', 'it', 'es', 'se', 'ch']
        }
    },
    {
        'name': 'Cisco Systems',
        'ats': 'cisco',
        'tier': 2,
        'careerUrl': 'https://careers.cisco.com/global/en/search-results',
        'filters': {
            'keywords': 'engineer',
            'locations': ['India', 'United Kingdom', 'Germany', 'France', 'Poland', 'Netherlands', 'Ireland', 'Italy', 'Spain', 'Sweden', 'Switzerland'],
        }
    },
    {
        'name': 'Qualcomm',
        'ats': 'eightfold',
        'tier': 2,
        'careerUrl': 'https://careers.qualcomm.com',
        'filters': {
            'locations': ['India', 'United Kingdom', 'Germany', 'France', 'Poland', 'Netherlands', 'Ireland', 'Italy', 'Spain', 'Sweden', 'Switzerland'],
            'query': '',
        }
    },
    {
        'name': 'AMD',
        'ats': 'amd',
        'tier': 2,
        'careerUrl': 'https://careers.amd.com/careers-home/jobs',
        'filters': {
            'locations': ['India', 'United Kingdom', 'Germany', 'France', 'Poland', 'Netherlands', 'Ireland', 'Italy', 'Spain', 'Sweden', 'Switzerland'],
            'keywords': '',
        }
    },
    {
        'name': 'Broadcom',
        'ats': 'workday',
        'tier': 2,
        'careerUrl': 'https://broadcom.wd1.myworkdayjobs.com/External_Career',
        'filters': {
            'locations': ['India', 'Remote', 'United Kingdom', 'Germany', 'France', 'Poland', 'Netherlands', 'Sweden', 'Switzerland', 'Ireland', 'Italy', 'Spain'],
            'searchText': '',
            'limit': 20,
        }
    },
    {
        'name': 'Intel',
        'ats': 'workday',
        'tier': 2,
        'careerUrl': 'https://intel.wd1.myworkdayjobs.com/en-US/External',
        'filters': {
            'locations': ['India', 'Remote', 'United Kingdom', 'Germany', 'France', 'Poland', 'Netherlands', 'Sweden', 'Switzerland', 'Ireland', 'Italy', 'Spain'],
            'searchText': '',
            'limit': 20,
        }
    },
    {
        'name': 'Microsoft',
        'ats': 'eightfold',
        'tier': 2,
        'careerUrl': 'https://careers.microsoft.com',
        'filters': {
            'locations': ['India', 'United Kingdom', 'Germany', 'France', 'Poland', 'Netherlands', 'Ireland', 'Italy', 'Spain', 'Sweden', 'Switzerland'],
            'query': '',
        }
    },
    {
        'name': 'IBM',
        'ats': 'ibm',
        'tier': 2,
        'careerUrl': 'https://careers.ibm.com/careers/search',
        'filters': {
            'countries': ['India', 'United Kingdom', 'Germany', 'France', 'Poland', 'Netherlands', 'Ireland', 'Italy', 'Spain', 'Sweden', 'Switzerland'],
            'category': 'Software Engineering',
        }
    },
    {
        'name': 'Ericsson',
        'ats': 'eightfold',
        'tier': 2,
        'careerUrl': 'https://jobs.ericsson.com',
        'filters': {
            'locations': ['India', 'United Kingdom', 'Germany', 'France', 'Poland', 'Netherlands', 'Ireland', 'Italy', 'Spain', 'Sweden', 'Switzerland'],
            'query': '',
        }
    },
    {
        'name': 'Arm',
        'ats': 'arm',
        'tier': 2,
        'careerUrl': 'https://careers.arm.com',
        'filters': {
            'locations': ['India', 'United Kingdom', 'Germany', 'France', 'Poland', 'Netherlands', 'Ireland', 'Italy', 'Spain', 'Sweden', 'Switzerland'],
        }
    }
]

def get_db_path():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_dir, '..', 'data', 'jobs.db'))

def init_db():
    db_path = get_db_path()
    db_dir = os.path.dirname(db_path)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    print(f"Initializing database at {db_path}...")
    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()

    # Enable WAL mode
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA foreign_keys = ON")

    # Create tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS companies (
          id              INTEGER PRIMARY KEY AUTOINCREMENT,
          name            TEXT NOT NULL UNIQUE,
          ats             TEXT NOT NULL,
          tier            INTEGER NOT NULL,
          career_url      TEXT NOT NULL,
          filters         TEXT,
          status          TEXT DEFAULT 'active',
          last_scraped_at TEXT,
          degraded_reason TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
          id               INTEGER PRIMARY KEY AUTOINCREMENT,
          company_name     TEXT NOT NULL,
          job_id           TEXT NOT NULL,
          job_title        TEXT NOT NULL,
          location         TEXT,
          department       TEXT,
          posted_date      TEXT,
          employment_type  TEXT,
          job_description  TEXT,
          url              TEXT,
          apply_url        TEXT,
          skills_display   TEXT,
          embedding_vector TEXT,
          title_vector     TEXT,
          description_vector TEXT,
          required_yoe     INTEGER DEFAULT NULL,
          embedding_status TEXT DEFAULT 'pending',
          scraped_at       TEXT NOT NULL,
          expires_at       TEXT NOT NULL,
          UNIQUE(company_name, job_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
          id                  INTEGER PRIMARY KEY AUTOINCREMENT,
          email               TEXT NOT NULL UNIQUE,
          resume_text         TEXT,
          resume_vector       TEXT,
          resume_skills       TEXT,
          selected_companies  TEXT,
          match_threshold     REAL DEFAULT 65.0,
          resume_uploaded_at  TEXT,
          last_notified_at    TEXT,
          created_at          TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matched_jobs (
          id           INTEGER PRIMARY KEY AUTOINCREMENT,
          email        TEXT NOT NULL,
          job_id       TEXT NOT NULL,
          company_name TEXT NOT NULL,
          match_score  REAL NOT NULL,
          job_title    TEXT,
          location     TEXT,
          apply_url    TEXT,
          skills_display TEXT,
          required_yoe INTEGER DEFAULT NULL,
          notified     INTEGER DEFAULT 0,
          notified_at  TEXT,
          expires_at   TEXT NOT NULL,
          UNIQUE(email, company_name, job_id)
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_company     ON jobs(company_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_expires     ON jobs(expires_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_embedding   ON jobs(embedding_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_matched_email    ON matched_jobs(email)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_matched_notified ON matched_jobs(notified)")

    # Seed companies
    for c in DEFAULT_COMPANIES:
        cursor.execute("""
            INSERT INTO companies (name, ats, tier, career_url, filters, status)
            VALUES (?, ?, ?, ?, ?, 'active')
            ON CONFLICT(name) DO UPDATE SET
              ats = excluded.ats,
              tier = excluded.tier,
              career_url = excluded.career_url,
              filters = excluded.filters
        """, (
            c['name'], c['ats'], c['tier'], c['careerUrl'], json.dumps(c['filters'])
        ))

    conn.commit()
    conn.close()
    print("Database initialization and seeding complete.")

if __name__ == '__main__':
    init_db()
