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
    expect(REQUIRED_SHEET_PREFIXES).toHaveLength(8);
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

import { parseReportingCodesSheet } from '../verificationReportParser';

describe('parseReportingCodesSheet', () => {
  it('extracts code + name + reporting code from grouped rows', () => {
    const wb = makeWorkbook({
      'Chart of Accounts - Reportin...': [
        ['Chart of Accounts - Reporting Codes'],
        [],
        [],
        [],
        [null, 'Account', '2026', '2025', '2024', '2023', '2022', '2021'],
        [],
        ['Chart of Accounts'],
        [null, 'ASS.CUR.CAS.BAN'],
        [null, '090 - Business Bank Account', -17849.87, -8703.2, 0, 0, 0, 0],
        [null, '091 - Business Savings Account', 6878.28, 0, 0, 0, 0, 0],
        [null, 'Total ASS.CUR.CAS.BAN', 0, 0, 0, 0, 0, 0],
        [null, 'REV.TRA.GOO'],
        [null, '200 - Sales', -53378.32, -4200.0, 0, 0, 0, 0],
        [null, 'Total REV.TRA.GOO', 0, 0, 0, 0, 0, 0],
        ['Total Chart of Accounts', null, 0, 0, 0, 0, 0, 0],
      ],
    });
    const sheet = findRequiredSheet(wb, 'Chart of Accounts - Reportin')!;
    const rows = parseReportingCodesSheet(sheet);
    expect(rows).toEqual([
      { code: '090', name: 'Business Bank Account', reportCode: 'ASS.CUR.CAS.BAN', currentBalance: -17849.87 },
      { code: '091', name: 'Business Savings Account', reportCode: 'ASS.CUR.CAS.BAN', currentBalance: 6878.28 },
      { code: '200', name: 'Sales', reportCode: 'REV.TRA.GOO', currentBalance: -53378.32 },
    ]);
  });

  it('keeps rows without a numeric code prefix (e.g. unnumbered bank accounts)', () => {
    const wb = makeWorkbook({
      'Chart of Accounts - Reportin...': [
        ['Chart of Accounts - Reporting Codes'],
        [],
        [],
        [],
        [null, 'Account', '2026'],
        [],
        ['Chart of Accounts'],
        [null, 'ASS.CUR.CAS.BAN'],
        [null, 'Old Bank', 100],
        [null, 'Total ASS.CUR.CAS.BAN', 0],
      ],
    });
    const sheet = findRequiredSheet(wb, 'Chart of Accounts - Reportin')!;
    const rows = parseReportingCodesSheet(sheet);
    expect(rows).toEqual([
      { code: '', name: 'Old Bank', reportCode: 'ASS.CUR.CAS.BAN', currentBalance: 100 },
    ]);
  });

  it('skips the grand Total Chart of Accounts row', () => {
    const wb = makeWorkbook({
      'Chart of Accounts - Reportin...': [
        ['Chart of Accounts - Reporting Codes'],
        [],
        [],
        [],
        [null, 'Account', '2026'],
        [],
        ['Chart of Accounts'],
        [null, 'EXP'],
        [null, '400 - Advertising', 500],
        [null, 'Total EXP', 0],
        ['Total Chart of Accounts', null, 0],
      ],
    });
    const sheet = findRequiredSheet(wb, 'Chart of Accounts - Reportin')!;
    const rows = parseReportingCodesSheet(sheet);
    expect(rows.map((r) => r.code)).toEqual(['400']);
  });

  it('silently skips account rows appearing before any group header', () => {
    const wb = makeWorkbook({
      'Chart of Accounts - Reportin...': [
        ['Chart of Accounts - Reporting Codes'],
        [],
        [],
        [],
        [null, 'Account', '2026'],
        [],
        ['Chart of Accounts'],
        // Stray account row before any group header — must be dropped.
        [null, '999 - Stray Account', 42],
        [null, 'EXP'],
        [null, '400 - Advertising', 500],
        [null, 'Total EXP', 0],
        ['Total Chart of Accounts', null, 0],
      ],
    });
    const sheet = findRequiredSheet(wb, 'Chart of Accounts - Reportin')!;
    const rows = parseReportingCodesSheet(sheet);
    expect(rows.map((r) => r.code)).toEqual(['400']);
  });
});
