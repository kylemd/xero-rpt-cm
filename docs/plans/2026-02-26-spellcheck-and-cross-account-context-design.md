# Spell-Check & Cross-Account Context Design

**Goal:** Improve code assignment accuracy by (1) correcting misspelt account names before rule matching, and (2) using chart-wide context to refine ambiguous head-only assignments.

**Architecture:** Two new processing stages added to the existing multi-pass pipeline in `mapping_logic_v15.py`. Spell-check runs as a pre-processing step before the main mapping loop. Cross-account context runs as a post-processing pass after accumulated depreciation strengthening.

**New dependency:** `pyspellchecker` (pure Python, Levenshtein distance edit-distance-2 correction).

---

## Feature 1: Spell-Check Pre-Processing

### Placement

Before the main mapping loop (before line 510 in `mapping_logic_v15.py`). Runs once over all account names, producing corrected names that feed into `normalise()` for rule engine matching.

### Pipeline Flow

1. **Initialise pyspellchecker** with English dictionary
2. **Whitelist domain terms** so they are not "corrected" to English words:
   - `AUSTRALIAN_BANKS` from `rules.py`
   - `VEHICLE_MAKES` from `rules.py`
   - `AUSTRALIAN_LENDERS` from `rules.py`
   - `OWNER_KEYWORDS` from `rules.py`
   - Business name extracted from trial balance header (row 1 of XLSX)
   - Common accounting abbreviations: PAYG, ATO, GST, ASIC, BAS, FBT, SGC, SGA, RCTI, etc.
3. **For each account name**, split into tokens and process in two stages:
   - **Stage A — Abbreviation expansion:** Look up each token in `ABBREVIATIONS` dict. If found, replace with expansion (e.g., `"scg"` -> `"sgc"`, `"lsl"` -> `"long service leave"`)
   - **Stage B — Typo correction:** Run remaining tokens through `spell.correction()`. Accept correction only when edit distance is 1-2 and the original token is `spell.unknown()` (not in dictionary or whitelist)
4. **Store results:**
   - `corrected_names[idx]` = corrected name string (or original if no changes)
   - `spell_corrections[idx]` = list of `{"original": "revalution", "corrected": "revaluation"}` dicts (empty if no changes)
5. **Main mapping loop** uses `corrected_names[idx]` instead of raw `row['*Name']` when calling `normalise()`

### Abbreviation Dictionary

New file: `spell_corrections.py` (keeps data separate from logic, like `rules.py`).

```python
# Domain-specific abbreviation expansions
ABBREVIATIONS = {
    "scg": "sgc",           # Super Guarantee Charge (common letter swap)
    "lsl": "long service leave",
    "wip": "work in progress",
    "fy": "financial year",
    "ytd": "year to date",
    "mtd": "month to date",
    "p&l": "profit and loss",
    "bal": "balance",
    "acct": "account",
    "dept": "department",
    "govt": "government",
    "insur": "insurance",
    "maint": "maintenance",
    "mgmt": "management",
    "prepd": "prepaid",
    "prov": "provision",
    "reval": "revaluation",
    "accum": "accumulated",
    "depr": "depreciation",
    "amort": "amortisation",
}

# Terms to whitelist in pyspellchecker (not typos, just domain jargon)
ACCOUNTING_TERMS = [
    "payg", "ato", "gst", "asic", "bas", "fbt", "sgc", "sga",
    "rcti", "abn", "acn", "tfn", "smsf", "div7a",
    "xero", "myob", "quickbooks",
    "pty", "ltd",
    "superannuation", "annuation",
    # Add more as discovered
]
```

### HTML Report Display

When spell corrections were applied to an account name, the HTML review report shows:
- **Primary:** Corrected name (used for matching) as the bold account name
- **Subtitle:** Original name in small grey italic text underneath (same `detail-row` style used for code descriptions)

Example rendering:
```
Asset Revaluation Reserve          (bold, corrected)
Originally: Asset Revalution Reserve   (grey italic subtitle)
```

No changes to the Source field or NeedsReview flag — spell correction is transparent but non-intrusive.

### Output

- `AugmentedChartOfAccounts.csv`: `*Name` column retains the **original** uncorrected name (it's the client's data)
- A new optional column `CorrectedName` contains the corrected name (only populated when corrections were applied)
- `ChangeOrErrorReport.csv`: Log each correction with IssueType `SpellCorrection`

---

## Feature 2: Cross-Account Context Pass

### Placement

New Pass 4, after accumulated depreciation strengthening (Pass 2) and before ServiceOnlyRevenueAdjustment (Pass 3). This ordering means cross-account context can use Pass 2's strengthened depreciation codes, and ServiceOnlyRevenueAdjustment still gets the final word on cost-of-sales reclassification.

### Key Constraint

