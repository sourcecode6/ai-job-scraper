from backend.nlp_service.config import get_db_path, load_settings
import os
import json
import sqlite3
from datetime import datetime

def load_companies_config():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.abspath(os.path.join(current_dir, '..', 'companies_config.json'))
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading companies_config.json: {e}")
        return []



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

    # Lightweight Migrations
    cursor.execute("PRAGMA user_version")
    current_version = cursor.fetchone()[0]

    if current_version == 0:
        print("Applying migration: Version 1 (Initial Schema)")
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
              degraded_reason TEXT,
              CHECK (tier IN (1, 2, 3)),
              CHECK (status IN ('active', 'degraded', 'disabled'))
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
              embedding_vector BLOB,
              title_vector     BLOB,
              description_vector BLOB,
              required_yoe     INTEGER DEFAULT NULL,
              embedding_status TEXT DEFAULT 'pending',
              scraped_at       TEXT NOT NULL,
              expires_at       TEXT NOT NULL,
              UNIQUE(company_name, job_id),
              CHECK (embedding_status IN ('pending', 'processing', 'completed', 'failed'))
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
              id                  INTEGER PRIMARY KEY AUTOINCREMENT,
              email               TEXT NOT NULL UNIQUE,
              resume_text         TEXT,
              resume_vector       BLOB,
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
              status       TEXT DEFAULT 'pending',
              notified_at  TEXT,
              scraped_at   TEXT,
              expires_at   TEXT,
              UNIQUE(email, company_name, job_id),
              CHECK (status IN ('pending', 'notified', 'rejected', 'applied'))
            )
        """)
        
        cursor.execute("PRAGMA user_version = 1")
        conn.commit()
        current_version = 1

    # Apply future migrations here
    # if current_version == 1:
    #     cursor.execute("...")
    #     cursor.execute("PRAGMA user_version = 2")
    #     conn.commit()
    #     current_version = 2

    # Load initial config
    print("Loading companies config...")
    configs = load_companies_config()
    if configs:
        for c in configs:
            cursor.execute("""
                INSERT INTO companies (name, ats, tier, career_url, filters)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                  ats=excluded.ats,
                  tier=excluded.tier,
                  career_url=excluded.career_url,
                  filters=excluded.filters
            """, (
                c['name'], c['ats'], c['tier'], c.get('careerUrl', ''),
                json.dumps(c.get('filters', {}))
            ))
        conn.commit()
        print(f"Upserted {len(configs)} companies into database.")
    else:
        print("Warning: No companies loaded from config.")

    conn.close()
    print("Database initialization complete.")

if __name__ == "__main__":
    init_db()
