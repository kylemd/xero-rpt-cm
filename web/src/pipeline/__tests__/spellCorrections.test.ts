import { describe, it, expect } from 'vitest';
import { correctAccountName } from '../spellCorrections';

describe('correctAccountName', () => {
  it('expands "depr" to "depreciation"', () => {
    const result = correctAccountName('Depr Expense');
    expect(result.corrected.toLowerCase()).toContain('depreciation');
    expect(result.corrections).toHaveLength(1);
    expect(result.corrections[0].original).toBe('Depr');
    expect(result.corrections[0].corrected).toBe('depreciation');
    expect(result.corrections[0].source).toBe('abbreviation');
  });

  it('expands "lsl" to "long service leave"', () => {
    const result = correctAccountName('LSL Provision');
    expect(result.corrected.toLowerCase()).toContain('long service leave');
    expect(result.corrections).toHaveLength(1);
    expect(result.corrections[0].source).toBe('abbreviation');
  });

  it('preserves case: ALL CAPS input -> uppercase expansion', () => {
    const result = correctAccountName('DEPR Expense');
    expect(result.corrected).toMatch(/^DEPRECIATION/);
  });

  it('preserves case: Capitalized input -> capitalize expansion', () => {
    const result = correctAccountName('Depr Expense');
    expect(result.corrected).toMatch(/^Depreciation/);
  });

  it('protects suffix after " - " separator', () => {
    const result = correctAccountName('Depr Expense - Hendra Motors');
    expect(result.corrected).toContain('Hendra Motors');
    expect(result.corrected.toLowerCase()).toContain('depreciation');
  });

  it('returns unchanged when no corrections needed', () => {
    const result = correctAccountName('Trade Debtors');
    expect(result.corrected).toBe('Trade Debtors');
    expect(result.corrections).toHaveLength(0);
  });

  it('expands "amort" to "amortisation"', () => {
    const result = correctAccountName('Amort Expense');
    expect(result.corrected.toLowerCase()).toContain('amortisation');
  });

  it('expands "wip" to "work in progress"', () => {
    const result = correctAccountName('WIP Account');
    expect(result.corrected.toLowerCase()).toContain('work in progress');
  });

  it('expands "scg" to "sgc"', () => {
    const result = correctAccountName('SCG Payable');
    expect(result.corrected.toLowerCase()).toContain('sgc');
  });

  it('handles multiple abbreviations in one name', () => {
    const result = correctAccountName('Govt Dept Expenses');
    expect(result.corrected.toLowerCase()).toContain('government');
    expect(result.corrected.toLowerCase()).toContain('department');
    expect(result.corrections).toHaveLength(2);
  });

  it('handles empty string', () => {
    const result = correctAccountName('');
    expect(result.corrected).toBe('');
    expect(result.corrections).toHaveLength(0);
  });
});
