/**
 * Text normalisation module — 1:1 port of Python normalisation functions
 * from mapping_logic_v15.py.
 *
 * Pure functions with no external dependencies.
 */

// ---------------------------------------------------------------------------
// Type equivalence map
// ---------------------------------------------------------------------------

const TYPE_EQ: Record<string, string> = {
  purchases: 'expense',
  'operating expense': 'expense',
  'operating expenses': 'expense',
  overhead: 'expense',
  overheads: 'expense',
};

// ---------------------------------------------------------------------------
// stripNoiseSuffixes
// ---------------------------------------------------------------------------

/**
 * Remove noisy suffixes from an account name:
 * - Takes last segment after colon (e.g. "Category: Equipment" -> "Equipment")
 * - Strips " - At Cost", " - Closing Balance", " at cost"
 */
export function stripNoiseSuffixes(name: string): string {
  if (!name) return '';
  let result = name.split(':').pop()!.trim();
  result = result.replace(/\s*-\s*(at cost|closing balance)$/i, '');
  result = result.replace(/\s+at cost$/i, '');
  return result.trim();
}

// ---------------------------------------------------------------------------
// normalise
// ---------------------------------------------------------------------------

/**
 * Normalise an account name for matching:
 * - Lowercase
 * - Replace & with "and"
 * - Canonicalise motor vehicle abbreviations (m/v, m-v, m v -> mv)
 * - Canonicalise R&M / R and M / R/M -> "repairs maintenance"
 * - Strip punctuation, collapse whitespace
 */
export function normalise(text: string): string {
  if (!text) return '';
  let s = text.toLowerCase();
  s = s.replace(/\s*&\s*/g, ' and ');
  // Canonicalize motor vehicle abbreviation variants
  s = s.replace(/\bm\s*\/\s*v\b/g, 'mv');
  s = s.replace(/\bm\s*-\s*v\b/g, 'mv');
  s = s.replace(/\bm\s+v\b/g, 'mv');
  // Canonicalize shorthand R&M -> "repairs maintenance"
  s = s.replace(/\br\s*(?:and|&|\/)\s*m\b/g, 'repairs maintenance');
  // Strip punctuation (keep word chars and whitespace)
  s = s.replace(/[^\w\s]/g, ' ');
  // Collapse whitespace and trim
  s = s.replace(/\s+/g, ' ').trim();
  return s;
}

// ---------------------------------------------------------------------------
// canonicalType
// ---------------------------------------------------------------------------

/**
 * Map a Xero account type to its canonical equivalent.
 * Returns the lowercased type if no mapping exists.
 */
export function canonicalType(t: string): string {
  if (!t) return '';
  const lower = t.toLowerCase().trim();
  return TYPE_EQ[lower] ?? lower;
}

// ---------------------------------------------------------------------------
// headFromType
// ---------------------------------------------------------------------------

const REVENUE_TYPES = new Set(['revenue', 'income', 'sales']);
const DIRECT_COST_TYPES = new Set(['direct costs', 'cost of sales', 'cost of goods sold']);
const ASSET_TYPES = new Set(['asset', 'bank', 'accounts receivable', 'inventory', 'prepayment']);
const LIABILITY_TYPES = new Set([
  'liability', 'accounts payable', 'credit card', 'term liability',
  'gst', 'historical', 'rounding', 'tracking',
]);
const EQUITY_TYPES = new Set(['equity', 'retained earnings']);

/**
 * Derive the reporting-code head prefix from a Xero account type.
 *
 * Applies canonicalType first, then maps to the correct head.
 * Unknown types default to 'EXP'.
 */
