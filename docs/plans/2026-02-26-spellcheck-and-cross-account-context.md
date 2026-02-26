# Spell-Check & Cross-Account Context Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve code assignment accuracy by correcting misspelt account names before rule matching and using chart-wide context to refine ambiguous head-only assignments.

**Architecture:** Two new processing stages in `mapping_logic_v15.py`: a spell-check pre-processing step before the main mapping loop, and a cross-account context post-processing pass after accumulated depreciation. A new `spell_corrections.py` module holds the abbreviation dictionary and accounting term whitelist. The `pyspellchecker` library handles general English typo correction.

**Tech Stack:** Python 3.12, pyspellchecker, pandas, existing rule engine

---

### Task 1: Add pyspellchecker dependency

**Files:**
- Modify: `pyproject.toml:7-10`

**Step 1: Add pyspellchecker to dependencies**

In `pyproject.toml`, change:

```toml
dependencies = [
    "pandas>=2.3.2",
    "openpyxl>=3.1.2",
]
```

To:

```toml
dependencies = [
    "pandas>=2.3.2",
    "openpyxl>=3.1.2",
    "pyspellchecker>=0.8.0",
]
```

**Step 2: Install the new dependency**

Run: `uv sync`
Expected: Successfully resolves and installs pyspellchecker

**Step 3: Verify import works**

Run: `uv run python -c "from spellchecker import SpellChecker; s = SpellChecker(); print('OK:', s.correction('revalution'))"`
Expected: `OK: revaluation`

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add pyspellchecker dependency"
```

---

### Task 2: Create spell_corrections.py module

**Files:**
- Create: `spell_corrections.py`
- Test: `tests/test_spellcheck.py`

**Step 1: Write the failing tests**

Create `tests/test_spellcheck.py`:

```python
"""Tests for spell correction preprocessing."""
import pytest
from spell_corrections import (
    ABBREVIATIONS, ACCOUNTING_TERMS,
    build_spell_checker, correct_account_name,
)


class TestAbbreviations:
    def test_scg_expands_to_sgc(self):
        result = correct_account_name("ATO - SCG payable", spell=None)
        assert "sgc" in result["corrected"].lower()

    def test_lsl_expands(self):
        result = correct_account_name("LSL Provision", spell=None)
        assert "long service leave" in result["corrected"].lower()

    def test_no_change_when_no_abbreviation(self):
        result = correct_account_name("Trade Debtors", spell=None)
        assert result["corrected"] == "Trade Debtors"
        assert result["corrections"] == []


class TestSpellChecker:
    @pytest.fixture
    def spell(self):
        return build_spell_checker(extra_known=[])

    def test_revalution_corrected(self, spell):
        result = correct_account_name("Asset Revalution Reserve", spell=spell)
        assert "revaluation" in result["corrected"].lower()
        assert len(result["corrections"]) == 1
        assert result["corrections"][0]["original"] == "Revalution"

    def test_known_terms_not_corrected(self, spell):
        result = correct_account_name("PAYG Withholding", spell=spell)
        # PAYG should not be corrected to an English word
        assert "payg" in result["corrected"].lower()

    def test_bank_names_whitelisted(self):
        from rules import AUSTRALIAN_BANKS
        spell = build_spell_checker(extra_known=AUSTRALIAN_BANKS)
        result = correct_account_name("Westpac Business Account", spell=spell)
        assert "westpac" in result["corrected"].lower()
        assert result["corrections"] == []

    def test_business_name_whitelisted(self):
        spell = build_spell_checker(extra_known=["acmecorp", "invigor8"])
        result = correct_account_name("Invigor8 Loan Account", spell=spell)
        assert result["corrections"] == []


class TestBuildSpellChecker:
    def test_accounting_terms_are_known(self):
        spell = build_spell_checker(extra_known=[])
        unknown = spell.unknown(["payg", "ato", "gst", "asic", "fbt"])
        assert len(unknown) == 0

    def test_extra_known_words_added(self):
        spell = build_spell_checker(extra_known=["westpac", "commbank"])
        unknown = spell.unknown(["westpac", "commbank"])
        assert len(unknown) == 0
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_spellcheck.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'spell_corrections'`

**Step 3: Create spell_corrections.py**

Create `spell_corrections.py`:

```python
"""Spell correction preprocessing for account names.

Provides abbreviation expansion and typo correction using pyspellchecker.
Domain-specific accounting terms and project dictionaries (bank names,
vehicle makes, lender names) are whitelisted to prevent false corrections.
"""
from typing import Dict, List, Optional

