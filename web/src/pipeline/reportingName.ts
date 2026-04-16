/**
 * Derive a canonical Reporting Name from an account name for known patterns.
 *
 * Patterns:
 * - ATO Integrated Client Account (or "ATO ICA") -> "ATO ICA"
 * - ATO Income Tax Account (or "ATO ITA") -> "ATO ITA"
 * - Div7A / Division 7A / 7A + a 4-digit year -> "Div7A <YYYY>"
 *
 * Returns null when no pattern matches.
 */
export function deriveReportingName(accountName: string): string | null {
  if (!accountName) return null;
  const s = accountName.trim();
  if (!s) return null;
  const lower = s.toLowerCase();

  if (/\bato\s+(ica|integrated\s+client\s+account)\b/.test(lower)) {
    return 'ATO ICA';
  }
  if (/\bato\s+(ita|income\s+tax\s+account)\b/.test(lower)) {
    return 'ATO ITA';
  }

  const isDiv7A =
    /\bdiv\s*7a\b/.test(lower) ||
    /\bdivision\s*7a\b/.test(lower) ||
    /\b7a\b/.test(lower);
  if (isDiv7A) {
    const yearMatch = s.match(/(19|20)\d{2}/);
    if (yearMatch) return `Div7A ${yearMatch[0]}`;
  }

  return null;
}
