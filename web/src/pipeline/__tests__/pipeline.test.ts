import { describe, it, expect } from 'vitest';
import { runPipeline, type PipelineInput } from '../pipeline';
import type { Account, RulesData, TemplateEntry, SystemMapping, GLEntry } from '../../types';

// ---------------------------------------------------------------------------
// Minimal fixture data
// ---------------------------------------------------------------------------

const RULES_DATA: RulesData = {
  version: 1,
  updatedAt: '2026-01-01T00:00:00Z',
  dictionaries: {
    OWNER_KEYWORDS: ['owner a'],
    AUSTRALIAN_BANKS: ['commonwealth bank', 'westpac', 'anz', 'nab'],
  },
  rules: [
    {
      name: 'bank-account',
      code: 'ASS.CUR.BNK',
      priority: 90,
      keywords: ['$AUSTRALIAN_BANKS'],
      keywordsAll: [],
      keywordsExclude: [],
      rawTypes: ['Bank'],
      canonTypes: [],
      typeExclude: [],
    },
    {
      name: 'wages-salaries',
      code: 'EXP.LAB.WAG',
      priority: 80,
      keywords: ['wages', 'salaries'],
      keywordsAll: [],
      keywordsExclude: [],
      rawTypes: [],
      canonTypes: ['expense'],
      typeExclude: [],
    },
  ],
};

const TEMPLATE_ENTRIES: TemplateEntry[] = [
  {
    code: '200',
    reportingCode: 'ASS.CUR.BNK',
    name: 'Business Bank Account',
    type: 'Bank',
    reportingName: 'Bank Accounts',
  },
];

const SYSTEM_MAPPINGS: SystemMapping[] = [
  { reportingCode: 'ASS.CUR.BNK', name: 'Bank Accounts', isLeaf: true },
  { reportingCode: 'EXP.LAB.WAG', name: 'Wages & Salaries', isLeaf: true },
  { reportingCode: 'EXP.ADM.GEN', name: 'General Expenses', isLeaf: true },
  { reportingCode: 'EXP', name: 'Expense', isLeaf: false },
];

const GL_SUMMARY: GLEntry[] = [
  {
    accountCode: '090',
    accountName: 'Westpac Business Account',
    openingBalance: 10000,
    debit: 5000,
    credit: 3000,
    netMovement: 2000,
    closingBalance: 12000,
    accountType: 'Bank',
  },
  {
    accountCode: '477',
    accountName: 'Wages & Salaries',
    openingBalance: 0,
    debit: 50000,
    credit: 0,
    netMovement: 50000,
    closingBalance: 50000,
    accountType: 'Expense',
  },
  {
    accountCode: '400',
    accountName: 'General Expenses',
    openingBalance: 0,
    debit: 100,
    credit: 0,
    netMovement: 100,
    closingBalance: 100,
    accountType: 'Expense',
  },
];

// ---------------------------------------------------------------------------
// Test accounts
// ---------------------------------------------------------------------------

