import { describe, it, expect } from 'vitest';
import { deriveReportingName } from '../reportingName';

describe('deriveReportingName', () => {
  it('returns "ATO ICA" for ATO Integrated Client Account', () => {
    expect(deriveReportingName('ATO Integrated Client Account')).toBe('ATO ICA');
    expect(deriveReportingName('ATO ICA')).toBe('ATO ICA');
    expect(deriveReportingName('ato ica - 12345')).toBe('ATO ICA');
  });

  it('returns "ATO ITA" for ATO Income Tax Account', () => {
    expect(deriveReportingName('ATO Income Tax Account')).toBe('ATO ITA');
    expect(deriveReportingName('ATO ITA')).toBe('ATO ITA');
  });

  it('returns "Div7A <YYYY>" for Div7A names containing a year', () => {
    expect(deriveReportingName('Div7A Loan 2024')).toBe('Div7A 2024');
    expect(deriveReportingName('Division 7A 2023')).toBe('Div7A 2023');
    expect(deriveReportingName('Loan 7A - John Smith (2022)')).toBe('Div7A 2022');
  });

  it('returns null when no pattern matches', () => {
    expect(deriveReportingName('Bank Fees')).toBeNull();
    expect(deriveReportingName('')).toBeNull();
    expect(deriveReportingName('Div7A loan with no year')).toBeNull();
  });

  it('prefers the first 4-digit year when multiple exist', () => {
    expect(deriveReportingName('Div7A 2020-2021')).toBe('Div7A 2020');
  });

  it('does not match loose "7a" unit/bay/lot tokens (false-positive guard)', () => {
    expect(deriveReportingName('Bay 7a 2024')).toBeNull();
    expect(deriveReportingName('Unit 7A 2023 rent')).toBeNull();
    expect(deriveReportingName('Lot 7a 2022 deposit')).toBeNull();
    expect(deriveReportingName('Locker 7a 2021')).toBeNull();
  });

  it('ignores years outside 1900..2099', () => {
    expect(deriveReportingName('Div7A 1850 loan')).toBeNull();
  });
});
