/* Smoke test: parses the on-disk demo Verification Report end-to-end. */

import { describe, it, expect } from 'vitest';
import * as XLSX from 'xlsx';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { parseVerificationReportFromWorkbook } from '../verificationReportParser';

const DEMO = resolve(
  __dirname,
  '../../../..',
  '.dev-info/Demo_Company__AU__-_Chart_of_Accounts_Verification_Report.xlsx',
);

describe('smoke: real demo workbook', () => {
  it('parses without throwing', () => {
    const buf = readFileSync(DEMO);
    const wb = XLSX.read(buf, { type: 'buffer' });
    const data = parseVerificationReportFromWorkbook(wb);
    expect(data.clientParams.displayName).toContain('Demo Company');
    expect(data.accounts.length).toBeGreaterThan(0);
    // Current Year Earnings + CURRADJUST must be excluded.
    expect(data.accounts.find((a) => a.name === 'Current Year Earnings')).toBeUndefined();
    expect(data.accounts.find((a) => a.name === 'Currency Adjustment')).toBeUndefined();
    // Every surviving account has a type from Type-and-Class.
    for (const a of data.accounts) {
      expect(a.type).toBeTruthy();
    }
  });
});
