import { describe, it, expect } from 'vitest';
import { ruleMatches, evaluateRules } from '../ruleEngine';
import type { Rule, MatchContext } from '../../types';

// ---------------------------------------------------------------------------
// Helper factories
// ---------------------------------------------------------------------------

function makeCtx(overrides: Partial<MatchContext> = {}): MatchContext {
  return {
    normalisedText: '',
    normalisedName: '',
    rawType: '',
    canonType: '',
    templateName: '',
    ownerKeywords: [],
    industry: '',
    ...overrides,
  };
}

function makeRule(overrides: Partial<Rule> = {}): Rule {
  return {
    name: 'test-rule',
    code: 'EXP.TST',
    priority: 70,
    keywords: [],
    keywordsAll: [],
    keywordsExclude: [],
    rawTypes: [],
    canonTypes: [],
    typeExclude: [],
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// ruleMatches
// ---------------------------------------------------------------------------

describe('ruleMatches', () => {
  describe('keywords (any-of)', () => {
    it('matches when any keyword is present in normalisedText', () => {
      const rule = makeRule({ keywords: ['bank', 'loan'] });
      const ctx = makeCtx({ normalisedText: 'bank fees' });
      expect(ruleMatches(rule, ctx)).toBe(true);
    });

    it('rejects when no keyword matches', () => {
      const rule = makeRule({ keywords: ['wages', 'salary'] });
      const ctx = makeCtx({ normalisedText: 'bank fees' });
      expect(ruleMatches(rule, ctx)).toBe(false);
    });

    it('uses substring matching, not word boundary matching', () => {
      const rule = makeRule({ keywords: ['bank'] });
      const ctx = makeCtx({ normalisedText: 'bankfees' });
      expect(ruleMatches(rule, ctx)).toBe(true);
    });

    it('matches with empty keywords (no constraint)', () => {
      const rule = makeRule({ keywords: [] });
      const ctx = makeCtx({ normalisedText: 'anything' });
      expect(ruleMatches(rule, ctx)).toBe(true);
    });
  });

  describe('keywordsAll (all-of)', () => {
    it('requires all keywordsAll to be present', () => {
      const rule = makeRule({ keywordsAll: ['motor', 'vehicle'] });
      const ctx = makeCtx({ normalisedText: 'motor vehicle insurance' });
      expect(ruleMatches(rule, ctx)).toBe(true);
    });

    it('rejects when only some keywordsAll are present', () => {
      const rule = makeRule({ keywordsAll: ['motor', 'vehicle'] });
      const ctx = makeCtx({ normalisedText: 'motor insurance' });
      expect(ruleMatches(rule, ctx)).toBe(false);
    });

    it('rejects when no keywordsAll are present', () => {
      const rule = makeRule({ keywordsAll: ['motor', 'vehicle'] });
      const ctx = makeCtx({ normalisedText: 'bank fees' });
      expect(ruleMatches(rule, ctx)).toBe(false);
    });
  });

  describe('keywordsExclude', () => {
    it('rejects when keywordsExclude matches', () => {
      const rule = makeRule({ keywords: ['loan'], keywordsExclude: ['director'] });
      const ctx = makeCtx({ normalisedText: 'director loan account' });
      expect(ruleMatches(rule, ctx)).toBe(false);
    });

    it('passes when keywordsExclude does not match', () => {
      const rule = makeRule({ keywords: ['loan'], keywordsExclude: ['director'] });
      const ctx = makeCtx({ normalisedText: 'bank loan' });
      expect(ruleMatches(rule, ctx)).toBe(true);
    });
  });

  describe('rawTypes', () => {
    it('matches rawType case-insensitively', () => {
      const rule = makeRule({ keywords: ['fees'], rawTypes: ['Expense'] });
      const ctx = makeCtx({ normalisedText: 'bank fees', rawType: 'expense' });
      expect(ruleMatches(rule, ctx)).toBe(true);
    });

    it('matches when rawType casing is inverted', () => {
      const rule = makeRule({ keywords: ['fees'], rawTypes: ['expense'] });
      const ctx = makeCtx({ normalisedText: 'bank fees', rawType: 'Expense' });
      expect(ruleMatches(rule, ctx)).toBe(true);
    });

    it('rejects when rawType does not match', () => {
      const rule = makeRule({ keywords: ['fees'], rawTypes: ['Revenue'] });
      const ctx = makeCtx({ normalisedText: 'bank fees', rawType: 'expense' });
      expect(ruleMatches(rule, ctx)).toBe(false);
    });

    it('passes with no rawTypes constraint', () => {
      const rule = makeRule({ keywords: ['fees'], rawTypes: [] });
      const ctx = makeCtx({ normalisedText: 'bank fees', rawType: 'expense' });
      expect(ruleMatches(rule, ctx)).toBe(true);
    });
  });

  describe('canonTypes', () => {
    it('checks canonTypes (case-sensitive)', () => {
      const rule = makeRule({ keywords: ['fees'], canonTypes: ['expense'] });
      const ctx = makeCtx({ normalisedText: 'bank fees', canonType: 'expense' });
      expect(ruleMatches(rule, ctx)).toBe(true);
    });

    it('rejects when canonType does not match', () => {
      const rule = makeRule({ keywords: ['fees'], canonTypes: ['revenue'] });
      const ctx = makeCtx({ normalisedText: 'bank fees', canonType: 'expense' });
      expect(ruleMatches(rule, ctx)).toBe(false);
    });
  });

  describe('typeExclude', () => {
    it('rejects typeExclude when canonType matches', () => {
      const rule = makeRule({ keywords: ['income'], typeExclude: ['revenue'] });
      const ctx = makeCtx({ normalisedText: 'other income', canonType: 'revenue' });
      expect(ruleMatches(rule, ctx)).toBe(false);
    });

    it('passes when canonType is not in typeExclude', () => {
      const rule = makeRule({ keywords: ['income'], typeExclude: ['revenue'] });
      const ctx = makeCtx({ normalisedText: 'other income', canonType: 'other income' });
      expect(ruleMatches(rule, ctx)).toBe(true);
    });
  });

  describe('template restriction', () => {
    it('matches when template equals templateName (case-insensitive)', () => {
      const rule = makeRule({ keywords: ['trust'], template: 'Trust' });
      const ctx = makeCtx({ normalisedText: 'trust income', templateName: 'trust' });
      expect(ruleMatches(rule, ctx)).toBe(true);
    });

    it('rejects when template differs from templateName', () => {
      const rule = makeRule({ keywords: ['trust'], template: 'Trust' });
      const ctx = makeCtx({ normalisedText: 'trust income', templateName: 'Company' });
      expect(ruleMatches(rule, ctx)).toBe(false);
    });

    it('lowercased comparison — rule template uppercase vs ctx lowercase', () => {
      const rule = makeRule({ keywords: ['fees'], template: 'COMPANY' });
      const ctx = makeCtx({ normalisedText: 'bank fees', templateName: 'company' });
      expect(ruleMatches(rule, ctx)).toBe(true);
    });

    it('passes with no template restriction', () => {
      const rule = makeRule({ keywords: ['fees'] });
      const ctx = makeCtx({ normalisedText: 'bank fees', templateName: 'Company' });
      expect(ruleMatches(rule, ctx)).toBe(true);
    });
  });

  describe('nameOnly', () => {
    it('uses normalisedName when nameOnly is true', () => {
      const rule = makeRule({ keywords: ['vehicle'], nameOnly: true });
      const ctx = makeCtx({
        normalisedText: 'vehicle insurance overhead',
        normalisedName: 'insurance',
      });
      // keyword "vehicle" is in normalisedText but NOT in normalisedName
      expect(ruleMatches(rule, ctx)).toBe(false);
    });

    it('matches normalisedName when nameOnly is true and keyword is present', () => {
      const rule = makeRule({ keywords: ['vehicle'], nameOnly: true });
      const ctx = makeCtx({
        normalisedText: 'something else',
        normalisedName: 'motor vehicle',
      });
      expect(ruleMatches(rule, ctx)).toBe(true);
    });

    it('uses normalisedText when nameOnly is false or unset', () => {
      const rule = makeRule({ keywords: ['vehicle'] });
      const ctx = makeCtx({
        normalisedText: 'motor vehicle insurance',
        normalisedName: 'insurance',
      });
      expect(ruleMatches(rule, ctx)).toBe(true);
    });
  });

  describe('ownerContext', () => {
    it('checks ownerContext (requires ownerKeywords in normalisedText)', () => {
      const rule = makeRule({ keywords: ['loan'], ownerContext: true });
      const ctx = makeCtx({
        normalisedText: 'john smith loan account',
        ownerKeywords: ['john smith'],
      });
      expect(ruleMatches(rule, ctx)).toBe(true);
    });

    it('rejects when ownerContext is true but no ownerKeywords match', () => {
      const rule = makeRule({ keywords: ['loan'], ownerContext: true });
      const ctx = makeCtx({
        normalisedText: 'bank loan',
        ownerKeywords: ['john smith'],
      });
      expect(ruleMatches(rule, ctx)).toBe(false);
    });

    it('rejects when ownerContext is true and ownerKeywords is empty', () => {
      const rule = makeRule({ keywords: ['loan'], ownerContext: true });
      const ctx = makeCtx({
        normalisedText: 'director loan',
        ownerKeywords: [],
      });
      expect(ruleMatches(rule, ctx)).toBe(false);
    });
  });

  describe('industry restriction', () => {
    it('matches when industry is in industries list', () => {
      const rule = makeRule({ keywords: ['catches'], industries: ['fishing'] });
      const ctx = makeCtx({ normalisedText: 'fish catches', industry: 'fishing' });
      expect(ruleMatches(rule, ctx)).toBe(true);
    });

    it('rejects when industry is not in industries list', () => {
      const rule = makeRule({ keywords: ['catches'], industries: ['fishing'] });
      const ctx = makeCtx({ normalisedText: 'fish catches', industry: 'retail' });
      expect(ruleMatches(rule, ctx)).toBe(false);
    });

    it('passes with no industries restriction', () => {
      const rule = makeRule({ keywords: ['fees'] });
      const ctx = makeCtx({ normalisedText: 'bank fees', industry: 'retail' });
      expect(ruleMatches(rule, ctx)).toBe(true);
    });
  });
});

// ---------------------------------------------------------------------------
// evaluateRules
// ---------------------------------------------------------------------------

describe('evaluateRules', () => {
  it('returns highest priority match when multiple rules match', () => {
    const rules: Rule[] = [
      makeRule({ name: 'low', code: 'EXP.LOW', priority: 60, keywords: ['fees'] }),
      makeRule({ name: 'high', code: 'EXP.HIGH', priority: 90, keywords: ['fees'] }),
      makeRule({ name: 'mid', code: 'EXP.MID', priority: 75, keywords: ['fees'] }),
    ];
    const ctx = makeCtx({ normalisedText: 'bank fees' });
    const result = evaluateRules(rules, ctx);
    expect(result).not.toBeNull();
    expect(result!.code).toBe('EXP.HIGH');
    expect(result!.name).toBe('high');
  });

  it('returns null when no rules match', () => {
    const rules: Rule[] = [
      makeRule({ keywords: ['wages'] }),
      makeRule({ keywords: ['salary'] }),
    ];
    const ctx = makeCtx({ normalisedText: 'bank fees' });
    const result = evaluateRules(rules, ctx);
    expect(result).toBeNull();
  });

  it('returns the single matching rule', () => {
    const rules: Rule[] = [
      makeRule({ name: 'bank-rule', code: 'ASS.CUR.BNK', priority: 80, keywords: ['bank'] }),
      makeRule({ name: 'wages-rule', code: 'EXP.LAB.WAG', priority: 80, keywords: ['wages'] }),
    ];
    const ctx = makeCtx({ normalisedText: 'bank account' });
    const result = evaluateRules(rules, ctx);
    expect(result).not.toBeNull();
    expect(result!.code).toBe('ASS.CUR.BNK');
    expect(result!.name).toBe('bank-rule');
  });

  it('returns null for empty rules array', () => {
    const ctx = makeCtx({ normalisedText: 'bank fees' });
    expect(evaluateRules([], ctx)).toBeNull();
  });
});
