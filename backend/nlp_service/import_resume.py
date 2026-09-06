import os
import sys
import re
import glob
import json
import hashlib
import sqlite3
import numpy as np
from datetime import datetime
from backend.nlp_service.db_init import init_db


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


def compute_pdf_hash(path):
    """Returns MD5 hex digest of a PDF file for change detection and dedup."""
    with open(path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def derive_slot_label(filename):
    """
    Derives a short human-readable label from the PDF filename.
    cvemb.pdf  -> 'Emb'
    cvnet.pdf  -> 'Net'
    cv_cloud.pdf -> 'Cloud'
    myresume.pdf -> 'Myresume'
    """
    name = os.path.splitext(os.path.basename(filename))[0]  # strip .pdf
    name = re.sub(r'^cv[-_]?', '', name, flags=re.IGNORECASE)  # strip leading 'cv' prefix
    return name.capitalize() if name else 'Resume'


def extract_professional_summary(text):
    """
    Extracts the 'Professional Summary' section from resume text.
    Returns text from that header until the next known section header.
    Falls back to full resume text if the header is not found.
    """
    NEXT_SECTIONS = re.compile(
        r'\n(Work Experience|Experience|Skills|Education|Projects|'
        r'Certifications|Achievements|Technical Skills|Publications|Awards)\s*\n',
        re.IGNORECASE
    )
    match = re.search(r'Professional Summary\s*\n', text, re.IGNORECASE)
    if not match:
        return text  # fallback: full resume text
    start = match.end()
    nxt = NEXT_SECTIONS.search(text, start)
    end = nxt.start() if nxt else len(text)
    return text[start:end].strip()


def find_pdf_resumes(max_resumes=4):
    """
    Finds all PDF resumes in the workspace root and backend/ directories.
    Priority order: cvemb.pdf first, cvnet.pdf second, then any other PDFs alphabetically.
    Returns a list of absolute paths, capped at max_resumes.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    search_dirs = [
        os.path.abspath(os.path.join(current_dir, '..', '..')),  # workspace root
        os.path.abspath(os.path.join(current_dir, '..'))          # backend/
    ]

    PRIORITY_NAMES = ['cvemb.pdf', 'cvnet.pdf']
    found = {}  # filename -> path (dedup by filename across dirs)

    for directory in search_dirs:
        if not os.path.exists(directory):
            continue
        for filepath in glob.glob(os.path.join(directory, '*.pdf')):
            fname = os.path.basename(filepath).lower()
            if fname not in found:
                found[fname] = filepath

    # Sort: priority names first, then alphabetically
    priority = [found[n] for n in PRIORITY_NAMES if n in found]
    others   = sorted([p for n, p in found.items() if n not in PRIORITY_NAMES])
    ordered  = priority + others

    if len(ordered) > max_resumes:
        print(f"Warning: found {len(ordered)} PDF resumes, only processing first {max_resumes}.")
        ordered = ordered[:max_resumes]

    return ordered


def embed_text(model, text, chunk_size=2000, overlap=200):
    """Chunks text and returns a single normalised averaged embedding vector."""
    chunks = []
    i = 0
    while i < len(text):
        chunk = text[i:i + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        if i + chunk_size >= len(text):
            break
        i += (chunk_size - overlap)

    if not chunks:
        return None

    embeddings = model.encode(chunks)
    avg = np.mean(embeddings, axis=0)
    norm = np.linalg.norm(avg)
    if norm > 0:
        avg = avg / norm
    return avg


def main():
    init_db()
    settings = load_settings()
    email = settings.get('notifyEmail') or settings.get('emailUser')
    if not email:
        print("Error: NOTIFY_EMAIL or EMAIL_USER must be set in backend/.env")
        sys.exit(1)

    pdf_paths = find_pdf_resumes(max_resumes=4)
    if not pdf_paths:
        print("Error: No PDF resume found in workspace root or backend/ folder.")
        sys.exit(1)

    print(f"\nFound {len(pdf_paths)} PDF resume(s): {[os.path.basename(p) for p in pdf_paths]}")
    print(f"Processing resumes for {email}...\n")

    try:
        import time
        from pypdf import PdfReader
        from backend.nlp_service.model_factory import get_sentence_transformer
        from backend.nlp_service.scraper import extract_skills, get_db_path
        from backend.nlp_service.logger import log_nlp_event

        model = get_sentence_transformer()

        # --- Deduplication: skip PDFs with identical content ---
        seen_hashes = {}   # hash -> filename
        to_process  = []   # list of (path, hash, label)

        for path in pdf_paths:
            h = compute_pdf_hash(path)
            fname = os.path.basename(path)
            if h in seen_hashes:
                print(f"  Skipping {fname} — duplicate content of '{seen_hashes[h]}'")
                continue
            seen_hashes[h] = fname
            label = derive_slot_label(fname)
            to_process.append((path, h, label))

        print(f"Processing {len(to_process)} unique resume(s)...\n")

        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        now_iso = datetime.utcnow().isoformat() + 'Z'

        # Ensure user row exists
        cursor.execute("""
            INSERT OR IGNORE INTO users (email, created_at)
            VALUES (?, ?)
        """, (email, now_iso))

        for i, (path, pdf_hash, label) in enumerate(to_process):
            fname = os.path.basename(path)
            print(f"[{i+1}/{len(to_process)}] Processing {fname} (label: {label})...")

            # Extract text
            reader = PdfReader(path)
            resume_text = ""
            for page in reader.pages:
                resume_text += page.extract_text() or ""
            resume_text = resume_text.strip()

            if not resume_text:
                print(f"  Warning: Could not extract text from {fname} — skipping.")
                continue

            # Extract summary section
            summary_text = extract_professional_summary(resume_text)
            print(f"  Summary extracted: {len(summary_text)} chars")

            # Extract skills
            resume_skills = extract_skills(resume_text)
            print(f"  Skills extracted ({len(resume_skills)}): {', '.join(resume_skills[:10])}{'...' if len(resume_skills) > 10 else ''}")

            # Embed full resume
            start = time.time()
            vec = embed_text(model, resume_text)
            summary_vec = embed_text(model, summary_text)
            elapsed = int((time.time() - start) * 1000)
            print(f"  Embeddings generated in {elapsed}ms")

            vec_bytes     = np.array(vec,         dtype=np.float32).tobytes() if vec         is not None else None
            sum_vec_bytes = np.array(summary_vec, dtype=np.float32).tobytes() if summary_vec is not None else None

            # Upsert into user_resumes
            cursor.execute("""
                INSERT INTO user_resumes
                    (email, pdf_filename, slot_label, pdf_hash,
                     resume_vector, resume_summary_vector, resume_skills,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email, pdf_filename) DO UPDATE SET
                    slot_label            = excluded.slot_label,
                    pdf_hash              = excluded.pdf_hash,
                    resume_vector         = excluded.resume_vector,
                    resume_summary_vector = excluded.resume_summary_vector,
                    resume_skills         = excluded.resume_skills,
                    updated_at            = excluded.updated_at
            """, (email, fname, label, pdf_hash,
                  vec_bytes, sum_vec_bytes, json.dumps(resume_skills),
                  now_iso, now_iso))

            # Mirror primary resume into users table for backward compat
            if i == 0:
                cursor.execute("""
                    UPDATE users SET
                        resume_text        = ?,
                        resume_vector      = ?,
                        resume_skills      = ?,
                        resume_uploaded_at = ?
                    WHERE email = ?
                """, (resume_text, vec_bytes, json.dumps(resume_skills), now_iso, email))

            log_nlp_event(
                message=f"Resume processed: {fname}",
                event="resume_processed",
                extra={"email": email, "label": label, "skillsExtracted": resume_skills, "vectorDimensions": 384}
            )

        # Remove stale rows — PDFs no longer present on disk
        current_filenames = [os.path.basename(p) for p, _, _ in to_process]
        if current_filenames:
            placeholders = ','.join('?' * len(current_filenames))
            cursor.execute(f"""
                DELETE FROM user_resumes
                WHERE email = ? AND pdf_filename NOT IN ({placeholders})
            """, [email] + current_filenames)
            deleted = cursor.rowcount
            if deleted > 0:
                print(f"\nRemoved {deleted} stale resume row(s) from user_resumes.")

        # Clear matched_jobs — fresh start with new embeddings
        cursor.execute("DELETE FROM matched_jobs WHERE email = ?", (email,))
        print(f"\nCleared matched_jobs for {email} — fresh start.")

        conn.commit()
        conn.close()

        print(f"\nResume import complete. {len(to_process)} resume(s) processed.")

    except Exception as e:
        print(f"Failed to import resume(s): {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