from spellchecker import SpellChecker


# Domain-specific abbreviation expansions.
# Applied before spell-checking. Keys are lowercase tokens.
ABBREVIATIONS: Dict[str, str] = {
    "scg": "sgc",
    "lsl": "long service leave",
    "wip": "work in progress",
    "fy": "financial year",
    "ytd": "year to date",
    "mtd": "month to date",
    "bal": "balance",
    "acct": "account",
    "dept": "department",
    "govt": "government",
    "insur": "insurance",
    "maint": "maintenance",
    "mgmt": "management",
    "prepd": "prepaid",
    "prov": "provision",
    "depr": "depreciation",
    "amort": "amortisation",
}

# Terms to whitelist in pyspellchecker — valid domain jargon, not typos.
ACCOUNTING_TERMS: List[str] = [
    "payg", "ato", "gst", "asic", "bas", "fbt", "sgc", "sga", "atsgc",
    "rcti", "abn", "acn", "tfn", "smsf",
    "xero", "myob", "quickbooks",
    "pty", "ltd",
    "superannuation", "annuation",
    "div7a", "payable", "receivable", "accrual", "accruals",
    "amortisation", "amortization", "depreciation",
    "franking", "imputation", "gearing",
]


def build_spell_checker(extra_known: List[str]) -> SpellChecker:
    """Build a SpellChecker with domain terms and extra words whitelisted.

    Args:
        extra_known: Additional words to whitelist (bank names, vehicle makes,
                     lender names, business name tokens, etc.)
    """
    spell = SpellChecker()
    # Whitelist accounting terms
    spell.word_frequency.load_words(ACCOUNTING_TERMS)
    # Whitelist extra domain words (lowercased)
    if extra_known:
        spell.word_frequency.load_words([w.lower() for w in extra_known])
    return spell


def correct_account_name(
    name: str,
    spell: Optional[SpellChecker] = None,
) -> Dict:
    """Correct an account name via abbreviation expansion then spell-check.

    Args:
        name: Raw account name from the chart of accounts.
        spell: Pre-built SpellChecker instance. If None, only abbreviation
               expansion is applied (no typo correction).

    Returns:
        Dict with keys:
            corrected: The corrected name string.
            corrections: List of {original, corrected, source} dicts.
    """
    tokens = name.split()
    corrections = []
    result_tokens = []

    for token in tokens:
        lower = token.lower()

        # Stage A: Abbreviation expansion
        if lower in ABBREVIATIONS:
            expanded = ABBREVIATIONS[lower]
            corrections.append({
                "original": token,
                "corrected": expanded,
                "source": "abbreviation",
            })
            result_tokens.append(expanded)
            continue

        # Stage B: Spell-check (if checker provided)
        if spell is not None:
            # Only check tokens that look like words (skip codes, numbers)
            if lower.isalpha() and len(lower) > 2:
                unknown = spell.unknown([lower])
                if unknown:
                    suggestion = spell.correction(lower)
                    if suggestion and suggestion != lower:
                        # Preserve original casing style
                        if token[0].isupper():
                            suggestion = suggestion.capitalize()
                        if token.isupper():
                            suggestion = suggestion.upper()
                        corrections.append({
                            "original": token,
                            "corrected": suggestion,
                            "source": "spellcheck",
                        })
                        result_tokens.append(suggestion)
                        continue

        result_tokens.append(token)

    corrected = " ".join(result_tokens)
    return {"corrected": corrected, "corrections": corrections}
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_spellcheck.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add spell_corrections.py tests/test_spellcheck.py
git commit -m "feat: add spell_corrections module with abbreviation expansion and pyspellchecker"
```

---

### Task 3: Extract company name from trial balance

**Files:**
- Modify: `file_handler.py:89-106`

**Step 1: Write the failing test**

Add to `tests/test_spellcheck.py`:

```python
class TestTrialBalanceCompanyName:
    def test_metadata_includes_company_name(self):
        """Trial balance metadata should include the company name from row 1."""
        import pathlib
        from file_handler import load_trial_balance_file
        tb_path = pathlib.Path(".dev-info/test-client/Trial_Balance.xlsx")
        if not tb_path.exists():
            pytest.skip("Test client trial balance not available")
        _, metadata = load_trial_balance_file(tb_path)
        assert "company_name" in metadata
        assert isinstance(metadata["company_name"], str)
        assert len(metadata["company_name"]) > 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_spellcheck.py::TestTrialBalanceCompanyName -v`
Expected: FAIL — `AssertionError: assert 'company_name' in {...}`

**Step 3: Modify file_handler.py to extract company name**

In `file_handler.py`, in the `sanitize_xlsx_trial_balance` function, at line 94 (after `period_date` extraction), add company name extraction:

Change lines 94-106 from:

```python
        period_date = str(df.iloc[2, 0]).strip().replace("As at ", "")

        # Skip first 4 rows
        df = df.iloc[4:].reset_index(drop=True)

        # Promote first row to header
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)

        # Parse amounts according to Xero format
        df = parse_trial_balance_amounts(df, {"format": "xero_trial_balance", "period": period_date})

        return df, {"format": "xero_trial_balance", "period": period_date, "sanitized": True}
