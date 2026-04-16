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
import { REPORTING_HEADS_SET } from '../pipeline/heads';

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

function cellNum(v: unknown): number {
  if (v === null || v === undefined || v === '') return 0;
  if (typeof v === 'number') return v;
  const s = String(v).trim().replace(/,/g, '');
  const isNeg = s.startsWith('(') && s.endsWith(')');
  const n = parseFloat(isNeg ? s.slice(1, -1) : s);
  if (isNaN(n)) return 0;
  return isNeg ? -n : n;
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

// ---------------------------------------------------------------------------
// Chart of Accounts - Reporting Codes
// ---------------------------------------------------------------------------

export interface ReportingCodeRow {
  code: string;
  name: string;
  reportCode: string;
  currentBalance: number;
}

// Matches "NNN - Name" where NNN is any non-space token (alphanumeric).
const CODE_NAME_RE = /^(\S+)\s*-\s*(.+)$/;

function isGroupHeader(row: Row): string | null {
  const a = cellStr(row[0]);
  const b = cellStr(row[1]);
  if (a) return null; // group headers have col A empty
  if (!b) return null;
  if (b.toLowerCase().startsWith('total ')) return null;
  if (b.toLowerCase() === 'account') return null;
  const head = b.split('.')[0];
  if (!REPORTING_HEADS_SET.has(head)) return null;
  return b;
}

function isAccountRow(row: Row): boolean {
  const a = cellStr(row[0]);
  const b = cellStr(row[1]);
  if (a) return false;
  if (!b) return false;
  if (b.toLowerCase().startsWith('total ')) return false;
  if (b.toLowerCase() === 'account') return false;
  const head = b.split('.')[0];
  if (REPORTING_HEADS_SET.has(head)) return false; // that's a group header
  return true;
}

export function parseReportingCodesSheet(
  sheet: XLSX.WorkSheet,
): ReportingCodeRow[] {
  const rows = sheetRows(sheet);
  const out: ReportingCodeRow[] = [];
  let currentReportCode = '';

  for (const row of rows) {
    const topTotal = cellStr(row[0]);
    if (topTotal.toLowerCase().startsWith('total chart of accounts')) {
      break; // end of data
    }
    const header = isGroupHeader(row);
    if (header) {
      currentReportCode = header;
      continue;
    }
    if (!isAccountRow(row)) continue;
    if (!currentReportCode) continue;

    const text = cellStr(row[1]);
    const m = text.match(CODE_NAME_RE);
    let code = '';
    let name = text;
    if (m) {
      code = m[1].trim();
      name = m[2].trim();
    }
    const currentBalance = cellNum(row[2]);
    out.push({ code, name, reportCode: currentReportCode, currentBalance });
  }
  return out;
}
