import { describe, it, expect } from 'vitest';
import { hasTypeMismatch } from '../typePredict';

describe('hasTypeMismatch', () => {
  it('returns false for a system type regardless of code', () => {
    expect(hasTypeMismatch('Bank', 'REV.TRA.GOO')).toBe(false);
  });

  it('returns false when code head matches type head', () => {
    expect(hasTypeMismatch('Expense', 'EXP.REN')).toBe(false);
  });

  it('returns true when code head differs from type head', () => {
    expect(hasTypeMismatch('Expense', 'REV.TRA.GOO')).toBe(true);
  });

  it('returns true for Direct Costs + non-COS expense code (prefix mismatch)', () => {
    expect(hasTypeMismatch('Direct Costs', 'EXP.REN')).toBe(true);
  });

  it('returns false for Direct Costs + EXP.COS code', () => {
    expect(hasTypeMismatch('Direct Costs', 'EXP.COS.GOO')).toBe(false);
  });

  it('returns true for Fixed Asset + non-FIX asset code (prefix mismatch)', () => {
    expect(hasTypeMismatch('Fixed Asset', 'ASS.CUR.CAS.BAN')).toBe(true);
  });

  it('returns false for Fixed Asset + ASS.NCA.FIX.PLA code', () => {
    expect(hasTypeMismatch('Fixed Asset', 'ASS.NCA.FIX.PLA')).toBe(false);
  });

  it('returns true for Inventory + ASS.CUR.REC code (prefix mismatch)', () => {
    expect(hasTypeMismatch('Inventory', 'ASS.CUR.REC.TRA')).toBe(true);
  });

  it('returns true for Sales + REV.OTH code (prefix mismatch)', () => {
    expect(hasTypeMismatch('Sales', 'REV.OTH')).toBe(true);
  });

  it('returns false when code is empty', () => {
    expect(hasTypeMismatch('Expense', '')).toBe(false);
  });

  it('returns false when type is unknown', () => {
    expect(hasTypeMismatch('Widget', 'EXP.REN')).toBe(false);
  });
});
