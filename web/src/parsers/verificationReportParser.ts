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
import type {
  VerificationReportData,
  Account,
  GLEntry,
  DepAsset,
  EntityParams,
  BeneficiaryEntry,
} from '../types';
import { canonicalType } from '../pipeline/normalise';

// ---------------------------------------------------------------------------
// Required sheets
// ---------------------------------------------------------------------------

export const REQUIRED_SHEET_PREFIXES = [
  'Client File Parameters Report',
  'Chart of Accounts - Reportin',
  'Chart of Accounts - Type and',
  'Account Movements - Current',
  'Account Movements - Prior Ye',
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

// ---------------------------------------------------------------------------
// Client File Parameters
// ---------------------------------------------------------------------------

function applyArrayValue(
  defaults: EntityParams,
  key: string,
  items: string[],
): void {
  const clean = items
    .map((s) => s.replace(/^["']|["']$/g, '').trim())
    .filter(Boolean);
  if (key === 'DIRECTOR_NAMES') defaults.directors.push(...clean);
  else if (key === 'TRUSTEE_NAMES') defaults.trustees.push(...clean);
}

function parseClientParams(sheet: XLSX.WorkSheet): EntityParams {
  const rows = sheetRows(sheet);
  const defaults: EntityParams = {
    displayName: '',
    legalName: '',
    abn: '',
    directors: [],
    trustees: [],
    signatories: [],
  };

  // Row 1 (second row) conventionally holds the entity name.
  if (rows[1]) defaults.displayName = cellStr(rows[1][0]);

  // Pseudo-JSON key lines look like:  [em-space]"KEY": value,
  // Array values may span cells:      "KEY": [first,   →  then cells  →  last]
  const KEY_RE = /"([A-Z_0-9]+)"\s*:\s*(.*?)\s*,?\s*$/;

  let openArrayKey: string | null = null;
  let openArrayAcc: string[] = [];

  const closeArray = () => {
    if (openArrayKey) {
      applyArrayValue(defaults, openArrayKey, openArrayAcc);
      openArrayKey = null;
      openArrayAcc = [];
    }
  };

  for (const row of rows) {
    const raw = cellStr(row[0]);
    if (!raw) continue;

    // Inside an open array — collect cells until we hit `]`.
    if (openArrayKey) {
      const endIdx = raw.indexOf(']');
      if (endIdx >= 0) {
        const piece = raw.slice(0, endIdx).trim();
        if (piece) openArrayAcc.push(piece);
        closeArray();
      } else {
        openArrayAcc.push(raw);
      }
      continue;
    }

    const m = raw.match(KEY_RE);
    if (!m) continue;
    const key = m[1];
    const rawValue = m[2].trim();

    // Array-valued key?
    if (rawValue.startsWith('[')) {
      const inner = rawValue.slice(1);
      const endIdx = inner.indexOf(']');
      if (endIdx >= 0) {
        // Single-line array
        const content = inner.slice(0, endIdx).trim();
        applyArrayValue(defaults, key, content ? [content] : []);
      } else {
        openArrayKey = key;
        openArrayAcc = inner.trim() ? [inner.trim()] : [];
      }
      continue;
    }

    // Scalar string value — strip surrounding quotes if any.
    const value = rawValue.replace(/^"|"$/g, '');
    switch (key) {
      case 'DISPLAY_NAME':
        if (value) defaults.displayName = value;
        break;
      case 'LEGAL_OR_TRADING_NAME':
      case 'LEGAL_NAME':
        defaults.legalName = value;
        break;
      case 'AUSTRALIAN_BUSINESS_NUMBER':
      case 'ABN':
        defaults.abn = value;
        break;
      default:
        break;
    }
  }

  // Safety: close any dangling open array at EOF.
  closeArray();

  return defaults;
}

// ---------------------------------------------------------------------------
// Account Movements (GL Summary)
// ---------------------------------------------------------------------------

function parseMovementSheet(sheet: XLSX.WorkSheet): GLEntry[] {
  const rows = sheetRows(sheet);
  let headerIdx = -1;
  for (let i = 0; i < rows.length; i++) {
    if (cellStr(rows[i][0]).toLowerCase() === 'account') {
      headerIdx = i;
      break;
    }
  }
  if (headerIdx < 0) return [];

  const out: GLEntry[] = [];
  for (let i = headerIdx + 1; i < rows.length; i++) {
    const row = rows[i];
    const name = cellStr(row[0]);
    if (!name) continue;
    if (name.toLowerCase() === 'total') continue;
    out.push({
      accountName: name,
      accountCode: cellStr(row[1]),
      openingBalance: cellNum(row[2]),
      debit: cellNum(row[3]),
      credit: cellNum(row[4]),
      netMovement: cellNum(row[5]),
      closingBalance: cellNum(row[6]),
      accountType: cellStr(row[7]),
    });
  }
  return out;
}

// ---------------------------------------------------------------------------
// Depreciation Schedule
// ---------------------------------------------------------------------------

function parseDepreciationSchedule(sheet: XLSX.WorkSheet): DepAsset[] {
  const rows = sheetRows(sheet);
  let headerIdx = -1;
  for (let i = 0; i < rows.length; i++) {
    if (cellStr(rows[i][0]).toLowerCase() === 'cost account') {
      headerIdx = i;
      break;
    }
  }
  if (headerIdx < 0) return [];

  const out: DepAsset[] = [];
  for (let i = headerIdx + 1; i < rows.length; i++) {
    const row = rows[i];
    const costAccount = cellStr(row[0]);
    if (!costAccount) continue;
    if (costAccount.toLowerCase() === 'total') continue;
    out.push({
      costAccount,
      name: cellStr(row[1]),
      assetNumber: cellStr(row[2]),
      assetType: cellStr(row[3]),
      expenseAccount: cellStr(row[5]),
      accumDepAccount: cellStr(row[6]),
      cost: cellNum(row[7]),
      closingAccumDep: cellNum(row[13]),
      closingValue: cellNum(row[14]),
    });
  }
  return out;
}

// ---------------------------------------------------------------------------
// Beneficiary Accounts
// ---------------------------------------------------------------------------

function parseBeneficiaryAccounts(sheet: XLSX.WorkSheet): BeneficiaryEntry[] {
  const rows = sheetRows(sheet);
  let headerIdx = -1;
  for (let i = 0; i < rows.length; i++) {
    if (cellStr(rows[i][0]).toLowerCase().startsWith('account code')) {
      headerIdx = i;
      break;
    }
  }
  if (headerIdx < 0) return [];

  const out: BeneficiaryEntry[] = [];
  for (let i = headerIdx + 1; i < rows.length; i++) {
    const row = rows[i];
    const code = cellStr(row[0]);
    if (!code) continue;
    out.push({
      accountCode: code,
      accountName: cellStr(row[1]),
      beneficiaryName: cellStr(row[2]),
    });
  }
  return out;
}

// ---------------------------------------------------------------------------
// Merge + archive-filter + activity-tag
// ---------------------------------------------------------------------------

function normaliseNameKey(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, ' ');
}

function mergeAccounts(
  reportingRows: ReportingCodeRow[],
  typeClassMap: Map<string, TypeClassEntry>,
  comparative: GLEntry[],
  considered: GLEntry[],
): Account[] {
  // Build name-based lookups for fallback matching.
  const typeClassByName = new Map<string, TypeClassEntry>();
  for (const entry of typeClassMap.values()) {
    typeClassByName.set(normaliseNameKey(entry.name), entry);
  }

  const comparativeCodes = new Set<string>();
  const comparativeNames = new Set<string>();
  for (const g of comparative) {
    if (g.accountCode) comparativeCodes.add(g.accountCode);
    if (g.accountName) comparativeNames.add(normaliseNameKey(g.accountName));
  }
  const consideredCodes = new Set<string>();
  const consideredNames = new Set<string>();
  for (const g of considered) {
    if (g.accountCode) consideredCodes.add(g.accountCode);
    if (g.accountName) consideredNames.add(normaliseNameKey(g.accountName));
  }

  const out: Account[] = [];
  for (const row of reportingRows) {
    // Match against Type and Class — by code, falling back to name.
    const match = row.code
      ? typeClassMap.get(row.code)
      : typeClassByName.get(normaliseNameKey(row.name));
    if (!match) continue; // system-level / excluded

    const nameKey = normaliseNameKey(row.name);
    const inConsidered =
      (row.code && consideredCodes.has(row.code)) || consideredNames.has(nameKey);
    if (!inConsidered) continue; // archive

    const inComparative =
      (row.code && comparativeCodes.has(row.code)) || comparativeNames.has(nameKey);

    out.push({
      code: row.code || match.code,
      name: row.name,
      type: match.type,
      canonType: canonicalType(match.type),
      reportCode: row.reportCode,
      class: match.class,
      activity: inComparative ? 'mandatory' : 'optional',
    });
  }
  return out;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function parseVerificationReportFromWorkbook(
  wb: XLSX.WorkBook,
): VerificationReportData {
  // Validate all required sheets exist.
  for (const prefix of REQUIRED_SHEET_PREFIXES) {
    if (!findRequiredSheet(wb, prefix)) {
      throw new Error(
        `Missing required sheet "${prefix}…". This file does not look like a Chart of Accounts Verification Report.`,
      );
    }
  }

  const paramsSheet = findRequiredSheet(wb, 'Client File Parameters Report')!;
  const reportingSheet = findRequiredSheet(wb, 'Chart of Accounts - Reportin')!;
  const typeAndClassSheet = findRequiredSheet(wb, 'Chart of Accounts - Type and')!;
  const currentSheet = findRequiredSheet(wb, 'Account Movements - Current')!;
  const comparativeSheet = findRequiredSheet(wb, 'Account Movements - Prior Ye')!;
  const consideredSheet = findRequiredSheet(wb, 'Account Movements - Consider')!;
  const depSheet = findRequiredSheet(wb, 'Depreciation Schedule')!;
  const benSheet = findRequiredSheet(wb, 'Beneficiary Accounts')!;

  const clientParams = parseClientParams(paramsSheet);
  const typeClassMap = parseTypeAndClassSheet(typeAndClassSheet);
  const reportingRows = parseReportingCodesSheet(reportingSheet);
  const glSummary = parseMovementSheet(currentSheet);
  const glSummaryComparative = parseMovementSheet(comparativeSheet);
  const glSummaryConsidered = parseMovementSheet(consideredSheet);
  const depSchedule = parseDepreciationSchedule(depSheet);
  const beneficiaryAccounts = parseBeneficiaryAccounts(benSheet);

  const accounts = mergeAccounts(
    reportingRows,
    typeClassMap,
    glSummaryComparative,
    glSummaryConsidered,
  );

  return {
    accounts,
    clientParams,
    glSummary,
    glSummaryComparative,
    glSummaryConsidered,
    depSchedule,
    beneficiaryAccounts,
  };
}

export async function parseVerificationReport(
  file: File,
): Promise<VerificationReportData> {
  const buffer = await file.arrayBuffer();
  const wb = XLSX.read(buffer, { type: 'array' });
  return parseVerificationReportFromWorkbook(wb);
}
