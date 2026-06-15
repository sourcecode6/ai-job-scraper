const { getEmbedding } = require('../src/services/embeddingService');

async function testEmbeddings() {
  console.log('--- Testing Hybrid Embeddings (FastAPI vs Fallback) ---');
  
  const text = "Software Engineer with experience in Python, C++, and Node.js.";
  
  console.log('1. Fetching embedding...');
  const start = Date.now();
  const vector = await getEmbedding(text);
  const duration = Date.now() - start;
  
  if (vector && Array.isArray(vector) && vector.length === 384) {
    console.log(`✅ Success! Embedding length: ${vector.length} (took ${duration}ms)`);
    console.log('Sample vector elements:', vector.slice(0, 5));
  } else {
    console.error('❌ Failed to get valid 384-dim embedding!', vector);
  }
}

testEmbeddings();
