# Verification Report Input — Design

**Date:** 2026-04-16
**Branch:** `feat/verification-report-input`
**Scope:** Web app (`web/`). Python CLI receives a deprecation notice only.

## 1. Problem

The web app currently requires three uploads: a Chart of Accounts CSV/XLSX, a multi-sheet Chart Check Report XLSX, and an optional Group Relationships CSV. The Xero-side export process has been redesigned to emit a single consolidated workbook — the **Chart of Accounts Verification Report** — that contains everything previously split across those two files. The web app must accept this new workbook as its primary input, drop the legacy two-file workflow, and at the same time close a set of UX regressions that exist between the old HTML report (`tools/gen_review_report.py`) and the current web UI.

The Python CLI (`mapping_logic_v15.py`) will not be updated. It remains as a reference implementation with a deprecation notice at the top of the file.

## 2. Goals

1. Replace the two legacy file uploads with a single "Verification Report" upload.
2. Emit the same internal data shapes (`Account[]`, `GLEntry[]`, `DepAsset[]`, `EntityParams`, `BeneficiaryEntry[]`) so the rest of the pipeline is unchanged.
3. Introduce three-tier account activity bucketing (Mandatory / Optional / Archived) driven by three movement-report sheets.
4. Close the following UX gaps relative to the old HTML report:
   - Progress counters (Accepted / Overridden / Pending).
   - Status filter.
   - Source filter (full source list with counts).
   - Import-safety banner.
   - Clear All / Reset action.
   - Override code description lookup.
   - Reporting name auto-derivation for ATO ICA, ATO ITA, and Div7A patterns.
   - Per-client localStorage persistence of decisions.
   - Auto-confirm matches, tightened with type compatibility checks.
   - Prefix-level type-mismatch detection.

## 3. Non-goals

- No changes to the rule engine, postprocessing, report generation, or any downstream Python module.
- No changes to test fixtures or the integration test harness.
- No backwards-compatibility path for the old two-file upload format. The old parsers are deleted.
- No changes to `tools/gen_review_report.py`, `tools/apply_decisions.py`, `tools/gen_mismatch_report.py`, or any other CLI-adjacent tooling.

## 4. Verification Report structure

The workbook contains seven required sheets. Sheet names are truncated by Xero's export — the truncated form is stable and used as the lookup key. The full name is always present in cell A1 of each sheet.

| Truncated sheet name | Full name (A1) | Contents |
|---|---|---|
| `Client File Parameters Report` | same | Entity-level parameters (display name, ABN, directors, trustees, signatories) |
| `Chart of Accounts - Reportin...` | `Chart of Accounts - Reporting Codes` | Accounts grouped under reporting-code headers; rows formatted `"NNN - Name"` with six years of closing balances |
| `Chart of Accounts - Type and...` | `Chart of Accounts - Type and Class` | Flat table: Account Code, Account, Account Type, Account Class |
| `Account Movements - Current …` | `Account Movements - Current FY` | GL movement for the current financial year |
| `Account Movements - Comparat…` | `Account Movements - Comparative` | GL movement for current + prior financial year (drives the Mandatory bucket) |
| `Account Movements - Consider…` | `Account Movements - Considered Active` | GL movement across the legislated retention window (drives the archive filter) |
| `Depreciation Schedule` | same | Fixed-asset cost/dep/accum-dep mapping |
| `Beneficiary Accounts` | same | Trust beneficiary names linked to accounts |

If any of these sheets is absent, the parser throws and the app refuses to process the file. Empty content is valid — only missing sheets are fatal. (In practice, Depreciation Schedule and Beneficiary Accounts are routinely empty for non-Trust entities.)

## 5. Parser: `verificationReportParser.ts`

**Location:** `web/src/parsers/verificationReportParser.ts`
**Contract:**

```ts
parseVerificationReport(file: File): Promise<VerificationReportData>

interface VerificationReportData {
  accounts: Account[];                        // archive-filtered, activity-tagged
  clientParams: EntityParams;
  glSummary: GLEntry[];                       // Current FY
  glSummaryComparative: GLEntry[];            // Current + Prior FY  (NEW)
  glSummaryConsidered: GLEntry[];             // Legislated retention (NEW; renamed from glSummaryActive)
  depSchedule: DepAsset[];
  beneficiaryAccounts: BeneficiaryEntry[];
}
```