export function headFromType(t: string): string {
  const ct = canonicalType(t);
  if (ct === 'other income') return 'REV.OTH';
  if (REVENUE_TYPES.has(ct)) return 'REV.TRA';
  if (DIRECT_COST_TYPES.has(ct)) return 'EXP.COS';
  if (ct === 'expense') return 'EXP';
  if (ct === 'depreciation') return 'EXP.DEP';
  if (ct === 'current asset') return 'ASS.CUR';
  if (ct === 'fixed asset') return 'ASS.NCA.FIX';
  if (ct === 'non-current asset') return 'ASS.NCA';
  if (ct === 'current liability') return 'LIA.CUR';
  if (ct === 'non-current liability') return 'LIA.NCL';
  if (ASSET_TYPES.has(ct)) return 'ASS';
  if (LIABILITY_TYPES.has(ct)) return 'LIA';
  if (EQUITY_TYPES.has(ct)) return 'EQU';
  return 'EXP';
}

// ---------------------------------------------------------------------------
// headGroup
// ---------------------------------------------------------------------------

/**
 * Map the root of a reporting code to its broad group:
 * - REV, EXP -> PL (Profit & Loss)
 * - ASS, LIA -> BS (Balance Sheet)
 * - EQU      -> EQ (Equity)
 */
export function headGroup(head: string): string {
  const root = head ? head.split('.')[0] : '';
  if (root === 'REV' || root === 'EXP') return 'PL';
  if (root === 'ASS' || root === 'LIA') return 'BS';
  if (root === 'EQU') return 'EQ';
  return '';
}

// ---------------------------------------------------------------------------
// similarity  (port of difflib.SequenceMatcher.ratio())
// ---------------------------------------------------------------------------

/**
 * Compute similarity ratio between two strings using the same algorithm as
 * Python's difflib.SequenceMatcher.ratio().
 *
 * The algorithm iteratively finds the longest common substring, then
 * recursively matches the left and right remainders, and returns:
 *   2 * total_matched_chars / (len(a) + len(b))
 *
 * Returns 0 for empty inputs, 1 for identical strings.
 */
export function similarity(a: string, b: string): number {
  if (a.length + b.length === 0) return 0;
  if (a === b) return 1;

  const matches = countMatchingChars(a, 0, a.length, b, 0, b.length);
  return (2 * matches) / (a.length + b.length);
}

/**
 * Find the longest common substring between a[aLo..aHi) and b[bLo..bHi).
 * Returns { aIdx, bIdx, size } or null if no common substring found.
 *
 * This mirrors Python's SequenceMatcher.find_longest_match().
 */
function findLongestMatch(
  a: string, aLo: number, aHi: number,
  b: string, bLo: number, bHi: number,
): { aIdx: number; bIdx: number; size: number } | null {
  let bestA = aLo;
  let bestB = bLo;
  let bestSize = 0;

  // j2len[j] = length of longest common substring ending at a[i-1] and b[j-1]
  let j2len: Map<number, number> = new Map();

  for (let i = aLo; i < aHi; i++) {
    const newJ2len: Map<number, number> = new Map();
    for (let j = bLo; j < bHi; j++) {
      if (a[i] === b[j]) {
        const k = (j2len.get(j - 1) ?? 0) + 1;
        newJ2len.set(j, k);
        if (k > bestSize) {
          bestA = i - k + 1;
          bestB = j - k + 1;
          bestSize = k;
        }
      }
    }
    j2len = newJ2len;
  }

  return bestSize > 0 ? { aIdx: bestA, bIdx: bestB, size: bestSize } : null;
}

/**
 * Recursively count matching characters between a[aLo..aHi) and b[bLo..bHi)
 * by finding the longest common substring and then matching the remaining
 * left and right portions.
 */
function countMatchingChars(
  a: string, aLo: number, aHi: number,
  b: string, bLo: number, bHi: number,
): number {
  const match = findLongestMatch(a, aLo, aHi, b, bLo, bHi);
  if (!match) return 0;

  const { aIdx, bIdx, size } = match;
  let count = size;

  // Recursively match left portions
  if (aLo < aIdx && bLo < bIdx) {
    count += countMatchingChars(a, aLo, aIdx, b, bLo, bIdx);
  }
  // Recursively match right portions
  if (aIdx + size < aHi && bIdx + size < bHi) {
    count += countMatchingChars(a, aIdx + size, aHi, b, bIdx + size, bHi);
  }

  return count;
}
