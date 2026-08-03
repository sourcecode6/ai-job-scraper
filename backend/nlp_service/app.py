from backend.nlp_service.config import get_db_path, load_settings
import os
import io
import json
import sqlite3
import asyncio
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import numpy as np

# Load emails module (runs load_env on import)
import email_sender
from backend.nlp_service.scraper import run_acquisition_cycle, load_settings, get_db_path, run_cleanup, extract_skills
from backend.nlp_service.matcher import run_match_cycle, match_for_user
from backend.nlp_service.logger import log_nlp_event, log_scrape_error
from backend.nlp_service.utils import clean_html
from backend.nlp_service.db_init import init_db



app = FastAPI(title="AI Job Scraper Backend")

# Enable CORS for frontend compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.nlp_service.model_factory import get_sentence_transformer
class TextPayload(BaseModel):
    text: str

class UserProfilePayload(BaseModel):
    email: str
    selectedCompanies: Optional[List[str]] = None
    matchThreshold: Optional[int] = None

class UserCompaniesPayload(BaseModel):
    selectedCompanies: List[str] = []

# ── Health check ────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "service": "AI Job Scraper Backend",
        "status": "running",
        "version": "1.0.0",
        "docs": "See README.md for API usage with curl",
    }

# ── Embed endpoint ──────────────────────────────────────────────────────────
@app.post("/embed")
async def get_embedding(payload: TextPayload):
    text = payload.text
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
        
    try:
        # Chunk text (matching the Node.js implementation: 2000 chars, overlap 200 chars)
        chunk_size = 2000
        overlap = 200
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
            raise HTTPException(status_code=400, detail="No chunks generated")
        
        # Generate embeddings for all chunks
        model = get_sentence_transformer()
        chunk_embeddings = model.encode(chunks)
        
        # Average the embeddings
        avg_embedding = np.mean(chunk_embeddings, axis=0)
        
        # Re-normalize
        norm = np.linalg.norm(avg_embedding)
        if norm > 0:
            avg_embedding = avg_embedding / norm
            
        skills = extract_skills(text)
        return {"embedding": avg_embedding.tolist(), "skills": skills}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Resume Endpoints ─────────────────────────────────────────────────────────
@app.post("/api/resume/upload")
@app.post("/resume/upload")
async def upload_resume(
    background_tasks: BackgroundTasks,
    email: str = Form(...), 
    file: UploadFile = File(...)
):
    if not email or not file:
        raise HTTPException(status_code=400, detail="email and file are required")
    
    try:
        import time
        # Read PDF bytes in-memory
        file_bytes = await file.read()
        reader = PdfReader(io.BytesIO(file_bytes))
        resume_text = ""
        for page in reader.pages:
            resume_text += page.extract_text() or ""
        resume_text = resume_text.strip()
        
        if not resume_text:
            raise HTTPException(status_code=400, detail="Could not extract text from PDF resume")
        
        # Generate embedding (overlap chunking)
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
        start_embed_time = time.time()
        if chunks:
            model = get_sentence_transformer()
            chunk_embeddings = model.encode(chunks)
            avg_embedding = np.mean(chunk_embeddings, axis=0)
            norm = np.linalg.norm(avg_embedding)
            if norm > 0:
                avg_embedding = avg_embedding / norm
            vector = avg_embedding.tolist()
            
        embed_duration_ms = int((time.time() - start_embed_time) * 1000)
        
        # Extract display skills
        resume_skills = extract_skills(resume_text)
        
        # Log resume events
        log_nlp_event(
            message="Resume embedding",
            event="resume_upload",
            extra={
                "email": email,
                "huggingFaceStatus": "success",
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

        # Write directly to SQLite users table
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        
        # Get active companies
        cursor.execute("SELECT name FROM companies WHERE status = 'active'")
        all_companies = [row[0] for row in cursor.fetchall()]
        
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
            email, resume_text, np.array(vector, dtype=np.float32).tobytes() if vector else None, json.dumps(resume_skills),
            json.dumps(all_companies), now_iso, now_iso
        ))
        
        # Clear matched_jobs within retention window for fresh re-match
        cursor.execute("DELETE FROM matched_jobs WHERE email = ? AND expires_at > datetime('now')", (email,))
        
        conn.commit()
        conn.close()
        
        # Trigger immediate matching in background
        background_tasks.add_task(match_for_user, email)
        
        return {
            "success": True,
            "email": email,
            "skillsExtracted": resume_skills,
            "skillsCount": len(resume_skills),
            "vectorDimensions": len(vector) if vector else 0,
            "message": "Resume processed. Matching is running in background — check your email."
        }
    except Exception as e:
        log_scrape_error(f"Error in upload_resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── User Endpoints ──────────────────────────────────────────────────────────
@app.post("/api/users")
async def create_or_update_user(payload: UserProfilePayload):
    email = payload.email
    if not email:
        raise HTTPException(status_code=400, detail="email is required")

    selected_companies = payload.selectedCompanies if payload.selectedCompanies is not None else []
    match_threshold = payload.matchThreshold if payload.matchThreshold is not None else 65

    db_path = get_db_path()
    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()
    now_iso = datetime.utcnow().isoformat() + 'Z'

    cursor.execute("""
        INSERT INTO users (email, selected_companies, match_threshold, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
          selected_companies = excluded.selected_companies,
          match_threshold    = excluded.match_threshold
    """, (email, json.dumps(selected_companies), match_threshold, now_iso))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "email": email,
        "selectedCompanies": selected_companies,
        "matchThreshold": match_threshold
    }