The `Account` type gains one new optional field:

```ts
interface Account {
  // ...existing fields
  activity?: 'mandatory' | 'optional';        // set by parser from movement-sheet membership
}
```

### 5.1 Parse sequence

1. Validate all seven required sheets exist. Match by truncated name (case-insensitive `startsWith` to tolerate minor wording drift). If any missing, throw with a user-facing message naming the missing sheet.
2. Parse `Client File Parameters Report` → `EntityParams` (reuse existing logic from the old chart-check parser; the sheet format is unchanged).
3. Parse `Chart of Accounts - Type and...` → `Map<code, {name, type, class}>`. Skip the top 5 header rows and the trailing `"Total"` row.
4. Parse `Chart of Accounts - Reportin...` → walk rows, tracking the current reporting-code group header. For each data row:
   - If the row matches `^(\S+)\s*-\s*(.+)$`, extract `(code, name)`.
   - Otherwise treat the entire cell as the account name, with no code. This supports bank accounts and similar that Xero allows without a numeric code.
   - Skip rows starting with `"Total "` and the grand total at the end.
5. Merge reporting-code rows into `Account[]`:
   - Row has a code → join to the Type-and-Class map by code. If no match, exclude (system-generated account like Current Year Earnings).
   - Row has no code → join to the Type-and-Class map by exact case-insensitive name. If no match, exclude.
   - On match, attach `reportCode` (the current group header), `type`, and `class`.
6. Parse the three `Account Movements - …` sheets using the existing GL-Summary row parser (column schema is unchanged: Account, Account Code, Opening Balance, Debit, Credit, Net Movement, Closing Balance, Account Type).
7. Parse `Depreciation Schedule` and `Beneficiary Accounts` using the existing parsers from the old Chart Check Report (schemas unchanged). Empty sheets produce empty arrays — never throw.
8. Apply the **archive filter**: drop any account whose code is not present in `glSummaryConsidered`. For code-less accounts (bank accounts without a number), match by name. Accounts that survive this filter are the set the user can ever see or export.
9. Apply the **activity tag**:
   - `mandatory` if the account's code (or name) appears in `glSummaryComparative`.
   - `optional` otherwise (present in Considered, absent from Comparative).

### 5.2 Edge cases

- **No code on Reporting Codes side, matched by name** — kept. Used for unnumbered bank accounts.
- **Code on Type-and-Class but not Reporting Codes** — excluded as a system-level account.
- **Row missing on Type-and-Class (e.g. Current Year Earnings)** — excluded.
- **Malformed reporting-code group headers** — not handled in code. One instance was found in the demo file (`PAYGLIA.CUR.PAY.PAY`) and has been fixed at the Xero source. If any leak through in the future, the pipeline's existing reporting-code validation will surface them and the user will fix them upstream.
- **Sheet name truncation** — always occurs, always consistent. Parser matches by truncated name; the full name (for error messages) is read from cell A1 when needed.

## 6. UI changes

### 6.1 InputPanel

- Remove the "Chart of Accounts" and "Chart Check Report" drop zones.
- Add a single **"Verification Report"** drop zone (`.xlsx` only).
- Keep the optional **"Group Relationships"** drop zone as-is.
- `canRun` becomes: `verificationReport !== null && rulesData !== null && !isProcessing`.
- On successful parse, show a summary: `N accounts · X mandatory · Y optional`.
- Add a persistent yellow banner above the input zone: *"Before using this report, make sure you've exported a fresh Verification Report from Xero — stale data will produce stale mappings."*

### 6.2 MappingTable

