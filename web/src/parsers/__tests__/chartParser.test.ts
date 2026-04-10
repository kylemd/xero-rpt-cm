import { describe, it, expect } from 'vitest';
import { parseCSVText } from '../chartParser';

describe('parseCSVText', () => {
  it('parses a standard Xero CSV with Code, Name, Type columns', () => {
    const csv = [
      '*Code,*Name,*Type,*Tax Code',
      '200,Sales,Revenue,GST on Income',
      '400,Advertising,Expense,GST on Expenses',
      '610,Accounts Receivable,Current Asset,BAS Excluded',
    ].join('\n');

    const accounts = parseCSVText(csv);
    expect(accounts).toHaveLength(3);

    expect(accounts[0]).toEqual({
      code: '200',
      name: 'Sales',
      type: 'Revenue',
      canonType: 'revenue',
      reportCode: undefined,
      taxCode: 'GST on Income',
      description: undefined,
    });

    expect(accounts[1].canonType).toBe('expense');
    expect(accounts[2].type).toBe('Current Asset');
    expect(accounts[2].canonType).toBe('current asset');
  });

  it('detects alternative header names', () => {
    const csv = [
      'AccountCode,Account,Type,Reporting Code',
      '100,Main Bank Account,Bank,ASS.CUR.CAS.BAN',
    ].join('\n');

    const accounts = parseCSVText(csv);
    expect(accounts).toHaveLength(1);
    expect(accounts[0].code).toBe('100');
    expect(accounts[0].name).toBe('Main Bank Account');
    expect(accounts[0].reportCode).toBe('ASS.CUR.CAS.BAN');
  });

  it('handles quoted fields with commas', () => {
    const csv = [
      'Code,Name,Type,Description',
      '300,"Rent, Rates & Insurance",Expense,"Building rent, council rates"',
    ].join('\n');

    const accounts = parseCSVText(csv);
    expect(accounts).toHaveLength(1);
    expect(accounts[0].name).toBe('Rent, Rates & Insurance');
    expect(accounts[0].description).toBe('Building rent, council rates');
  });

  it('handles empty rows gracefully', () => {
    const csv = [
      'Code,Name,Type',
      '200,Sales,Revenue',
      '',
      '  ',
      '400,Expenses,Expense',
    ].join('\n');

    const accounts = parseCSVText(csv);
    expect(accounts).toHaveLength(2);
  });

  it('canonicalises Overhead type to expense', () => {
    const csv = [
      'Code,Name,Type',
      '500,Office Supplies,Overhead',
    ].join('\n');

    const accounts = parseCSVText(csv);
    expect(accounts[0].type).toBe('Overhead');
    expect(accounts[0].canonType).toBe('expense');
  });

  it('throws on missing required columns', () => {
    const csv = [
      'Foo,Bar,Baz',
      '1,2,3',
    ].join('\n');

    expect(() => parseCSVText(csv)).toThrow(/Could not detect required columns/);
  });

  it('returns empty array for a header-only file', () => {
    const csv = 'Code,Name,Type';
    const accounts = parseCSVText(csv);
    expect(accounts).toHaveLength(0);
  });

  it('handles CRLF line endings', () => {
    const csv = 'Code,Name,Type\r\n200,Sales,Revenue\r\n400,Expenses,Expense';
    const accounts = parseCSVText(csv);
    expect(accounts).toHaveLength(2);
  });
});