```

To:

```python
        period_date = str(df.iloc[2, 0]).strip().replace("As at ", "")
        company_name = str(df.iloc[1, 0]).strip() if len(df) > 1 and pd.notnull(df.iloc[1, 0]) else ""

        # Skip first 4 rows
        df = df.iloc[4:].reset_index(drop=True)

        # Promote first row to header
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)

        # Parse amounts according to Xero format
        metadata = {"format": "xero_trial_balance", "period": period_date, "company_name": company_name, "sanitized": True}
        df = parse_trial_balance_amounts(df, metadata)

        return df, metadata
```

Note: Add `import pandas as pd` at top if not already present (check — it likely is).

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_spellcheck.py::TestTrialBalanceCompanyName -v`
Expected: PASS

**Step 5: Run full test suite to check for regressions**

Run: `uv run pytest tests/ -v --tb=short`
Expected: 860+ passed, 0 failures

**Step 6: Commit**

```bash
git add file_handler.py tests/test_spellcheck.py
git commit -m "feat: extract company name from trial balance metadata"
```

---

### Task 4: Integrate spell-check into mapping pipeline

**Files:**
- Modify: `mapping_logic_v15.py:310-315,510-512`

**Step 1: Add imports**

At the top of `mapping_logic_v15.py`, add after existing imports:

```python
from spell_corrections import build_spell_checker, correct_account_name
from rules import AUSTRALIAN_BANKS, VEHICLE_MAKES, AUSTRALIAN_LENDERS
```

Note: `OWNER_KEYWORDS` is already imported from rules.

**Step 2: Build the spell checker after trial balance loading**

After line 314 (`print(f"Loaded trial balance: {trial_metadata}")`), add:

```python
# Build spell checker with domain dictionaries
_extra_known = AUSTRALIAN_BANKS + VEHICLE_MAKES + AUSTRALIAN_LENDERS
# Add business name tokens from trial balance
_company_name = trial_metadata.get("company_name", "")
if _company_name:
    _extra_known.extend(_company_name.lower().split())
spell_checker = build_spell_checker(extra_known=_extra_known)
```

**Step 3: Apply spell correction in the main loop**

At line 512, change:

```python
clean_nm=normalise(strip_noise_suffixes(row['*Name']))
```

To:

```python
_raw_name = row['*Name']
_spell_result = correct_account_name(strip_noise_suffixes(_raw_name), spell=spell_checker)
_corrected_name = _spell_result["corrected"]
if _spell_result["corrections"]:
    spell_log.append({"idx": idx, "code": row.get("*Code", ""), "original": _raw_name, "corrected": _corrected_name, "corrections": _spell_result["corrections"]})
clean_nm = normalise(_corrected_name)
```

Also, initialise `spell_log = []` before the main loop (around line 509).

**Step 4: Add corrected name to output**

After line 760 (`coa['Source']=src`), add:

```python
# Add corrected names column (only populated when corrections applied)
corrected_names = [""] * len(coa)
for entry in spell_log:
    corrected_names[entry["idx"]] = entry["corrected"]
coa['CorrectedName'] = corrected_names
```

Also add spell corrections to the ChangeOrErrorReport (find the section around line 780 that builds `change_rows` and append):

```python
for entry in spell_log:
    change_rows.append({
        "RowNumber": entry["idx"] + 1,
        "FieldName": "*Name",
        "OriginalValue": entry["original"],
        "CorrectedValue": entry["corrected"],
        "IssueType": "SpellCorrection",
        "Notes": "; ".join(f"{c['original']}→{c['corrected']} ({c['source']})" for c in entry["corrections"]),
    })
```

