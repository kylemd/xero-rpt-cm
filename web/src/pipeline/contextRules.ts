/**
 * Context rules module — port of context_rules.py.
 *
 * Cross-account context inference: detects anchor accounts (e.g., active
 * Goodwill) and infers codes for nearby ambiguous accounts. Also provides
 * section inference that promotes head-only codes based on neighbour consensus.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ContextAccount {
  code: string;
  name: string;
  predicted: string;
  source: string;
}

export interface Change {
  index: number;
  code: string;
  name: string;
  inferred_code: string;
  reason: string;
  anchor_code?: string;
}

interface ContextAnchorConfig {
  anchor_name: string;
  anchor_keywords: string[];
  nearby_keywords: string[];
  nearby_fallback_heads: Set<string>;
  inferred_code: string;
  proximity: number;
}

interface DetectedAnchor {
  anchor_name: string;
  anchor_index: number;
  anchor_code: string;
  anchor_code_num: number;
  anchor_config: ContextAnchorConfig;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const HEAD_ONLY_CODES = new Set(['ASS', 'EXP', 'REV', 'LIA', 'EQU']);

export const SECTION_INFERENCE_EXCLUSIONS = [
  'historical adjustment', 'rounding',
  'suspense', 'clearing', 'unallocated',
  'general expense', 'general expenses',
  'reconciliation', 'discrepancy',
  'revaluation', 'conversion',
  'private use',
];

const CONTEXT_ANCHORS: ContextAnchorConfig[] = [
  {
    anchor_name: 'goodwill_intangibles',
    anchor_keywords: ['goodwill'],
    nearby_keywords: ['legal', 'capital', 'acquisition', 'formation', 'incorporation', 'stamp duty'],
    nearby_fallback_heads: new Set(['ASS']),
    inferred_code: 'ASS.NCA.INT',
    proximity: 50,
  },
  {
    anchor_name: 'land_buildings',
    anchor_keywords: ['land', 'building', 'property'],
    nearby_keywords: ['improvement', 'fitout', 'fit out', 'renovation', 'refurbishment', 'leasehold'],
    nearby_fallback_heads: new Set(['ASS']),
    inferred_code: 'ASS.NCA.FIX.PLA',
    proximity: 30,
  },
];

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function parseCodeNumber(codeStr: string): number {
  const cleaned = codeStr.replace(/,/g, '').trim();
  const num = parseFloat(cleaned);
  return isNaN(num) ? NaN : num;
}

function detectAnchors(
  accounts: ContextAccount[],
  balLookup: Record<string, number>,
): DetectedAnchor[] {
  const detected: DetectedAnchor[] = [];

  for (let i = 0; i < accounts.length; i++) {
    const acct = accounts[i];
    const nameLower = acct.name.toLowerCase();
    const balance = balLookup[acct.code] ?? 0;

    if (!balance || balance === 0) continue;

    for (const anchor of CONTEXT_ANCHORS) {
      if (anchor.anchor_keywords.some(kw => nameLower.includes(kw))) {
        detected.push({
          anchor_name: anchor.anchor_name,
          anchor_index: i,
          anchor_code: acct.code,
          anchor_code_num: parseCodeNumber(acct.code),
          anchor_config: anchor,
        });
      }
    }
  }

  return detected;
}

// ---------------------------------------------------------------------------
// inferFromContext
// ---------------------------------------------------------------------------

/**
 * Run cross-account context inference on head-only fallback accounts.
 *
 * When an anchor account (e.g. Goodwill) has an active balance, nearby
 * accounts matching inference keywords get refined to a more specific code.
 */
