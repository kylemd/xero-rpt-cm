/**
 * Suggested values for Rule type fields.
 *
 * Sourced from actual usage across `web/data/rules.json` so suggestions match
 * what the rule engine consumes today. Free-text entries are still allowed —
 * these are hints, not an exhaustive whitelist.
 */

export const RAW_TYPE_OPTIONS: readonly string[] = [
  'asset',
  'bank',
  'cost of sales',
  'current asset',
  'current liability',
  'direct costs',
  'equity',
  'expense',
  'fixed asset',
  'liability',
  'non-current asset',
  'non-current liability',
  'other income',
  'overhead',
  'overheads',
  'purchases',
  'retained earnings',
  'revenue',
  'sales',
];

export const CANON_TYPE_OPTIONS: readonly string[] = [
  'asset',
  'current asset',
  'current liability',
  'depreciation',
  'direct costs',
  'equity',
  'expense',
  'fixed asset',
  'historical',
  'income',
  'inventory',
  'liability',
  'non-current asset',
  'non-current liability',
  'other income',
  'revenue',
  'sales',
];