**Step 5: Run full test suite**

Run: `uv run pytest tests/ -v --tb=short`
Expected: 860+ passed, 0 failures

**Step 6: Test with test-client data**

Run: `uv run python mapping_logic_v15.py ".dev-info/test-client/ChartOfAccounts (3).csv" ".dev-info/test-client/Trial_Balance.xlsx" --chart company`
Expected: Runs successfully. Check `AugmentedChartOfAccounts.csv` for `CorrectedName` column.

Verify spell corrections applied:
```
uv run python -c "
import csv
with open('.dev-info/test-client/AugmentedChartOfAccounts.csv') as f:
    for r in csv.DictReader(f):
        cn = r.get('CorrectedName','')
        if cn:
            print(f'{r[\"*Code\"]:>8} {r[\"*Name\"][:40]:<42} → {cn}')
"
```

**Step 7: Commit**

```bash
git add mapping_logic_v15.py
git commit -m "feat: integrate spell-check preprocessing into mapping pipeline"
```

---

### Task 5: Show spell corrections in HTML review report

**Files:**
- Modify: `tools/gen_review_report.py:38-59,273`

**Step 1: Load corrected name from augmented CSV**

In `load_augmented()` (line 38), add to the account dict:

```python
"corrected_name": row.get("CorrectedName", "").strip(),
```

**Step 2: Show original name subtitle when corrected**

At line 273, change:

```python
parts.append(f'  <td><strong>{h(a["name"])}</strong></td>\n')
```

To:

```python
if a["corrected_name"]:
    parts.append(f'  <td><strong>{h(a["corrected_name"])}</strong>'
                 f'<br><span class="detail-row" style="font-style:italic">Originally: {h(a["name"])}</span></td>\n')
else:
    parts.append(f'  <td><strong>{h(a["name"])}</strong></td>\n')
```

**Step 3: Include corrected_name in search data**

At the `search_text` construction (around line 263), add `a["corrected_name"]` to the search string so users can search for either the original or corrected name.

**Step 4: Run report generator and verify**

Run:
```bash
uv run python mapping_logic_v15.py ".dev-info/test-client/ChartOfAccounts (3).csv" ".dev-info/test-client/Trial_Balance.xlsx" --chart company
uv run python tools/gen_review_report.py ".dev-info/test-client/AugmentedChartOfAccounts.csv"
```

Open `ReviewReport.html` and verify corrected names show with "Originally:" subtitle.

**Step 5: Commit**

```bash
git add tools/gen_review_report.py
git commit -m "feat: show spell-corrected names with original subtitle in review report"
```

---

### Task 6: Cross-account context — anchor detection and data structures

**Files:**
- Create: `context_rules.py`
- Test: `tests/test_cross_account.py`

**Step 1: Write the failing tests**

Create `tests/test_cross_account.py`:

