# Verification Report Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the web app's two-file intake (Chart of Accounts + Chart Check Report) with a single Verification Report workbook, and close the UX gaps between the old HTML report and the current web UI (localStorage persistence, progress counters, status/source filters, reporting-name auto-derivation, prefix-level type mismatch, type-compatibility-aware auto-confirm, clear-all, import-safety banner).

**Architecture:** One new parser (`verificationReportParser.ts`) emits the same internal shapes the pipeline already consumes. A new persistence service (`decisionsStorage.ts`) scopes decisions to localStorage per client. Auto-confirm and reporting-name derivation are pure functions bolted onto the existing pipeline output. UI work is concentrated in `InputPanel.tsx`, `MappingTable.tsx`, and `AccountDetailPanel.tsx`.

**Tech Stack:** React 19, TypeScript, Zustand, TanStack Table, xlsx (SheetJS), Vitest.

**Design spec:** `docs/superpowers/specs/2026-04-16-verification-report-input-design.md`

---

## File Structure

### New files
- `web/src/parsers/verificationReportParser.ts` — workbook → `VerificationReportData`
- `web/src/parsers/__tests__/verificationReportParser.test.ts`
- `web/src/services/decisionsStorage.ts` — localStorage read/write, per-client scoping
- `web/src/services/__tests__/decisionsStorage.test.ts`
- `web/src/pipeline/autoConfirm.ts` — pure function: mark safe Auto rows approved
- `web/src/pipeline/__tests__/autoConfirm.test.ts`
- `web/src/pipeline/reportingName.ts` — pure function: ATO ICA / ITA / Div7A derivation
- `web/src/pipeline/__tests__/reportingName.test.ts`
- `web/src/pipeline/__tests__/typeMismatch.test.ts` — tests for the tighter mismatch check

### Modified files
- `web/src/types/index.ts` — add `activity`, `VerificationReportData`, `AccountDecision`
- `web/src/pipeline/typePredict.ts` — add `REQUIRED_PREFIX_BY_TYPE`, export `hasTypeMismatch`
- `web/src/pipeline/pipeline.ts` — invoke `autoConfirm` post-map
- `web/src/store/appStore.ts` — replace `accounts`/`chartCheckData` with `verificationReport`, add `decisionsByClient`, hydrate + persist actions
- `web/src/components/InputPanel.tsx` — single drop zone, safety banner, summary
- `web/src/components/MappingTable.tsx` — activity / status / source filters, progress counters, Clear All, tighter mismatch, Mandatory/Optional badge, deriveReportingName in export
- `web/src/components/AccountDetailPanel.tsx` — consume `verificationReport`, description lookup
- `mapping_logic_v15.py` — deprecation banner at top

### Deleted files
- `web/src/parsers/chartParser.ts`
- `web/src/parsers/chartCheckParser.ts`
- `web/src/parsers/__tests__/chartParser.test.ts`

---

## Task 1: Add new types

**Files:**
- Modify: `web/src/types/index.ts`

- [ ] **Step 1: Add `activity` to `Account` and new types for the parser + decisions**

In `web/src/types/index.ts`, update `Account` and add the new interfaces. After the existing `Account` interface (around line 3–11), replace it with the version below, then add the new interfaces below `ChartCheckData` (around line 108):

```ts
export interface Account {
  code: string;
  name: string;
  type: string;
  canonType: string;
  reportCode?: string;
  taxCode?: string;
  description?: string;
  activity?: 'mandatory' | 'optional';
  class?: string;
}

// ...existing MappedAccount, Rule, etc. stay unchanged...

// Verification Report

export interface VerificationReportData {
  accounts: Account[];
  clientParams: EntityParams;
  glSummary: GLEntry[];
  glSummaryComparative: GLEntry[];
  glSummaryConsidered: GLEntry[];
  depSchedule: DepAsset[];
  beneficiaryAccounts: BeneficiaryEntry[];
}

// Persisted per-account decision

export interface AccountDecision {
  overrideCode?: string;
  overrideReason?: string;
  typeOverride?: string;
  approved?: boolean;
  auto?: boolean;
}

export type DecisionMap = Record<string, AccountDecision>;

export interface ClientDecisionsFile {
  version: 1;
  clientKey: string;
  savedAt: string;
  decisions: DecisionMap;
}
```

- [ ] **Step 2: TypeScript check**

Run: `cd web && npx tsc --noEmit`
Expected: no errors. (Existing code will not reference the new fields yet.)

- [ ] **Step 3: Commit**

```bash
cd C:/Users/kyle/newDev/xero-report-code-mapper
git add web/src/types/index.ts
git commit -m "feat(web): add VerificationReportData, AccountDecision, Account.activity types"
```

---

## Task 2: Tighter type-mismatch helper

**Files:**
- Modify: `web/src/pipeline/typePredict.ts`
- Create: `web/src/pipeline/__tests__/typeMismatch.test.ts`

- [ ] **Step 1: Write the failing test**

Create `web/src/pipeline/__tests__/typeMismatch.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { hasTypeMismatch } from '../typePredict';

describe('hasTypeMismatch', () => {
  it('returns false for a system type regardless of code', () => {
    expect(hasTypeMismatch('Bank', 'REV.TRA.GOO')).toBe(false);
  });

  it('returns false when code head matches type head', () => {
    expect(hasTypeMismatch('Expense', 'EXP.REN')).toBe(false);
  });

  it('returns true when code head differs from type head', () => {
    expect(hasTypeMismatch('Expense', 'REV.TRA.GOO')).toBe(true);
  });

  it('returns true for Direct Costs + non-COS expense code (prefix mismatch)', () => {
    expect(hasTypeMismatch('Direct Costs', 'EXP.REN')).toBe(true);
  });

  it('returns false for Direct Costs + EXP.COS code', () => {
    expect(hasTypeMismatch('Direct Costs', 'EXP.COS.GOO')).toBe(false);
  });

  it('returns true for Fixed Asset + non-FIX asset code (prefix mismatch)', () => {
    expect(hasTypeMismatch('Fixed Asset', 'ASS.CUR.CAS.BAN')).toBe(true);
  });

  it('returns false for Fixed Asset + ASS.NCA.FIX.PLA code', () => {
    expect(hasTypeMismatch('Fixed Asset', 'ASS.NCA.FIX.PLA')).toBe(false);
  });

  it('returns true for Inventory + ASS.CUR.REC code (prefix mismatch)', () => {
    expect(hasTypeMismatch('Inventory', 'ASS.CUR.REC.TRA')).toBe(true);
  });

  it('returns true for Sales + REV.OTH code (prefix mismatch)', () => {
    expect(hasTypeMismatch('Sales', 'REV.OTH')).toBe(true);
  });

  it('returns false when code is empty', () => {
    expect(hasTypeMismatch('Expense', '')).toBe(false);
  });

  it('returns false when type is unknown', () => {
    expect(hasTypeMismatch('Widget', 'EXP.REN')).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/pipeline/__tests__/typeMismatch.test.ts`
Expected: FAIL with "hasTypeMismatch is not a function" or "Cannot read property 'hasTypeMismatch' of undefined".

- [ ] **Step 3: Implement `REQUIRED_PREFIX_BY_TYPE` and `hasTypeMismatch`**

In `web/src/pipeline/typePredict.ts`, append below `SYSTEM_TYPES`:

```ts
// ---------------------------------------------------------------------------
// Prefix-level constraints: types that require a specific code sub-prefix
// ---------------------------------------------------------------------------

export const REQUIRED_PREFIX_BY_TYPE: Record<string, string> = {
  'Direct Costs': 'EXP.COS',
  Depreciation: 'EXP.DEP',
  'Fixed Asset': 'ASS.NCA.FIX',
  Inventory: 'ASS.CUR.INY',
  Prepayment: 'ASS.CUR.REC.PRE',
  Revenue: 'REV.TRA',
  Sales: 'REV.TRA',
  'Current Asset': 'ASS.CUR',
  'Non-current Asset': 'ASS.NCA',
  'Current Liability': 'LIA.CUR',
  'Non-current Liability': 'LIA.NCL',
};

// ---------------------------------------------------------------------------
// Type-mismatch check (head + prefix level)
// ---------------------------------------------------------------------------

/**
 * Return true when the account's Xero type is incompatible with the
 * reporting code at either the head level or the required sub-prefix.
 *
 * System types (Bank, GST, etc.) are never flagged — they carry their own
 * typing rules and are locked on export.
 */
export function hasTypeMismatch(type: string, code: string): boolean {
  if (!code) return false;
  if (SYSTEM_TYPES.has(type)) return false;

  const upper = code.toUpperCase();
  const typeHead = HEAD_FROM_TYPE[type];
  if (!typeHead) return false;

  const codeHead = upper.split('.')[0];
  if (typeHead !== codeHead) return true;

  const requiredPrefix = REQUIRED_PREFIX_BY_TYPE[type];
  return !!requiredPrefix && !upper.startsWith(requiredPrefix);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npx vitest run src/pipeline/__tests__/typeMismatch.test.ts`
Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/pipeline/typePredict.ts web/src/pipeline/__tests__/typeMismatch.test.ts
git commit -m "feat(web): add REQUIRED_PREFIX_BY_TYPE and hasTypeMismatch with head+prefix checks"
```

---

## Task 3: Reporting name auto-derivation

**Files:**
- Create: `web/src/pipeline/reportingName.ts`
- Create: `web/src/pipeline/__tests__/reportingName.test.ts`

- [ ] **Step 1: Write the failing test**

Create `web/src/pipeline/__tests__/reportingName.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { deriveReportingName } from '../reportingName';

