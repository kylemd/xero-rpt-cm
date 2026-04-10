import { describe, it, expect } from 'vitest';
import { extractAccumBaseKey, pairAccumDep } from '../accumDep';

describe('extractAccumBaseKey', () => {
  it('extracts from "Less Accumulated Depreciation on Office Equipment"', () => {
    expect(extractAccumBaseKey('Less Accumulated Depreciation on Office Equipment'))
      .toBe('office equipment');
  });

  it('extracts from "Accumulated Depreciation on Motor Vehicles"', () => {
    expect(extractAccumBaseKey('Accumulated Depreciation on Motor Vehicles'))
      .toBe('motor vehicles');
  });

  it('extracts from "Less Accumulated Amortisation of Leasehold Improvements"', () => {
    expect(extractAccumBaseKey('Less Accumulated Amortisation of Leasehold Improvements'))
      .toBe('leasehold improvements');
  });

  it('extracts from "Accum Dep - Motor Vehicles"', () => {
    expect(extractAccumBaseKey('Accum Dep - Motor Vehicles'))
      .toBe('motor vehicles');
  });

  it('extracts from "Less Accum Dep on Computer Equipment"', () => {
    expect(extractAccumBaseKey('Less Accum Dep on Computer Equipment'))
      .toBe('computer equipment');
  });

  it('extracts from "Accum. Dep. - Plant"', () => {
    expect(extractAccumBaseKey('Accum. Dep. - Plant'))
      .toBe('plant');
  });

  it('returns empty string for non-depreciation names', () => {
    expect(extractAccumBaseKey('Office Supplies')).toBe('');
    expect(extractAccumBaseKey('Motor Vehicle Expenses')).toBe('');
    expect(extractAccumBaseKey('Bank Account')).toBe('');
  });

  it('returns empty string for empty/null input', () => {
    expect(extractAccumBaseKey('')).toBe('');
  });
});

describe('pairAccumDep', () => {
  it('pairs fallback accounts with matching base key to .ACC code', () => {
    const accounts = [
      { name: 'Office Equipment', predictedCode: 'ASS.NCA.FIX.PPE', source: 'RuleEngine' },
      { name: 'Less Accumulated Depreciation on Office Equipment', predictedCode: 'ASS', source: 'FallbackParent' },
    ];
    const nameToCode = new Map([['office equipment', 'ASS.NCA.FIX.PPE']]);
    pairAccumDep(accounts, nameToCode);
    expect(accounts[1].predictedCode).toBe('ASS.NCA.FIX.PPE.ACC');
    expect(accounts[1].source).toBe('AccumDepPairing');
  });

  it('does not modify accounts that are not fallback', () => {
    const accounts = [
      { name: 'Less Accumulated Depreciation on Office Equipment', predictedCode: 'ASS.NCA.FIX.PPE.ACC', source: 'RuleEngine' },
    ];
    const nameToCode = new Map([['office equipment', 'ASS.NCA.FIX.PPE']]);
    pairAccumDep(accounts, nameToCode);
    // Should remain unchanged since source is not a fallback
    expect(accounts[0].predictedCode).toBe('ASS.NCA.FIX.PPE.ACC');
    expect(accounts[0].source).toBe('RuleEngine');
  });

  it('does not modify when no base key found', () => {
    const accounts = [
      { name: 'Office Supplies', predictedCode: 'EXP', source: 'FallbackParent' },
    ];
    const nameToCode = new Map<string, string>();
    pairAccumDep(accounts, nameToCode);
    expect(accounts[0].predictedCode).toBe('EXP');
  });
});