```python
"""Tests for cross-account context pass."""
import pytest
from context_rules import CONTEXT_ANCHORS, detect_anchors, infer_from_context


class TestAnchorDetection:
    def test_goodwill_detected_when_active(self):
        """Goodwill with non-zero balance should be detected as anchor."""
        accounts = [
            {"code": "718", "name": "goodwill", "type": "Non-current Asset",
             "predicted": "ASS.NCA.INT.GOO", "source": "some_rule"},
        ]
        bal = {"718": 50000.0}
        anchors = detect_anchors(accounts, bal)
        assert len(anchors) >= 1
        assert any(a["anchor_name"] == "goodwill_intangibles" for a in anchors)

    def test_goodwill_ignored_when_zero_balance(self):
        """Goodwill with zero balance should not be detected."""
        accounts = [
            {"code": "718", "name": "goodwill", "type": "Non-current Asset",
             "predicted": "ASS.NCA.INT.GOO", "source": "some_rule"},
        ]
        bal = {"718": 0.0}
        anchors = detect_anchors(accounts, bal)
        assert not any(a["anchor_name"] == "goodwill_intangibles" for a in anchors)

    def test_goodwill_ignored_when_no_balance(self):
        """Goodwill not in trial balance should not be detected."""
        accounts = [
            {"code": "718", "name": "goodwill", "type": "Non-current Asset",
             "predicted": "ASS.NCA.INT.GOO", "source": "some_rule"},
        ]
        bal = {}
        anchors = detect_anchors(accounts, bal)
        assert not any(a["anchor_name"] == "goodwill_intangibles" for a in anchors)


class TestContextInference:
    def test_capital_legal_near_goodwill(self):
        """Capital Legal Expenses near active Goodwill should infer ASS.NCA.INT."""
        accounts = [
            {"code": "718", "name": "goodwill", "type": "Non-current Asset",
             "predicted": "ASS.NCA.INT.GOO", "source": "some_rule"},
            {"code": "720", "name": "capital legal expenses", "type": "Non-current Asset",
             "predicted": "ASS", "source": "FallbackParent"},
        ]
        bal = {"718": 50000.0, "720": 12000.0}
        overridden = set()
        result = infer_from_context(accounts, bal, overridden)
        match = [r for r in result if r["code"] == "720"]
        assert len(match) == 1
        assert match[0]["inferred_code"] == "ASS.NCA.INT"

    def test_no_inference_when_already_specific(self):
        """Accounts with specific codes should not be overridden."""
        accounts = [
            {"code": "718", "name": "goodwill", "type": "Non-current Asset",
             "predicted": "ASS.NCA.INT.GOO", "source": "some_rule"},
            {"code": "720", "name": "capital legal expenses", "type": "Non-current Asset",
             "predicted": "ASS.NCA.FIX.PLA", "source": "ppe_asset"},
        ]
        bal = {"718": 50000.0, "720": 12000.0}
        overridden = set()
        result = infer_from_context(accounts, bal, overridden)
        match = [r for r in result if r["code"] == "720"]
        assert len(match) == 0

    def test_no_inference_when_overridden(self):
        """Audited overrides should be skipped."""
        accounts = [
            {"code": "718", "name": "goodwill", "type": "Non-current Asset",
             "predicted": "ASS.NCA.INT.GOO", "source": "some_rule"},
            {"code": "720", "name": "capital legal expenses", "type": "Non-current Asset",
             "predicted": "ASS", "source": "FallbackParent"},
        ]
        bal = {"718": 50000.0, "720": 12000.0}
        overridden = {1}  # index of code 720
        result = infer_from_context(accounts, bal, overridden)
        match = [r for r in result if r["code"] == "720"]
        assert len(match) == 0
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cross_account.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'context_rules'`

**Step 3: Create context_rules.py**

Create `context_rules.py`:

