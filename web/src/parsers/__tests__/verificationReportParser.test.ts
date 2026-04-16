import { describe, it, expect } from 'vitest';
import * as XLSX from 'xlsx';
import {
  findRequiredSheet,
  parseTypeAndClassSheet,
  REQUIRED_SHEET_PREFIXES,
} from '../verificationReportParser';

function makeWorkbook(
  sheets: Record<string, (string | number | null)[][]>,
): XLSX.WorkBook {
  const wb = XLSX.utils.book_new();
  for (const [name, data] of Object.entries(sheets)) {
    const ws = XLSX.utils.aoa_to_sheet(data);
    XLSX.utils.book_append_sheet(wb, ws, name);
  }
  return wb;
}

describe('findRequiredSheet', () => {
  it('finds a sheet by its truncated prefix', () => {
    const wb = makeWorkbook({ 'Chart of Accounts - Type and...': [['x']] });
    const sheet = findRequiredSheet(wb, 'Chart of Accounts - Type and');
    expect(sheet).toBeDefined();
  });

  it('is case-insensitive', () => {
    const wb = makeWorkbook({ 'Chart of Accounts - Type AND...': [['x']] });
    const sheet = findRequiredSheet(wb, 'chart of accounts - type and');
    expect(sheet).toBeDefined();
  });

  it('returns undefined when no sheet matches', () => {
    const wb = makeWorkbook({ 'Other Sheet': [['x']] });
    expect(findRequiredSheet(wb, 'Chart of Accounts - Reportin')).toBeUndefined();
  });

  it('exposes the full list of required prefixes', () => {
    expect(REQUIRED_SHEET_PREFIXES).toContain('Chart of Accounts - Reportin');
    expect(REQUIRED_SHEET_PREFIXES).toContain('Chart of Accounts - Type and');
    expect(REQUIRED_SHEET_PREFIXES).toContain('Account Movements - Current');
    expect(REQUIRED_SHEET_PREFIXES).toContain('Account Movements - Comparat');
    expect(REQUIRED_SHEET_PREFIXES).toContain('Account Movements - Consider');
    expect(REQUIRED_SHEET_PREFIXES).toContain('Depreciation Schedule');
    expect(REQUIRED_SHEET_PREFIXES).toContain('Beneficiary Accounts');
    expect(REQUIRED_SHEET_PREFIXES).toContain('Client File Parameters Report');
  });
});

describe('parseTypeAndClassSheet', () => {
  it('parses accounts from the Type and Class grid', () => {
    const wb = makeWorkbook({
      'Chart of Accounts - Type and...': [
        ['Chart of Accounts - Type and Class'],
        ['Demo Company (AU)'],
        ['As at 30 June 2026'],
        [],
        ['Account Code', 'Account', 'Account Type', 'Account Class'],
        ['200', 'Sales', 'Revenue', 'Revenue'],
        ['090', 'Business Bank Account', 'Bank', 'Asset'],
        ['Total', null, null, null],
      ],
    });
    const sheet = findRequiredSheet(wb, 'Chart of Accounts - Type and')!;
    const map = parseTypeAndClassSheet(sheet);
    expect(map.size).toBe(2);
    expect(map.get('200')).toEqual({
      code: '200',
      name: 'Sales',
      type: 'Revenue',
      class: 'Revenue',
    });
    expect(map.get('090')).toEqual({
      code: '090',
      name: 'Business Bank Account',
      type: 'Bank',
      class: 'Asset',
    });
  });

  it('ignores the trailing Total row', () => {
    const wb = makeWorkbook({
      'Chart of Accounts - Type and...': [
        ['Chart of Accounts - Type and Class'],
        [],
        [],
        [],
        ['Account Code', 'Account', 'Account Type', 'Account Class'],
        ['100', 'X', 'Expense', 'Expense'],
        ['Total', '', '', ''],
      ],
    });
    const sheet = findRequiredSheet(wb, 'Chart of Accounts - Type and')!;
    const map = parseTypeAndClassSheet(sheet);
    expect(map.size).toBe(1);
    expect(map.get('Total')).toBeUndefined();
  });

  it('tolerates empty rows between data rows', () => {
    const wb = makeWorkbook({
      'Chart of Accounts - Type and...': [
        ['Chart of Accounts - Type and Class'],
        [],
        [],
        [],
        ['Account Code', 'Account', 'Account Type', 'Account Class'],
        ['100', 'X', 'Expense', 'Expense'],
        [null, null, null, null],
        ['200', 'Y', 'Revenue', 'Revenue'],
      ],
    });
    const sheet = findRequiredSheet(wb, 'Chart of Accounts - Type and')!;
    const map = parseTypeAndClassSheet(sheet);
    expect(map.size).toBe(2);
  });
});
