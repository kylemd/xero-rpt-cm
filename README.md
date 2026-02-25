# Xero Report Code Mapping

Python toolkit for assigning Xero reporting codes to client Charts of Accounts.
Takes a client chart (CSV/XLSX) and a trial balance, matches each account
against template charts, a declarative rule engine, and heuristic keyword rules,
then produces an augmented chart with reporting codes, a change report, and a
reporting tree.

## Repository Layout

```
mapping_logic_v15.py          Main CLI entry point (pipeline orchestrator)
rule_engine.py                Declarative rule engine (Rule dataclass + evaluator)
rules.py                      ~130 keyword rules organised by category
synonyms.py                   SQLite-backed synonym normalisation
file_handler.py               CSV/XLSX loading, Xero format detection
integrity_validator.py        Type/code compatibility and balance anomaly checks
audit_heuristics.py           Heuristic rule auditing
postprocess_outputs.py        Output summarisation

ChartOfAccounts/              Template charts (Company, Trust, SoleTrader, etc.)
SystemFiles/                  Canonical lookup tables (SystemMappings.csv, etc.)
financial-reports/            Report structure definitions (JSON)
examples/                     Sample input files for testing
data/                         Synonym seed data and SQLite database

tests/                        pytest suite (unit, integrity, integration)
tools/                        Helper scripts (chart repair, mismatch review, etc.)
docs/                         Architecture guide, staff guide, ML model guide
prompts/                      Reference prompts and design specifications
web_interface/                Flask-based browser UI (prototype)
```

## Setup

This project uses **uv** for environment management:

```bash
uv venv .venv
uv pip install -e ".[dev]"
```

Core dependencies: `pandas`, `openpyxl`. Dev dependencies: `pytest`, `pytest-html`.
See `pyproject.toml` for the full list.

## Usage

```bash
python mapping_logic_v15.py <ChartOfAccounts.csv> <TrialBalance.csv> --chart <Template>
```

Where `--chart` selects a template from `ChartOfAccounts/` by filename (without
extension), e.g. `--chart Company`, `--chart Trust`.

### Outputs (written alongside the client chart)

- `AugmentedChartOfAccounts.csv` - enriched chart with assigned reporting codes
- `ChangeOrErrorReport.csv` - validation failures and warnings
- `ReportingTree.json` - inferred reporting code hierarchy from the template

### Validate only (no mapping)

```bash
python mapping_logic_v15.py <ChartOfAccounts.csv> <TrialBalance.csv> --chart Company --validate-only
```

## Rule Engine

The rule engine (`rule_engine.py` + `rules.py`) replaces the monolithic keyword
matching previously embedded in `mapping_logic_v15.py`. Rules are declarative
dataclass instances with explicit conditions and priority-based evaluation.

### How it works

1. Each `Rule` specifies keywords, account types, and a target reporting code
2. `evaluate_rules()` tests all rules against a normalised account context
3. The highest-priority matching rule wins
4. Priority tiers: 100+ (type-specific), 90-99 (high-confidence), 70-79 (general), 60-69 (broad)

### Dictionaries

`rules.py` includes Australian market keyword dictionaries used by the rule engine
for entity recognition:

| Dictionary | Entries | Purpose |
|-----------|---------|---------|
| `AUSTRALIAN_BANKS` | 25 institutions + abbreviations | Detect bank names in account descriptions (fees, accounts) |
| `VEHICLE_MAKES` | 40 makes + abbreviations + popular models | Detect vehicle-related liabilities and expenses |
| `AUSTRALIAN_LENDERS` | 50 lenders + abbreviations | Detect loan liabilities from recognised lender names |

`BANK_NAMES` is a backwards-compatible alias for `AUSTRALIAN_BANKS`.

### Synonym normalisation

`synonyms.py` provides a SQLite-backed lookup for abbreviations, typos, and
acronyms (e.g. "MV" -> "motor vehicle", "super" -> "superannuation"). Seeded
by `data/seed_synonyms.py`.

## Tests

```bash
uv run pytest tests/ -v
```

| Suite | File | What it covers |
|-------|------|----------------|
| Unit | `test_rule_engine.py` | Rule creation, matching, priority logic |
| Unit | `test_rules.py` | Individual rule correctness (~100 tests) |
| Integrity | `test_rules_integrity.py` | Code validity and type compatibility |
| Integration | `test_integration.py` | Rule engine vs 7 validated client datasets (~1,260 rows) |
| Synonyms | `test_synonyms.py` | Synonym DB creation, lookup, normalisation |

Current status: **770 passed, 11 xfailed** (xfails are anonymised test data
where distinguishing signals were removed).

## Helper Scripts

| Script | Purpose |
|--------|---------|
| `tools/fix_broken_chart.py` | Repair misaligned chart CSV files |
| `tools/generate_account_type_rules.py` | Regenerate account type rules from financial report JSONs |
| `tools/gen_mismatch_report.py` | Generate interactive HTML report for reviewing integration test mismatches |
| `tools/apply_decisions.py` | Apply user mismatch decisions to validated fixture CSVs |
| `tools/sanitize_dev_info.py` | Anonymise client PII in development data |
| `postprocess_outputs.py` | Summarise mapping outputs |

## Data Maintenance

- `SystemFiles/SystemMappings.csv` is the authoritative reporting-code hierarchy.
  Update it carefully and keep backups.
- `ChartOfAccounts/*.csv` are the template charts used for matching. Each represents
  a different entity structure (Company, Trust, SoleTrader, Partnership, XeroHandi).
- `tests/fixtures/validated/` contains human-validated fixture CSVs for integration
  testing. Update via `tools/apply_decisions.py` after reviewing mismatches.
- Generated artefacts should live alongside client inputs, not in the repo root.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - Pipeline design, module overview, data flow
- [`docs/STAFF_GUIDE.md`](docs/STAFF_GUIDE.md) - End-user guide (web interface is prototype; CLI is primary)
- [`docs/ML_MODEL_GUIDE.md`](docs/ML_MODEL_GUIDE.md) - ML system architecture (planned, not yet implemented)
- [`prompts/`](prompts/) - Design specs and reference prompts