export function inferFromContext(
  accounts: ContextAccount[],
  balLookup: Record<string, number>,
  overriddenIndices: Set<number>,
): Change[] {
  const anchors = detectAnchors(accounts, balLookup);
  if (anchors.length === 0) return [];

  const results: Change[] = [];

  for (let i = 0; i < accounts.length; i++) {
    if (overriddenIndices.has(i)) continue;

    const acct = accounts[i];
    const predicted = acct.predicted ?? '';

    // Only refine head-only fallback codes
    if (!HEAD_ONLY_CODES.has(predicted)) continue;

    const nameLower = acct.name.toLowerCase();
    const acctCodeNum = parseCodeNumber(acct.code);

    for (const anchor of anchors) {
      const config = anchor.anchor_config;

      // Check if this account's fallback head matches the anchor's target
      if (!config.nearby_fallback_heads.has(predicted)) continue;

      // NaN-safe proximity check
      const anchorNum = anchor.anchor_code_num;
      if (isNaN(acctCodeNum) || isNaN(anchorNum)) continue;
      if (Math.abs(acctCodeNum - anchorNum) > config.proximity) continue;

      // Check if name matches any inference keywords
      if (config.nearby_keywords.some(kw => nameLower.includes(kw))) {
        results.push({
          index: i,
          code: acct.code,
          name: acct.name,
          inferred_code: config.inferred_code,
          reason: `CrossAccountContext:${anchor.anchor_name}`,
          anchor_code: anchor.anchor_code,
        });
        break; // One inference per account
      }
    }
  }

  return results;
}

// ---------------------------------------------------------------------------
// inferSection
// ---------------------------------------------------------------------------

/**
 * Infer balance sheet section for head-only accounts from neighbours.
 *
 * Looks at nearby accounts (by index position) and if a supermajority share
 * the same 2-level code prefix (e.g. ASS.CUR), refines the head-only account
 * to match that section.
 *
 * Balance weighting: active accounts (balance > 0) get weight 1.0, inactive
 * accounts get weight 0.3.
 */
export function inferSection(
  accounts: ContextAccount[],
  balLookup: Record<string, number>,
  overriddenIndices: Set<number>,
  window = 5,
  consensusThreshold = 0.6,
): Change[] {
  const results: Change[] = [];

  for (let i = 0; i < accounts.length; i++) {
    if (overriddenIndices.has(i)) continue;

    const acct = accounts[i];
    const predicted = acct.predicted ?? '';
    if (!HEAD_ONLY_CODES.has(predicted)) continue;

    // Skip clearing/generic accounts that should stay at head level
    const nameLower = acct.name.toLowerCase();
    if (SECTION_INFERENCE_EXCLUSIONS.some(excl => nameLower.includes(excl))) continue;

    // Gather neighbours' code prefixes (2-level: ASS.NCA, LIA.CUR, etc.)
    const neighbourPrefixes: Array<[string, number]> = [];
    const lo = Math.max(0, i - window);
    const hi = Math.min(accounts.length, i + window + 1);

    for (let j = lo; j < hi; j++) {
      if (j === i) continue;
      const nbCode = accounts[j].predicted ?? '';
      if (!nbCode || HEAD_ONLY_CODES.has(nbCode)) continue;

      const parts = nbCode.split('.');
      if (parts.length >= 2 && parts[0] === predicted) {
        // Same head -- record the 2-level prefix
        const prefix = parts.slice(0, 2).join('.');
        // Weight by active balance
        const balance = Math.abs(balLookup[accounts[j].code] ?? 0);
        const weight = balance > 0 ? 1.0 : 0.3;
        neighbourPrefixes.push([prefix, weight]);
      }
    }

    if (neighbourPrefixes.length === 0) continue;

    // Find consensus prefix
    const weightedCounts = new Map<string, number>();
    for (const [prefix, weight] of neighbourPrefixes) {
      weightedCounts.set(prefix, (weightedCounts.get(prefix) ?? 0) + weight);
    }

    let totalWeight = 0;
    for (const w of weightedCounts.values()) totalWeight += w;
    if (totalWeight === 0) continue;

    let bestPrefix = '';
    let bestWeight = 0;
    for (const [prefix, weight] of weightedCounts) {
      if (weight > bestWeight) {
        bestPrefix = prefix;
        bestWeight = weight;
      }
    }

    if (bestWeight / totalWeight >= consensusThreshold) {
      results.push({
        index: i,
        code: acct.code,
        name: acct.name,
        inferred_code: bestPrefix,
        reason: `SectionInference:${bestPrefix}`,
      });
    }
  }

  return results;
}
