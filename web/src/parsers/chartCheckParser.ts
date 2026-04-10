/**
 * Chart Check Report parser.
 *
 * Parses multi-sheet XLSX files (Chart Check Reports) exported from
 * practice management tools. Extracts:
 *   - GL Summary
 *   - Depreciation Schedule
 *   - Client Parameters
 *   - Beneficiary Accounts
 */

import type {
  ChartCheckData,
  GLEntry,
  DepAsset,
  EntityParams,
  BeneficiaryEntry,
} from '../types';
import * as XLSX from 'xlsx';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Parse an amount string, handling parentheses as negative values and
 * removing currency symbols / thousand separators.
 */
function parseAmount(value: unknown): number {
  if (value === null || value === undefined || value === '') return 0;
  if (typeof value === 'number') return value;
  let s = String(value).trim();
  // Check for parentheses (negative)
  const isNeg = s.startsWith('(') && s.endsWith(')');
  if (isNeg) s = s.slice(1, -1);
  // Strip currency and thousand separators
  s = s.replace(/[$,\s]/g, '');
  const n = parseFloat(s);
  if (isNaN(n)) return 0;
  return isNeg ? -n : n;
}

/**
 * Find a sheet by name (case-insensitive, partial match).
 */
function findSheet(
  wb: XLSX.WorkBook,
  ...patterns: string[]
): XLSX.WorkSheet | null {
  for (const pattern of patterns) {
    const lower = pattern.toLowerCase();
    const name = wb.SheetNames.find((n) => n.toLowerCase().includes(lower));
    if (name) return wb.Sheets[name];
  }
  return null;
}

/**
 * Convert a sheet to a 2D string array.
 */
function sheetToRows(sheet: XLSX.WorkSheet): string[][] {
  const json = XLSX.utils.sheet_to_json<string[]>(sheet, {
    header: 1,
    defval: '',
  });
  return json;
}

/**
 * Find the header row index — the first row containing a target string.
 */
function findHeaderRow(rows: string[][], target: string): number {
  const lower = target.toLowerCase();
  for (let i = 0; i < rows.length; i++) {
    if (rows[i].some((cell) => String(cell).toLowerCase().includes(lower))) {
      return i;
    }
  }
  return -1;
}

function colIndex(headers: string[], ...names: string[]): number {
  const lower = headers.map((h) => String(h).trim().toLowerCase());
  for (const name of names) {
    const idx = lower.findIndex((h) => h.includes(name.toLowerCase()));
    if (idx >= 0) return idx;
  }
  return -1;
}

// ---------------------------------------------------------------------------
// GL Summary
// ---------------------------------------------------------------------------

function parseGLSummary(wb: XLSX.WorkBook): GLEntry[] {
  const sheet = findSheet(wb, 'general ledger summary', 'gl summary');
  if (!sheet) return [];

  const rows = sheetToRows(sheet);
  const headerIdx = findHeaderRow(rows, 'account');
  if (headerIdx < 0) return [];

  const headers = rows[headerIdx].map((h) => String(h));
  const iCode = colIndex(headers, 'account code', 'code', 'account');
  const iName = colIndex(headers, 'account name', 'name');
  const iOpening = colIndex(headers, 'opening');
  const iDebit = colIndex(headers, 'debit');
  const iCredit = colIndex(headers, 'credit');
  const iNet = colIndex(headers, 'net movement', 'movement');
  const iClosing = colIndex(headers, 'closing');
  const iType = colIndex(headers, 'type', 'account type');

  const entries: GLEntry[] = [];
  for (let i = headerIdx + 1; i < rows.length; i++) {
    const row = rows[i];
    const code = String(row[iCode] ?? '').trim();
    if (!code || !/\d/.test(code)) continue; // skip non-data rows

    entries.push({
      accountCode: code,
      accountName: iName >= 0 ? String(row[iName] ?? '').trim() : '',
      openingBalance: iOpening >= 0 ? parseAmount(row[iOpening]) : 0,
      debit: iDebit >= 0 ? parseAmount(row[iDebit]) : 0,
      credit: iCredit >= 0 ? parseAmount(row[iCredit]) : 0,
      netMovement: iNet >= 0 ? parseAmount(row[iNet]) : 0,
      closingBalance: iClosing >= 0 ? parseAmount(row[iClosing]) : 0,
      accountType: iType >= 0 ? String(row[iType] ?? '').trim() : '',
    });
  }
  return entries;
}

// ---------------------------------------------------------------------------
// Depreciation Schedule
// ---------------------------------------------------------------------------

