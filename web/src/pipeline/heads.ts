/**
 * The five reporting-code heads used across the mapping pipeline.
 *
 * A reporting code is dot-separated (`HEAD.SUB.LEAF`), and the head
 * determines the account group:
 *   ASS = Asset
 *   LIA = Liability
 *   EQU = Equity
 *   REV = Revenue
 *   EXP = Expense
 */

export const REPORTING_HEADS = ['ASS', 'LIA', 'EQU', 'REV', 'EXP'] as const;

export type ReportingHead = (typeof REPORTING_HEADS)[number];

export const REPORTING_HEADS_SET: ReadonlySet<string> = new Set(REPORTING_HEADS);