const TEST_ACCOUNTS: Account[] = [
  {
    code: '090',
    name: 'Westpac Business Account',
    type: 'Bank',
    canonType: 'bank',
  },
  {
    code: '477',
    name: 'Wages & Salaries',
    type: 'Expense',
    canonType: 'expense',
  },
  {
    code: '400',
    name: 'General Expenses',
    type: 'Expense',
    canonType: 'expense',
  },
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('runPipeline', () => {
  it('maps bank account via rule engine (dictionary expansion)', () => {
    const result = runPipeline({
      accounts: TEST_ACCOUNTS,
      rulesData: RULES_DATA,
      templateEntries: TEMPLATE_ENTRIES,
      systemMappings: SYSTEM_MAPPINGS,
      glSummary: GL_SUMMARY,
      industry: '',
      templateName: 'Company',
    });

    expect(result).toHaveLength(3);

    // Bank account: "westpac" should match the $AUSTRALIAN_BANKS dictionary expansion
    const bank = result[0];
    expect(bank.predictedCode).toBe('ASS.CUR.BNK');
    expect(bank.source).toContain('Rule');
    expect(bank.source).toContain('bank-account');
    expect(bank.hasActivity).toBe(true);
    expect(bank.closingBalance).toBe(12000);
    expect(bank.needsReview).toBe(false);
  });

  it('maps wages account via rule engine', () => {
    const result = runPipeline({
      accounts: TEST_ACCOUNTS,
      rulesData: RULES_DATA,
      templateEntries: TEMPLATE_ENTRIES,
      systemMappings: SYSTEM_MAPPINGS,
      glSummary: GL_SUMMARY,
      industry: '',
      templateName: 'Company',
    });

    const wages = result[1];
    expect(wages.predictedCode).toBe('EXP.LAB.WAG');
    expect(wages.source).toContain('Rule');
    expect(wages.source).toContain('wages-salaries');
    expect(wages.hasActivity).toBe(true);
    expect(wages.closingBalance).toBe(50000);
    expect(wages.needsReview).toBe(false);
  });

  it('falls back for generic accounts with no rule match', () => {
    const result = runPipeline({
      accounts: TEST_ACCOUNTS,
      rulesData: RULES_DATA,
      templateEntries: TEMPLATE_ENTRIES,
      systemMappings: SYSTEM_MAPPINGS,
      glSummary: GL_SUMMARY,
      industry: '',
      templateName: 'Company',
    });

    const general = result[2];
    // "General Expenses" should match via DirectNameMatch or FuzzyMatch or FallbackParent
    // With the system mappings provided, it may match "General Expenses" -> EXP.ADM.GEN
    // via DirectNameMatch or FuzzyMatch
    expect(general.predictedCode).toBeDefined();
    expect(general.closingBalance).toBe(100);
  });

  it('returns empty array for empty input', () => {
    const result = runPipeline({
      accounts: [],
      rulesData: RULES_DATA,
      templateEntries: TEMPLATE_ENTRIES,
      systemMappings: SYSTEM_MAPPINGS,
      glSummary: [],
      industry: '',
      templateName: 'Company',
    });

    expect(result).toHaveLength(0);
  });

  it('applies cross-head guard for mismatched codes (PL vs BS)', () => {
    const badRulesData: RulesData = {
      ...RULES_DATA,
      rules: [
        {
          name: 'bad-rule',
          code: 'ASS.CUR.BNK',  // Balance sheet code for an expense account
          priority: 90,
          keywords: ['special'],
          keywordsAll: [],
          keywordsExclude: [],
          rawTypes: [],
          canonTypes: [],
          typeExclude: [],
        },
      ],
    };

    const accounts: Account[] = [
      {
        code: '500',
        name: 'Special Expense',
        type: 'Expense',
        canonType: 'expense',
      },
    ];

    const result = runPipeline({
      accounts,
      rulesData: badRulesData,
      templateEntries: [],
      systemMappings: SYSTEM_MAPPINGS,
      glSummary: [],
      industry: '',
      templateName: 'Company',
    });

    // Rule would assign ASS.CUR.BNK (BS group) but account is Expense (PL group)
    // Cross-head guard should revert to EXP fallback
    expect(result[0].predictedCode).toBe('EXP');
    expect(result[0].source).toBe('FallbackParent');
  });
});

describe('runPipeline + autoConfirm integration', () => {
  it('auto-approves compatible predicted===reportCode rows', () => {
    const input: PipelineInput = {
      accounts: [
        {
          code: '404',
          name: 'Bank Fees',
          type: 'Expense',
          canonType: 'expense',
          reportCode: 'EXP',
        },
      ],
      rulesData: { version: 1, updatedAt: '', dictionaries: {}, rules: [] },
      templateEntries: [],
      systemMappings: [],
      glSummary: [],
      industry: '',
      templateName: 'Company',
    };
    const out = runPipeline(input);
    expect(out[0].predictedCode).toBe('EXP');
    expect(out[0].approved).toBe(true);
    expect(out[0].auto).toBe(true);
  });
});
