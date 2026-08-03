from backend.nlp_service.config import get_db_path, load_settings
import sqlite3
import json
import time
import numpy as np
from backend.nlp_service.config import load_settings, get_db_path
from backend.nlp_service.logger import log_nlp_event, log_scrape_error
from backend.nlp_service.model_factory import get_sentence_transformer

def run_enrichment_cycle():
    print("\n=== Enrichment Cycle Started ===")
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT id, company_name, job_id, job_title, department, job_description FROM jobs WHERE embedding_status = 'pending'")
    pending_jobs = cursor.fetchall()
    
    if not pending_jobs:
        print("No pending jobs to enrich.")
        conn.close()
        return

    print(f"Found {len(pending_jobs)} jobs to enrich.")
    model = get_sentence_transformer()

    updated_count = 0
    for job in pending_jobs:
        try:
            # Title Embedding
            title_vector = model.encode([job['job_title']])[0].tolist()
            title_vec_str = np.array(title_vector, dtype=np.float32).tobytes()

            # Description Embedding
            desc_text = f"{job['job_title']} {job['department']} {job['job_description']}"
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

            desc_vec_str = None
            if chunks:
                chunk_embeddings = model.encode(chunks)
                avg_embedding = np.mean(chunk_embeddings, axis=0)
                norm = np.linalg.norm(avg_embedding)
                if norm > 0:
                    avg_embedding = avg_embedding / norm
                desc_vec_str = np.array(avg_embedding, dtype=np.float32).tobytes()

            cursor.execute("""
                UPDATE jobs 
                SET title_vector = ?, description_vector = ?, embedding_vector = ?, embedding_status = 'done'
                WHERE id = ?
            """, (title_vec_str, desc_vec_str, desc_vec_str, job['id']))
            
            updated_count += 1
            if updated_count % 50 == 0:
                conn.commit()
                print(f"Enriched {updated_count}/{len(pending_jobs)} jobs...")

        except Exception as e:
            log_scrape_error(f"Failed to enrich job {job['job_id']}: {e}")
            cursor.execute("UPDATE jobs SET embedding_status = 'failed' WHERE id = ?", (job['id'],))

    conn.commit()
    conn.close()
    
    log_nlp_event(message=f"Enrichment complete. Embedded {updated_count} jobs.", event="enrichment_cycle")
    print(f"=== Enrichment Cycle Complete ({updated_count} jobs updated) ===")
