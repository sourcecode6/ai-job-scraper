from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import numpy as np
import asyncio
import os
import sqlite3
from scraper import run_acquisition_cycle, load_settings, get_db_path

app = FastAPI(title="AI Job Scraper - NLP Embeddings Service")

# Load model on startup
print("Loading sentence-transformers/all-MiniLM-L6-v2...")
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print("Model loaded successfully!")

class TextPayload(BaseModel):
    text: str

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
        chunk_embeddings = model.encode(chunks)
        
        # Average the embeddings
        avg_embedding = np.mean(chunk_embeddings, axis=0)
        
        # Re-normalize
        norm = np.linalg.norm(avg_embedding)
        if norm > 0:
            avg_embedding = avg_embedding / norm
            
        from scraper import extract_skills
        skills = extract_skills(text)
        return {"embedding": avg_embedding.tolist(), "skills": skills}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Background scheduler loop task
scheduler_task = None
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
                await loop.run_in_executor(None, run_acquisition_cycle, model)
            except Exception as e:
                print(f"Error in background scraper loop: {e}")
            finally:
                is_scraping_in_progress = False
        
        await asyncio.sleep(interval_seconds)

@app.post("/scrape")
async def trigger_scrape():
    global is_scraping_in_progress
    if is_scraping_in_progress:
        return {"success": False, "message": "Scrape already in progress"}
    
    is_scraping_in_progress = True
    def run_sync():
        global is_scraping_in_progress
        try:
            run_acquisition_cycle(model)
        except Exception as e:
            print(f"Error in manual scrape: {e}")
        finally:
            is_scraping_in_progress = False
            
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, run_sync)
    return {"success": True, "message": "Scrape cycle triggered"}

@app.get("/status")
async def get_status():
    global is_scraping_in_progress
    db_path = get_db_path()
    companies = []
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT name, status, last_scraped_at, degraded_reason FROM companies")
            companies = [dict(row) for row in cursor.fetchall()]
            conn.close()
        except Exception as e:
            companies = [{"error": str(e)}]
            
    return {
        "scraping_in_progress": is_scraping_in_progress,
        "companies": companies
    }

@app.on_event("startup")
async def startup_event():
    global scheduler_task
    scheduler_task = asyncio.create_task(scraper_loop())

@app.on_event("shutdown")
async def shutdown_event():
    if scheduler_task:
        scheduler_task.cancel()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
