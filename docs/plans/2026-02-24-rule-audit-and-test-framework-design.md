# Rule Audit & Test Framework Design

**Goal:** Refactor the monolithic keyword heuristic rules into a declarative, auditable,
testable rule engine backed by a synonym normalisation database, then build a pytest + HTML
test framework to verify accuracy against validated client datasets.

**Architecture:** Rules move from ~400 lines of if/elif chains in `keyword_match()` to a
declarative `rules.py` with explicit priorities. A SQLite synonym database handles
abbreviation/typo/synonym normalisation before rule evaluation. pytest parametrized tests
verify each rule in isolation and integration tests run against 7 validated client datasets.

**Package manager:** uv (resolves from pyproject.toml)

---

## 1. Rule Audit Scope

### A. Structural Issues (bugs, dead code, duplicates)

| Issue | Location | Description |
|-------|----------|-------------|
| Duplicate elif blocks | Lines 929-939 | `trailer` and `council rates` rules appear twice |
| Dead code | Line 550 | `row['*Type'].lower()=='cost of sales'` inside `row_type=='expense'` guard is unreachable |
| Implicit operator precedence | Line 538 | `or`/`and` precedence correct but should use explicit parens |

### B. Semantic Accuracy (rules that produce wrong codes)

| Issue | Location | Description |
|-------|----------|-------------|
| Aggressive first-name matching | Lines 303-307 | COMMON_FIRST_NAMES catches "St John's", "Peterson Supplies" |
| Overly broad 'grant' | Line 327 | Matches person names, non-government grants |
| 'apprentice' → grant | Line 327 | "Apprentice Wages" is EXP.EMP.WAG, not REV.GRA.GOV |
| Company loan direction | Line 345 | Always maps to ASS.NCA.REL but loan could be FROM company (liability) |
| Broad 'staff' catch-all | Line 504 | Catches everything with "staff" indiscriminately |

### C. Completeness Gaps

| Missing Rule | Expected Code | Notes |
|-------------|---------------|-------|
| Rent (expense) | EXP.REN / EXP.OCC | Context-dependent: office rent vs property |
| Interest Income | REV.INV.INT | Other income type |
| Bank fallback | ASS.CUR.CAS.BAN | head_from_type maps 'bank' to generic 'ASS' |

---

## 2. Rule Engine Architecture

### Current: Procedural if/elif chains

```
keyword_match():          ~350 lines of if/elif
early overrides (1b):     ~60 lines of if/elif
    ↓
order-dependent, implicit priority, untestable
```

### Proposed: Declarative rule table

```
rules.py:
    RULES = [Rule(...), Rule(...), ...]     # each rule is a data record
    ↓
rule_engine.py:
    evaluate(row, context) → (code, rule_name)
    - evaluates all matching rules
    - picks highest priority winner
    - explicit priority, independently testable
```

### Rule data structure

```python
@dataclass
class Rule:
    name: str                    # unique identifier
    code: str                    # reporting code output
    priority: int                # explicit priority (100=highest)
    keywords: list[str]          # ANY of these in normalised text
    keywords_all: list[str]      # ALL must be present
    keywords_exclude: list[str]  # NONE may be present
    raw_types: set[str]          # raw *Type must be one of these
    canon_types: set[str]        # canonical type must be one of these
    type_exclude: set[str]       # canonical type must NOT be these
    template: str | None         # only for this template
    owner_context: bool          # requires OWNER_KEYWORDS match
    name_only: bool              # match name only, not name+description
    notes: str                   # audit trail
```

### Priority tiers

| Tier | Range | Examples |
|------|-------|---------|
| Type-specific overrides | 100+ | bank→credit card, bank→bank account |
| High-confidence keywords | 90-99 | drawings, wages, superannuation |
| Industry-specific | 80-89 | building & construction rules |
| General expense categories | 70-79 | insurance, utilities, advertising |
| Broad patterns | 60-69 | generic loan, generic staff |
| Catch-all | 50-59 | "staff"→EMP, "cost of sales"→COS |

### Rule evaluation

```python
def evaluate(row, context):
    candidates = [r for r in RULES if r.matches(row, context)]
    if not candidates:
        return None, None
    winner = max(candidates, key=lambda r: r.priority)
    return winner.code, winner.name
```

### What stays unchanged

- Overall pipeline structure in mapping_logic_v15.py
- Template matching (steps 2-6 in the priority cascade)
- head_from_type, normalise, canonical_type utilities
- Accumulated depreciation pairing logic
- Post-processing passes (service-only reclass, etc.)

---

## 3. Normalisation Database (SQLite)

