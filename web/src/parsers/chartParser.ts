/**
 * Chart of Accounts file parser.
 *
 * Handles CSV and XLSX files exported from Xero.
 * Detects column positions by header names and returns Account objects.
 */

import type { Account } from '../types';
import { canonicalType } from '../pipeline/normalise';
import * as XLSX from 'xlsx';

// ---------------------------------------------------------------------------
// CSV parsing (quote-aware)
// ---------------------------------------------------------------------------

function splitCSVRow(line: string): string[] {
  const fields: string[] = [];
  let i = 0;
  const len = line.length;

  while (i <= len) {
    if (i === len) {
      fields.push('');
      break;
    }
    if (line[i] === '"') {
      i++; // skip opening quote
      let field = '';
      while (i < len) {
        if (line[i] === '"') {
          if (i + 1 < len && line[i + 1] === '"') {
            field += '"';
            i += 2;
          } else {
            i++; // skip closing quote
            break;
          }
        } else {
          field += line[i];
          i++;
        }
      }
      fields.push(field);
      if (i < len && line[i] === ',') i++;
    } else {
      let field = '';
      while (i < len && line[i] !== ',') {
        field += line[i];
        i++;
      }
      fields.push(field);
      if (i < len && line[i] === ',') {
        i++;
        // Handle trailing comma -> empty field
        if (i === len) {
          fields.push('');
        }
      } else {
        break;
      }
    }
  }
  return fields;
}

// ---------------------------------------------------------------------------
// Column detection
// ---------------------------------------------------------------------------

const CODE_HEADERS = ['*code', 'code', 'accountcode', 'account code'];
const NAME_HEADERS = ['*name', 'name', 'account', 'accountname', 'account name'];
const TYPE_HEADERS = ['*type', 'type', 'accounttype', 'account type'];
const TAX_HEADERS = ['*tax code', 'tax code', 'taxcode'];
const REPORT_CODE_HEADERS = ['report code', 'reporting code', 'reportcode', 'reportingcode'];
const DESCRIPTION_HEADERS = ['description'];

function findColumn(headers: string[], candidates: string[]): number {
  const lower = headers.map((h) => h.trim().toLowerCase());
  for (const c of candidates) {
    const idx = lower.indexOf(c.toLowerCase());
    if (idx >= 0) return idx;
  }
  return -1;
}

// ---------------------------------------------------------------------------
// parseCSVText
// ---------------------------------------------------------------------------

export function parseCSVText(text: string): Account[] {
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length < 2) return [];

  const headers = splitCSVRow(lines[0]);
  const iCode = findColumn(headers, CODE_HEADERS);
  const iName = findColumn(headers, NAME_HEADERS);
  const iType = findColumn(headers, TYPE_HEADERS);
  const iTax = findColumn(headers, TAX_HEADERS);
  const iReport = findColumn(headers, REPORT_CODE_HEADERS);
  const iDesc = findColumn(headers, DESCRIPTION_HEADERS);

  if (iCode < 0 || iName < 0) {
    throw new Error(
      'Could not detect required columns (Code, Name). ' +
      `Found headers: ${headers.join(', ')}`,
    );
  }

  const accounts: Account[] = [];

  for (let row = 1; row < lines.length; row++) {
    const fields = splitCSVRow(lines[row]);
    const code = fields[iCode]?.trim() ?? '';
    const name = fields[iName]?.trim() ?? '';
    if (!code && !name) continue;

    const rawType = iType >= 0 ? (fields[iType]?.trim() ?? '') : '';
    accounts.push({
      code,
      name,
      type: rawType,
      canonType: canonicalType(rawType),
      reportCode: iReport >= 0 ? (fields[iReport]?.trim() ?? '') : undefined,
      taxCode: iTax >= 0 ? (fields[iTax]?.trim() ?? '') : undefined,
      description: iDesc >= 0 ? (fields[iDesc]?.trim() ?? '') : undefined,
    });
  }

  return accounts;
}

// ---------------------------------------------------------------------------
// parseChartFile
// ---------------------------------------------------------------------------

export async function parseChartFile(file: File): Promise<Account[]> {
  const name = file.name.toLowerCase();

  if (name.endsWith('.csv')) {
    const text = await file.text();
    return parseCSVText(text);
  }

  if (name.endsWith('.xlsx') || name.endsWith('.xls')) {
    const buffer = await file.arrayBuffer();
    const wb = XLSX.read(buffer, { type: 'array' });
    const sheet = wb.Sheets[wb.SheetNames[0]];
    const csv = XLSX.utils.sheet_to_csv(sheet);
    return parseCSVText(csv);
  }

  throw new Error(`Unsupported file format: ${file.name}`);
}