- **Activity filter (segmented control):** Mandatory | Optional | All. Default: Mandatory.
- **Status filter (dropdown):** All | Pending | Accepted | Overridden.
- **Source filter (dropdown):** All | one entry per distinct `source` value, with `(count)` next to each label. Rebuilt from `mappedAccounts` whenever the mapping changes.
- **"Needs Review" / "Fallback Only" / "Type Mismatch" / "Active"** chips: keep them as quick-filter shortcuts alongside the new controls.
- **Progress counters** in the toolbar: `Accepted N · Overridden N · Pending N · M% complete`.
- **Clear All** button in the toolbar: prompts for confirmation, then resets all decisions for the current client (overrides, type overrides, approval flags). Does not reset the decision for other clients stored in localStorage.
- **Decision column** renders a subtle "Mandatory" / "Optional" badge in the `All` view; hidden in the single-bucket views.

### 6.3 AccountDetailPanel

- **Override code description lookup:** when the user types or picks a code in the override input, display the description of that code (from `codeToName`) inline. Already partially present; ensure it reacts to typing as well as dropdown selection.

### 6.4 Reporting name auto-derivation

A new utility `deriveReportingName(account: MappedAccount): string | null` is applied during CSV export. Initial patterns:

| Trigger (normalised name) | Derived Reporting Name |
|---|---|
| Matches `/^ato\s+(ica|integrated client account)/i` | `ATO ICA` |
| Matches `/^ato\s+(ita|income tax account)/i` | `ATO ITA` |
| Matches `/^(div\s*7a|division\s*7a|.*\b7a\b)/i` AND contains a 4-digit year | `Div7A <YYYY>` |

The function is called from `generateExportCSV` and populates the `Reporting Name` column when empty. Explicit overrides win.

## 7. Persistence

### 7.1 localStorage schema

One namespaced key per client:

```
xrcm:decisions:v1:<clientKey>
```

`clientKey` is derived from `clientParams.displayName` with spaces collapsed to `_`, lowercased, and non-alphanumerics stripped. If no display name is present, key falls back to a hash of the account codes. This matches the scoping fix already applied to the old HTML report.

Value schema:

```ts
{
  version: 1,
  clientKey: string,
  savedAt: string,                             // ISO timestamp
  decisions: Record<string, {                   // keyed by account.code
    overrideCode?: string,
    overrideReason?: string,
    typeOverride?: string,
    approved?: boolean,
    auto?: boolean,                             // true when set by autoConfirmMatches
  }>
}
```

### 7.2 Store integration

- New store slice: `decisionsByClient: Record<string, DecisionMap>` — in-memory mirror of localStorage.
- On `setMappedAccounts`: hydrate each row's decision fields from `decisionsByClient[clientKey]` before rendering.
- On `overrideAccount` / `approveAccount` / `overrideAccountType`: mutate the in-memory decisions and persist the current client's slice.
- `reset` / Clear All: deletes the current client's key; other clients are untouched.

## 8. Auto-confirm matches

Runs once per pipeline run, immediately after `setMappedAccounts`. For each account:

1. Skip if `reportCode` is empty.
2. Skip if `overrideCode` or `approved` is already set (user decision wins).
3. Skip if `predictedCode !== reportCode`.
4. Skip if the account's type is not in `SYSTEM_TYPES` and:
   - `HEAD_FROM_TYPE[type] !== firstSegment(predictedCode)`, OR
   - `REQUIRED_PREFIX_BY_TYPE[type]` exists and `predictedCode` does not start with that prefix.
5. Otherwise set `approved = true, auto = true` and persist.

The toolbar Decision cell keeps showing "Auto" for these, so visually nothing regresses — but now the flag reflects a real decision rather than a display-only heuristic, and incompatible codes are no longer silently auto-approved.

## 9. Prefix-level type mismatch

Add `REQUIRED_PREFIX_BY_TYPE` to `web/src/pipeline/typePredict.ts`, ported from `tools/gen_review_report.py`:

```ts
export const REQUIRED_PREFIX_BY_TYPE: Record<string, string> = {
  'Direct Costs': 'EXP.COS',
  'Depreciation': 'EXP.DEP',
  'Fixed Asset': 'ASS.NCA.FIX',
  'Inventory': 'ASS.CUR.INY',
  'Prepayment': 'ASS.CUR.REC.PRE',
  'Revenue': 'REV.TRA',
  'Sales': 'REV.TRA',
  'Current Asset': 'ASS.CUR',
  'Non-current Asset': 'ASS.NCA',
  'Current Liability': 'LIA.CUR',
  'Non-current Liability': 'LIA.NCL',
};
```

