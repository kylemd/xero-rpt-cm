import { describe, it, expect } from 'vitest';
import { serviceOnlyReclass, autoIndustryReclass, typeRangeCorrection } from '../postProcess';
import type { MappedAccount } from '../../types';

// ---------------------------------------------------------------------------
// Helper factory
// ---------------------------------------------------------------------------

function makeMapped(overrides: Partial<MappedAccount> = {}): MappedAccount {
  return {
    code: '400',
    name: 'Test Account',
    type: 'Expense',
    canonType: 'expense',
    predictedCode: 'EXP',
    mappingName: '',
    source: 'RuleEngine',
    needsReview: false,
    hasActivity: false,
    closingBalance: 0,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// serviceOnlyReclass
// ---------------------------------------------------------------------------

describe('serviceOnlyReclass', () => {
  it('reclassifies EXP.COS to EXP when no direct cost has activity', () => {
    const accounts = [
      makeMapped({ predictedCode: 'EXP.COS', hasActivity: false }),
      makeMapped({ predictedCode: 'EXP.COS.PUR', hasActivity: false }),
      makeMapped({ predictedCode: 'EXP.EMP.WAG', hasActivity: true }),
    ];

    serviceOnlyReclass(accounts, '');

    expect(accounts[0].predictedCode).toBe('EXP');
    expect(accounts[0].source).toBe('ServiceOnlyRevenueAdjustment');
    expect(accounts[1].predictedCode).toBe('EXP');
    expect(accounts[1].source).toBe('ServiceOnlyRevenueAdjustment');
    // Non-COS account should be untouched
    expect(accounts[2].predictedCode).toBe('EXP.EMP.WAG');
  });

  it('does NOT reclassify when a direct cost account has activity', () => {
    const accounts = [
      makeMapped({ predictedCode: 'EXP.COS', hasActivity: true }),
      makeMapped({ predictedCode: 'EXP.COS.PUR', hasActivity: false }),
    ];

    serviceOnlyReclass(accounts, '');

    expect(accounts[0].predictedCode).toBe('EXP.COS');
    expect(accounts[1].predictedCode).toBe('EXP.COS.PUR');
  });

  it('does NOT reclassify for construction industry', () => {
    const accounts = [
      makeMapped({ predictedCode: 'EXP.COS', hasActivity: false }),
    ];

    serviceOnlyReclass(accounts, 'construction');

    expect(accounts[0].predictedCode).toBe('EXP.COS');
  });

  it('sets needsReview=true on reclassified accounts', () => {
    const accounts = [
      makeMapped({ predictedCode: 'EXP.COS', hasActivity: false, needsReview: false }),
    ];

    serviceOnlyReclass(accounts, '');

    expect(accounts[0].needsReview).toBe(true);
  });

  it('handles empty accounts array', () => {
    const accounts: MappedAccount[] = [];
    serviceOnlyReclass(accounts, '');
    expect(accounts).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// autoIndustryReclass
// ---------------------------------------------------------------------------

describe('autoIndustryReclass', () => {
  it('reclassifies EXP.VEH to EXP.COS for auto industry', () => {
    const accounts = [
      makeMapped({ predictedCode: 'EXP.VEH', name: 'Fuel' }),
      makeMapped({ predictedCode: 'EXP.VEH.FUE', name: 'Petrol' }),
    ];

    autoIndustryReclass(accounts, 'auto');

    expect(accounts[0].predictedCode).toBe('EXP.COS');
    expect(accounts[1].predictedCode).toBe('EXP.COS');
  });

  it('skips accumulated depreciation entries', () => {
    const accounts = [
      makeMapped({ predictedCode: 'EXP.VEH.ACC', name: 'Accum Depreciation' }),
      makeMapped({ predictedCode: 'EXP.VEH', name: 'MV Depreciation' }),
    ];

    autoIndustryReclass(accounts, 'auto');

    expect(accounts[0].predictedCode).toBe('EXP.VEH.ACC');
    expect(accounts[1].predictedCode).toBe('EXP.VEH');
  });

  it('does nothing for non-auto industries', () => {
    const accounts = [
      makeMapped({ predictedCode: 'EXP.VEH', name: 'Fuel' }),
    ];

    autoIndustryReclass(accounts, 'construction');

    expect(accounts[0].predictedCode).toBe('EXP.VEH');
  });
});

// ---------------------------------------------------------------------------
// typeRangeCorrection
// ---------------------------------------------------------------------------

describe('typeRangeCorrection', () => {
  it('corrects head-only codes to expected head', () => {
    const accounts = [
      makeMapped({
        predictedCode: 'EXP',
        type: 'Current Asset',
        source: 'FallbackParent',
      }),
    ];

    typeRangeCorrection(accounts);

    expect(accounts[0].predictedCode).toBe('ASS.CUR');
    expect(accounts[0].source).toBe('TypeRangeCorrection');
  });

  it('skips accounts with trusted sources', () => {
    const accounts = [
      makeMapped({
        predictedCode: 'EXP',
        type: 'Current Asset',
        source: 'DefaultChart',
      }),
    ];

    typeRangeCorrection(accounts);

    expect(accounts[0].predictedCode).toBe('EXP');
  });

  it('flags specific leaf codes in wrong group for review without changing', () => {
    const accounts = [
      makeMapped({
        predictedCode: 'EXP.EMP.WAG',
        type: 'Current Asset',
        source: 'RuleEngine',
      }),
    ];

    typeRangeCorrection(accounts);

    // Should not change the code
    expect(accounts[0].predictedCode).toBe('EXP.EMP.WAG');
    // But should flag for review
    expect(accounts[0].needsReview).toBe(true);
  });

  it('does not flag codes already in correct group', () => {
    const accounts = [
      makeMapped({
        predictedCode: 'EXP.EMP.WAG',
        type: 'Expense',
        source: 'RuleEngine',
        needsReview: false,
      }),
    ];

    typeRangeCorrection(accounts);

    expect(accounts[0].needsReview).toBe(false);
  });
});
