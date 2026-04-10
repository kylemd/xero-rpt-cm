import { describe, it, expect } from 'vitest';
import {
  stripNoiseSuffixes,
  normalise,
  canonicalType,
  headFromType,
  headGroup,
  similarity,
} from '../normalise';

describe('stripNoiseSuffixes', () => {
  it('strips " - At Cost" suffix (case-insensitive)', () => {
    expect(stripNoiseSuffixes('Motor Vehicle - At Cost')).toBe('Motor Vehicle');
    expect(stripNoiseSuffixes('Motor Vehicle - at cost')).toBe('Motor Vehicle');
    expect(stripNoiseSuffixes('Motor Vehicle - AT COST')).toBe('Motor Vehicle');
  });

  it('strips " - Closing Balance" suffix', () => {
    expect(stripNoiseSuffixes('Loan - Closing Balance')).toBe('Loan');
    expect(stripNoiseSuffixes('Loan - closing balance')).toBe('Loan');
  });

  it('strips " at cost" suffix (without dash)', () => {
    expect(stripNoiseSuffixes('Motor Vehicle at cost')).toBe('Motor Vehicle');
  });

  it('takes last segment after colon', () => {
    expect(stripNoiseSuffixes('Category: Equipment')).toBe('Equipment');
    expect(stripNoiseSuffixes('A: B: Final')).toBe('Final');
  });

  it('returns empty string for null/undefined/empty', () => {
    expect(stripNoiseSuffixes('')).toBe('');
    expect(stripNoiseSuffixes(null as unknown as string)).toBe('');
    expect(stripNoiseSuffixes(undefined as unknown as string)).toBe('');
  });
});

describe('normalise', () => {
  it('lowercases and replaces & with "and", strips punctuation', () => {
    expect(normalise('R&D Expenses')).toBe('r and d expenses');
    expect(normalise('Fees & Charges')).toBe('fees and charges');
  });

  it('canonicalises m/v, m-v, m v to "mv"', () => {
    expect(normalise('M/V Insurance')).toBe('mv insurance');
    expect(normalise('M-V Insurance')).toBe('mv insurance');
    expect(normalise('M V Insurance')).toBe('mv insurance');
  });

  it('canonicalises "r&m", "r and m", "r/m" to "repairs maintenance"', () => {
    expect(normalise('R&M')).toBe('repairs maintenance');
    expect(normalise('R and M')).toBe('repairs maintenance');
    expect(normalise('R/M')).toBe('repairs maintenance');
  });

  it('collapses whitespace and trims', () => {
    expect(normalise('  hello    world  ')).toBe('hello world');
  });

  it('returns empty string for falsy input', () => {
    expect(normalise('')).toBe('');
    expect(normalise(null as unknown as string)).toBe('');
    expect(normalise(undefined as unknown as string)).toBe('');
  });
});

describe('canonicalType', () => {
  it('maps "Purchases" to "expense"', () => {
    expect(canonicalType('Purchases')).toBe('expense');
  });

  it('maps "Overhead" to "expense"', () => {
    expect(canonicalType('Overhead')).toBe('expense');
  });

  it('maps "Overheads" to "expense"', () => {
    expect(canonicalType('Overheads')).toBe('expense');
  });

  it('maps "Operating Expense" to "expense"', () => {
    expect(canonicalType('Operating Expense')).toBe('expense');
  });

  it('passes through unknown types lowercased', () => {
    expect(canonicalType('Revenue')).toBe('revenue');
    expect(canonicalType('Fixed Asset')).toBe('fixed asset');
  });

  it('returns empty string for falsy input', () => {
    expect(canonicalType('')).toBe('');
    expect(canonicalType(null as unknown as string)).toBe('');
  });
});