function parseDepSchedule(wb: XLSX.WorkBook): DepAsset[] {
  const sheet = findSheet(wb, 'depreciation');
  if (!sheet) return [];

  const rows = sheetToRows(sheet);
  const headerIdx = findHeaderRow(rows, 'cost account');
  if (headerIdx < 0) return [];

  const headers = rows[headerIdx].map((h) => String(h));
  const iCostAcct = colIndex(headers, 'cost account');
  const iName = colIndex(headers, 'asset name', 'name');
  const iNumber = colIndex(headers, 'asset number', 'number');
  const iAssetType = colIndex(headers, 'asset type', 'type');
  const iExpAcct = colIndex(headers, 'expense account', 'dep account');
  const iAccumAcct = colIndex(headers, 'accum dep account', 'accumulated');
  const iCost = colIndex(headers, 'cost');
  const iClosingAccumDep = colIndex(headers, 'closing accum', 'closing accumulated');
  const iClosingValue = colIndex(headers, 'closing value', 'closing book');

  const assets: DepAsset[] = [];
  for (let i = headerIdx + 1; i < rows.length; i++) {
    const row = rows[i];
    const costAcct = String(row[iCostAcct] ?? '').trim();
    if (!costAcct) continue;

    assets.push({
      costAccount: costAcct,
      name: iName >= 0 ? String(row[iName] ?? '').trim() : '',
      assetNumber: iNumber >= 0 ? String(row[iNumber] ?? '').trim() : '',
      assetType: iAssetType >= 0 ? String(row[iAssetType] ?? '').trim() : '',
      expenseAccount: iExpAcct >= 0 ? String(row[iExpAcct] ?? '').trim() : '',
      accumDepAccount: iAccumAcct >= 0 ? String(row[iAccumAcct] ?? '').trim() : '',
      cost: iCost >= 0 ? parseAmount(row[iCost]) : 0,
      closingAccumDep: iClosingAccumDep >= 0 ? parseAmount(row[iClosingAccumDep]) : 0,
      closingValue: iClosingValue >= 0 ? parseAmount(row[iClosingValue]) : 0,
    });
  }
  return assets;
}

// ---------------------------------------------------------------------------
// Client Parameters
// ---------------------------------------------------------------------------

function parseClientParams(wb: XLSX.WorkBook): EntityParams {
  const sheet = findSheet(wb, 'parameter', 'client file');
  const defaults: EntityParams = {
    displayName: '',
    legalName: '',
    abn: '',
    directors: [],
    trustees: [],
    signatories: [],
  };
  if (!sheet) return defaults;

  const rows = sheetToRows(sheet);
  const kvMap: Record<string, string> = {};
  for (const row of rows) {
    const key = String(row[0] ?? '').trim().toUpperCase();
    const val = String(row[1] ?? '').trim();
    if (key && val) kvMap[key] = val;
  }

  defaults.displayName = kvMap['DISPLAY_NAME'] ?? kvMap['DISPLAY NAME'] ?? '';
  defaults.legalName = kvMap['LEGAL_NAME'] ?? kvMap['LEGAL NAME'] ?? '';
  defaults.abn = kvMap['ABN'] ?? '';

  // Parse JSON arrays
  const tryParseArray = (key: string): string[] => {
    const raw = kvMap[key];
    if (!raw) return [];
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      // Fallback: comma-separated
      return raw.split(',').map((s) => s.trim()).filter(Boolean);
    }
  };

  defaults.directors = tryParseArray('DIRECTOR_NAMES');
  defaults.trustees = tryParseArray('TRUSTEE_NAMES');
  defaults.signatories = tryParseArray('SIGNATORY_NAMES');

  return defaults;
}

// ---------------------------------------------------------------------------
// Beneficiary Accounts
// ---------------------------------------------------------------------------

function parseBeneficiaryAccounts(wb: XLSX.WorkBook): BeneficiaryEntry[] {
  const sheet = findSheet(wb, 'beneficiar');
  if (!sheet) return [];

  const rows = sheetToRows(sheet);
  if (rows.length < 2) return [];

  const headers = rows[0].map((h) => String(h));
  const iCode = colIndex(headers, 'account code', 'code');
  const iName = colIndex(headers, 'account name', 'name');
  const iBeneficiary = colIndex(headers, 'beneficiary');

  const entries: BeneficiaryEntry[] = [];
  for (let i = 1; i < rows.length; i++) {
    const row = rows[i];
    const code = String(row[iCode] ?? '').trim();
    if (!code) continue;

    entries.push({
      accountCode: code,
      accountName: iName >= 0 ? String(row[iName] ?? '').trim() : '',
      beneficiaryName: iBeneficiary >= 0 ? String(row[iBeneficiary] ?? '').trim() : '',
    });
  }
  return entries;
}

// ---------------------------------------------------------------------------
// Main parser
// ---------------------------------------------------------------------------

export async function parseChartCheckReport(file: File): Promise<ChartCheckData> {
  const buffer = await file.arrayBuffer();
  const wb = XLSX.read(buffer, { type: 'array' });

  return {
    glSummary: parseGLSummary(wb),
    depSchedule: parseDepSchedule(wb),
    clientParams: parseClientParams(wb),
    beneficiaryAccounts: parseBeneficiaryAccounts(wb),
  };
}
