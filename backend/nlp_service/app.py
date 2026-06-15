from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import numpy as np

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
            
        return {"embedding": avg_embedding.tolist()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