```python
"""Cross-account context rules for refining ambiguous code assignments.

Detects anchor accounts (e.g., Goodwill with active trial balance) and
infers codes for nearby ambiguous accounts based on chart structure.
"""
from typing import Dict, List, Set

from mapping_logic_v15 import normalise


# Head-only codes that are candidates for refinement
HEAD_ONLY_CODES = {"ASS", "EXP", "REV", "LIA", "EQU"}


# Context anchors: when an anchor account is detected with an active balance,
# nearby accounts matching the inference keywords get refined.
CONTEXT_ANCHORS = [
    {
        "anchor_name": "goodwill_intangibles",
        "anchor_keywords": ["goodwill"],
        "nearby_keywords": ["legal", "capital", "acquisition", "formation",
                            "incorporation", "stamp duty"],
        "nearby_fallback_heads": {"ASS"},
        "inferred_code": "ASS.NCA.INT",
        "proximity": 50,
        "notes": "Business acquisition costs near active goodwill -> intangibles",
    },
    {
        "anchor_name": "land_buildings",
        "anchor_keywords": ["land", "building", "property"],
        "nearby_keywords": ["improvement", "fitout", "fit out", "renovation",
                            "refurbishment", "leasehold"],
        "nearby_fallback_heads": {"ASS"},
        "inferred_code": "ASS.NCA.FIX.PLA",
        "proximity": 30,
        "notes": "Improvements near active land/buildings -> fixed assets",
    },
]


def _parse_code_number(code_str: str) -> float:
    """Parse an account code string to a numeric value for proximity checks."""
    try:
        return float(code_str.replace(",", "").strip())
    except (ValueError, TypeError):
        return float("nan")


def detect_anchors(
    accounts: List[Dict],
    bal_lookup: Dict[str, float],
) -> List[Dict]:
    """Detect anchor accounts that have active trial balance balances.

    Args:
        accounts: List of account dicts with 'code', 'name', 'predicted' keys.
        bal_lookup: {account_code: closing_balance} from trial balance.

    Returns:
        List of detected anchor dicts with anchor_name, account index, code number.
    """
    detected = []
    for i, acct in enumerate(accounts):
        name_lower = normalise(acct["name"])
        code = acct["code"]
        balance = bal_lookup.get(code, 0.0)

        # Skip if no active balance
        if not balance or balance == 0.0:
            continue

        for anchor in CONTEXT_ANCHORS:
            if any(kw in name_lower for kw in anchor["anchor_keywords"]):
                detected.append({
                    "anchor_name": anchor["anchor_name"],
                    "anchor_index": i,
                    "anchor_code": code,
                    "anchor_code_num": _parse_code_number(code),
                    "anchor_config": anchor,
                })
    return detected


def infer_from_context(
    accounts: List[Dict],
    bal_lookup: Dict[str, float],
    overridden_indices: Set[int],
) -> List[Dict]:
    """Run cross-account context inference on head-only fallback accounts.

    Args:
        accounts: List of account dicts with 'code', 'name', 'predicted', 'source'.
        bal_lookup: {account_code: closing_balance} from trial balance.
        overridden_indices: Set of indices to skip (audited overrides).

    Returns:
        List of inference result dicts with code, inferred_code, reason.
    """
    anchors = detect_anchors(accounts, bal_lookup)
    if not anchors:
        return []

    results = []
    for i, acct in enumerate(accounts):
        if i in overridden_indices:
            continue

        predicted = acct.get("predicted", "")
        # Only refine head-only fallback codes
        if predicted not in HEAD_ONLY_CODES:
            continue

        name_lower = normalise(acct["name"])
        acct_code_num = _parse_code_number(acct["code"])

        for anchor in anchors:
            config = anchor["anchor_config"]

            # Check if this account's fallback head matches the anchor's target
            if predicted not in config["nearby_fallback_heads"]:
                continue

            # Check proximity
            anchor_num = anchor["anchor_code_num"]
            if (acct_code_num != acct_code_num or anchor_num != anchor_num):
                continue  # NaN check
            if abs(acct_code_num - anchor_num) > config["proximity"]:
                continue

            # Check if name matches any inference keywords
            if any(kw in name_lower for kw in config["nearby_keywords"]):
                results.append({
                    "index": i,
                    "code": acct["code"],
                    "name": acct["name"],
                    "inferred_code": config["inferred_code"],
                    "reason": f"CrossAccountContext:{anchor['anchor_name']}",
                    "anchor_code": anchor["anchor_code"],
                })
                break  # One inference per account

    return results
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cross_account.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add context_rules.py tests/test_cross_account.py
git commit -m "feat: add context_rules module with anchor detection and cross-account inference"
```

---

### Task 7: Integrate cross-account context into mapping pipeline

**Files:**
- Modify: `mapping_logic_v15.py:713-730`

**Step 1: Add import**

At the top of `mapping_logic_v15.py`, add:

```python
from context_rules import infer_from_context
```

**Step 2: Add cross-account context pass**

After Pass 2 (accumulated depreciation, line 730) and before Pass 3 (ServiceOnlyRevenueAdjustment, line 732), insert:

```python
# Pass 2.5: Cross-account context inference
# Uses active trial balance balances + chart structure to refine head-only fallbacks
_context_accounts = []
for idx, row in coa.iterrows():
    _context_accounts.append({
        "code": str(row.get("*Code", "")).strip(),
        "name": str(row.get("*Name", "")),
        "type": str(row.get("*Type", "")),
        "predicted": prc[idx] if isinstance(prc[idx], str) else "",
        "source": src[idx] if isinstance(src[idx], str) else "",
    })

_context_results = infer_from_context(_context_accounts, bal_lookup, overridden_indices)
for cr in _context_results:
    i = cr["index"]
    prc[i] = cr["inferred_code"]
    src[i] = cr["reason"]
    need[i] = "Y"  # Still flag for human review
```

**Step 3: Run full test suite**

Run: `uv run pytest tests/ -v --tb=short`
Expected: 860+ passed, 0 failures

**Step 4: Test with test-client data**

Run:
```bash
uv run python mapping_logic_v15.py ".dev-info/test-client/ChartOfAccounts (3).csv" ".dev-info/test-client/Trial_Balance.xlsx" --chart company
```

