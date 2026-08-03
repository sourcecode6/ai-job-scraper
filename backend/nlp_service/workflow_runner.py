from backend.nlp_service.config import get_db_path, load_settings
import os
import sys
import sqlite3

from backend.nlp_service.db_init import init_db
from backend.nlp_service.scraper import run_acquisition_cycle, run_cleanup, get_db_path
from backend.nlp_service.matcher import run_match_cycle
from backend.nlp_service.import_resume import main as import_resume_main

def main():
    print("=== Standalone Workflow Runner Starting ===")
    
    # 1. Initialize DB
    print("\n[Step 1/6] Initializing Database...")
    init_db()
    
    # 2. Check and Import Resume
    print("\n[Step 2/6] Checking user and resume state...")
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    conn.close()
    
    if user_count == 0:
        print("No users found in database. Importing resume...")
        try:
            import_resume_main()
        except Exception as e:
            print(f"Error during resume import: {e}")
    else:
        print(f"Found {user_count} user(s) in database. Skipping resume import.")
        
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
