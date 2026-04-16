/**
 * Auto-confirm matches where the predicted reporting code equals the
 * account's original reporting code AND the account type is compatible
 * with that code at both head and sub-prefix levels.
 *
 * Pure: returns a new array; never mutates input.
 * Existing user decisions (overrideCode, explicit approved) are respected.
 */

import type { MappedAccount } from '../types';
import { hasTypeMismatch } from './typePredict';

export function autoConfirmMatches(
  accounts: MappedAccount[],
): MappedAccount[] {
  return accounts.map((a) => {
    if (a.overrideCode !== undefined) return a;
    if (a.approved !== undefined) return a;
    if (!a.reportCode) return a;
    if (a.predictedCode !== a.reportCode) return a;
    if (hasTypeMismatch(a.type, a.predictedCode)) return a;

    return { ...a, approved: true, auto: true };
  });
}
