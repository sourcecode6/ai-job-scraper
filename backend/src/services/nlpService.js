const fs = require('fs');
const path = require('path');

// Load skills vocabulary once at startup
const vocabPath = path.join(__dirname, '../../data/skills_vocab.json');
let vocab = { skills: [], aliases: {} };

try {
  vocab = JSON.parse(fs.readFileSync(vocabPath, 'utf8'));
} catch {
  console.warn('skills_vocab.json not found — skill display tags will be empty');
}

// Build a flat skills set and alias map for fast lookup
const allSkills = vocab.skills || [];
const aliases = vocab.aliases || {};

// Lowercase lookup map: "kubernetes" → "Kubernetes"
const skillLowerMap = new Map(allSkills.map((s) => [s.toLowerCase(), s]));
const aliasLowerMap = new Map(
  Object.entries(aliases).map(([alias, canonical]) => [alias.toLowerCase(), canonical])
);

/**
 * Extracts recognized tech skills from a text blob.
 * Used for display tags in email digests — NOT for matching (embeddings handle that).
 *
 * @param {string} text - Raw text (job description, resume text, etc.)
 * @returns {string[]} Array of canonical skill names found in the text
 */
function extractSkills(text) {
  if (!text) return [];

  const lower = text.toLowerCase();
  const found = new Set();

  // Helper to build a regex that respects boundaries for both word and non-word characters
  const buildRegex = (term) => {
    const escaped = escapeRegex(term);
    const start = /^[a-zA-Z0-9_]/.test(term) ? '(?<![a-zA-Z0-9_])' : '';
    const end = /[a-zA-Z0-9_]$/.test(term) ? '(?![a-zA-Z0-9_])' : '';
    return new RegExp(start + escaped + end);
  };

  // Check direct skill matches
  for (const [lowerSkill, canonical] of skillLowerMap) {
    const regex = buildRegex(lowerSkill);
    if (regex.test(lower)) {
      found.add(canonical);
    }
  }

  // Check aliases (e.g. "k8s" → "Kubernetes")
  for (const [alias, canonical] of aliasLowerMap) {
    const regex = buildRegex(alias);
    if (regex.test(lower)) {
      found.add(canonical);
    }
  }

  return Array.from(found);
}

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

module.exports = { extractSkills };
