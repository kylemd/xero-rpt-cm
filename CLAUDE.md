# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run full test suite
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_rules.py -v

# Run a single test by name
uv run pytest tests/test_rules.py -v -k "test_bank_fees"

# Run the mapping pipeline
uv run python mapping_logic_v15.py <client_chart.csv> <trial_balance.xlsx> --chart Company

# Generate HTML review report (--type defaults to Company)
uv run python tools/gen_review_report.py <AugmentedChartOfAccounts.csv> [--type Trust]

# Generate mismatch review report (after integration tests surface mismatches)
uv run python tools/gen_mismatch_report.py

# Apply mismatch decisions back to fixture CSVs
uv run python tools/apply_decisions.py <decisions.json>
```

Available `--chart` / `--type` values: `Company`, `Trust`, `Partnership`, `SoleTrader`, `XeroHandi`.

pytest is configured to write an HTML test report to `tests/report.html` after every run.

## Architecture

### Pipeline passes (`mapping_logic_v15.py`)

Each account in the client chart is processed through a **priority-ordered waterfall** — the first strategy that produces a code wins:

1. **Template name match** — exact/fuzzy name match against `ChartOfAccounts/<template>.csv` via `difflib.SequenceMatcher` (threshold 0.75)
2. **Default chart dict** — direct `(normalised_name, canon_type)` lookup against the template
3. **Rule engine** (`evaluate_rules(ALL_RULES, ctx)`) — declarative keyword rules, highest priority wins
4. **Accumulated depreciation pairing** — matches "Less Accumulated..." names to their base asset's reporting code + `.ACC`
5. **DirectNameMatch** — normalised name appears verbatim in `SystemMappings.csv` with a compatible type head
6. **ExistingCodeValidByName** — client's existing code matches a SystemMappings entry by name
7. **AlreadyCorrect / ExistingCodeValid** — client's existing code is a known leaf; accepted as-is unless overridden by stronger signals
8. **FuzzyMatch** — fuzzy match within the correct type head (threshold 0.75 + shared word required)
9. **FallbackParent** — head-only code derived from account type (`REV`, `EXP`, etc.)

After the waterfall, three post-processing passes run over the full chart:

- **Cross-account context** (`context_rules.py`) — anchor accounts (e.g., active Goodwill) promote nearby ambiguous accounts to more specific codes
- **Section inference** — accounts with head-only fallback codes adopt the most common specific code in their numeric neighbourhood
- **ServiceOnlyRevenueAdjustment** — if no COGS accounts have balances, reclassifies `EXP.COS` → `EXP` for service-only businesses
- **TypeRangeCorrection** — reconciles head mismatches between the assigned code and the account type

### Rule engine (`rule_engine.py` + `rules.py`)

`Rule` dataclass fields: `keywords` (any match), `keywords_all` (all must match), `keywords_exclude`, `raw_types`/`canon_types`/`type_exclude`, `code`, `priority`.

`evaluate_rules()` builds a `MatchContext` from the normalised account text and type, tests all ~130 rules, and returns the highest-priority match. Priority tiers: 100+ entity-specific, 90–99 high-confidence, 80–89 industry, 70–79 general, 60–69 broad, 50–59 fallback.

Adding a rule: append a `Rule(...)` instance to `ALL_RULES` in `rules.py` and add a corresponding test in `tests/test_rules.py`.

### Reporting code structure

Codes follow a dot-separated hierarchy: `HEAD.SUB.LEAF` (e.g., `EXP.VEH.FUE`).

- Head determines the account group: `ASS`=Asset, `LIA`=Liability, `EQU`=Equity, `REV`=Revenue, `EXP`=Expense
- Leaf codes (assignable to individual accounts) are defined in `SystemFiles/SystemMappings.csv`
- Head-only codes (`REV`, `EXP`, etc.) are fallback/parent codes, not final assignments

The **type → head** relationship matters throughout:

| Xero type | Expected head |
|---|---|
| Revenue, Sales | `REV.TRA` |
| Other Income | `REV` (accepts `REV.OTH`, `REV.INV`, `REV.GRA`, etc.) |
| Expense, Overhead | `EXP` |
| Direct Costs | `EXP.COS` |
| Depreciation | `EXP.DEP` |
| Current Asset | `ASS.CUR` |
| Fixed Asset | `ASS.NCA.FIX` |

### Review report (`tools/gen_review_report.py`)

Produces a self-contained HTML file from `AugmentedChartOfAccounts.csv`. All JS is embedded inline.

Key JS data structures in the generated HTML:
- `ACCOUNTS` — full account array from the augmented CSV
- `CODE_TYPE_MAP` — `{REPORTING_CODE: XeroType}` built from the selected `ChartOfAccounts/*.csv` at generation time; used by `predictTypeFromCode()` as the authoritative source before falling back to prefix heuristics
- `decisions` / `typeDecisions` — persisted to `localStorage` (keys `review_decisions_v1` / `review_type_decisions_v2`); only written on explicit user action, never auto-saved

The "Expected Type" column runs `predictTypeFromCode(finalCode, currentType)`, which checks `CODE_TYPE_MAP` first. It only shows a mismatch dropdown when the assigned code is incompatible with the current Xero type.

### Test fixtures

Integration tests (`test_integration.py`) compare rule engine output against `tests/fixtures/validated/*_validated_final.csv`. To update fixtures after reviewing mismatches:

1. Run `uv run python tools/gen_mismatch_report.py` → opens `tests/mismatch_report.html`
2. Review each mismatch and export `decisions.json`
3. Run `uv run python tools/apply_decisions.py decisions.json`

Accounts marked `xfail` in integration tests are permanently anonymised cases where identifying signals (director names, car brands) were removed during sanitisation — do not attempt to fix them.