describe('deriveReportingName', () => {
  it('returns "ATO ICA" for ATO Integrated Client Account', () => {
    expect(deriveReportingName('ATO Integrated Client Account')).toBe('ATO ICA');
    expect(deriveReportingName('ATO ICA')).toBe('ATO ICA');
    expect(deriveReportingName('ato ica - 12345')).toBe('ATO ICA');
  });

  it('returns "ATO ITA" for ATO Income Tax Account', () => {
    expect(deriveReportingName('ATO Income Tax Account')).toBe('ATO ITA');
    expect(deriveReportingName('ATO ITA')).toBe('ATO ITA');
  });

  it('returns "Div7A <YYYY>" for Div7A names containing a year', () => {
    expect(deriveReportingName('Div7A Loan 2024')).toBe('Div7A 2024');
    expect(deriveReportingName('Division 7A 2023')).toBe('Div7A 2023');
    expect(deriveReportingName('Loan 7A - John Smith (2022)')).toBe('Div7A 2022');
  });

  it('returns null when no pattern matches', () => {
    expect(deriveReportingName('Bank Fees')).toBeNull();
    expect(deriveReportingName('')).toBeNull();
    expect(deriveReportingName('Div7A loan with no year')).toBeNull();
  });

  it('prefers the first 4-digit year when multiple exist', () => {
    expect(deriveReportingName('Div7A 2020-2021')).toBe('Div7A 2020');
  });

  it('ignores years outside 1900..2099', () => {
    expect(deriveReportingName('Div7A 1850 loan')).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/pipeline/__tests__/reportingName.test.ts`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `deriveReportingName`**

Create `web/src/pipeline/reportingName.ts`:

```ts
/**
 * Derive a canonical Reporting Name from an account name for known patterns.
 *
 * Patterns:
 * - ATO Integrated Client Account (or "ATO ICA") -> "ATO ICA"
 * - ATO Income Tax Account (or "ATO ITA") -> "ATO ITA"
 * - Div7A / Division 7A / 7A + a 4-digit year -> "Div7A <YYYY>"
 *
 * Returns null when no pattern matches.
 */
export function deriveReportingName(accountName: string): string | null {
  if (!accountName) return null;
  const s = accountName.trim();
  if (!s) return null;
  const lower = s.toLowerCase();

  if (/\bato\s+(ica|integrated\s+client\s+account)\b/.test(lower)) {
    return 'ATO ICA';
  }
  if (/\bato\s+(ita|income\s+tax\s+account)\b/.test(lower)) {
    return 'ATO ITA';
  }

  const isDiv7A =
    /\bdiv\s*7a\b/.test(lower) ||
    /\bdivision\s*7a\b/.test(lower) ||
    /\b7a\b/.test(lower);
  if (isDiv7A) {
    const yearMatch = s.match(/(19|20)\d{2}/);
    if (yearMatch) return `Div7A ${yearMatch[0]}`;
  }

  return null;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npx vitest run src/pipeline/__tests__/reportingName.test.ts`
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/pipeline/reportingName.ts web/src/pipeline/__tests__/reportingName.test.ts
git commit -m "feat(web): add deriveReportingName for ATO ICA/ITA/Div7A patterns"
```

---

## Task 4: Auto-confirm pure function

**Files:**
- Create: `web/src/pipeline/autoConfirm.ts`
- Create: `web/src/pipeline/__tests__/autoConfirm.test.ts`

- [ ] **Step 1: Write the failing test**

Create `web/src/pipeline/__tests__/autoConfirm.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { autoConfirmMatches } from '../autoConfirm';
import type { MappedAccount } from '../../types';

function makeAcct(partial: Partial<MappedAccount>): MappedAccount {
  return {
    code: '100',
    name: 'Test',
    type: 'Expense',
    canonType: 'expense',
    predictedCode: 'EXP',
    mappingName: 'Expense',
    source: 'FallbackParent',
    needsReview: false,
    hasActivity: true,
    closingBalance: 0,
    ...partial,
  };
}

describe('autoConfirmMatches', () => {
  it('marks head-compatible predicted===reportCode as auto-approved', () => {
    const accts = [
      makeAcct({ code: '404', reportCode: 'EXP', predictedCode: 'EXP', type: 'Expense' }),
    ];
    const out = autoConfirmMatches(accts);
    expect(out[0].approved).toBe(true);
    expect(out[0].auto).toBe(true);
  });

  it('does not mark when predicted !== reportCode', () => {
    const accts = [
      makeAcct({ code: '404', reportCode: 'EXP.REN', predictedCode: 'EXP', type: 'Expense' }),
    ];
    const out = autoConfirmMatches(accts);
    expect(out[0].approved).toBeUndefined();
    expect(out[0].auto).toBeUndefined();
  });

  it('does not mark when reportCode is empty', () => {
    const accts = [
      makeAcct({ code: '404', reportCode: undefined, predictedCode: 'EXP', type: 'Expense' }),
    ];
    const out = autoConfirmMatches(accts);
    expect(out[0].approved).toBeUndefined();
  });

  it('respects existing user decisions (overrideCode set)', () => {
    const accts = [
      makeAcct({
        code: '404',
        reportCode: 'EXP',
        predictedCode: 'EXP',
        overrideCode: 'EXP.REN',
      }),
    ];
    const out = autoConfirmMatches(accts);
    expect(out[0].approved).toBeUndefined();
  });

  it('respects existing approval', () => {
    const accts = [
      makeAcct({ code: '404', reportCode: 'EXP', predictedCode: 'EXP', approved: true, auto: false }),
    ];
    const out = autoConfirmMatches(accts);
    expect(out[0].auto).toBe(false); // untouched
  });

  it('does not mark when type has head-level mismatch', () => {
    const accts = [
      makeAcct({ code: '200', reportCode: 'EXP', predictedCode: 'EXP', type: 'Revenue' }),
    ];
    const out = autoConfirmMatches(accts);
    expect(out[0].approved).toBeUndefined();
  });

  it('does not mark when type has prefix-level mismatch (Direct Costs + EXP.REN)', () => {
    const accts = [
      makeAcct({
        code: '300',
        reportCode: 'EXP.REN',
        predictedCode: 'EXP.REN',
        type: 'Direct Costs',
      }),
    ];
    const out = autoConfirmMatches(accts);
    expect(out[0].approved).toBeUndefined();
  });

  it('marks system-typed accounts (Bank) without prefix check', () => {
    const accts = [
      makeAcct({
        code: '090',
        reportCode: 'ASS.CUR.CAS.BAN',
        predictedCode: 'ASS.CUR.CAS.BAN',
        type: 'Bank',
      }),
    ];
    const out = autoConfirmMatches(accts);
    expect(out[0].approved).toBe(true);
    expect(out[0].auto).toBe(true);
  });

  it('returns a new array and does not mutate input', () => {
    const original = makeAcct({ code: '404', reportCode: 'EXP', predictedCode: 'EXP' });
    const accts = [original];
    const out = autoConfirmMatches(accts);
    expect(out).not.toBe(accts);
    expect(original.approved).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/pipeline/__tests__/autoConfirm.test.ts`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `autoConfirmMatches`**

Create `web/src/pipeline/autoConfirm.ts`:

```ts
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
```

- [ ] **Step 4: Extend `MappedAccount` with `auto`**

In `web/src/types/index.ts`, add one field to `MappedAccount`:

```ts
export interface MappedAccount extends Account {
  predictedCode: string;
  mappingName: string;
  source: string;
  needsReview: boolean;
  hasActivity: boolean;
  closingBalance: number;
  correctedName?: string;
  overrideCode?: string;
  overrideReason?: string;
  approved?: boolean;
  auto?: boolean;
  typeOverride?: string;
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd web && npx vitest run src/pipeline/__tests__/autoConfirm.test.ts`
Expected: all 9 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/pipeline/autoConfirm.ts web/src/pipeline/__tests__/autoConfirm.test.ts web/src/types/index.ts
git commit -m "feat(web): add autoConfirmMatches with type-compatibility checks"
```

---

## Task 5: Decisions storage service

**Files:**
- Create: `web/src/services/decisionsStorage.ts`
- Create: `web/src/services/__tests__/decisionsStorage.test.ts`

- [ ] **Step 1: Write the failing test**

Create `web/src/services/__tests__/decisionsStorage.test.ts`:

```ts
import { describe, it, expect, beforeEach } from 'vitest';
import {
  deriveClientKey,
  loadDecisions,
  saveDecisions,
  clearDecisions,
  STORAGE_KEY_PREFIX,
} from '../decisionsStorage';
import type { DecisionMap } from '../../types';

// jsdom provides localStorage; clear it between tests
beforeEach(() => {
  localStorage.clear();
});

describe('deriveClientKey', () => {
  it('normalises display name to lowercase alphanumeric with underscores', () => {
    expect(deriveClientKey('Demo Company (AU)')).toBe('demo_company_au');
    expect(deriveClientKey('Smith & Co. Pty Ltd')).toBe('smith_co_pty_ltd');
  });

  it('returns a code-hash fallback when name is empty', () => {
    const key = deriveClientKey('', ['100', '200', '300']);
    expect(key).toMatch(/^codes_[a-z0-9]+$/);
    // Deterministic: same codes give the same key
    expect(deriveClientKey('', ['100', '200', '300'])).toBe(key);
  });

  it('returns different keys for different code sets', () => {
    const a = deriveClientKey('', ['100']);
    const b = deriveClientKey('', ['200']);
    expect(a).not.toBe(b);
  });
});

describe('saveDecisions / loadDecisions / clearDecisions', () => {
  it('round-trips a decision map for a given client', () => {
    const decisions: DecisionMap = {
      '404': { approved: true, auto: true },
      '200': { overrideCode: 'REV.TRA.GOO', overrideReason: 'user correction' },
    };
    saveDecisions('demo_company', decisions);
    expect(loadDecisions('demo_company')).toEqual(decisions);
  });

  it('returns an empty map when no data stored for the client', () => {
    expect(loadDecisions('unknown_client')).toEqual({});
  });

  it('scopes storage per client', () => {
    saveDecisions('client_a', { '100': { approved: true } });
    saveDecisions('client_b', { '100': { overrideCode: 'EXP' } });
    expect(loadDecisions('client_a')).toEqual({ '100': { approved: true } });
    expect(loadDecisions('client_b')).toEqual({ '100': { overrideCode: 'EXP' } });
  });

  it('clearDecisions removes only the target client', () => {
    saveDecisions('client_a', { '100': { approved: true } });
    saveDecisions('client_b', { '100': { overrideCode: 'EXP' } });
    clearDecisions('client_a');
    expect(loadDecisions('client_a')).toEqual({});
    expect(loadDecisions('client_b')).toEqual({ '100': { overrideCode: 'EXP' } });
  });

  it('writes under the versioned namespace', () => {
    saveDecisions('demo', { '100': { approved: true } });
    const raw = localStorage.getItem(`${STORAGE_KEY_PREFIX}demo`);
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw!);
    expect(parsed.version).toBe(1);
    expect(parsed.clientKey).toBe('demo');
    expect(parsed.decisions['100'].approved).toBe(true);
  });

  it('ignores malformed stored data', () => {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}broken`, '{not json');
    expect(loadDecisions('broken')).toEqual({});
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/services/__tests__/decisionsStorage.test.ts`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `decisionsStorage.ts`**

Create `web/src/services/decisionsStorage.ts`:

```ts
/**
 * Per-client decision persistence backed by localStorage.
 *
 * Storage key: `xrcm:decisions:v1:<clientKey>`
 * clientKey is derived from the entity display name, or from a hash of
 * account codes when no display name is available.
 */

import type { ClientDecisionsFile, DecisionMap } from '../types';

export const STORAGE_KEY_PREFIX = 'xrcm:decisions:v1:';

/**
 * FNV-1a 32-bit hash, base36-encoded. Stable across sessions.
 */
function hashCodes(codes: string[]): string {
  let h = 0x811c9dc5;
  for (const code of codes) {
    for (let i = 0; i < code.length; i++) {
      h ^= code.charCodeAt(i);
      h = Math.imul(h, 0x01000193);
    }
    h ^= 0x7c;
  }
  return (h >>> 0).toString(36);
}

export function deriveClientKey(displayName: string, codes: string[] = []): string {
  const normalized = displayName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
  if (normalized) return normalized;
  return `codes_${hashCodes(codes)}`;
}

export function loadDecisions(clientKey: string): DecisionMap {
  if (!clientKey) return {};
  try {
    const raw = localStorage.getItem(`${STORAGE_KEY_PREFIX}${clientKey}`);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as ClientDecisionsFile;
    if (parsed?.version !== 1 || !parsed.decisions) return {};
    return parsed.decisions;
  } catch {
    return {};
  }
}

export function saveDecisions(clientKey: string, decisions: DecisionMap): void {
  if (!clientKey) return;
  const payload: ClientDecisionsFile = {
    version: 1,
    clientKey,
    savedAt: new Date().toISOString(),
    decisions,
  };
  try {
    localStorage.setItem(
      `${STORAGE_KEY_PREFIX}${clientKey}`,
      JSON.stringify(payload),
    );
  } catch {
    // Quota exceeded or localStorage unavailable — silently drop.
  }
}

export function clearDecisions(clientKey: string): void {
  if (!clientKey) return;
  try {
    localStorage.removeItem(`${STORAGE_KEY_PREFIX}${clientKey}`);
  } catch {
    // noop
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npx vitest run src/services/__tests__/decisionsStorage.test.ts`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/services/decisionsStorage.ts web/src/services/__tests__/decisionsStorage.test.ts
git commit -m "feat(web): add per-client decisions storage service"
```

---

## Task 6: Verification Report parser — sheet helpers and Type-and-Class

**Files:**
- Create: `web/src/parsers/verificationReportParser.ts`
- Create: `web/src/parsers/__tests__/verificationReportParser.test.ts`

- [ ] **Step 1: Write the failing test**

Create `web/src/parsers/__tests__/verificationReportParser.test.ts`. Start with the helper + Type-and-Class cases (the full test file will grow in later tasks):

```ts
import { describe, it, expect } from 'vitest';
import * as XLSX from 'xlsx';
import {
  findRequiredSheet,
  parseTypeAndClassSheet,
  REQUIRED_SHEET_PREFIXES,
} from '../verificationReportParser';

function makeWorkbook(
  sheets: Record<string, (string | number | null)[][]>,
): XLSX.WorkBook {
  const wb = XLSX.utils.book_new();
  for (const [name, data] of Object.entries(sheets)) {
    const ws = XLSX.utils.aoa_to_sheet(data);
    XLSX.utils.book_append_sheet(wb, ws, name);
  }
  return wb;
}

describe('findRequiredSheet', () => {
  it('finds a sheet by its truncated prefix', () => {
    const wb = makeWorkbook({ 'Chart of Accounts - Type and...': [['x']] });
    const sheet = findRequiredSheet(wb, 'Chart of Accounts - Type and');
    expect(sheet).toBeDefined();
  });

  it('is case-insensitive', () => {
    const wb = makeWorkbook({ 'Chart of Accounts - Type AND...': [['x']] });
    const sheet = findRequiredSheet(wb, 'chart of accounts - type and');
    expect(sheet).toBeDefined();
  });

  it('returns undefined when no sheet matches', () => {
    const wb = makeWorkbook({ 'Other Sheet': [['x']] });
    expect(findRequiredSheet(wb, 'Chart of Accounts - Reportin')).toBeUndefined();
  });

  it('exposes the full list of required prefixes', () => {
    expect(REQUIRED_SHEET_PREFIXES).toContain('Chart of Accounts - Reportin');
    expect(REQUIRED_SHEET_PREFIXES).toContain('Chart of Accounts - Type and');
    expect(REQUIRED_SHEET_PREFIXES).toContain('Account Movements - Current');
    expect(REQUIRED_SHEET_PREFIXES).toContain('Account Movements - Comparat');
    expect(REQUIRED_SHEET_PREFIXES).toContain('Account Movements - Consider');
    expect(REQUIRED_SHEET_PREFIXES).toContain('Depreciation Schedule');
    expect(REQUIRED_SHEET_PREFIXES).toContain('Beneficiary Accounts');
    expect(REQUIRED_SHEET_PREFIXES).toContain('Client File Parameters Report');
  });
});

describe('parseTypeAndClassSheet', () => {
  it('parses accounts from the Type and Class grid', () => {
    const wb = makeWorkbook({
      'Chart of Accounts - Type and...': [
        ['Chart of Accounts - Type and Class'],
        ['Demo Company (AU)'],
        ['As at 30 June 2026'],
        [],
        ['Account Code', 'Account', 'Account Type', 'Account Class'],
        ['200', 'Sales', 'Revenue', 'Revenue'],
        ['090', 'Business Bank Account', 'Bank', 'Asset'],
        ['Total', null, null, null],
      ],
    });
    const sheet = findRequiredSheet(wb, 'Chart of Accounts - Type and')!;
    const map = parseTypeAndClassSheet(sheet);
    expect(map.size).toBe(2);
    expect(map.get('200')).toEqual({
      code: '200',
      name: 'Sales',
      type: 'Revenue',
      class: 'Revenue',
    });
    expect(map.get('090')).toEqual({
      code: '090',
      name: 'Business Bank Account',
      type: 'Bank',
      class: 'Asset',
    });
  });

  it('ignores the trailing Total row', () => {
    const wb = makeWorkbook({
      'Chart of Accounts - Type and...': [
        ['Chart of Accounts - Type and Class'],
        [],
        [],
        [],
        ['Account Code', 'Account', 'Account Type', 'Account Class'],
        ['100', 'X', 'Expense', 'Expense'],
        ['Total', '', '', ''],
      ],
    });
    const sheet = findRequiredSheet(wb, 'Chart of Accounts - Type and')!;
    const map = parseTypeAndClassSheet(sheet);
    expect(map.size).toBe(1);
    expect(map.get('Total')).toBeUndefined();
  });

  it('tolerates empty rows between data rows', () => {
    const wb = makeWorkbook({
      'Chart of Accounts - Type and...': [
        ['Chart of Accounts - Type and Class'],
        [],
        [],
        [],
        ['Account Code', 'Account', 'Account Type', 'Account Class'],
        ['100', 'X', 'Expense', 'Expense'],
        [null, null, null, null],
        ['200', 'Y', 'Revenue', 'Revenue'],
      ],
    });
    const sheet = findRequiredSheet(wb, 'Chart of Accounts - Type and')!;
    const map = parseTypeAndClassSheet(sheet);
    expect(map.size).toBe(2);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/parsers/__tests__/verificationReportParser.test.ts`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement helpers + `parseTypeAndClassSheet`**

Create `web/src/parsers/verificationReportParser.ts`:

```ts
/**
 * Chart of Accounts Verification Report parser.
 *
 * Parses the multi-sheet workbook Xero emits as the single consolidated
 * input, producing every shape the downstream pipeline consumes.
 *
 * Sheet names are truncated by Xero's export; they are stable, so we match
 * on the truncated prefix. The full name lives in cell A1 of each sheet
 * and is only used for error messages.
 */

import * as XLSX from 'xlsx';
import type {
  VerificationReportData,
  Account,
  GLEntry,
  DepAsset,
  EntityParams,
  BeneficiaryEntry,
} from '../types';
import { canonicalType } from '../pipeline/normalise';

// ---------------------------------------------------------------------------
// Required sheets
// ---------------------------------------------------------------------------

export const REQUIRED_SHEET_PREFIXES = [
  'Client File Parameters Report',
  'Chart of Accounts - Reportin',
  'Chart of Accounts - Type and',
  'Account Movements - Current',
  'Account Movements - Comparat',
  'Account Movements - Consider',
  'Depreciation Schedule',
  'Beneficiary Accounts',
] as const;

export function findRequiredSheet(
  wb: XLSX.WorkBook,
  prefix: string,
): XLSX.WorkSheet | undefined {
  const lower = prefix.toLowerCase();
  const name = wb.SheetNames.find((n) => n.toLowerCase().startsWith(lower));
  return name ? wb.Sheets[name] : undefined;
}

// ---------------------------------------------------------------------------
// Shared row helpers
// ---------------------------------------------------------------------------

type Row = (string | number | null | undefined)[];

function sheetRows(sheet: XLSX.WorkSheet): Row[] {
  return XLSX.utils.sheet_to_json<Row>(sheet, { header: 1, defval: null });
}

function cellStr(v: unknown): string {
  if (v === null || v === undefined) return '';
  return String(v).trim();
}

function cellNum(v: unknown): number {
  if (v === null || v === undefined || v === '') return 0;
  if (typeof v === 'number') return v;
  const s = String(v).trim().replace(/,/g, '');
  const isNeg = s.startsWith('(') && s.endsWith(')');
  const n = parseFloat(isNeg ? s.slice(1, -1) : s);
  if (isNaN(n)) return 0;
  return isNeg ? -n : n;
}

// ---------------------------------------------------------------------------
// Chart of Accounts - Type and Class
// ---------------------------------------------------------------------------

export interface TypeClassEntry {
  code: string;
  name: string;
  type: string;
  class: string;
}

export function parseTypeAndClassSheet(
  sheet: XLSX.WorkSheet,
): Map<string, TypeClassEntry> {
  const rows = sheetRows(sheet);
  const out = new Map<string, TypeClassEntry>();

  // Find the header row (first row starting with "Account Code")
  let headerIdx = -1;
  for (let i = 0; i < rows.length; i++) {
    if (cellStr(rows[i][0]).toLowerCase() === 'account code') {
      headerIdx = i;
      break;
    }
  }
  if (headerIdx < 0) return out;

  for (let i = headerIdx + 1; i < rows.length; i++) {
    const row = rows[i];
    const code = cellStr(row[0]);
    if (!code) continue;
    if (code.toLowerCase() === 'total') continue;
    const name = cellStr(row[1]);
    const type = cellStr(row[2]);
    const cls = cellStr(row[3]);
    out.set(code, { code, name, type, class: cls });
  }
  return out;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npx vitest run src/parsers/__tests__/verificationReportParser.test.ts`
Expected: all tests PASS (4 `findRequiredSheet` + 3 `parseTypeAndClassSheet`).

- [ ] **Step 5: Commit**

```bash
git add web/src/parsers/verificationReportParser.ts web/src/parsers/__tests__/verificationReportParser.test.ts
git commit -m "feat(web): verification-report parser — sheet helpers + Type and Class"
```

---

## Task 7: Verification Report parser — Reporting Codes sheet

**Files:**
- Modify: `web/src/parsers/verificationReportParser.ts`
- Modify: `web/src/parsers/__tests__/verificationReportParser.test.ts`

- [ ] **Step 1: Write the failing test**

Append to `web/src/parsers/__tests__/verificationReportParser.test.ts`:

```ts
import { parseReportingCodesSheet } from '../verificationReportParser';

describe('parseReportingCodesSheet', () => {
  it('extracts code + name + reporting code from grouped rows', () => {
    const wb = makeWorkbook({
      'Chart of Accounts - Reportin...': [
        ['Chart of Accounts - Reporting Codes'],
        [],
        [],
        [],
        [null, 'Account', '2026', '2025', '2024', '2023', '2022', '2021'],
        [],
        ['Chart of Accounts'],
        [null, 'ASS.CUR.CAS.BAN'],
        [null, '090 - Business Bank Account', -17849.87, -8703.2, 0, 0, 0, 0],
        [null, '091 - Business Savings Account', 6878.28, 0, 0, 0, 0, 0],
        [null, 'Total ASS.CUR.CAS.BAN', 0, 0, 0, 0, 0, 0],
        [null, 'REV.TRA.GOO'],
        [null, '200 - Sales', -53378.32, -4200.0, 0, 0, 0, 0],
        [null, 'Total REV.TRA.GOO', 0, 0, 0, 0, 0, 0],
        ['Total Chart of Accounts', null, 0, 0, 0, 0, 0, 0],
      ],
    });
    const sheet = findRequiredSheet(wb, 'Chart of Accounts - Reportin')!;
    const rows = parseReportingCodesSheet(sheet);
    expect(rows).toEqual([
      { code: '090', name: 'Business Bank Account', reportCode: 'ASS.CUR.CAS.BAN', currentBalance: -17849.87 },
      { code: '091', name: 'Business Savings Account', reportCode: 'ASS.CUR.CAS.BAN', currentBalance: 6878.28 },
      { code: '200', name: 'Sales', reportCode: 'REV.TRA.GOO', currentBalance: -53378.32 },
    ]);
  });

  it('keeps rows without a numeric code prefix (e.g. unnumbered bank accounts)', () => {
    const wb = makeWorkbook({
      'Chart of Accounts - Reportin...': [
        ['Chart of Accounts - Reporting Codes'],
        [],
        [],
        [],
        [null, 'Account', '2026'],
        [],
        ['Chart of Accounts'],
        [null, 'ASS.CUR.CAS.BAN'],
        [null, 'Old Bank', 100],
        [null, 'Total ASS.CUR.CAS.BAN', 0],
      ],
    });
    const sheet = findRequiredSheet(wb, 'Chart of Accounts - Reportin')!;
    const rows = parseReportingCodesSheet(sheet);
    expect(rows).toEqual([
      { code: '', name: 'Old Bank', reportCode: 'ASS.CUR.CAS.BAN', currentBalance: 100 },
    ]);
  });

  it('skips the grand Total Chart of Accounts row', () => {
    const wb = makeWorkbook({
      'Chart of Accounts - Reportin...': [
        ['Chart of Accounts - Reporting Codes'],
        [],
        [],
        [],
        [null, 'Account', '2026'],
        [],
        ['Chart of Accounts'],
        [null, 'EXP'],
        [null, '400 - Advertising', 500],
        [null, 'Total EXP', 0],
        ['Total Chart of Accounts', null, 0],
      ],
    });
    const sheet = findRequiredSheet(wb, 'Chart of Accounts - Reportin')!;
    const rows = parseReportingCodesSheet(sheet);
    expect(rows.map((r) => r.code)).toEqual(['400']);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/parsers/__tests__/verificationReportParser.test.ts -t parseReportingCodesSheet`
Expected: FAIL — `parseReportingCodesSheet is not exported`.

- [ ] **Step 3: Implement `parseReportingCodesSheet`**

Append to `web/src/parsers/verificationReportParser.ts`:

```ts
// ---------------------------------------------------------------------------
// Chart of Accounts - Reporting Codes
// ---------------------------------------------------------------------------

export interface ReportingCodeRow {
  code: string;
  name: string;
  reportCode: string;
  currentBalance: number;
}

// Matches "NNN - Name" where NNN is any non-space token (alphanumeric).
const CODE_NAME_RE = /^(\S+)\s*-\s*(.+)$/;

// Reporting-code group header: starts with a known head.
const KNOWN_HEADS = new Set(['ASS', 'LIA', 'EQU', 'REV', 'EXP']);

function isGroupHeader(row: Row): string | null {
  const a = cellStr(row[0]);
  const b = cellStr(row[1]);
  if (a) return null; // group headers have col A empty
  if (!b) return null;
  if (b.toLowerCase().startsWith('total ')) return null;
  if (b.toLowerCase() === 'account') return null;
  const head = b.split('.')[0];
  if (!KNOWN_HEADS.has(head)) return null;
  return b;
}

function isAccountRow(row: Row): boolean {
  const a = cellStr(row[0]);
  const b = cellStr(row[1]);
  if (a) return false;
  if (!b) return false;
  if (b.toLowerCase().startsWith('total ')) return false;
  if (b.toLowerCase() === 'account') return false;
  const head = b.split('.')[0];
  if (KNOWN_HEADS.has(head)) return false; // that's a group header
  return true;
}

export function parseReportingCodesSheet(
  sheet: XLSX.WorkSheet,
): ReportingCodeRow[] {
  const rows = sheetRows(sheet);
  const out: ReportingCodeRow[] = [];
  let currentReportCode = '';

  for (const row of rows) {
    const topTotal = cellStr(row[0]);
    if (topTotal.toLowerCase().startsWith('total chart of accounts')) {
      break; // end of data
    }
    const header = isGroupHeader(row);
    if (header) {
      currentReportCode = header;
      continue;
    }
    if (!isAccountRow(row)) continue;
    if (!currentReportCode) continue;

    const text = cellStr(row[1]);
    const m = text.match(CODE_NAME_RE);
    let code = '';
    let name = text;
    if (m) {
      code = m[1].trim();
      name = m[2].trim();
    }
    const currentBalance = cellNum(row[2]);
    out.push({ code, name, reportCode: currentReportCode, currentBalance });
  }
  return out;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npx vitest run src/parsers/__tests__/verificationReportParser.test.ts`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/parsers/verificationReportParser.ts web/src/parsers/__tests__/verificationReportParser.test.ts
git commit -m "feat(web): verification-report parser — Reporting Codes sheet"
```

---

## Task 8: Verification Report parser — orchestrator (merge, archive filter, activity tag)

**Files:**
- Modify: `web/src/parsers/verificationReportParser.ts`
- Modify: `web/src/parsers/__tests__/verificationReportParser.test.ts`

- [ ] **Step 1: Write the failing test**

Append to `web/src/parsers/__tests__/verificationReportParser.test.ts`:

```ts
import { parseVerificationReportFromWorkbook } from '../verificationReportParser';

function makeFullDemoWorkbook(): XLSX.WorkBook {
  return makeWorkbook({
    'Client File Parameters Report': [
      ['Client File Parameters Report'],
      ['Demo Company (AU)'],
      ['For the year ended 30 June 2026'],
    ],
    'Chart of Accounts - Reportin...': [
      ['Chart of Accounts - Reporting Codes'],
      [], [], [],
      [null, 'Account', '2026'],
      [],
      ['Chart of Accounts'],
      [null, 'ASS.CUR.CAS.BAN'],
      [null, '090 - Business Bank Account', -17849],
      [null, '091 - Business Savings Account', 6878],
      [null, 'Total ASS.CUR.CAS.BAN', 0],
      [null, 'EXP'],
      [null, '400 - Advertising', 500],
      [null, '404 - Bank Fees', 0],
      [null, 'Total EXP', 0],
      [null, 'EQU.RET.CUR'],
      [null, 'Current Year Earnings', 1234],
      [null, 'Total EQU.RET.CUR', 0],
      ['Total Chart of Accounts', null, 0],
    ],
    'Chart of Accounts - Type and...': [
      ['Chart of Accounts - Type and Class'],
      [], [], [],
      ['Account Code', 'Account', 'Account Type', 'Account Class'],
      ['090', 'Business Bank Account', 'Bank', 'Asset'],
      ['091', 'Business Savings Account', 'Bank', 'Asset'],
      ['400', 'Advertising', 'Expense', 'Expense'],
      ['404', 'Bank Fees', 'Expense', 'Expense'],
      ['CURRADJUST', 'Currency Adjustment', 'Bank', 'Asset'],
      ['Total', null, null, null],
    ],
    'Account Movements - Current FY': [
      ['Account Movements - Current FY'], [], [], [],
      ['Account', 'Account Code', 'Opening Balance', 'Debit', 'Credit', 'Net Movement', 'Closing Balance', 'Account Type'],
      ['Business Bank Account', '090', 0, 100, 200, -100, -17849, 'Bank'],
      ['Advertising', '400', 0, 500, 0, 500, 500, 'Expense'],
      ['Total', null, 0, 0, 0, 0, 0, null],
    ],
    'Account Movements - Comparative': [
      ['Account Movements - Comparative'], [], [], [],
      ['Account', 'Account Code', 'Opening Balance', 'Debit', 'Credit', 'Net Movement', 'Closing Balance', 'Account Type'],
      ['Business Bank Account', '090', 0, 100, 200, -100, -17849, 'Bank'],
      ['Advertising', '400', 0, 500, 0, 500, 500, 'Expense'],
      ['Total', null, 0, 0, 0, 0, 0, null],
    ],
    'Account Movements - Considered Active': [
      ['Account Movements - Considered Active'], [], [], [],
      ['Account', 'Account Code', 'Opening Balance', 'Debit', 'Credit', 'Net Movement', 'Closing Balance', 'Account Type'],
      ['Business Bank Account', '090', 0, 100, 200, -100, -17849, 'Bank'],
      ['Business Savings Account', '091', 0, 50, 0, 50, 6878, 'Bank'],
      ['Advertising', '400', 0, 500, 0, 500, 500, 'Expense'],
      ['Total', null, 0, 0, 0, 0, 0, null],
    ],
    'Depreciation Schedule': [
      ['Depreciation Schedule'],
      ['Demo Company (AU)'],
      ['For the year ended 30 June 2026'],
    ],
    'Beneficiary Accounts': [
      ['Beneficiary Accounts'],
      ['Demo Company (AU)'],
      ['For the year ended 30 June 2026'],
    ],
  });
}

describe('parseVerificationReportFromWorkbook', () => {
  it('throws when a required sheet is missing', () => {
    const wb = makeFullDemoWorkbook();
    delete (wb.Sheets as Record<string, unknown>)['Beneficiary Accounts'];
    wb.SheetNames = wb.SheetNames.filter((n) => n !== 'Beneficiary Accounts');
    expect(() => parseVerificationReportFromWorkbook(wb)).toThrowError(
      /Beneficiary Accounts/i,
    );
  });

  it('parses a full demo workbook', () => {
    const wb = makeFullDemoWorkbook();
    const data = parseVerificationReportFromWorkbook(wb);
    expect(data.clientParams.displayName).toBe('Demo Company (AU)');
    // Current Year Earnings has no code on Type and Class -> excluded.
    // CURRADJUST is on Type and Class but not on Reporting Codes -> excluded.
    // 404 Bank Fees: not in Considered -> archived.
    expect(data.accounts.map((a) => a.code).sort()).toEqual(['090', '091', '400']);
  });

  it('tags accounts as mandatory when present in Comparative', () => {
    const wb = makeFullDemoWorkbook();
    const data = parseVerificationReportFromWorkbook(wb);
    const bank = data.accounts.find((a) => a.code === '090');
    expect(bank?.activity).toBe('mandatory');
    const advertising = data.accounts.find((a) => a.code === '400');
    expect(advertising?.activity).toBe('mandatory');
  });

  it('tags accounts as optional when in Considered but not Comparative', () => {
    const wb = makeFullDemoWorkbook();
    const data = parseVerificationReportFromWorkbook(wb);
    const savings = data.accounts.find((a) => a.code === '091');
    expect(savings?.activity).toBe('optional');
  });

  it('fills type and class from the Type and Class sheet', () => {
    const wb = makeFullDemoWorkbook();
    const data = parseVerificationReportFromWorkbook(wb);
    const advertising = data.accounts.find((a) => a.code === '400');
    expect(advertising?.type).toBe('Expense');
    expect(advertising?.class).toBe('Expense');
    expect(advertising?.reportCode).toBe('EXP');
    expect(advertising?.canonType).toBe('expense');
  });

  it('populates glSummary, glSummaryComparative, glSummaryConsidered from their sheets', () => {
    const wb = makeFullDemoWorkbook();
    const data = parseVerificationReportFromWorkbook(wb);
    expect(data.glSummary.map((g) => g.accountCode)).toEqual(['090', '400']);
    expect(data.glSummaryComparative.map((g) => g.accountCode)).toEqual(['090', '400']);
    expect(data.glSummaryConsidered.map((g) => g.accountCode)).toEqual(['090', '091', '400']);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run src/parsers/__tests__/verificationReportParser.test.ts -t parseVerificationReportFromWorkbook`
Expected: FAIL — function not exported.

- [ ] **Step 3: Implement the orchestrator**

Append to `web/src/parsers/verificationReportParser.ts`:

```ts
// ---------------------------------------------------------------------------
// Client File Parameters
// ---------------------------------------------------------------------------

function parseClientParams(sheet: XLSX.WorkSheet): EntityParams {
  const rows = sheetRows(sheet);
  const defaults: EntityParams = {
    displayName: '',
    legalName: '',
    abn: '',
    directors: [],
    trustees: [],
    signatories: [],
  };
  // Title is row 0; display name is typically row 1 (entity name).
  if (rows[1]) defaults.displayName = cellStr(rows[1][0]);

  // Key-value lines embedded in the sheet (JSON-ish).
  for (const row of rows) {
    const raw = cellStr(row[0]);
    const m = raw.match(/"([A-Z_]+)"\s*:\s*(.+?),?\s*$/);
    if (!m) continue;
    const key = m[1];
    const value = m[2].trim().replace(/^"|"$|,$/g, '');
    switch (key) {
      case 'DISPLAY_NAME':
        if (value) defaults.displayName = value;
        break;
      case 'LEGAL_OR_TRADING_NAME':
      case 'LEGAL_NAME':
        defaults.legalName = value;
        break;
      case 'AUSTRALIAN_BUSINESS_NUMBER':
      case 'ABN':
        defaults.abn = value;
        break;
      default:
        break;
    }
  }
  return defaults;
}

// ---------------------------------------------------------------------------
// Account Movements (GL Summary)
// ---------------------------------------------------------------------------

function parseMovementSheet(sheet: XLSX.WorkSheet): GLEntry[] {
  const rows = sheetRows(sheet);
  let headerIdx = -1;
  for (let i = 0; i < rows.length; i++) {
    if (cellStr(rows[i][0]).toLowerCase() === 'account') {
      headerIdx = i;
      break;
    }
  }
  if (headerIdx < 0) return [];

  const out: GLEntry[] = [];
  for (let i = headerIdx + 1; i < rows.length; i++) {
    const row = rows[i];
    const name = cellStr(row[0]);
    if (!name) continue;
    if (name.toLowerCase() === 'total') continue;
    out.push({
      accountName: name,
      accountCode: cellStr(row[1]),
      openingBalance: cellNum(row[2]),
      debit: cellNum(row[3]),
      credit: cellNum(row[4]),
      netMovement: cellNum(row[5]),
      closingBalance: cellNum(row[6]),
      accountType: cellStr(row[7]),
    });
  }
  return out;
}

// ---------------------------------------------------------------------------
// Depreciation Schedule
// ---------------------------------------------------------------------------

function parseDepreciationSchedule(sheet: XLSX.WorkSheet): DepAsset[] {
  const rows = sheetRows(sheet);
  let headerIdx = -1;
  for (let i = 0; i < rows.length; i++) {
    if (cellStr(rows[i][0]).toLowerCase() === 'cost account') {
      headerIdx = i;
      break;
    }
  }
  if (headerIdx < 0) return [];

  const out: DepAsset[] = [];
  for (let i = headerIdx + 1; i < rows.length; i++) {
    const row = rows[i];
    const costAccount = cellStr(row[0]);
    if (!costAccount) continue;
    if (costAccount.toLowerCase() === 'total') continue;
    out.push({
      costAccount,
      name: cellStr(row[1]),
      assetNumber: cellStr(row[2]),
      assetType: cellStr(row[3]),
      expenseAccount: cellStr(row[5]),
      accumDepAccount: cellStr(row[6]),
      cost: cellNum(row[7]),
      closingAccumDep: cellNum(row[13]),
      closingValue: cellNum(row[14]),
    });
  }
  return out;
}

// ---------------------------------------------------------------------------
// Beneficiary Accounts
// ---------------------------------------------------------------------------

function parseBeneficiaryAccounts(sheet: XLSX.WorkSheet): BeneficiaryEntry[] {
  const rows = sheetRows(sheet);
  let headerIdx = -1;
  for (let i = 0; i < rows.length; i++) {
    if (cellStr(rows[i][0]).toLowerCase().startsWith('account code')) {
      headerIdx = i;
      break;
    }
  }
  if (headerIdx < 0) return [];

  const out: BeneficiaryEntry[] = [];
  for (let i = headerIdx + 1; i < rows.length; i++) {
    const row = rows[i];
    const code = cellStr(row[0]);
    if (!code) continue;
    out.push({
      accountCode: code,
      accountName: cellStr(row[1]),
      beneficiaryName: cellStr(row[2]),
    });
  }
  return out;
}

// ---------------------------------------------------------------------------
// Merge + archive-filter + activity-tag
// ---------------------------------------------------------------------------

function normaliseNameKey(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, ' ');
}

function mergeAccounts(
  reportingRows: ReportingCodeRow[],
  typeClassMap: Map<string, TypeClassEntry>,
  comparative: GLEntry[],
  considered: GLEntry[],
): Account[] {
  // Build name-based lookups for fallback matching.
  const typeClassByName = new Map<string, TypeClassEntry>();
  for (const entry of typeClassMap.values()) {
    typeClassByName.set(normaliseNameKey(entry.name), entry);
  }

  const comparativeCodes = new Set<string>();
  const comparativeNames = new Set<string>();
  for (const g of comparative) {
    if (g.accountCode) comparativeCodes.add(g.accountCode);
    if (g.accountName) comparativeNames.add(normaliseNameKey(g.accountName));
  }
  const consideredCodes = new Set<string>();
  const consideredNames = new Set<string>();
  for (const g of considered) {
    if (g.accountCode) consideredCodes.add(g.accountCode);
    if (g.accountName) consideredNames.add(normaliseNameKey(g.accountName));
  }

  const out: Account[] = [];
  for (const row of reportingRows) {
    // Match against Type and Class — by code, falling back to name.
    const match = row.code
      ? typeClassMap.get(row.code)
      : typeClassByName.get(normaliseNameKey(row.name));
    if (!match) continue; // system-level / excluded

    const nameKey = normaliseNameKey(row.name);
    const inConsidered =
      (row.code && consideredCodes.has(row.code)) || consideredNames.has(nameKey);
    if (!inConsidered) continue; // archive

    const inComparative =
      (row.code && comparativeCodes.has(row.code)) || comparativeNames.has(nameKey);

    out.push({
      code: row.code || match.code,
      name: row.name,
      type: match.type,
      canonType: canonicalType(match.type),
      reportCode: row.reportCode,
      class: match.class,
      activity: inComparative ? 'mandatory' : 'optional',
    });
  }
  return out;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function parseVerificationReportFromWorkbook(
  wb: XLSX.WorkBook,
): VerificationReportData {
  // Validate all required sheets exist.
  for (const prefix of REQUIRED_SHEET_PREFIXES) {
    if (!findRequiredSheet(wb, prefix)) {
      throw new Error(
        `Missing required sheet "${prefix}…". This file does not look like a Chart of Accounts Verification Report.`,
      );
    }
  }

  const paramsSheet = findRequiredSheet(wb, 'Client File Parameters Report')!;
  const reportingSheet = findRequiredSheet(wb, 'Chart of Accounts - Reportin')!;
  const typeAndClassSheet = findRequiredSheet(wb, 'Chart of Accounts - Type and')!;
  const currentSheet = findRequiredSheet(wb, 'Account Movements - Current')!;
  const comparativeSheet = findRequiredSheet(wb, 'Account Movements - Comparat')!;
  const consideredSheet = findRequiredSheet(wb, 'Account Movements - Consider')!;
  const depSheet = findRequiredSheet(wb, 'Depreciation Schedule')!;
  const benSheet = findRequiredSheet(wb, 'Beneficiary Accounts')!;

  const clientParams = parseClientParams(paramsSheet);
  const typeClassMap = parseTypeAndClassSheet(typeAndClassSheet);
  const reportingRows = parseReportingCodesSheet(reportingSheet);
  const glSummary = parseMovementSheet(currentSheet);
  const glSummaryComparative = parseMovementSheet(comparativeSheet);
  const glSummaryConsidered = parseMovementSheet(consideredSheet);
  const depSchedule = parseDepreciationSchedule(depSheet);
  const beneficiaryAccounts = parseBeneficiaryAccounts(benSheet);

  const accounts = mergeAccounts(
    reportingRows,
    typeClassMap,
    glSummaryComparative,
    glSummaryConsidered,
  );

  return {
    accounts,
    clientParams,
    glSummary,
    glSummaryComparative,
    glSummaryConsidered,
    depSchedule,
    beneficiaryAccounts,
  };
}

export async function parseVerificationReport(
  file: File,
): Promise<VerificationReportData> {
  const buffer = await file.arrayBuffer();
  const wb = XLSX.read(buffer, { type: 'array' });
  return parseVerificationReportFromWorkbook(wb);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npx vitest run src/parsers/__tests__/verificationReportParser.test.ts`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/parsers/verificationReportParser.ts web/src/parsers/__tests__/verificationReportParser.test.ts
git commit -m "feat(web): verification-report parser orchestrator with merge + archive filter"
```

---

## Task 9: Delete legacy parsers

**Files:**
- Delete: `web/src/parsers/chartParser.ts`
- Delete: `web/src/parsers/chartCheckParser.ts`
- Delete: `web/src/parsers/__tests__/chartParser.test.ts`
- Modify: `web/src/components/InputPanel.tsx` (imports only — will be fully rewritten in Task 12)

- [ ] **Step 1: Verify no other files still reference the legacy parsers**

Run: `cd web && grep -rn "chartParser\|chartCheckParser" src/ || echo 'NO REFERENCES'`
Expected output (before this task starts) will show references from `InputPanel.tsx`. Those will be fixed in Task 12.

- [ ] **Step 2: Temporarily stub-out the imports in `InputPanel.tsx`**

To keep TypeScript building between Task 9 and Task 12, wrap the legacy imports as inline stubs inside `InputPanel.tsx`. **This is a temporary scaffold** that Task 12 replaces completely. Edit the imports at the top of `web/src/components/InputPanel.tsx`:

Delete these three lines:
```ts
import { parseChartFile } from '../parsers/chartParser';
import { parseChartCheckReport } from '../parsers/chartCheckParser';
import { parseGroupRelationshipsFile } from '../parsers/groupParser';
```

Replace with:
```ts
import { parseGroupRelationshipsFile } from '../parsers/groupParser';
// Legacy parser imports removed — Task 12 rewires to verificationReportParser.
async function parseChartFile(_f: File): Promise<never> {
  throw new Error('Legacy parser removed — re-run after Task 12.');
}
async function parseChartCheckReport(_f: File): Promise<never> {
  throw new Error('Legacy parser removed — re-run after Task 12.');
}
```

- [ ] **Step 3: Delete the legacy parser files**

```bash
cd C:/Users/kyle/newDev/xero-report-code-mapper
rm web/src/parsers/chartParser.ts
rm web/src/parsers/chartCheckParser.ts
rm web/src/parsers/__tests__/chartParser.test.ts
```

- [ ] **Step 4: Confirm the app still type-checks and tests still pass**

Run: `cd web && npx tsc --noEmit && npx vitest run`
Expected: no TS errors; all surviving tests pass.

- [ ] **Step 5: Commit**

```bash
git add -A web/src/parsers/ web/src/components/InputPanel.tsx
git commit -m "chore(web): remove legacy chart and chart-check parsers"
```

---

## Task 10: Store — `verificationReport` slot + `decisionsByClient` hydration

**Files:**
- Modify: `web/src/store/appStore.ts`

- [ ] **Step 1: Rewrite `appStore.ts` wholesale**

Replace the entire contents of `web/src/store/appStore.ts` with:

```ts
/**
 * Global application state managed via Zustand.
 *
 * Stores the parsed Verification Report, pipeline outputs, rule data,
 * and admin state. Decisions are persisted per-client to localStorage
 * via decisionsStorage.
 */

import { create } from 'zustand';
import type {
  MappedAccount,
  RulesData,
  GroupRelationships,
  TemplateName,
  VerificationReportData,
  DecisionMap,
} from '../types';
import {
  deriveClientKey,
  loadDecisions,
  saveDecisions,
  clearDecisions,
} from '../services/decisionsStorage';

const GITHUB_TOKEN_KEY = 'github_token';

function loadGithubToken(): string | null {
  try {
    return localStorage.getItem(GITHUB_TOKEN_KEY);
  } catch {
    return null;
  }
}

function saveGithubToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(GITHUB_TOKEN_KEY, token);
    else localStorage.removeItem(GITHUB_TOKEN_KEY);
  } catch {
    // ignore
  }
}

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

interface AppState {
  // Inputs
  templateName: TemplateName;
  verificationReport: VerificationReportData | null;
  groupRelationships: GroupRelationships | null;
  industry: string;

  // Outputs
  mappedAccounts: MappedAccount[];
  isProcessing: boolean;
  codeTypeMap: Record<string, string>;

  // Rules
  rulesData: RulesData | null;
  rulesLoading: boolean;

  // Decisions (per-client, mirrored into localStorage)
  clientKey: string;
  decisions: DecisionMap;

  // Admin
  githubToken: string | null;

  // Actions
  setTemplateName: (name: TemplateName) => void;
  setVerificationReport: (data: VerificationReportData) => void;
  setGroupRelationships: (data: GroupRelationships) => void;
  setIndustry: (industry: string) => void;
  setMappedAccounts: (accounts: MappedAccount[]) => void;
  setIsProcessing: (processing: boolean) => void;
  setRulesData: (data: RulesData) => void;
  setRulesLoading: (loading: boolean) => void;
  setGithubToken: (token: string | null) => void;
  setCodeTypeMap: (map: Record<string, string>) => void;
  overrideAccount: (index: number, code: string, reason: string) => void;
  approveAccount: (index: number) => void;
  overrideAccountType: (index: number, newType: string) => void;
  clearAllDecisions: () => void;
  reset: () => void;
}

const initialState = {
  templateName: 'Company' as TemplateName,
  verificationReport: null as VerificationReportData | null,
  groupRelationships: null as GroupRelationships | null,
  industry: '',

  mappedAccounts: [] as MappedAccount[],
  isProcessing: false,
  codeTypeMap: {} as Record<string, string>,

  rulesData: null as RulesData | null,
  rulesLoading: false,

  clientKey: '',
  decisions: {} as DecisionMap,

  githubToken: loadGithubToken(),
};

// ---------------------------------------------------------------------------
// Hydration helpers
// ---------------------------------------------------------------------------

function applyDecisions(
  accounts: MappedAccount[],
  decisions: DecisionMap,
): MappedAccount[] {
  return accounts.map((a) => {
    const d = decisions[a.code];
    if (!d) return a;
    return {
      ...a,
      overrideCode: d.overrideCode ?? a.overrideCode,
      overrideReason: d.overrideReason ?? a.overrideReason,
      typeOverride: d.typeOverride ?? a.typeOverride,
      approved: d.approved ?? a.approved,
      auto: d.auto ?? a.auto,
    };
  });
}

function decisionForAccount(a: MappedAccount) {
  const d = {
    overrideCode: a.overrideCode,
    overrideReason: a.overrideReason,
    typeOverride: a.typeOverride,
    approved: a.approved,
    auto: a.auto,
  };
  // Drop undefined keys so "no decision" accounts stay absent from storage.
  const cleaned: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(d)) {
    if (v !== undefined) cleaned[k] = v;
  }
  return cleaned;
}

function extractDecisions(accounts: MappedAccount[]): DecisionMap {
  const out: DecisionMap = {};
  for (const a of accounts) {
    const d = decisionForAccount(a);
    if (Object.keys(d).length > 0) out[a.code] = d;
  }
  return out;
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useAppStore = create<AppState>()((set, get) => ({
  ...initialState,

  setTemplateName: (name) => set({ templateName: name }),

  setVerificationReport: (data) => {
    const codes = data.accounts.map((a) => a.code);
    const clientKey = deriveClientKey(data.clientParams.displayName, codes);
    const decisions = loadDecisions(clientKey);
    set({ verificationReport: data, clientKey, decisions });
  },

  setGroupRelationships: (data) => set({ groupRelationships: data }),

  setIndustry: (industry) => set({ industry }),

  setMappedAccounts: (accounts) => {
    const { decisions } = get();
    set({ mappedAccounts: applyDecisions(accounts, decisions) });
  },

  setIsProcessing: (processing) => set({ isProcessing: processing }),

  setRulesData: (data) => set({ rulesData: data }),

  setRulesLoading: (loading) => set({ rulesLoading: loading }),

  setCodeTypeMap: (map) => set({ codeTypeMap: map }),

  setGithubToken: (token) => {
    saveGithubToken(token);
    set({ githubToken: token });
  },

  overrideAccount: (index, code, reason) =>
    set((state) => {
      if (index < 0 || index >= state.mappedAccounts.length) return state;
      const updated = [...state.mappedAccounts];
      updated[index] = { ...updated[index], overrideCode: code, overrideReason: reason };
      const decisions = extractDecisions(updated);
      if (state.clientKey) saveDecisions(state.clientKey, decisions);
      return { mappedAccounts: updated, decisions };
    }),

  approveAccount: (index) =>
    set((state) => {
      if (index < 0 || index >= state.mappedAccounts.length) return state;
      const updated = [...state.mappedAccounts];
      updated[index] = { ...updated[index], approved: true };
      const decisions = extractDecisions(updated);
      if (state.clientKey) saveDecisions(state.clientKey, decisions);
      return { mappedAccounts: updated, decisions };
    }),

  overrideAccountType: (index, newType) =>
    set((state) => {
      if (index < 0 || index >= state.mappedAccounts.length) return state;
      const updated = [...state.mappedAccounts];
      updated[index] = { ...updated[index], typeOverride: newType };
      const decisions = extractDecisions(updated);
      if (state.clientKey) saveDecisions(state.clientKey, decisions);
      return { mappedAccounts: updated, decisions };
    }),

  clearAllDecisions: () =>
    set((state) => {
      if (state.clientKey) clearDecisions(state.clientKey);
      const cleared = state.mappedAccounts.map((a) => ({
        ...a,
        overrideCode: undefined,
        overrideReason: undefined,
        typeOverride: undefined,
        approved: undefined,
        auto: undefined,
      }));
      return { mappedAccounts: cleared, decisions: {} };
    }),

  reset: () =>
    set({
      ...initialState,
      githubToken: loadGithubToken(),
    }),
}));
```

- [ ] **Step 2: Update `AccountDetailPanel.tsx` to read from `verificationReport` instead of `chartCheckData`**

In `web/src/components/AccountDetailPanel.tsx`, replace these references (around lines 62–94):

```ts
const chartCheckData = useAppStore((s) => s.chartCheckData);
// ...
const glEntry = chartCheckData?.glSummary.find(...);
const depAssets = chartCheckData?.depSchedule.filter(...);
// ...entityName usage...
```

with:

```ts
const verificationReport = useAppStore((s) => s.verificationReport);
// ...
const glEntry = verificationReport?.glSummary.find(
  (gl) => gl.accountCode === account.code,
);
const depAssets = verificationReport?.depSchedule.filter(
  (d) => d.costAccount === account.code,
);
const entityRelationships = useMemo(() => {
  if (!groupRelationships || !verificationReport) return [];
  const entityName = verificationReport.clientParams.displayName;
  if (!entityName) return [];
  return groupRelationships.relationships.filter(
    (r) =>
      r.entityName.toLowerCase().includes(entityName.toLowerCase()) ||
      r.relatedClient.toLowerCase().includes(entityName.toLowerCase()),
  );
}, [groupRelationships, verificationReport]);
```

- [ ] **Step 3: Type-check**

Run: `cd web && npx tsc --noEmit`
Expected: no errors. (InputPanel still uses stubs from Task 9; that's fine — it still compiles because the stub functions throw, not fail typing.)

- [ ] **Step 4: Commit**

```bash
git add web/src/store/appStore.ts web/src/components/AccountDetailPanel.tsx
git commit -m "feat(web): store holds verificationReport and per-client decisions"
```

---

## Task 11: Pipeline — invoke autoConfirm after mapping

**Files:**
- Modify: `web/src/pipeline/pipeline.ts`

- [ ] **Step 1: Append `autoConfirm` call at the end of `runPipeline`**

In `web/src/pipeline/pipeline.ts`, add the import at the top:

```ts
import { autoConfirmMatches } from './autoConfirm';
```

At the very end of `runPipeline`, replace `return mapped;` with:

```ts
  return autoConfirmMatches(mapped);
}
```

- [ ] **Step 2: Add a pipeline integration test**

Append to `web/src/pipeline/__tests__/pipeline.test.ts` (or create a minimal new test file if too noisy to add):

```ts
import { describe, it, expect } from 'vitest';
import { runPipeline } from '../pipeline';
import type { PipelineInput } from '../pipeline';

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
```

- [ ] **Step 3: Run tests**

Run: `cd web && npx vitest run src/pipeline/__tests__/pipeline.test.ts`
Expected: all pipeline tests pass, including the new one.

- [ ] **Step 4: Commit**

```bash
git add web/src/pipeline/pipeline.ts web/src/pipeline/__tests__/pipeline.test.ts
git commit -m "feat(web): invoke autoConfirmMatches at end of runPipeline"
```

---

## Task 12: InputPanel — single drop zone + safety banner

**Files:**
- Modify: `web/src/components/InputPanel.tsx`

- [ ] **Step 1: Rewrite `InputPanel.tsx`**

Replace the entire contents of `web/src/components/InputPanel.tsx` with:

```tsx
/**
 * Left sidebar panel for pipeline inputs.
 *
 * Single Verification Report drop zone (replaces the legacy two-file
 * intake) plus an optional Group Relationships file and the template
 * selector.
 */

import { useCallback, useState } from 'react';
import FileDropZone from './FileDropZone';
import { useAppStore } from '../store/appStore';
import { parseVerificationReport } from '../parsers/verificationReportParser';
import { parseGroupRelationshipsFile } from '../parsers/groupParser';
import { runPipeline } from '../pipeline/pipeline';
import { buildCodeTypeMap } from '../pipeline/typePredict';
import systemMappings from '../data/systemMappings.json';
import type { TemplateName, SystemMapping } from '../types';

const TEMPLATE_OPTIONS: TemplateName[] = [
  'Company',
  'Trust',
  'Partnership',
  'SoleTrader',
  'XeroHandi',
];

export default function InputPanel() {
  const templateName = useAppStore((s) => s.templateName);
  const setTemplateName = useAppStore((s) => s.setTemplateName);
  const verificationReport = useAppStore((s) => s.verificationReport);
  const setVerificationReport = useAppStore((s) => s.setVerificationReport);
  const setGroupRelationships = useAppStore((s) => s.setGroupRelationships);
  const rulesData = useAppStore((s) => s.rulesData);
  const isProcessing = useAppStore((s) => s.isProcessing);
  const setIsProcessing = useAppStore((s) => s.setIsProcessing);
  const setMappedAccounts = useAppStore((s) => s.setMappedAccounts);
  const setCodeTypeMap = useAppStore((s) => s.setCodeTypeMap);
  const industry = useAppStore((s) => s.industry);

  const [reportFileName, setReportFileName] = useState<string>();
  const [groupFileName, setGroupFileName] = useState<string>();
  const [reportStatus, setReportStatus] = useState<string>();
  const [error, setError] = useState<string>();

  const canRun =
    verificationReport !== null && rulesData !== null && !isProcessing;

  const handleReportFile = useCallback(
    async (file: File) => {
      setError(undefined);
      setReportFileName(file.name);
      setReportStatus('Parsing...');
      try {
        const data = await parseVerificationReport(file);
        setVerificationReport(data);
        const mandatory = data.accounts.filter((a) => a.activity === 'mandatory').length;
        const optional = data.accounts.filter((a) => a.activity === 'optional').length;
        setReportStatus(
          `${data.accounts.length} accounts · ${mandatory} mandatory · ${optional} optional`,
        );
      } catch (e) {
        setReportStatus(undefined);
        setReportFileName(undefined);
        setError(
          e instanceof Error
            ? e.message
            : 'Failed to parse Verification Report',
        );
      }
    },
    [setVerificationReport],
  );

  const handleGroupFile = useCallback(
    async (file: File) => {
      setError(undefined);
      setGroupFileName(file.name);
      try {
        const data = await parseGroupRelationshipsFile(file);
        setGroupRelationships(data);
      } catch (e) {
        setGroupFileName(undefined);
        setError(
          e instanceof Error ? e.message : 'Failed to parse group relationships',
        );
      }
    },
    [setGroupRelationships],
  );

  const handleRunMapping = useCallback(async () => {
    if (!canRun || !rulesData || !verificationReport) return;
    setError(undefined);
    setIsProcessing(true);
    try {
      const templateModule = await import(
        `../data/templates/${templateName}.json`
      );
      const templateEntries = templateModule.default;
      setCodeTypeMap(buildCodeTypeMap(templateEntries));

      const result = runPipeline({
        accounts: verificationReport.accounts,
        rulesData,
        templateEntries,
        systemMappings: systemMappings as SystemMapping[],
        glSummary: verificationReport.glSummary,
        industry,
        templateName,
      });
      setMappedAccounts(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Pipeline failed');
    } finally {
      setIsProcessing(false);
    }
  }, [
    canRun,
    rulesData,
    verificationReport,
    templateName,
    industry,
    setIsProcessing,
    setMappedAccounts,
    setCodeTypeMap,
  ]);

  const clientParams = verificationReport?.clientParams;

  return (
    <aside className="w-72 shrink-0 border-r border-gray-200 bg-gray-50 p-4 overflow-y-auto">
      <h2 className="text-sm font-semibold text-gray-700 mb-3">
        Pipeline Inputs
      </h2>

      {/* Safety banner */}
      <div className="mb-3 p-2 bg-yellow-50 border border-yellow-200 rounded text-xs text-yellow-800">
        Before using this report, make sure you've exported a fresh
        Verification Report from Xero — stale data produces stale mappings.
      </div>

      {/* Template selector */}
      <div className="mb-3">
        <label className="block text-xs font-medium text-gray-600 mb-1">
          Template
        </label>
        <select
          value={templateName}
          onChange={(e) => setTemplateName(e.target.value as TemplateName)}
          className="w-full text-sm border border-gray-300 rounded-md px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          {TEMPLATE_OPTIONS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      {/* Verification Report */}
      <FileDropZone
        label="Verification Report"
        required
        accept=".xlsx"
        onFile={handleReportFile}
        fileName={reportFileName}
        status={reportStatus}
      />

      {/* Group Relationships (optional) */}
      <FileDropZone
        label="Group Relationships"
        accept=".csv"
        onFile={handleGroupFile}
        fileName={groupFileName}
      />

      {/* Error */}
      {error && (
        <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
          {error}
        </div>
      )}

      {/* Run button */}
      <button
        onClick={handleRunMapping}
        disabled={!canRun}
        className={`w-full py-2 px-4 rounded-md text-sm font-medium transition-colors ${
          canRun
            ? 'bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800'
            : 'bg-gray-200 text-gray-400 cursor-not-allowed'
        }`}
      >
        {isProcessing ? 'Processing...' : 'Run Mapping'}
      </button>

      {/* Rules status */}
      <div className="mt-3 text-xs text-gray-500">
        {rulesData
          ? `Rules loaded: v${rulesData.version} (${rulesData.rules.length} rules)`
          : 'Loading rules...'}
      </div>

      {/* Entity context */}
      {clientParams && clientParams.displayName && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <h3 className="text-xs font-semibold text-gray-600 mb-2 uppercase tracking-wide">
            Entity Context
          </h3>
          <dl className="space-y-1.5 text-xs">
            <div>
              <dt className="text-gray-400">Name</dt>
              <dd className="text-gray-700 font-medium">
                {clientParams.displayName}
              </dd>
            </div>
            {clientParams.abn && (
              <div>
                <dt className="text-gray-400">ABN</dt>
                <dd className="text-gray-700">{clientParams.abn}</dd>
              </div>
            )}
            {clientParams.directors.length > 0 && (
              <div>
                <dt className="text-gray-400">Directors</dt>
                <dd className="text-gray-700">
                  {clientParams.directors.join(', ')}
                </dd>
              </div>
            )}
          </dl>
        </div>
      )}
    </aside>
  );
}
```

- [ ] **Step 2: Type-check and run**

Run: `cd web && npx tsc --noEmit && npx vitest run`
Expected: no TS errors; all tests pass.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/InputPanel.tsx
git commit -m "feat(web): single-file InputPanel with Verification Report drop zone"
```

---

## Task 13: MappingTable — switch to `hasTypeMismatch`

**Files:**
- Modify: `web/src/components/MappingTable.tsx`

- [ ] **Step 1: Replace inline mismatch check with the new helper**

In `web/src/components/MappingTable.tsx`:

1. Update imports (around line 19–24):
```ts
import {
  predictTypeFromCode,
  HEAD_FROM_TYPE,
  SYSTEM_TYPES,
  ALLOWED_TYPES_BY_HEAD,
  hasTypeMismatch,
} from '../pipeline/typePredict';
```

2. Replace the local `hasTypeMismatchForAccount` helper (around lines 115–121) with:
```ts
function hasTypeMismatchForAccount(acct: MappedAccount): boolean {
  return hasTypeMismatch(acct.type, acct.overrideCode || acct.predictedCode);
}
```

3. Inside the Type cell renderer and row loop (two places that compute `hasMismatch` inline around lines 205–210 and 562–567), replace each with a call to `hasTypeMismatchForAccount(acct)`.

Example for the row loop (lines 560–568):
```tsx
{table.getRowModel().rows.map((row) => {
  const acct = row.original;
  const mismatch = hasTypeMismatchForAccount(acct);
  return (
    <tr
      key={row.id}
      onClick={() => handleRowClick(row.index)}
      className={`cursor-pointer transition-colors ${
        selectedRowIndex === row.index
          ? 'bg-blue-50'
          : mismatch
            ? 'hover:bg-red-50'
            : 'hover:bg-gray-50'
      }`}
    >
```
and cell highlight:
```tsx
<td
  key={cell.id}
  className={`px-3 py-2 ${isTypeCell && hasTypeMismatchForAccount(acct) && !acct.typeOverride ? 'bg-red-100' : ''}`}
>
```

- [ ] **Step 2: Type-check + run tests**

Run: `cd web && npx tsc --noEmit && npx vitest run`
Expected: no errors; all tests pass.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/MappingTable.tsx
git commit -m "feat(web): mapping table uses prefix-aware hasTypeMismatch"
```

---

## Task 14: MappingTable — activity filter (Mandatory / Optional / All)

**Files:**
- Modify: `web/src/components/MappingTable.tsx`

- [ ] **Step 1: Add activity filter state + UI**

In `web/src/components/MappingTable.tsx`:

1. Add below the existing `FilterMode` type (around line 32):
```ts
type ActivityFilter = 'mandatory' | 'optional' | 'all';
```

2. Add state (around line 143):
```tsx
const [activityFilter, setActivityFilter] = useState<ActivityFilter>('mandatory');
```

3. Extend the `filteredData` `useMemo` (around line 147) to apply activity filter first:
```tsx
const filteredData = useMemo(() => {
  let data = mappedAccounts;

  // Activity filter
  if (activityFilter === 'mandatory') {
    data = data.filter((a) => a.activity !== 'optional');
  } else if (activityFilter === 'optional') {
    data = data.filter((a) => a.activity === 'optional');
  }

  switch (filterMode) {
    case 'review':
      data = data.filter((a) => a.needsReview);
      break;
    case 'fallback':
      data = data.filter((a) => a.source === 'FallbackParent');
      break;
    case 'active':
      data = data.filter((a) => a.hasActivity);
      break;
    case 'typeMismatch':
      data = data.filter((a) => hasTypeMismatchForAccount(a));
      break;
  }
  return data;
}, [mappedAccounts, filterMode, activityFilter]);
```

4. Add the segmented control to the toolbar (immediately after the search input around line 487, before the `filterChips`):
```tsx
{/* Activity filter */}
<div className="flex gap-1">
  {(['mandatory', 'optional', 'all'] as ActivityFilter[]).map((mode) => (
    <button
      key={mode}
      onClick={() => setActivityFilter(mode)}
      className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors capitalize ${
        activityFilter === mode
          ? 'bg-blue-600 text-white'
          : 'bg-white border border-gray-300 text-gray-600 hover:bg-gray-50'
      }`}
    >
      {mode}
    </button>
  ))}
</div>
```

- [ ] **Step 2: Run tests**

Run: `cd web && npx tsc --noEmit && npx vitest run`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/MappingTable.tsx
git commit -m "feat(web): Mandatory/Optional/All activity filter in MappingTable"
```

---

## Task 15: MappingTable — status filter

**Files:**
- Modify: `web/src/components/MappingTable.tsx`

- [ ] **Step 1: Add status filter**

In `web/src/components/MappingTable.tsx`:

1. Add type + state:
```ts
type StatusFilter = 'all' | 'pending' | 'accepted' | 'overridden';
```
```tsx
const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
```

2. Add a status-computation helper above the component:
```ts
function decisionStatus(a: MappedAccount): 'accepted' | 'overridden' | 'pending' {
  if (a.overrideCode) return 'overridden';
  if (a.approved) return 'accepted';
  // Predicted === original without a user click: counts as accepted (Auto).
  if (!a.reportCode || a.predictedCode === a.reportCode) return 'accepted';
  return 'pending';
}
```

3. Extend `filteredData`:
```tsx
if (statusFilter !== 'all') {
  data = data.filter((a) => decisionStatus(a) === statusFilter);
}
```
Place this after the activity filter block, before the switch statement. Add `statusFilter` to the dependency array.

4. Add the dropdown to the toolbar, between activity filter and the filter chips:
```tsx
<select
  value={statusFilter}
  onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
  className="px-2 py-1 text-xs border border-gray-300 rounded-md bg-white"
>
  <option value="all">Status: All</option>
  <option value="pending">Pending</option>
  <option value="accepted">Accepted</option>
  <option value="overridden">Overridden</option>
</select>
```

- [ ] **Step 2: Tests**

Run: `cd web && npx tsc --noEmit && npx vitest run`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/MappingTable.tsx
git commit -m "feat(web): status filter (pending/accepted/overridden) in MappingTable"
```

---

## Task 16: MappingTable — source filter with counts

**Files:**
- Modify: `web/src/components/MappingTable.tsx`

- [ ] **Step 1: Add source filter state + dropdown**

In `web/src/components/MappingTable.tsx`:

1. State:
```tsx
const [sourceFilter, setSourceFilter] = useState<string>('all');
```

2. Compute source counts via `useMemo`:
```tsx
const sourceCounts = useMemo(() => {
  const counts = new Map<string, number>();
  for (const a of mappedAccounts) {
    counts.set(a.source, (counts.get(a.source) ?? 0) + 1);
  }
  return counts;
}, [mappedAccounts]);
```

3. Extend `filteredData` (before the filterMode switch):
```tsx
if (sourceFilter !== 'all') {
  data = data.filter((a) => a.source === sourceFilter);
}
```
Add `sourceFilter` to deps.

4. Add the dropdown to the toolbar:
```tsx
<select
  value={sourceFilter}
  onChange={(e) => setSourceFilter(e.target.value)}
  className="px-2 py-1 text-xs border border-gray-300 rounded-md bg-white"
>
  <option value="all">Source: All</option>
  {Array.from(sourceCounts.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([src, n]) => (
      <option key={src} value={src}>{src} ({n})</option>
    ))}
</select>
```

- [ ] **Step 2: Tests**

Run: `cd web && npx tsc --noEmit && npx vitest run`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/MappingTable.tsx
git commit -m "feat(web): source filter with per-source counts in MappingTable"
```

---

## Task 17: MappingTable — progress counters in toolbar

**Files:**
- Modify: `web/src/components/MappingTable.tsx`

- [ ] **Step 1: Add progress counters**

In `web/src/components/MappingTable.tsx`:

1. Inside the component, compute counts using the existing `decisionStatus` helper from Task 15:
```tsx
const progressCounts = useMemo(() => {
  let accepted = 0, overridden = 0, pending = 0;
  for (const a of mappedAccounts) {
    const s = decisionStatus(a);
    if (s === 'accepted') accepted++;
    else if (s === 'overridden') overridden++;
    else pending++;
  }
  const total = mappedAccounts.length;
  const done = accepted + overridden;
  const pct = total === 0 ? 0 : Math.round((done / total) * 100);
  return { accepted, overridden, pending, total, pct };
}, [mappedAccounts]);
```

2. Render in the toolbar, before the Export buttons:
```tsx
<div className="flex items-center gap-3 text-xs text-gray-600 px-2 py-1 bg-gray-50 border border-gray-200 rounded-md">
  <span><span className="font-semibold text-green-600">{progressCounts.accepted}</span> accepted</span>
  <span><span className="font-semibold text-blue-600">{progressCounts.overridden}</span> overridden</span>
  <span><span className="font-semibold text-amber-600">{progressCounts.pending}</span> pending</span>
  <span className="text-gray-400">|</span>
  <span className="font-semibold">{progressCounts.pct}%</span>
</div>
```

- [ ] **Step 2: Tests**

Run: `cd web && npx tsc --noEmit && npx vitest run`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/MappingTable.tsx
git commit -m "feat(web): live progress counters in MappingTable toolbar"
```

---

## Task 18: MappingTable — Clear All button

**Files:**
- Modify: `web/src/components/MappingTable.tsx`

- [ ] **Step 1: Add Clear All**

In `web/src/components/MappingTable.tsx`:

1. Pull the new action from the store:
```tsx
const clearAllDecisions = useAppStore((s) => s.clearAllDecisions);
```

2. Handler:
```tsx
const handleClearAll = useCallback(() => {
  const confirmed = window.confirm(
    'Reset all decisions for this client? This cannot be undone.',
  );
  if (!confirmed) return;
  clearAllDecisions();
}, [clearAllDecisions]);
```

3. Button (right-aligned in the toolbar, before the Export buttons):
```tsx
<button
  onClick={handleClearAll}
  className="px-3 py-1.5 text-xs font-medium bg-white border border-gray-300 rounded-md hover:bg-red-50 hover:border-red-300 hover:text-red-700 text-gray-700"
>
  Clear All
</button>
```

- [ ] **Step 2: Tests**

Run: `cd web && npx tsc --noEmit && npx vitest run`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/MappingTable.tsx
git commit -m "feat(web): Clear All button resets all decisions for current client"
```

---

## Task 19: AccountDetailPanel — override code description lookup

**Files:**
- Modify: `web/src/components/AccountDetailPanel.tsx`

- [ ] **Step 1: Add description lookup under the override selector**

In `web/src/components/AccountDetailPanel.tsx`:

1. Add a `codeToDescription` lookup above the component (after the existing `leafByHead` computation):
```ts
const codeToDescription: Record<string, string> = {};
for (const m of allMappings) {
  codeToDescription[m.reportingCode] = m.name;
}
```

2. Replace the existing `{overrideCode && (...)}` block (around line 340) with:
```tsx
{overrideCode && (
  <div className="mb-2 text-xs">
    <div className="text-blue-600 font-mono">Selected: {overrideCode}</div>
    {codeToDescription[overrideCode] && (
      <div className="text-gray-500 mt-0.5">
        {codeToDescription[overrideCode]}
      </div>
    )}
  </div>
)}
```

- [ ] **Step 2: Tests**

Run: `cd web && npx tsc --noEmit && npx vitest run`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/AccountDetailPanel.tsx
git commit -m "feat(web): show description for selected override code in detail panel"
```

---

## Task 20: Wire `deriveReportingName` into CSV export

**Files:**
- Modify: `web/src/components/MappingTable.tsx`

- [ ] **Step 1: Update CSV export to include derived Reporting Name**

In `web/src/components/MappingTable.tsx`:

1. Add import:
```ts
import { deriveReportingName } from '../pipeline/reportingName';
```

2. Replace `generateExportCSV` with:
```ts
function generateExportCSV(
  accounts: MappedAccount[],
  codeTypeMap: Record<string, string>,
): string {
  const header = '*Code,*Name,*Type,*Tax Code,Report Code,Reporting Name';
  const rows = accounts.map((a) => {
    const reportCode = a.overrideCode ?? a.predictedCode;
    const finalType =
      a.typeOverride || predictTypeFromCode(reportCode, a.type, codeTypeMap);
    const reportingName = deriveReportingName(a.name) ?? '';
    const escape = (s: string) =>
      s.includes(',') || s.includes('"') ? `"${s.replace(/"/g, '""')}"` : s;
    return [
      escape(a.code),
      escape(a.name),
      escape(finalType),
      escape(a.taxCode ?? ''),
      escape(reportCode),
      escape(reportingName),
    ].join(',');
  });
  return [header, ...rows].join('\n');
}
```

- [ ] **Step 2: Tests**

Run: `cd web && npx tsc --noEmit && npx vitest run`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/MappingTable.tsx
git commit -m "feat(web): derive ATO/Div7A reporting names during CSV export"
```

---

## Task 21: Deprecation notice on `mapping_logic_v15.py`

**Files:**
- Modify: `mapping_logic_v15.py`

- [ ] **Step 1: Insert deprecation banner**

In `mapping_logic_v15.py`, replace the existing module docstring (lines 1–13) with:

```python
"""mapping_logic_v15.py – Reporting Code mapper for Xero-style Chart of Accounts.

⚠️  DEPRECATED (as of 2026-04-16): This CLI entrypoint is no longer the
    supported path for running mappings. The web app at ``web/`` now
    consumes a single Verification Report workbook and is the sole
    maintained pipeline.

    This module is retained as a reference implementation of the rule
    engine and post-processing passes for the Python test suite; do not
    add new features here. Run ``cd web && npm run dev`` to use the
    current tool.

Run (legacy CLI, for reference only):
    python mapping_logic_v15.py <ClientChartOfAccounts.csv> <ClientTrialBalance.csv> --chart <CHARTNAME>

Where:
    --chart selects a template CSV in ChartOfAccounts/ by filename (without extension).

Outputs:
    - AugmentedChartOfAccounts.csv alongside the client chart
    - ReportingTree.json documenting inferred ranges from the selected template
"""
```

- [ ] **Step 2: Confirm tests still pass**

Run: `cd C:/Users/kyle/newDev/xero-report-code-mapper && uv run pytest tests/ -v`
Expected: all existing tests pass unchanged (tests import modules, not this docstring).

- [ ] **Step 3: Commit**

```bash
git add mapping_logic_v15.py
git commit -m "docs: mark mapping_logic_v15.py as deprecated reference-only"
```

---

## Task 22: Smoke test against the real demo workbook

**Files:**
- Create: `web/src/parsers/__tests__/verificationReportParser.smoke.test.ts`

- [ ] **Step 1: Add a smoke test that loads the on-disk demo file**

Create `web/src/parsers/__tests__/verificationReportParser.smoke.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import * as XLSX from 'xlsx';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { parseVerificationReportFromWorkbook } from '../verificationReportParser';

const DEMO = resolve(
  __dirname,
  '../../../..',
  '.dev-info/Demo_Company__AU__-_Chart_of_Accounts_Verification_Report.xlsx',
);

describe('smoke: real demo workbook', () => {
  it('parses without throwing', () => {
    const buf = readFileSync(DEMO);
    const wb = XLSX.read(buf, { type: 'buffer' });
    const data = parseVerificationReportFromWorkbook(wb);
    expect(data.clientParams.displayName).toContain('Demo Company');
    expect(data.accounts.length).toBeGreaterThan(0);
    // Current Year Earnings + CURRADJUST must be excluded.
    expect(data.accounts.find((a) => a.name === 'Current Year Earnings')).toBeUndefined();
    expect(data.accounts.find((a) => a.name === 'Currency Adjustment')).toBeUndefined();
    // Every surviving account has a type from Type-and-Class.
    for (const a of data.accounts) {
      expect(a.type).toBeTruthy();
    }
  });
});
```

Note: the demo file is updated by the user occasionally — so the only hard assertions are structural (parses, plausible counts, system accounts excluded). If the demo is regenerated with a different entity name, update the display-name assertion accordingly.

- [ ] **Step 2: Run the smoke test**

Run: `cd web && npx vitest run src/parsers/__tests__/verificationReportParser.smoke.test.ts`
Expected: test passes. If it fails on the demo file, read the failure carefully before editing — the failure is the point.

- [ ] **Step 3: Full test suite run**

Run: `cd web && npx vitest run && cd .. && uv run pytest tests/ -v`
Expected: all web vitest and python pytest tests pass.

- [ ] **Step 4: Manual browser smoke**

Run: `cd web && npm run dev`
Then:
1. Open `http://localhost:5173`.
2. Drop `.dev-info/Demo_Company__AU__-_Chart_of_Accounts_Verification_Report.xlsx` on the Verification Report dropzone.
3. Confirm status reads something like `N accounts · X mandatory · Y optional`.
4. Click **Run Mapping**. Confirm the table renders.
5. Confirm the activity segmented control defaults to Mandatory.
6. Click a row; confirm the detail panel shows GL activity pulled from the Current-FY movements.
7. Override a code; confirm the progress counter updates and the decision persists after a page refresh.
8. Click **Clear All**; confirm it resets.
9. Close the dev server with Ctrl-C.

- [ ] **Step 5: Commit**

```bash
git add web/src/parsers/__tests__/verificationReportParser.smoke.test.ts
git commit -m "test(web): smoke test parser against real demo workbook"
```

---

## Self-review checklist

- [x] **Spec coverage:** Every item in the spec's §2 goals list has a task:
  - Parser swap → Tasks 6–9
  - Three-sheet movements + archive filter + activity tag → Task 8
  - Safety banner → Task 12
  - Progress counters → Task 17
  - Status filter → Task 15
  - Source filter → Task 16
  - Clear All → Task 18, Task 10 (store action)
  - Override code description lookup → Task 19
  - Reporting name auto-derivation → Tasks 3, 20
  - localStorage persistence → Tasks 5, 10
  - Auto-confirm tightened + persisted → Tasks 2 (hasTypeMismatch), 4, 11
  - Prefix-level mismatch → Tasks 2, 13
  - Python deprecation notice → Task 21
- [x] **No placeholders:** every step contains the actual code, path, or command.
- [x] **Type consistency:** `hasTypeMismatch` signature matches between Task 2 definition and Task 4/13 callers. `AccountDecision` and `DecisionMap` defined in Task 1 and used verbatim in Tasks 5 and 10. `VerificationReportData` defined in Task 1 and used in Tasks 8, 10, 12.
