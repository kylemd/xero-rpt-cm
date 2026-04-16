/**
 * Type prediction from reporting codes.
 *
 * Detects mismatches between the assigned reporting code and the current
 * Xero account type.  Used by the MappingTable to highlight rows where
 * the predicted code implies a different type.
 */

// ---------------------------------------------------------------------------
// predictTypeFromCode
// ---------------------------------------------------------------------------

/**
 * Given a reporting code and the account's current Xero type, predict the
 * type that the code implies.
 *
 * Checks `codeTypeMap` (built from the template chart) first, then falls
 * back to prefix-based heuristics.
 */
export function predictTypeFromCode(
  code: string,
  currentType: string,
  codeTypeMap: Record<string, string>,
): string {
  if (!code) return currentType;
  const c = code.toUpperCase();
  if (codeTypeMap[c]) return codeTypeMap[c];
  if (c.startsWith('ASS.CUR.INY')) return 'Inventory';
  if (c.startsWith('ASS.NCA.FIX')) return 'Fixed Asset';
  if (c.startsWith('ASS.CUR.REC.PRE')) return 'Prepayment';
  if (c.startsWith('ASS.NCA')) return 'Non-current Asset';
  if (c.startsWith('ASS')) return 'Current Asset';
  if (c.startsWith('EXP.DEP')) return 'Depreciation';
  if (c.startsWith('EXP.COS')) return 'Direct Costs';
  if (c.startsWith('EXP')) {
    if (currentType === 'Overhead') return 'Overhead';
    return 'Expense';
  }
  if (c.startsWith('LIA.NCL')) return 'Non-current Liability';
  if (c.startsWith('LIA')) return 'Current Liability';
  if (c.startsWith('REV.OTH')) return 'Other Income';
  if (c.startsWith('REV.INV')) return 'Other Income';
  if (c.startsWith('REV')) {
    if (currentType === 'Sales') return 'Sales';
    return 'Revenue';
  }
  if (c.startsWith('EQU')) return 'Equity';
  return currentType;
}

// ---------------------------------------------------------------------------
// buildCodeTypeMap
// ---------------------------------------------------------------------------

export function buildCodeTypeMap(
  templateEntries: Array<{ reportingCode: string; type: string }>,
): Record<string, string> {
  const map: Record<string, string> = {};
  for (const entry of templateEntries) {
    const key = entry.reportingCode.toUpperCase();
    if (!map[key]) map[key] = entry.type;
  }
  return map;
}

// ---------------------------------------------------------------------------
// HEAD_FROM_TYPE
// ---------------------------------------------------------------------------

export const HEAD_FROM_TYPE: Record<string, string> = {
  'Current Asset': 'ASS',
  'Fixed Asset': 'ASS',
  Inventory: 'ASS',
  'Non-current Asset': 'ASS',
  Prepayment: 'ASS',
  Equity: 'EQU',
  Depreciation: 'EXP',
  'Direct Costs': 'EXP',
  Expense: 'EXP',
  Overhead: 'EXP',
  'Current Liability': 'LIA',
  Liability: 'LIA',
  'Non-current Liability': 'LIA',
  'Other Income': 'REV',
  Revenue: 'REV',
  Sales: 'REV',
};

// ---------------------------------------------------------------------------
// ALLOWED_TYPES_BY_HEAD
// ---------------------------------------------------------------------------

export const ALLOWED_TYPES_BY_HEAD: Record<string, string[]> = {
  ASS: ['Current Asset', 'Fixed Asset', 'Inventory', 'Non-current Asset', 'Prepayment'],
  EQU: ['Equity'],
  EXP: ['Depreciation', 'Direct Costs', 'Expense', 'Overhead'],
  LIA: ['Current Liability', 'Liability', 'Non-current Liability'],
  REV: ['Other Income', 'Revenue', 'Sales'],
};

// ---------------------------------------------------------------------------
// System types (no mismatch dropdown)
// ---------------------------------------------------------------------------

export const SYSTEM_TYPES = new Set([
  'Bank',
  'Accounts Receivable',
  'Accounts Payable',
  'GST',
  'Historical',
  'Rounding',
  'Tracking',
  'Unpaid Expense Claims',
  'Retained Earnings',
  'Inventory',
  'Prepayment',
]);

// ---------------------------------------------------------------------------
// Prefix-level constraints: types that require a specific code sub-prefix
// ---------------------------------------------------------------------------

export const REQUIRED_PREFIX_BY_TYPE: Record<string, string> = {
  'Direct Costs': 'EXP.COS',
  Depreciation: 'EXP.DEP',
  'Fixed Asset': 'ASS.NCA.FIX',
  Inventory: 'ASS.CUR.INY',
  Prepayment: 'ASS.CUR.REC.PRE',
  Revenue: 'REV.TRA',
  Sales: 'REV.TRA',
  'Current Asset': 'ASS.CUR',
  'Non-current Asset': 'ASS.NCA',
  'Current Liability': 'LIA.CUR',
  'Non-current Liability': 'LIA.NCL',
};

// ---------------------------------------------------------------------------
// Type-mismatch check (head + prefix level)
// ---------------------------------------------------------------------------

/**
 * Return true when the account's Xero type is incompatible with the
 * reporting code at either the head level or the required sub-prefix.
 *
 * System types (Bank, GST, etc.) are never flagged — they carry their own
 * typing rules and are locked on export.
 */
export function hasTypeMismatch(type: string, code: string): boolean {
  if (!code) return false;

  const upper = code.toUpperCase();
  const requiredPrefix = REQUIRED_PREFIX_BY_TYPE[type];

  // Types with a required prefix (e.g., Inventory, Prepayment) are checked
  // even if they also appear in SYSTEM_TYPES — the prefix constraint wins.
  if (requiredPrefix) {
    return !upper.startsWith(requiredPrefix);
  }

  if (SYSTEM_TYPES.has(type)) return false;

  const typeHead = HEAD_FROM_TYPE[type];
  if (!typeHead) return false;

  const codeHead = upper.split('.')[0];
  return typeHead !== codeHead;
}