Update `hasTypeMismatchForAccount` in `MappingTable.tsx`:

```ts
function hasTypeMismatchForAccount(acct: MappedAccount): boolean {
  if (SYSTEM_TYPES.has(acct.type)) return false;
  const finalCode = (acct.overrideCode || acct.predictedCode).toUpperCase();
  if (!finalCode) return false;
  const currentHead = HEAD_FROM_TYPE[acct.type] || '';
  const codeHead = finalCode.split('.')[0];
  if (currentHead && currentHead !== codeHead) return true;           // head mismatch
  const requiredPrefix = REQUIRED_PREFIX_BY_TYPE[acct.type];
  return !!requiredPrefix && !finalCode.startsWith(requiredPrefix);    // prefix mismatch
}
```

This strictly widens what counts as a mismatch — existing head-level mismatches keep triggering, and the new prefix cases are added on top.

## 10. Files touched

**Added**
- `web/src/parsers/verificationReportParser.ts`
- `web/src/parsers/__tests__/verificationReportParser.test.ts`
- `web/src/services/decisionsStorage.ts` (localStorage read/write)
- `web/src/pipeline/autoConfirm.ts` (pure function)

**Modified**
- `web/src/components/InputPanel.tsx` — single drop zone, safety banner, summary.
- `web/src/components/MappingTable.tsx` — activity / status / source filters, progress counters, Clear All, mandatory/optional badge, tighter mismatch check.
- `web/src/components/AccountDetailPanel.tsx` — description-on-type for override input.
- `web/src/store/appStore.ts` — `verificationReport` slot, `decisionsByClient`, hydration wiring.
- `web/src/pipeline/pipeline.ts` — invoke `autoConfirm` post-map.
- `web/src/pipeline/typePredict.ts` — add `REQUIRED_PREFIX_BY_TYPE`.
- `web/src/types/index.ts` — `VerificationReportData`, `activity` field on `Account`.
- `mapping_logic_v15.py` — deprecation notice at top of file.

**Deleted**
- `web/src/parsers/chartParser.ts`
- `web/src/parsers/chartCheckParser.ts`
- `web/src/parsers/__tests__/chartParser.test.ts`
- `web/src/parsers/__tests__/chartCheckParser.test.ts`

## 11. Testing

- **Parser unit tests** (Vitest): cover all seven sheets present, each sheet missing (seven failure cases), code-matched merge, name-matched merge, code-less bank account, Type-and-Class orphan (excluded), Current Year Earnings (excluded), empty Dep Schedule, empty Beneficiary Accounts, archive filter (code in none of the movement sheets), Mandatory tag, Optional tag.
- **Auto-confirm unit tests**: head-compatible match confirms; head-incompatible match does not; prefix-incompatible match does not; already-decided row is not touched; system-typed row confirms without prefix check.
- **Mismatch detection unit tests**: Direct Costs + `EXP.REN` flags; Direct Costs + `EXP.COS.FOO` passes; Fixed Asset + `ASS.CUR` flags; Inventory + `ASS.CUR.INY.X` passes.
- **Decisions storage tests**: per-client scoping, hydration into a fresh `mappedAccounts` array, Clear All does not affect other clients.
- **Smoke test**: load the real demo workbook (`.dev-info/Demo_Company__AU__-_Chart_of_Accounts_Verification_Report.xlsx`), run the pipeline, confirm the account count and that Mandatory / Optional bucketing matches expectations.

## 12. Open risks

- **Demo workbook drift.** The user has been regenerating the demo file during this design session. The parser must tolerate the Current / Comparative / Considered trio being renamed slightly or arriving in a different sheet order. Sheet lookup is by truncated-prefix match, not by index.
- **Reporting-name derivation scope creep.** Only three patterns are implemented. If more are needed, they get added to `deriveReportingName`. Out of scope for this task: user-configurable patterns.
- **Activity tag accuracy for code-less accounts.** Bank accounts without a number match by name. If a bank account's name changes between sheets or has whitespace drift, it may be miscategorised. Mitigation: normalise both sides (trim, collapse whitespace, lowercase) before matching.
