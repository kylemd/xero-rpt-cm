import { describe, it, expect } from 'vitest';
import { fuzzyMatchInHead } from '../fuzzyMatch';
import type { SystemMapping } from '../../types';

const makeLeaf = (reportingCode: string, name: string): SystemMapping => ({
  reportingCode,
  name,
  isLeaf: true,
});

describe('fuzzyMatchInHead', () => {
  it('returns best match above threshold with shared word', () => {
    const leaves: SystemMapping[] = [
      makeLeaf('EXP.ADM.OFF', 'Office Supplies'),
      makeLeaf('EXP.ADM.TEL', 'Telephone'),
      makeLeaf('EXP.ADM.PRI', 'Printing and Stationery'),
    ];
    const result = fuzzyMatchInHead('office supplies', 'EXP', leaves);
    expect(result).not.toBeNull();
    expect(result!.reportingCode).toBe('EXP.ADM.OFF');
    expect(result!.score).toBeGreaterThanOrEqual(0.75);
  });

  it('returns null when no match above threshold', () => {
    const leaves: SystemMapping[] = [
      makeLeaf('EXP.ADM.OFF', 'Office Supplies'),
      makeLeaf('EXP.ADM.TEL', 'Telephone'),
    ];
    const result = fuzzyMatchInHead('xyz completely different name', 'EXP', leaves);
    expect(result).toBeNull();
  });

  it('requires at least one shared word', () => {
    // "wages" vs "pages" might have high similarity but no shared word
    const leaves: SystemMapping[] = [
      makeLeaf('EXP.SAL.WAG', 'Wages'),
    ];
    // "pages" has no shared word with "wages" even if similarity might be high
    const result = fuzzyMatchInHead('pages', 'EXP', leaves);
    expect(result).toBeNull();
  });

  it('only matches leaves with same root head', () => {
    const leaves: SystemMapping[] = [
      makeLeaf('REV.TRA.SAL', 'Sales Revenue'),
      makeLeaf('EXP.ADM.OFF', 'Office Supplies'),
    ];
    // Looking for EXP head, should not match REV leaf
    const result = fuzzyMatchInHead('sales revenue', 'EXP', leaves);
    expect(result).toBeNull();
  });

  it('applies depreciation boost when both sides have depreciation tokens', () => {
    const leaves: SystemMapping[] = [
      makeLeaf('EXP.DEP.BUI', 'Depreciation Buildings'),
      makeLeaf('EXP.DEP.VEH', 'Depreciation Motor Vehicles'),
    ];
    const result = fuzzyMatchInHead('depreciation buildings', 'EXP', leaves);
    expect(result).not.toBeNull();
    expect(result!.reportingCode).toBe('EXP.DEP.BUI');
  });

  it('returns null for empty leaves array', () => {
    const result = fuzzyMatchInHead('office supplies', 'EXP', []);
    expect(result).toBeNull();
  });
});
