# Xero Report Code Mapping

Python toolkit for assigning Xero reporting codes to client Charts of Accounts.
Takes a client chart (CSV/XLSX) and an optional trial balance, matches each account
against template charts and heuristic rules, and produces an augmented chart with
reporting codes, a change report, and a reporting tree.

## Repository Layout

```
mapping_logic_v15.py          Main CLI entry point (heuristic mapper)
file_handler.py               CSV/XLSX loading, Xero format detection
integrity_validator.py        Type/code compatibility and balance anomaly checks
audit_heuristics.py           Heuristic rule auditing
postprocess_outputs.py        Output summarisation

ChartOfAccounts/              Template charts (Company, Trust, SoleTrader, etc.)
SystemFiles/                  Canonical lookup tables (SystemMappings.csv, etc.)
financial-reports/            Report structure definitions (JSON)
examples/                     Sample input files for testing

web_interface/                Flask-based browser UI (prototype)
tools/                        Helper scripts (chart repair, rule generation, etc.)
docs/                         Architecture guide, staff guide, ML model guide
prompts/                      Reference prompts and design specifications
```

## Setup

This project uses a **conda** environment:

```bash
conda activate ReportCodeMapping
```

Core dependencies: `pandas`, `openpyxl`, `scikit-learn`, `xgboost`, `flask`.
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

## Helper Scripts

| Script | Purpose |
|--------|---------|
| `tools/fix_broken_chart.py` | Repair misaligned chart CSV files |
| `tools/generate_account_type_rules.py` | Regenerate account type rules from financial report JSONs |
| `postprocess_outputs.py` | Summarise mapping outputs |

Regenerate rules after editing template charts:

```bash
python tools/generate_account_type_rules.py
```

## Data Maintenance

- `SystemFiles/SystemMappings.csv` is the authoritative reporting-code hierarchy.
  Update it carefully and keep backups.
- `ChartOfAccounts/*.csv` are the template charts used for matching. Each represents
  a different entity structure (Company, Trust, SoleTrader, Partnership, XeroHandi).
- Generated artefacts should live alongside client inputs, not in the repo root.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - Pipeline design, module overview, data flow
- [`docs/STAFF_GUIDE.md`](docs/STAFF_GUIDE.md) - End-user guide for the web interface
- [`docs/ML_MODEL_GUIDE.md`](docs/ML_MODEL_GUIDE.md) - ML system architecture (future)
- [`prompts/`](prompts/) - Design specs and reference prompts
