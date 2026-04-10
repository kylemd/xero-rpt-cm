import { describe, it, expect } from 'vitest';
import { inferFromContext, inferSection } from '../contextRules';

describe('inferFromContext', () => {
  it('infers intangible code for nearby keyword account when goodwill has balance', () => {
    const accounts = [
      { code: '300', name: 'Goodwill', predicted: 'ASS.NCA.INT', source: 'RuleEngine' },
      { code: '310', name: 'Legal Costs on Acquisition', predicted: 'ASS', source: 'FallbackParent' },
    ];
    const balLookup: Record<string, number> = { '300': 50000 };
    const overridden = new Set<number>();
    const changes = inferFromContext(accounts, balLookup, overridden);
    expect(changes).toHaveLength(1);
    expect(changes[0].index).toBe(1);
    expect(changes[0].inferred_code).toBe('ASS.NCA.INT');
    expect(changes[0].reason).toContain('goodwill_intangibles');
  });

  it('does not infer when anchor has no balance', () => {
    const accounts = [
      { code: '300', name: 'Goodwill', predicted: 'ASS.NCA.INT', source: 'RuleEngine' },
      { code: '310', name: 'Legal Costs on Acquisition', predicted: 'ASS', source: 'FallbackParent' },
    ];
    const balLookup: Record<string, number> = { '300': 0 };
    const overridden = new Set<number>();
    const changes = inferFromContext(accounts, balLookup, overridden);
    expect(changes).toHaveLength(0);
  });

  it('skips overridden indices', () => {
    const accounts = [
      { code: '300', name: 'Goodwill', predicted: 'ASS.NCA.INT', source: 'RuleEngine' },
      { code: '310', name: 'Legal Costs on Acquisition', predicted: 'ASS', source: 'FallbackParent' },
    ];
    const balLookup: Record<string, number> = { '300': 50000 };
    const overridden = new Set<number>([1]);
    const changes = inferFromContext(accounts, balLookup, overridden);
    expect(changes).toHaveLength(0);
  });
});

describe('inferSection', () => {
  it('promotes head-only code based on neighbour consensus', () => {
    const accounts = [
      { code: '100', name: 'Trade Debtors', predicted: 'ASS.CUR.REC', source: 'RuleEngine' },
      { code: '110', name: 'Prepayments', predicted: 'ASS.CUR.REC.PRE', source: 'RuleEngine' },
      { code: '120', name: 'Other Current Asset', predicted: 'ASS', source: 'FallbackParent' },
      { code: '130', name: 'GST Receivable', predicted: 'ASS.CUR.REC', source: 'RuleEngine' },
      { code: '140', name: 'Petty Cash', predicted: 'ASS.CUR.CAS', source: 'RuleEngine' },
    ];
    const balLookup: Record<string, number> = {
      '100': 5000, '110': 1000, '120': 500, '130': 2000, '140': 100,
    };
    const overridden = new Set<number>();
    const changes = inferSection(accounts, balLookup, overridden);
    expect(changes).toHaveLength(1);
    expect(changes[0].index).toBe(2);
    expect(changes[0].inferred_code).toBe('ASS.CUR');
  });

  it('skips excluded names like "suspense" and "rounding"', () => {
    const accounts = [
      { code: '100', name: 'Trade Debtors', predicted: 'ASS.CUR.REC', source: 'RuleEngine' },
      { code: '110', name: 'Suspense Account', predicted: 'ASS', source: 'FallbackParent' },
      { code: '120', name: 'GST Receivable', predicted: 'ASS.CUR.REC', source: 'RuleEngine' },
    ];
    const balLookup: Record<string, number> = {
      '100': 5000, '110': 500, '120': 2000,
    };
    const overridden = new Set<number>();
    const changes = inferSection(accounts, balLookup, overridden);
    expect(changes).toHaveLength(0);
  });

  it('skips overridden indices', () => {
    const accounts = [
      { code: '100', name: 'Trade Debtors', predicted: 'ASS.CUR.REC', source: 'RuleEngine' },
      { code: '110', name: 'Other Asset', predicted: 'ASS', source: 'FallbackParent' },
      { code: '120', name: 'GST Receivable', predicted: 'ASS.CUR.REC', source: 'RuleEngine' },
    ];
    const balLookup: Record<string, number> = {
      '100': 5000, '120': 2000,
    };
    const overridden = new Set<number>([1]);
    const changes = inferSection(accounts, balLookup, overridden);
    expect(changes).toHaveLength(0);
  });

  it('weights active accounts higher than inactive', () => {
    // 2 active ASS.CUR neighbours and 3 inactive ASS.NCA neighbours
    // Active weight = 1.0 each = 2.0 for ASS.CUR
    // Inactive weight = 0.3 each = 0.9 for ASS.NCA
    // ASS.CUR should win
    const accounts = [
      { code: '100', name: 'Item A', predicted: 'ASS.CUR.REC', source: 'RuleEngine' },
      { code: '101', name: 'Item B', predicted: 'ASS.CUR.CAS', source: 'RuleEngine' },
      { code: '102', name: 'Ambiguous Item', predicted: 'ASS', source: 'FallbackParent' },
      { code: '103', name: 'Item C', predicted: 'ASS.NCA.FIX', source: 'RuleEngine' },
      { code: '104', name: 'Item D', predicted: 'ASS.NCA.INT', source: 'RuleEngine' },
      { code: '105', name: 'Item E', predicted: 'ASS.NCA.FIX', source: 'RuleEngine' },
    ];
    const balLookup: Record<string, number> = {
      '100': 1000, '101': 2000, '102': 100,
      // 103, 104, 105 have no balance -> weight 0.3 each
    };
    const overridden = new Set<number>();
    const changes = inferSection(accounts, balLookup, overridden);
    expect(changes).toHaveLength(1);
    expect(changes[0].inferred_code).toBe('ASS.CUR');
  });
});