Cross-account inference only applies when anchor accounts have a **non-zero closing balance in the trial balance**. An inactive account provides no context about the business.

### Tier 1: Fixed Asset Grouping (Priority)

**Anchor detection:** Scan all accounts for known high-signal patterns with active trial balance balances:

| Anchor Pattern | Implies | Inference for Nearby Head-Only Accounts |
|---|---|---|
| Goodwill (active balance) | Business acquisition | Nearby `ASS` fallbacks with "legal", "capital", "acquisition" keywords -> `ASS.NCA.INT` |
| Land / Buildings (active) | Property ownership | Nearby `ASS` fallbacks with "improvements", "fitout" -> `ASS.NCA.FIX.PLA` |
| Motor Vehicles (active) | Vehicle fleet | Nearby `LIA` fallbacks with finance/loan keywords -> `LIA.NCL.HPA` |

**"Nearby" definition:** Accounts whose numeric code falls within a configurable range of the anchor's code (e.g., within 20 code numbers). This works because Xero charts typically group related accounts by code number.

**Logic:**
```
for each anchor account with active balance:
    for each nearby account that fell to head-only (FallbackParent):
        if name keywords match inference rules for this anchor:
            refine code to specific leaf
            set Source = 'CrossAccountContext'
            set NeedsReview = 'Y'  (still flagged for human review)
```

### Tier 2: Balance Sheet Section Inference

After all codes are assigned, group accounts by code number ranges and look for consensus:

- If 4 of 5 accounts in code range 700-730 are `ASS.NCA.*`, and the 5th is generic `ASS`, infer `ASS.NCA`
- Only applies to head-only fallback accounts (don't override specific rule matches)
- Weighted by trial balance activity (active accounts contribute more to section consensus)

### Tier 3: Type Inconsistency Detection

Compare each account's Xero type against its assigned code head. Flag mismatches as notes in the review report. This supplements the existing Expected Type column — it adds a note explaining *why* the type might be wrong based on chart context.

Example: "Account type is 'Current Liability' but code EQU.RET suggests this should be 'Equity'. 4 other accounts in this range are Equity-typed."

### Data Structures

The cross-account pass needs access to:
- `prc[]` — predicted codes from Pass 1 (read + write)
- `src[]` — source reasons (write)
- `need[]` — review flags (write)
- `coa` DataFrame — account names, types, codes (read)
- `bal_lookup` — trial balance balances (read)
- `overridden_indices` — skip audited overrides (read)

All of these are already available in the pipeline scope.

### Configuration

Inference rules defined as data (similar to `rules.py`), not hardcoded logic:

```python
CONTEXT_ANCHORS = [
    {
        "name": "goodwill_intangibles",
        "anchor_keywords": ["goodwill"],
        "anchor_types": {"non-current asset", "fixed asset"},
        "nearby_keywords": ["legal", "capital", "acquisition", "formation"],
        "nearby_fallback_heads": {"ASS"},
        "inferred_code": "ASS.NCA.INT",
        "proximity": 50,
    },
    # More anchors...
]
```

---

## Testing Strategy

### Spell-Check Tests
- Unit tests for abbreviation expansion (ABBREVIATIONS dict)
- Unit tests for pyspellchecker integration (mock spell checker)
- Integration test: "Asset Revalution Reserve" -> corrected -> matches `asset_revaluation_reserve` rule
- Integration test: "ATO - SCG payable" -> "scg" expanded to "sgc" -> matches `sgc_payable` rule
- Whitelist test: bank names, vehicle makes not corrected

### Cross-Account Context Tests
- Unit tests for anchor detection with mock trial balance
- Unit tests for proximity-based inference
- Integration test: Goodwill (active) + "Capital Legal Expenses" -> `ASS.NCA.INT`
- Integration test: Goodwill (zero balance) + "Capital Legal Expenses" -> no inference (stays `ASS`)
- Negative test: Don't override specific rule matches, only head-only fallbacks

---

## Files Modified/Created

| File | Change |
|---|---|
| `spell_corrections.py` | **New** — ABBREVIATIONS dict, ACCOUNTING_TERMS whitelist |
| `mapping_logic_v15.py` | Add spell-check pre-processing, add cross-account context pass |
| `tools/gen_review_report.py` | Show original name subtitle when spell-corrected |
| `pyproject.toml` | Add `pyspellchecker` dependency |
| `tests/test_spellcheck.py` | **New** — spell-check unit tests |
| `tests/test_cross_account.py` | **New** — cross-account context unit tests |
| `tests/test_integration.py` | Update xfails if cross-account fixes previously-ambiguous accounts |

---

## What This Doesn't Solve

- **310/313 (Cost of Sales):** ServiceOnlyRevenueAdjustment override — user said leave as-is
- **645 (Deposit):** "Deposit" is genuinely ambiguous without business context beyond what chart structure provides. May remain a head-only fallback requiring human review.