@app.get("/api/users")
async def get_user_profile(email: str = Query(..., description="email query param required")):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_dict = dict(user)
    return {
        "email": user_dict["email"],
        "selectedCompanies": json.loads(user_dict["selected_companies"] or "[]"),
        "resumeSkills": json.loads(user_dict["resume_skills"] or "[]"),
        "matchThreshold": user_dict["match_threshold"],
        "resumeUploadedAt": user_dict["resume_uploaded_at"],
        "lastNotifiedAt": user_dict["last_notified_at"],
        "hasResume": bool(user_dict["resume_vector"]),
    }

@app.put("/api/users/{email}/companies")
async def update_user_companies(email: str, payload: UserCompaniesPayload):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE users SET selected_companies = ? WHERE email = ?",
        (json.dumps(payload.selectedCompanies), email)
    )
    conn.commit()
    conn.close()

    return {
        "success": True,
        "email": email,
        "selectedCompanies": payload.selectedCompanies
    }

# ── Companies and Jobs Endpoints ────────────────────────────────────────────
@app.get("/api/companies")
async def get_companies():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT name, ats, tier, career_url, status, last_scraped_at, degraded_reason FROM companies ORDER BY name")
    companies = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return companies

@app.get("/api/jobs")
async def get_jobs(company: str = Query(..., description="company query param required")):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT job_id, job_title, location, department, posted_date, employment_type,
               apply_url, skills_display, embedding_status, scraped_at
        FROM jobs
        WHERE company_name = ? AND expires_at > datetime('now')
        ORDER BY scraped_at DESC
    """, (company,))
    jobs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {
        "company": company,
        "count": len(jobs),
        "jobs": jobs
    }

@app.get("/api/matches")
async def get_matches(email: str = Query(..., description="email query param required")):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT company_name, job_id, job_title, location, match_score,
               apply_url, skills_display, notified, notified_at, expires_at
        FROM matched_jobs
        WHERE email = ? AND expires_at > datetime('now')
        ORDER BY match_score DESC
    """, (email,))
    matches = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {
        "email": email,
        "count": len(matches),
        "matches": matches
    }

# ── Admin Endpoints ──────────────────────────────────────────────────────────
@app.get("/api/admin/status")
@app.get("/status")
async def get_status():
    global is_scraping_in_progress
    db_path = get_db_path()
    companies = []
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT name, status, last_scraped_at, degraded_reason FROM companies")
            companies = [dict(row) for row in cursor.fetchall()]
            conn.close()
        except Exception as e:
            companies = [{"error": str(e)}]
            
    return {
        "node_status": {
            "db_path": "backend/data/jobs.db",
            "cleanup_schedule": "2 AM daily",
        },
        "python_status": {
            "scraping_in_progress": is_scraping_in_progress,
            "companies": companies
        }
    }