### Problem

The current `normalise()` handles a handful of abbreviations ad-hoc:
- M/V → mv (motor vehicle)
- R&M → repairs maintenance

But misses hundreds of common accounting abbreviations, synonyms, and typos.

### Schema

```sql
CREATE TABLE synonyms (
    id INTEGER PRIMARY KEY,
    term TEXT NOT NULL,           -- raw form encountered
    canonical TEXT NOT NULL,      -- normalised form
    category TEXT NOT NULL,       -- abbreviation | synonym | typo | acronym
    domain TEXT DEFAULT NULL,     -- vehicle | payroll | asset | tax | etc.
    notes TEXT DEFAULT NULL
);
CREATE UNIQUE INDEX idx_synonyms_term ON synonyms(term);
```

### Integration

1. `normalise()` tokenises the text
2. Each token is looked up in the synonyms table
3. Matched tokens are replaced with canonical forms
4. Rules match against canonical terms only

### Seed data sources

- Existing ad-hoc normalisations in `normalise()` (M/V, R&M, &→and)
- Existing keyword lists (VEHICLE_TOKENS, BANK_NAMES, etc.)
- Common Australian accounting abbreviations
- Known typos from the validated datasets

---

## 4. Test Framework

### Stack

- **pytest** with parametrized tests
- **pytest-html** for visual HTML mismatch reports
- **uv** for environment management

### Test structure

```
tests/
    conftest.py              # Shared fixtures
    test_rule_engine.py      # Unit tests for rule matching engine
    test_rules_integrity.py  # Every rule's code valid for its types
    test_keyword_rules.py    # Per-rule positive/negative tests
    test_normalise.py        # Synonym expansion tests
    test_pipeline.py         # Integration against validated datasets
    fixtures/
        validated/           # Extracted validated_final CSVs
        synthetic/           # Hand-crafted edge cases
```

### Test categories

1. **Rule integrity (automated):** Every rule's output code exists in SystemMappings
   and is compatible with its declared type constraints per
   Account_Types_per_Financial-Reports.json.

2. **Per-rule unit tests:** Each rule gets at least one positive example (should match)
   and one negative example (should not match).

3. **Integration against validated data:** Run the full mapper on 7 validated client
   datasets (~1,264 rows), compare to validated codes. HTML report shows mismatches.
   User re-verifies flagged cases; confirmed corrections become hard assertions.

4. **Synonym coverage:** Each synonym entry has a test confirming normalisation works.

### Validated datasets

7 client files from `.dev-info/old-codebases/Report Code Mapping - Data Analysis/output/`:

| File | Rows | Human corrections |
|------|------|-------------------|
| ChartOfAccounts_38_validated_final.csv | 128 | 128 |
| client_008_validated_final.csv | 92 | 41 |
| client_130_validated_final.csv | 150 | 35 |
| client_182_validated_final.csv | 85 | 85 |
| client_234_validated_final.csv | 277 | 277 |
| client_255_validated_final.csv | 117 | 21 |
| client_267_validated_final.csv | 409 | 146 |

---

## 5. Implementation Order

### Phase 1: Environment & Rule Extraction (audit + refactor)
1. Set up uv environment with pytest, pytest-html, pandas, openpyxl
2. Create `rule_engine.py` with Rule dataclass and evaluation engine
3. Extract every rule from `keyword_match()` and early overrides into `rules.py`
4. Audit each rule during extraction: fix bugs, add type guards, remove dead code
5. Create SQLite normalisation database with seed synonyms
6. Update `normalise()` to use synonym lookups
7. Rewire `mapping_logic_v15.py` to use rule engine

### Phase 2: Test Framework
8. Write rule integrity tests (automated validation of all rules)
9. Write per-rule unit tests (positive/negative per rule)
10. Extract validated datasets into `tests/fixtures/validated/`
11. Write integration tests against validated data
12. Generate HTML mismatch report for user re-verification

### Phase 3: Iteration
13. User reviews HTML report, confirms or corrects expected values
14. Confirmed corrections become hard assertions
15. Fix rules to reduce failures
16. Re-run, iterate until stable

---

## Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Approach | Rule audit first, then test | User preference |
| Rule storage | Python (rules.py) | Complex conditions awkward in SQL |
| Normalisation storage | SQLite | Tabular data, queryable, maintainable |
| Package manager | uv | Fast, works with pyproject.toml |
| Test framework | pytest + pytest-html | Standard, visual HTML reports |
| Validated data | Use as starting point, user re-verifies | Some old corrections may be outdated |
| Architecture | Declarative rule table with priority engine | Auditable, testable, extensible |
