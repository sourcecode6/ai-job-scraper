import os
import sys
import glob
import json
import sqlite3
from datetime import datetime
import requests
from db_init import init_db


def load_settings():
    settings = {
        'matchThreshold': float(os.environ.get('MATCH_THRESHOLD', 65.0)),
        'dataRetentionDays': int(os.environ.get('DATA_RETENTION_DAYS', 3)),
        'scrapeIntervalHours': int(os.environ.get('SCRAPE_INTERVAL_HOURS', 6)),
        'notifyEmail': os.environ.get('NOTIFY_EMAIL'),
        'emailUser': os.environ.get('EMAIL_USER'),
    }
    current_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.abspath(os.path.join(current_dir, '..', '.env'))
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split('=', 1)
                        if len(parts) == 2:
                            key = parts[0].strip()
                            val = parts[1].strip()
                            if key == 'NOTIFY_EMAIL':
                                settings['notifyEmail'] = val
                            elif key == 'EMAIL_USER':
                                settings['emailUser'] = val
                            elif key == 'MATCH_THRESHOLD':
                                settings['matchThreshold'] = float(val)
        except Exception as e:
            print(f"Error loading .env: {e}")
    return settings

def find_pdf_resume():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    search_dirs = [
        os.path.abspath(os.path.join(current_dir, '..', '..')),  # Root workspace
        os.path.abspath(os.path.join(current_dir, '..'))         # backend/
    ]
    
    for directory in search_dirs:
        if not os.path.exists(directory):
            continue
        pattern = os.path.join(directory, '*')
        for filepath in glob.glob(pattern):
            if os.path.basename(filepath).lower() == 'saurabh_surashe.pdf':
                return filepath

    for directory in search_dirs:
        if not os.path.exists(directory):
            continue
        pattern = os.path.join(directory, '*.pdf')
        pdfs = glob.glob(pattern)
        if pdfs:
            return pdfs[0]

    return None

def main():
    # Automatically initialize and seed SQLite database
    init_db()
    settings = load_settings()
    email = settings.get('notifyEmail') or settings.get('emailUser')
    if not email:
        print("Error: NOTIFY_EMAIL or EMAIL_USER must be set in backend/.env")
        sys.exit(1)
        
    resume_path = find_pdf_resume()
    if not resume_path:
        print("Error: No PDF resume found in root workspace or backend folder.")
        sys.exit(1)
        
    print(f"\nFound resume PDF: {os.path.basename(resume_path)} at {resume_path}")
    print(f"Processing resume for {email}...")

    # Extract, Embed, and Write directly to SQLite
    try:
        import time
        from pypdf import PdfReader
        from sentence_transformers import SentenceTransformer
        import numpy as np
        
        # Load skills extractor helper locally from scraper module
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from scraper import extract_skills, get_db_path
        from logger import log_nlp_event, log_scrape_error
        
        # Parse PDF text
        reader = PdfReader(resume_path)
        resume_text = ""
        for page in reader.pages:
            resume_text += page.extract_text() or ""
        resume_text = resume_text.strip()
        
        if not resume_text:
            print("Error: Could not extract text from PDF resume")
            sys.exit(1)
            
        # Extract skills
        resume_skills = extract_skills(resume_text)
        
        # Generate embedding locally
        start_embed_time = time.time()
        print("Loading SentenceTransformer model locally (this may take a few seconds)...")
        model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        
        chunk_size = 2000
        overlap = 200
        chunks = []
        i = 0
        while i < len(resume_text):
            chunk = resume_text[i:i + chunk_size].strip()
            if chunk:
                chunks.append(chunk)
            if i + chunk_size >= len(resume_text):
                break
            i += (chunk_size - overlap)
            
        vector = None
        if chunks:
            chunk_embeddings = model.encode(chunks)
            avg_embedding = np.mean(chunk_embeddings, axis=0)
            norm = np.linalg.norm(avg_embedding)
            if norm > 0:
                avg_embedding = avg_embedding / norm
            vector = avg_embedding.tolist()
            
        embed_duration_ms = int((time.time() - start_embed_time) * 1000)
        
        log_nlp_event(
            message="Resume embedding",
            event="resume_upload",
            extra={
                "email": email,
                "localModelStatus": "success",
                "vectorDimensions": 384,
                "durationMs": embed_duration_ms
            }
        )
        
        log_nlp_event(
            message="Resume processed",
            event="resume_processed",
            extra={
                "email": email,
                "skillsExtracted": resume_skills,
                "vectorDimensions": 384
            }
        )

        # Write to SQLite
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        
        # Seed companies table if not exists or query active
        cursor.execute("SELECT name FROM companies WHERE status = 'active'")
        all_companies = [row[0] for row in cursor.fetchall()]
        if not all_companies:
            all_companies = ["NVIDIA", "Arista Networks", "Cisco Systems", "Qualcomm", "AMD", "Broadcom", "Intel", "Microsoft", "IBM", "Ericsson"]
            
        now_iso = datetime.utcnow().isoformat() + 'Z'
        
        cursor.execute("""
            INSERT INTO users (email, resume_text, resume_vector, resume_skills, selected_companies, resume_uploaded_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
              resume_text = excluded.resume_text,
              resume_vector = excluded.resume_vector,
              resume_skills = excluded.resume_skills,
              resume_uploaded_at = excluded.resume_uploaded_at
        """, (
            email, resume_text, json.dumps(vector) if vector else None, json.dumps(resume_skills),
            json.dumps(all_companies), now_iso, now_iso
        ))
        
        cursor.execute("DELETE FROM matched_jobs WHERE email = ? AND expires_at > datetime('now')", (email,))
        
        conn.commit()
        conn.close()
        
        print("Resume processed and stored directly in SQLite database successfully!")
        print(f"   Skills Extracted ({len(resume_skills)}): {', '.join(resume_skills)}")
        
    except Exception as e:
        # Import log_scrape_error inline just in case logger is not loaded yet
        try:
            from logger import log_scrape_error
            log_scrape_error(f"Failed to parse or store resume locally: {e}")
        except Exception:
            print(f"Failed to parse or store resume locally: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
