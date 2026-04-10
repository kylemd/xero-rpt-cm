/**
 * Fuzzy match module — port of the fuzzy matching logic from mapping_logic_v15.py.
 *
 * Matches a normalised account name against system mapping leaves within the
 * same reporting-code head group.
 */

import type { SystemMapping } from '../types';
import { normalise, similarity } from './normalise';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const FUZZY_THRESHOLD = 0.75;
export const DEPRECIATION_BOOST = 0.10;
export const DEPRECIATION_TOKENS = [
  'accumulated depreciation',
  'accumulated amortisation',
  'accumulated amortization',
  'depreciation',
  'amortisation',
  'amortization',
  'accum dep',
];

// ---------------------------------------------------------------------------
// fuzzyMatchInHead
// ---------------------------------------------------------------------------

/**
 * Find the best fuzzy match for a normalised account name among leaves that
 * share the same reporting-code root (e.g. both start with "EXP").
 *
 * Scoring rules:
 * - Similarity is computed between the normalised account name and normalised leaf name.
 * - If both names contain a depreciation token, a +0.10 boost is applied.
 * - A match requires score >= 0.75 AND at least one shared word.
 * - The best-scoring match is returned, or null if none qualifies.
 */
export function fuzzyMatchInHead(
  normalisedName: string,
  expectedHead: string,
  leaves: SystemMapping[],
): (SystemMapping & { score: number }) | null {
  const expectedRoot = expectedHead.split('.')[0];
  const nameWords = new Set(normalisedName.split(/\s+/).filter(Boolean));

  let bestMatch: (SystemMapping & { score: number }) | null = null;
  let bestScore = 0;

  for (const leaf of leaves) {
    // Check same root head
    const leafRoot = leaf.reportingCode.split('.')[0];
    if (leafRoot !== expectedRoot) continue;

    const leafNorm = normalise(leaf.name);
    let score = similarity(normalisedName, leafNorm);

    // Depreciation boost: if both sides contain a depreciation token
    const nameHasDep = DEPRECIATION_TOKENS.some(tok => normalisedName.includes(tok));
    const leafHasDep = DEPRECIATION_TOKENS.some(tok => leafNorm.includes(tok));
    if (nameHasDep && leafHasDep) {
      score += DEPRECIATION_BOOST;
    }

    // Must meet threshold
    if (score < FUZZY_THRESHOLD) continue;

    // Must share at least one word
    const leafWords = new Set(leafNorm.split(/\s+/).filter(Boolean));
    let hasSharedWord = false;
    for (const w of nameWords) {
      if (leafWords.has(w)) {
        hasSharedWord = true;
        break;
      }
    }
    if (!hasSharedWord) continue;

    if (score > bestScore) {
      bestScore = score;
      bestMatch = { ...leaf, score };
    }
  }

  return bestMatch;
}