Then compare against review decisions:
```
uv run python -c "
import csv, json
with open('.dev-info/test-client/review_decisions.json') as f:
    decisions = json.load(f)
with open('.dev-info/test-client/AugmentedChartOfAccounts.csv') as f:
    rows = {r['*Code'].strip(): r for r in csv.DictReader(f)}
for d in decisions:
    row = rows.get(d['account_code'])
    if row:
        predicted = row.get('predictedReportCode','').strip()
        if predicted != d['final_code']:
            print(f'{d[\"account_code\"]:>8} {d[\"account_name\"][:35]:<37} want={d[\"final_code\"]:<20} got={predicted:<20} [{row.get(\"Source\",\"\")}]')
"
```

Expected: Account 720 (Capital Legal Expenses) should now show `ASS.NCA.INT` via `CrossAccountContext:goodwill_intangibles` if Goodwill has an active trial balance balance.

**Step 5: Commit**

```bash
git add mapping_logic_v15.py
git commit -m "feat: integrate cross-account context pass into mapping pipeline"
```

---

### Task 8: Balance sheet section inference (Tier 2)

**Files:**
- Modify: `context_rules.py`
- Test: `tests/test_cross_account.py`

**Step 1: Write failing test**

Add to `tests/test_cross_account.py`:

```python
class TestSectionInference:
    def test_lone_head_among_nca_inferred(self):
        """A head-only ASS among NCA neighbours should infer ASS.NCA."""
        accounts = [
            {"code": "700", "name": "land", "type": "Non-current Asset",
             "predicted": "ASS.NCA.FIX.PLA", "source": "ppe_asset"},
            {"code": "710", "name": "equipment", "type": "Non-current Asset",
             "predicted": "ASS.NCA.FIX.PLA", "source": "ppe_asset"},
            {"code": "715", "name": "deposit bond", "type": "Non-current Asset",
             "predicted": "ASS", "source": "FallbackParent"},
            {"code": "720", "name": "other nca", "type": "Non-current Asset",
             "predicted": "ASS.NCA", "source": "some_rule"},
        ]
        bal = {"700": 100000, "710": 50000, "715": 5000, "720": 8000}
        result = infer_section(accounts, bal, set())
        match = [r for r in result if r["code"] == "715"]
        assert len(match) == 1
        assert match[0]["inferred_code"] == "ASS.NCA"

    def test_no_inference_when_no_consensus(self):
        """Mixed neighbours should not trigger section inference."""
        accounts = [
            {"code": "700", "name": "asset a", "type": "Current Asset",
             "predicted": "ASS.CUR.REC", "source": "rule_a"},
            {"code": "710", "name": "asset b", "type": "Non-current Asset",
             "predicted": "ASS.NCA", "source": "rule_b"},
            {"code": "715", "name": "deposit", "type": "Current Asset",
             "predicted": "ASS", "source": "FallbackParent"},
        ]
        bal = {"700": 100000, "710": 50000, "715": 5000}
        result = infer_section(accounts, bal, set())
        match = [r for r in result if r["code"] == "715"]
        assert len(match) == 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cross_account.py::TestSectionInference -v`
Expected: FAIL — `ImportError: cannot import name 'infer_section'`

**Step 3: Implement infer_section in context_rules.py**

Add to `context_rules.py`:

```python
import math
from collections import Counter


def infer_section(
    accounts: List[Dict],
    bal_lookup: Dict[str, float],
    overridden_indices: Set[int],
    window: int = 5,
    consensus_threshold: float = 0.6,
) -> List[Dict]:
    """Infer balance sheet section for head-only accounts from neighbours.

    Looks at nearby accounts (by index position) and if a supermajority share
    the same code prefix (e.g., ASS.NCA), refines the head-only account to
    match that section.

    Args:
        accounts: List of account dicts.
        bal_lookup: Trial balance lookup.
        overridden_indices: Indices to skip.
        window: Number of neighbours to examine in each direction.
        consensus_threshold: Fraction of neighbours that must agree.

    Returns:
        List of inference result dicts.
    """
    results = []

    for i, acct in enumerate(accounts):
        if i in overridden_indices:
            continue
        predicted = acct.get("predicted", "")
        if predicted not in HEAD_ONLY_CODES:
            continue

        # Gather neighbours' code prefixes (2-level: ASS.NCA, LIA.CUR, etc.)
        neighbour_prefixes = []
        for j in range(max(0, i - window), min(len(accounts), i + window + 1)):
            if j == i:
                continue
            nb_code = accounts[j].get("predicted", "")
            if not nb_code or nb_code in HEAD_ONLY_CODES:
                continue
            parts = nb_code.split(".")
            if len(parts) >= 2 and parts[0] == predicted:
                # Same head — record the 2-level prefix
                prefix = ".".join(parts[:2])
                # Weight by active balance
                nb_acct_code = accounts[j]["code"]
                balance = abs(bal_lookup.get(nb_acct_code, 0.0))
                weight = 1.0 if balance > 0 else 0.3
                neighbour_prefixes.append((prefix, weight))

        if not neighbour_prefixes:
            continue

        # Find consensus prefix
        weighted_counts: Dict[str, float] = {}
        for prefix, weight in neighbour_prefixes:
            weighted_counts[prefix] = weighted_counts.get(prefix, 0.0) + weight

        total_weight = sum(weighted_counts.values())
        if total_weight == 0:
            continue

        best_prefix, best_weight = max(weighted_counts.items(), key=lambda x: x[1])
        if best_weight / total_weight >= consensus_threshold:
            results.append({
                "index": i,
                "code": acct["code"],
                "name": acct["name"],
                "inferred_code": best_prefix,
                "reason": f"SectionInference:{best_prefix}",
            })

    return results
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_cross_account.py -v`
Expected: All tests PASS

