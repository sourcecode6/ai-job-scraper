const { pipeline } = require('@xenova/transformers');
const axios = require('axios');
const { db } = require('../config/db');
const logger = require('../logger');

let extractorPromise = null;

async function getExtractor() {
  if (!extractorPromise) {
    logger.info('Initializing local SentenceTransformer model (Xenova/all-MiniLM-L6-v2)...');
    extractorPromise = pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2');
  }
  return extractorPromise;
}

/**
 * Generates a 384-dim sentence embedding using local Python FastAPI service, falling back to local JS.
 *
 * @param {string} text - Input text to embed
 * @returns {Promise<number[]|null>} 384-dimensional float array or null on failure
 */
async function getEmbedding(text) {
  if (!text) return null;

  try {
    // Attempt to call the local Python FastAPI NLP service
    const response = await axios.post('http://127.0.0.1:8000/embed', { text }, { timeout: 15000 });
    return response.data?.embedding || null;
  } catch (err) {
    logger.warn('Python local embedding service call failed, attempting fallback to local JS extractor', { message: err.message });
    try {
      const extractor = await getExtractor();

      // Chunk text (e.g. 2000 chars, overlap 200 chars) to represent the whole document
      const chunkSize = 2000;
      const overlap = 200;
      const chunks = [];

      for (let i = 0; i < text.length; i += chunkSize - overlap) {
        const chunk = text.slice(i, i + chunkSize).trim();
        if (chunk) {
          chunks.push(chunk);
        }
        if (i + chunkSize >= text.length) break;
      }

      if (chunks.length === 0) return null;

      const embeddings = [];
      for (const chunk of chunks) {
        const output = await extractor([chunk], { pooling: 'mean', normalize: true });
        const vector = output.tolist()[0];
        if (Array.isArray(vector) && typeof vector[0] === 'number') {
          embeddings.push(vector);
        }
      }

      if (embeddings.length === 0) return null;

      // Compute the average vector
      const numDimensions = embeddings[0].length;
      const averagedVector = new Array(numDimensions).fill(0);
      for (const vector of embeddings) {
        for (let d = 0; d < numDimensions; d++) {
          averagedVector[d] += vector[d];
        }
      }

      for (let d = 0; d < numDimensions; d++) {
        averagedVector[d] /= embeddings.length;
      }

      // Re-normalize the averaged vector so cosine similarity remains mathematically valid
      let magnitude = 0;
      for (let d = 0; d < numDimensions; d++) {
        magnitude += averagedVector[d] * averagedVector[d];
      }
      magnitude = Math.sqrt(magnitude);

      if (magnitude > 0) {
        for (let d = 0; d < numDimensions; d++) {
          averagedVector[d] /= magnitude;
        }
      }

      return averagedVector;
    } catch (fallbackErr) {
      logger.error('Local embedding extraction and fallback both failed', { message: fallbackErr.message });
      return null;
    }
  }
}

/**
 * Computes cosine similarity between two equal-length vectors.
 * Returns a value between 0 and 1 (multiply by 100 for percentage).
 */
function cosineSimilarity(vecA, vecB) {
  if (!vecA || !vecB || vecA.length !== vecB.length) return 0;
  let dot = 0, magA = 0, magB = 0;
  for (let i = 0; i < vecA.length; i++) {
    dot += vecA[i] * vecB[i];
    magA += vecA[i] * vecA[i];
    magB += vecB[i] * vecB[i];
  }
  if (magA === 0 || magB === 0) return 0;
  return dot / (Math.sqrt(magA) * Math.sqrt(magB));
}

/**
 * Gets or creates the embedding vector for a resume text.
 * Updates the user record in DB.
 *
 * @param {string} email
 * @param {string} resumeText
 * @returns {number[]|null}
 */
async function embedResume(email, resumeText) {
  const startTime = Date.now();
  const vector = await getEmbedding(resumeText);

  logger.info('Resume embedding', {
    logType: 'nlp',
    event: 'resume_upload',
    email,
    vectorDimensions: vector?.length || 0,
    huggingFaceStatus: vector ? 'success' : 'failed',
    durationMs: Date.now() - startTime,
  });

  return vector;
}

module.exports = { getEmbedding, cosineSimilarity, embedResume };
