from backend.nlp_service.config import get_db_path, load_settings
import os
import sys
import sqlite3

from backend.nlp_service.db_init import init_db
from backend.nlp_service.scraper import run_acquisition_cycle, run_cleanup, get_db_path
from backend.nlp_service.matcher import run_match_cycle
from backend.nlp_service.import_resume import main as import_resume_main

def check_resume_changes():
    """
    Compares MD5 hashes of PDF files on disk against stored hashes in user_resumes.
    Returns True if any resume has changed (new, modified, or removed).
    """
    from backend.nlp_service.import_resume import find_pdf_resumes, compute_pdf_hash

    pdf_paths = find_pdf_resumes(max_resumes=4)
    db_path = get_db_path()

    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT pdf_filename, pdf_hash FROM user_resumes")
    stored = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()

    current_fnames = set()
    for path in pdf_paths:
        fname = os.path.basename(path)
        current_fnames.add(fname)
        current_hash = compute_pdf_hash(path)
        if current_hash != stored.get(fname, ''):
            print(f"  Change detected: {fname} (hash mismatch or new file)")
            return True

    # Check for removed PDFs (stored in DB but no longer on disk)
    for stored_fname in stored:
        if stored_fname not in current_fnames:
            print(f"  Change detected: {stored_fname} removed from disk")
            return True

    return False

def main():
    print("=== Standalone Workflow Runner Starting ===")
    
    # 1. Initialize DB
    print("\n[Step 1/6] Initializing Database...")
    init_db()

    # 2. Resume change detection — auto re-import if any PDF changed
    print("\n[Step 2/6] Checking resume PDFs for changes...")
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM user_resumes")
    resume_count = cursor.fetchone()[0]
    conn.close()

    if user_count == 0 or resume_count == 0:
        print("No user or resume vectors found — running initial import...")
        try:
            import_resume_main()
        except Exception as e:
            print(f"Error during initial resume import: {e}")
    else:
        try:
            changed = check_resume_changes()
            if changed:
                print("Resume change detected — re-importing automatically...")
                import_resume_main()
            else:
                print("Resume unchanged — skipping re-import.")
        except Exception as e:
            print(f"Error during resume change check: {e} — skipping re-import.")

    # 3. Load Model
    print("Model loaded successfully.")
    
    # 4. Run Scraping Cycle
    print("\n[Step 4/6] Running Job Acquisition...")
    run_acquisition_cycle()
    
    # 4. Enrich DB (generate embeddings for new jobs)
    print("\n[Step 4/6] Running Enrichment Cycle...")
    from backend.nlp_service.enricher import run_enrichment_cycle
    run_enrichment_cycle()
    
    # 5. Run Matching & Notification
    print("\n[Step 5/6] Running Match & Notification Cycle...")
    run_match_cycle()
    
    # 6. Run Daily Cleanup
    print("\n[Step 6/6] Running Daily Cleanup...")
    run_cleanup()
    
    print("\n=== Standalone Workflow Runner Complete ===")

if __name__ == '__main__':
    main()