**Step 5: Integrate into pipeline**

In `mapping_logic_v15.py`, after the anchor-based context pass (added in Task 7), add:

```python
from context_rules import infer_from_context, infer_section
```

And after the `infer_from_context` results are applied:

```python
# Pass 2.6: Section inference from neighbours
_section_results = infer_section(_context_accounts, bal_lookup, overridden_indices)
for sr in _section_results:
    i = sr["index"]
    # Only apply if anchor inference didn't already refine this account
    if prc[i] in HEAD_ONLY_CODES:
        prc[i] = sr["inferred_code"]
        src[i] = sr["reason"]
        need[i] = "Y"
```

**Step 6: Run full test suite**

Run: `uv run pytest tests/ -v --tb=short`
Expected: 860+ passed, 0 failures

**Step 7: Commit**

```bash
git add context_rules.py tests/test_cross_account.py mapping_logic_v15.py
git commit -m "feat: add section inference from neighbour accounts"
```

---

### Task 9: Final integration test and verification

**Files:**
- Modify: `tests/test_integration.py` (if needed for new xfails)

**Step 1: Run the full pipeline on test-client**

```bash
uv run python mapping_logic_v15.py ".dev-info/test-client/ChartOfAccounts (3).csv" ".dev-info/test-client/Trial_Balance.xlsx" --chart company
```

**Step 2: Compare against all 34 review decisions**

```
uv run python -c "
import csv, json
with open('.dev-info/test-client/review_decisions.json') as f:
    decisions = json.load(f)
with open('.dev-info/test-client/AugmentedChartOfAccounts.csv') as f:
    rows = {r['*Code'].strip(): r for r in csv.DictReader(f)}
m, v = 0, 0
for d in decisions:
    row = rows.get(d['account_code'])
    if not row: continue
    predicted = row.get('predictedReportCode','').strip()
    if predicted == d['final_code']:
        m += 1
    else:
        v += 1
        print(f'{d[\"account_code\"]:>8} {d[\"account_name\"][:35]:<37} want={d[\"final_code\"]:<20} got={predicted:<20} [{row.get(\"Source\",\"\")}]')
print(f'\\nMatches: {m}/{m+v}')
"
```

Expected: 30+/34 matches (up from 29/34).

**Step 3: Check spell corrections applied**

```
uv run python -c "
import csv
with open('.dev-info/test-client/AugmentedChartOfAccounts.csv') as f:
    for r in csv.DictReader(f):
        cn = r.get('CorrectedName','')
        if cn:
            print(f'{r[\"*Code\"]:>8} {r[\"*Name\"][:40]:<42} → {cn}')
"
```

**Step 4: Regenerate and verify HTML report**

```bash
uv run python tools/gen_review_report.py ".dev-info/test-client/AugmentedChartOfAccounts.csv"
```

Open `ReviewReport.html` and verify:
- Spell-corrected accounts show "Originally:" subtitle
- Expected Type column still works
- No JS errors in console

**Step 5: Run full test suite**

Run: `uv run pytest tests/ -v --tb=short`
Expected: All tests pass (update xfails if cross-account context resolves previously-ambiguous accounts in validated data)

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: complete spell-check and cross-account context integration"
```
