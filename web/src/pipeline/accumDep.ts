/**
 * Accumulated depreciation pairing module — port of the accumulated
 * depreciation logic from mapping_logic_v15.py.
 *
 * Extracts the base asset name from accumulated depreciation account names
 * and pairs them with the corresponding asset code + ".ACC".
 */

import { normalise } from './normalise';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ACCUM_PATTERNS: RegExp[] = [
  /less accumulated (?:depreciation|amortisation|amortization) (?:on |of )?(.+)/i,
  /accumulated (?:depreciation|amortisation|amortization) (?:on |of )?(.+)/i,
  /less accum\.? dep\.? (?:on |of |- ?)?(.+)/i,
  /accum\.? dep\.? (?:on |of |- ?)?(.+)/i,
];

/** Sources that indicate a head-only fallback (no specific rule matched). */
const FALLBACK_SOURCES = new Set([
  'FallbackParent',
  'FallbackHead',
  'TypeOnly',
]);

// ---------------------------------------------------------------------------
// extractAccumBaseKey
// ---------------------------------------------------------------------------

/**
 * Extract the base asset name from an accumulated depreciation account name.
 *
 * Examples:
 * - "Less Accumulated Depreciation on Office Equipment" -> "office equipment"
 * - "Accum Dep - Motor Vehicles" -> "motor vehicles"
 * - "Less Accum Dep on Computer Equipment" -> "computer equipment"
 * - Non-depreciation names -> "" (empty)
 *
 * The extracted base is normalised via `normalise()`.
 */
export function extractAccumBaseKey(nameRaw: string): string {
  if (!nameRaw) return '';

  const name = nameRaw.trim();
  // Normalise for pattern matching — normalise() lowercases & strips punctuation
  // but we need to match against patterns that expect "accum. dep." with dots,
  // so we try patterns against both the raw lowercased and normalised forms.

  for (const pattern of ACCUM_PATTERNS) {
    const m = name.match(pattern);
    if (m && m[1]) {
      return normalise(m[1].trim());
    }
  }

  return '';
}

// ---------------------------------------------------------------------------
// pairAccumDep
// ---------------------------------------------------------------------------

/**
 * Mutate accounts in place: for fallback accounts whose name extracts to a
 * known base asset key, set predictedCode to code + ".ACC".
 *
 * @param accounts - Array of account objects to mutate
 * @param nameToCode - Map from normalised base asset name to reporting code
 */
export function pairAccumDep(
  accounts: Array<{ name: string; predictedCode: string; source: string }>,
  nameToCode: Map<string, string>,
): void {
  for (const acct of accounts) {
    // Only refine fallback accounts
    if (!FALLBACK_SOURCES.has(acct.source)) continue;

    const baseKey = extractAccumBaseKey(acct.name);
    if (!baseKey) continue;

    const code = nameToCode.get(baseKey);
    if (code) {
      acct.predictedCode = code + '.ACC';
      acct.source = 'AccumDepPairing';
    }
  }
}