describe('headFromType', () => {
  it('revenue -> REV.TRA', () => {
    expect(headFromType('revenue')).toBe('REV.TRA');
    expect(headFromType('income')).toBe('REV.TRA');
    expect(headFromType('sales')).toBe('REV.TRA');
  });

  it('other income -> REV.OTH', () => {
    expect(headFromType('other income')).toBe('REV.OTH');
    expect(headFromType('Other Income')).toBe('REV.OTH');
  });

  it('expense -> EXP', () => {
    expect(headFromType('expense')).toBe('EXP');
  });

  it('depreciation -> EXP.DEP', () => {
    expect(headFromType('depreciation')).toBe('EXP.DEP');
  });

  it('direct costs -> EXP.COS', () => {
    expect(headFromType('direct costs')).toBe('EXP.COS');
    expect(headFromType('cost of sales')).toBe('EXP.COS');
  });

  it('fixed asset -> ASS.NCA.FIX', () => {
    expect(headFromType('fixed asset')).toBe('ASS.NCA.FIX');
  });

  it('current asset -> ASS.CUR', () => {
    expect(headFromType('current asset')).toBe('ASS.CUR');
  });

  it('non-current asset -> ASS.NCA', () => {
    expect(headFromType('non-current asset')).toBe('ASS.NCA');
  });

  it('bank -> ASS', () => {
    expect(headFromType('bank')).toBe('ASS');
  });

  it('equity -> EQU', () => {
    expect(headFromType('equity')).toBe('EQU');
    expect(headFromType('retained earnings')).toBe('EQU');
  });

  it('current liability -> LIA.CUR', () => {
    expect(headFromType('current liability')).toBe('LIA.CUR');
  });

  it('non-current liability -> LIA.NCL', () => {
    expect(headFromType('non-current liability')).toBe('LIA.NCL');
  });

  it('liability types -> LIA', () => {
    expect(headFromType('liability')).toBe('LIA');
    expect(headFromType('accounts payable')).toBe('LIA');
    expect(headFromType('credit card')).toBe('LIA');
  });

  it('unknown -> EXP (default)', () => {
    expect(headFromType('something unknown')).toBe('EXP');
  });
});

describe('headGroup', () => {
  it('REV -> PL', () => {
    expect(headGroup('REV')).toBe('PL');
    expect(headGroup('REV.TRA')).toBe('PL');
    expect(headGroup('REV.OTH.INV')).toBe('PL');
  });

  it('EXP -> PL', () => {
    expect(headGroup('EXP')).toBe('PL');
    expect(headGroup('EXP.COS')).toBe('PL');
  });

  it('ASS -> BS', () => {
    expect(headGroup('ASS')).toBe('BS');
    expect(headGroup('ASS.NCA.FIX')).toBe('BS');
  });

  it('LIA -> BS', () => {
    expect(headGroup('LIA')).toBe('BS');
    expect(headGroup('LIA.CUR')).toBe('BS');
  });

  it('EQU -> EQ', () => {
    expect(headGroup('EQU')).toBe('EQ');
    expect(headGroup('EQU.RET')).toBe('EQ');
  });
});

describe('similarity', () => {
  it('identical strings -> 1', () => {
    expect(similarity('hello', 'hello')).toBe(1);
  });

  it('empty string -> 0', () => {
    expect(similarity('', 'hello')).toBe(0);
    expect(similarity('hello', '')).toBe(0);
    expect(similarity('', '')).toBe(0);
  });

  it('"wages and salaries" vs "wages salaries" -> > 0.8', () => {
    const score = similarity('wages and salaries', 'wages salaries');
    expect(score).toBeGreaterThan(0.8);
  });

  it('completely different strings -> low score', () => {
    const score = similarity('abc', 'xyz');
    expect(score).toBe(0);
  });

  it('partial overlap gives intermediate score', () => {
    const score = similarity('motor vehicle', 'motor');
    expect(score).toBeGreaterThan(0.4);
    expect(score).toBeLessThan(1);
  });

  // Cross-validation against Python difflib.SequenceMatcher.ratio()
  it('matches Python SequenceMatcher.ratio() for known pairs', () => {
    const cases: [string, string, number][] = [
      ['wages and salaries', 'wages salaries', 0.875],
      ['motor vehicle', 'motor', 0.555556],
      ['abc', 'xyz', 0.0],
      ['hello', 'hello', 1.0],
      ['', 'hello', 0.0],
      ['bank fees', 'bank charges', 0.666667],
      ['telephone internet', 'telephone and internet', 0.9],
      ['office supplies', 'office expenses', 0.666667],
    ];
    for (const [a, b, expected] of cases) {
      expect(similarity(a, b)).toBeCloseTo(expected, 4);
    }
  });
});
