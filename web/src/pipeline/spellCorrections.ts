/**
 * Spell corrections module — port of abbreviation expansion from spell_corrections.py.
 *
 * Only the ABBREVIATIONS dict expansion is ported (pyspellchecker is skipped
 * for the browser environment). Expands domain-specific abbreviations like
 * "depr" -> "depreciation", "lsl" -> "long service leave", etc.
 */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const ABBREVIATIONS: Record<string, string> = {
  scg: 'sgc',
  lsl: 'long service leave',
  wip: 'work in progress',
  fy: 'financial year',
  ytd: 'year to date',
  mtd: 'month to date',
  bal: 'balance',
  acct: 'account',
  dept: 'department',
  govt: 'government',
  insur: 'insurance',
  maint: 'maintenance',
  mgmt: 'management',
  prepd: 'prepaid',
  prov: 'provision',
  depr: 'depreciation',
  amort: 'amortisation',
};

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Preserve the casing style of the original token on the expanded text.
 * - ALL CAPS -> uppercase
 * - First letter uppercase -> capitalize first letter of expansion
 * - Otherwise -> lowercase (as-is from ABBREVIATIONS)
 */
function preserveCase(original: string, expanded: string): string {
  if (original === original.toUpperCase() && original !== original.toLowerCase()) {
    return expanded.toUpperCase();
  }
  if (original[0] === original[0].toUpperCase() && original[0] !== original[0].toLowerCase()) {
    return expanded.charAt(0).toUpperCase() + expanded.slice(1);
  }
  return expanded;
}

/**
 * Correct tokens in a text segment via abbreviation expansion.
 */
function correctTokens(
  text: string,
): { corrected: string; corrections: Array<{ original: string; corrected: string; source: string }> } {
  const tokens = text.split(/\s+/).filter(Boolean);
  const corrections: Array<{ original: string; corrected: string; source: string }> = [];
  const resultTokens: string[] = [];

  for (const token of tokens) {
    const lower = token.toLowerCase();

    if (lower in ABBREVIATIONS) {
      const expanded = ABBREVIATIONS[lower];
      const cased = preserveCase(token, expanded);
      corrections.push({
        original: token,
        corrected: expanded,
        source: 'abbreviation',
      });
      resultTokens.push(cased);
    } else {
      resultTokens.push(token);
    }
  }

  return {
    corrected: resultTokens.join(' '),
    corrections,
  };
}

// ---------------------------------------------------------------------------
// correctAccountName
// ---------------------------------------------------------------------------

/**
 * Correct an account name via abbreviation expansion.
 *
 * Splits on the first ` - ` (space-dash-space) separator. Only the prefix
 * (the accounting description) is processed; the suffix (often a business
 * name, personal name, or location) passes through untouched.
 *
 * @returns Object with `corrected` (full corrected name) and `corrections`
 *          (list of individual corrections applied).
 */
export function correctAccountName(
  name: string,
): { corrected: string; corrections: Array<{ original: string; corrected: string; source: string }> } {
  if (!name) {
    return { corrected: '', corrections: [] };
  }

  const sep = ' - ';
  const idx = name.indexOf(sep);

  if (idx >= 0) {
    const prefix = name.slice(0, idx);
    const suffix = name.slice(idx); // includes " - ..."
    const result = correctTokens(prefix);
    result.corrected = result.corrected + suffix;
    return result;
  }

  return correctTokens(name);
}
