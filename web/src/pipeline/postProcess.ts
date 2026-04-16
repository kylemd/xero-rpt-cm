/**
 * Post-processing passes that run after the main mapping waterfall.
 *
 * Ported from mapping_logic_v15.py post-processing logic.
 */

import type { MappedAccount } from '../types';
import { REPORTING_HEADS_SET } from './heads';
import { headFromType, headGroup, normalise } from './normalise';

// Sources that should be skipped by typeRangeCorrection
const SKIP_SOURCES = new Set([
  'DefaultChart',
  'AlreadyCorrect',
  'ExistingCodeValid',
  'ExistingCodeValidByName',
  'UserClarified',
]);

// ---------------------------------------------------------------------------
// serviceOnlyReclass
// ---------------------------------------------------------------------------

/**
 * If the client has no direct-cost accounts with activity, reclassify
 * all EXP.COS* accounts to plain EXP (they are service-only).
 *
 * Disabled for the construction industry where COGS is always relevant.
 */
export function serviceOnlyReclass(
  accounts: MappedAccount[],
  industry: string,
): void {
  if (industry.toLowerCase() === 'construction') return;

  // Check if any direct-cost account has activity
  const hasDirectCostActivity = accounts.some(
    (a) =>
      (a.predictedCode === 'EXP.COS' || a.predictedCode.startsWith('EXP.COS.')) &&
      a.hasActivity,
  );

  if (hasDirectCostActivity) return;

  // Reclassify all EXP.COS* to EXP
  for (const a of accounts) {
    if (a.predictedCode === 'EXP.COS' || a.predictedCode.startsWith('EXP.COS.')) {
      a.predictedCode = 'EXP';
      a.source = 'ServiceOnlyRevenueAdjustment';
      a.needsReview = true;
    }
  }
}

// ---------------------------------------------------------------------------
// autoIndustryReclass
// ---------------------------------------------------------------------------

const ACCUM_TOKENS = ['deprec', 'accumulated', 'amort', 'accum'];

/**
 * For auto dealers, reclassify EXP.VEH* (except accumulated depreciation
 * entries) to EXP.COS, since vehicle expenses are cost of sales.
 */
export function autoIndustryReclass(
  accounts: MappedAccount[],
  industry: string,
): void {
  if (industry.toLowerCase() !== 'auto') return;

  for (const a of accounts) {
    if (a.predictedCode === 'EXP.VEH' || a.predictedCode.startsWith('EXP.VEH.')) {
      // Skip accumulated depreciation entries
      const normName = normalise(a.name);
      if (ACCUM_TOKENS.some((tok) => normName.includes(tok))) continue;
      // Skip .ACC sub-codes (accumulated depreciation leaves)
      if (a.predictedCode.endsWith('.ACC')) continue;

      a.predictedCode = 'EXP.COS';
      a.source = 'AutoIndustryVehicleCOS';
      a.needsReview = true;
    }
  }
}

// ---------------------------------------------------------------------------
// typeRangeCorrection
// ---------------------------------------------------------------------------

/**
 * Ensure each account's assigned reporting code root matches the expected
 * head derived from its account type.
 *
 * If the code's root group (PL/BS/EQ) differs from the expected group,
 * correct the code to the expected head (for head-only codes and
 * FallbackParent) or flag for review (for specific leaf codes).
 *
 * Skips accounts whose source is in the trusted-source set.
 */
export function typeRangeCorrection(accounts: MappedAccount[]): void {
  for (const a of accounts) {
    if (SKIP_SOURCES.has(a.source)) continue;
    if (!a.predictedCode || !a.type) continue;

    const expectedHead = headFromType(a.type);
    const codeRoot = a.predictedCode.split('.')[0];
    const expectedRoot = expectedHead.split('.')[0];

    if (!expectedRoot || !codeRoot) continue;
    if (codeRoot === expectedRoot) continue;

    // Roots differ — check if they are in different groups
    const codeGroup = headGroup(a.predictedCode);
    const expectedGroup = headGroup(expectedHead);

    if (codeGroup === expectedGroup) continue;

    // Head-only codes or FallbackParent: correct to expected head
    if (REPORTING_HEADS_SET.has(a.predictedCode) || a.source === 'FallbackParent') {
      a.predictedCode = expectedHead;
      a.source = 'TypeRangeCorrection';
      a.needsReview = true;
    } else {
      // Specific leaf code in wrong group — flag for review but don't change
      a.needsReview = true;
    }
  }
}
