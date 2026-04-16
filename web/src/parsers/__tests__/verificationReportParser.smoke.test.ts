/**
 * Smoke test against the real demo workbook.
 *
 * Currently skipped: the demo file `.dev-info/Demo_Company__AU__-_Chart_of_Accounts_Verification_Report.xlsx`
 * still uses the legacy movement-sheet names (`Account Movement Report - Cu...` /
 * `Account Movement Report - Co...`). Once Xero regenerates it with the new
 * three-sheet layout (`Account Movements - Current / Comparat / Consider`),
 * change `it.skip` to `it` and the test will validate the parser end-to-end.
 */

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
  it.skip('parses without throwing (re-enable after demo regeneration)', () => {
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
