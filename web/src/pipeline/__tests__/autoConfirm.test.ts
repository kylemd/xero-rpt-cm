import { describe, it, expect } from 'vitest';
import { autoConfirmMatches } from '../autoConfirm';
import type { MappedAccount } from '../../types';

function makeAcct(partial: Partial<MappedAccount>): MappedAccount {
  return {
    code: '100',
    name: 'Test',
    type: 'Expense',
    canonType: 'expense',
    predictedCode: 'EXP',
    mappingName: 'Expense',
    source: 'FallbackParent',
    needsReview: false,
    hasActivity: true,
    closingBalance: 0,
    ...partial,
  };
}

describe('autoConfirmMatches', () => {
  it('marks head-compatible predicted===reportCode as auto-approved', () => {
    const accts = [
      makeAcct({ code: '404', reportCode: 'EXP', predictedCode: 'EXP', type: 'Expense' }),
    ];
    const out = autoConfirmMatches(accts);
    expect(out[0].approved).toBe(true);
    expect(out[0].auto).toBe(true);
  });

  it('does not mark when predicted !== reportCode', () => {
    const accts = [
      makeAcct({ code: '404', reportCode: 'EXP.REN', predictedCode: 'EXP', type: 'Expense' }),
    ];
    const out = autoConfirmMatches(accts);
    expect(out[0].approved).toBeUndefined();
    expect(out[0].auto).toBeUndefined();
  });

  it('does not mark when reportCode is empty', () => {
    const accts = [
      makeAcct({ code: '404', reportCode: undefined, predictedCode: 'EXP', type: 'Expense' }),
    ];
    const out = autoConfirmMatches(accts);
    expect(out[0].approved).toBeUndefined();
  });

  it('respects existing user decisions (overrideCode set)', () => {
    const accts = [
      makeAcct({
        code: '404',
        reportCode: 'EXP',
        predictedCode: 'EXP',
        overrideCode: 'EXP.REN',
      }),
    ];
    const out = autoConfirmMatches(accts);
    expect(out[0].approved).toBeUndefined();
  });

  it('respects existing approval', () => {
    const accts = [
      makeAcct({ code: '404', reportCode: 'EXP', predictedCode: 'EXP', approved: true, auto: false }),
    ];
    const out = autoConfirmMatches(accts);
    expect(out[0].auto).toBe(false); // untouched
  });

  it('does not mark when type has head-level mismatch', () => {
    const accts = [
      makeAcct({ code: '200', reportCode: 'EXP', predictedCode: 'EXP', type: 'Revenue' }),
    ];
    const out = autoConfirmMatches(accts);
    expect(out[0].approved).toBeUndefined();
  });

  it('does not mark when type has prefix-level mismatch (Direct Costs + EXP.REN)', () => {
    const accts = [
      makeAcct({
        code: '300',
        reportCode: 'EXP.REN',
        predictedCode: 'EXP.REN',
        type: 'Direct Costs',
      }),
    ];
    const out = autoConfirmMatches(accts);
    expect(out[0].approved).toBeUndefined();
  });

  it('marks system-typed accounts (Bank) without prefix check', () => {
    const accts = [
      makeAcct({
        code: '090',
        reportCode: 'ASS.CUR.CAS.BAN',
        predictedCode: 'ASS.CUR.CAS.BAN',
        type: 'Bank',
      }),
    ];
    const out = autoConfirmMatches(accts);
    expect(out[0].approved).toBe(true);
    expect(out[0].auto).toBe(true);
  });

  it('returns a new array and does not mutate input', () => {
    const original = makeAcct({ code: '404', reportCode: 'EXP', predictedCode: 'EXP' });
    const accts = [original];
    const out = autoConfirmMatches(accts);
    expect(out).not.toBe(accts);
    expect(original.approved).toBeUndefined();
  });
});