@app.post("/api/admin/scrape")
@app.post("/scrape")
async def trigger_scrape(background_tasks: BackgroundTasks):
    global is_scraping_in_progress
    if is_scraping_in_progress:
        return {"success": False, "message": "Scrape already in progress"}
    
    is_scraping_in_progress = True
    def run_sync():
        global is_scraping_in_progress
        try:
            run_acquisition_cycle()
            from backend.nlp_service.enricher import run_enrichment_cycle
            run_enrichment_cycle()
            # Run match cycle immediately after scraping and enrichment completes
            run_match_cycle()
        except Exception as e:
            print(f"Error in manual scrape: {e}")
        finally:
            is_scraping_in_progress = False
            
    background_tasks.add_task(run_sync)
    return {"success": True, "message": "Scrape cycle triggered"}

@app.post("/api/admin/match-all")
async def trigger_match_all(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_match_cycle)
    return {"success": True, "message": "Match cycle triggered for all users"}

@app.post("/api/admin/match")
async def trigger_match(background_tasks: BackgroundTasks, email: str = Query(..., description="email query param required")):
    background_tasks.add_task(match_for_user, email)
    return {"success": True, "message": f"Match cycle triggered for {email} — check your inbox"}

@app.post("/api/admin/reset")
async def reset_user_history(email: str = Query(..., description="email query param required")):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()
    
    cursor.execute("UPDATE users SET last_notified_at = NULL WHERE email = ?", (email,))
    cursor.execute("DELETE FROM matched_jobs WHERE email = ?", (email,))
    
    conn.commit()
    conn.close()
    return {"success": True, "message": f"Match history and last_notified_at reset for {email}."}

@app.post("/api/admin/activate")
async def activate_company(company: str = Query(..., description="company query param required")):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE companies SET status = 'active', degraded_reason = NULL WHERE name = ?",
        (company,)
    )
    changes = conn.total_changes
    conn.commit()
    conn.close()

    if changes == 0:
        raise HTTPException(status_code=404, detail="Company not found or already active")

    return {"success": True, "company": company, "status": "active"}

@app.post("/api/admin/cleanup")
@app.post("/cleanup")
async def trigger_cleanup(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_cleanup)
    return {"success": True, "message": "Cleanup complete"}

# Background scheduler loop task
scheduler_task = None
cleanup_task = None
is_scraping_in_progress = False

async def scraper_loop():
    global is_scraping_in_progress
    settings = load_settings()
    interval_hours = settings.get('scrapeIntervalHours', 6)
    interval_seconds = interval_hours * 3600
    
    # Run immediately on startup (give 5 seconds for initialization)
    await asyncio.sleep(5)
    while True:
        if not is_scraping_in_progress:
            is_scraping_in_progress = True
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, run_acquisition_cycle)
                from backend.nlp_service.enricher import run_enrichment_cycle
                await loop.run_in_executor(None, run_enrichment_cycle)
                await loop.run_in_executor(None, run_match_cycle)
            except Exception as e:
                print(f"Error in background scraper loop: {e}")
            finally:
                is_scraping_in_progress = False
        
        await asyncio.sleep(interval_seconds)

async def cleanup_loop():
    while True:
        now = datetime.now()
        # Trigger cleanup daily at 2 AM
        if now.hour == 2 and now.minute == 0:
            print("Daily 2 AM cleanup triggered...")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, run_cleanup)
            await asyncio.sleep(65)
        else:
            await asyncio.sleep(30)

@app.on_event("startup")
async def startup_event():
    global scheduler_task, cleanup_task
    # Automatically initialize and seed SQLite database
    init_db()
    scheduler_task = asyncio.create_task(scraper_loop())
    cleanup_task = asyncio.create_task(cleanup_loop())

@app.on_event("shutdown")
async def shutdown_event():
    if scheduler_task:
        scheduler_task.cancel()
    if cleanup_task:
        cleanup_task.cancel()

if __name__ == "__main__":
    import uvicorn
    # Load port from .env or default to 3000
    port_str = os.environ.get("PORT", "3000")
    try:
        port = int(port_str)
    except ValueError:
        port = 3000
    uvicorn.run(app, host="127.0.0.1", port=port)
