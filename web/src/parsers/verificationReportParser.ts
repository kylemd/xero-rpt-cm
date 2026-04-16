/**
 * Chart of Accounts Verification Report parser.
 *
 * Parses the multi-sheet workbook Xero emits as the single consolidated
 * input, producing every shape the downstream pipeline consumes.
 *
 * Sheet names are truncated by Xero's export; they are stable, so we match
 * on the truncated prefix. The full name lives in cell A1 of each sheet
 * and is only used for error messages.
 */

import * as XLSX from 'xlsx';

// ---------------------------------------------------------------------------
// Required sheets
// ---------------------------------------------------------------------------

export const REQUIRED_SHEET_PREFIXES = [
  'Client File Parameters Report',
  'Chart of Accounts - Reportin',
  'Chart of Accounts - Type and',
  'Account Movements - Current',
  'Account Movements - Comparat',
  'Account Movements - Consider',
  'Depreciation Schedule',
  'Beneficiary Accounts',
] as const;

export function findRequiredSheet(
  wb: XLSX.WorkBook,
  prefix: string,
): XLSX.WorkSheet | undefined {
  const lower = prefix.toLowerCase();
  const name = wb.SheetNames.find((n) => n.toLowerCase().startsWith(lower));
  return name ? wb.Sheets[name] : undefined;
}

// ---------------------------------------------------------------------------
// Shared row helpers
// ---------------------------------------------------------------------------

type Row = (string | number | null | undefined)[];

function sheetRows(sheet: XLSX.WorkSheet): Row[] {
  return XLSX.utils.sheet_to_json<Row>(sheet, { header: 1, defval: null });
}

function cellStr(v: unknown): string {
  if (v === null || v === undefined) return '';
  return String(v).trim();
}

// ---------------------------------------------------------------------------
// Chart of Accounts - Type and Class
// ---------------------------------------------------------------------------

export interface TypeClassEntry {
  code: string;
  name: string;
  type: string;
  class: string;
}

export function parseTypeAndClassSheet(
  sheet: XLSX.WorkSheet,
): Map<string, TypeClassEntry> {
  const rows = sheetRows(sheet);
  const out = new Map<string, TypeClassEntry>();

  // Find the header row (first row starting with "Account Code")
  let headerIdx = -1;
  for (let i = 0; i < rows.length; i++) {
    if (cellStr(rows[i][0]).toLowerCase() === 'account code') {
      headerIdx = i;
      break;
    }
  }
  if (headerIdx < 0) return out;

  for (let i = headerIdx + 1; i < rows.length; i++) {
    const row = rows[i];
    const code = cellStr(row[0]);
    if (!code) continue;
    if (code.toLowerCase() === 'total') continue;
    const name = cellStr(row[1]);
    const type = cellStr(row[2]);
    const cls = cellStr(row[3]);
    out.set(code, { code, name, type, class: cls });
  }
  return out;
}
