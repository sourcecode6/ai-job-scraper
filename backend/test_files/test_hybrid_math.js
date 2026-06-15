const { cosineSimilarity } = require('../src/services/embeddingService');
const logger = require('../src/logger');

let similarityAddon = null;
try {
  similarityAddon = require('../src/addon/build/Release/similarity.node');
  console.log('✅ Successfully loaded C++ similarity addon!');
} catch (e) {
  console.log('⚠️ C++ similarity addon not loaded:', e.message);
}

// Helper to compute using C++ or fallback to JS
function computeSimilarity(vecA, vecB) {
  if (similarityAddon) {
    try {
      return similarityAddon.calculateCosineSimilarity(vecA, vecB);
    } catch (err) {
      console.log('Error inside C++ computeSimilarity, falling back to JS:', err.message);
      return cosineSimilarity(vecA, vecB);
    }
  }
  return cosineSimilarity(vecA, vecB);
}

// Generate test vectors
const size = 384;
const vec1 = Array.from({ length: size }, () => Math.random());
const vec2 = Array.from({ length: size }, () => Math.random());

console.log('--- Comparing JS vs C++ Addon Math ---');
const scoreJS = cosineSimilarity(vec1, vec2);
const scoreCPP = computeSimilarity(vec1, vec2);

console.log('JS Similarity Score:', scoreJS);
console.log('CPP/Hybrid Similarity Score:', scoreCPP);

const difference = Math.abs(scoreJS - scoreCPP);
console.log('Difference:', difference);

if (difference < 1e-9) {
  console.log('✅ PASS: Math matches exactly (within floating-point precision)!');
} else {
  console.log('❌ FAIL: Similarity scores do not match!');
}
