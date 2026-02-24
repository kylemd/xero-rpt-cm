# Architecture

## Pipeline Overview

The system assigns Xero reporting codes to a client's Chart of Accounts by
matching each account against template charts, heuristic keyword rules, and
integrity constraints. The pipeline runs as a single CLI invocation:

```
Client Chart (CSV/XLSX)  +  Trial Balance (CSV/XLSX)
                     |
              mapping_logic_v15.py --chart <Template>
                     |
        +------------+------------+
        |            |            |
  Augmented     Change/Error   Reporting
    Chart         Report         Tree
```

## Core Modules

### mapping_logic_v15.py (1,206 lines)

The main entry point. Orchestrates the full pipeline:

1. **Normalisation** - Strips punctuation, lowercases account names, builds
   searchable text from name + description fields.
2. **Template matching** - Compares client accounts against the selected
   template chart using `difflib.SequenceMatcher` for fuzzy name matching.
3. **Keyword heuristics** - Rule-based classification using curated keyword
   lists for specific account types (bank accounts, vehicles, owner drawings,
   cost of sales, etc.).
4. **Code range inference** - Builds a reporting tree from the template chart,
   mapping account code ranges to reporting code hierarchy.
5. **Integrity validation** - Runs type/code compatibility checks via
   `IntegrityValidator`.
6. **Output generation** - Writes augmented chart, change report, and
   reporting tree JSON.

Key data structures:
- `TYPE_EQ` - Account type equivalence mapping
- `OWNER_KEYWORDS`, `VEHICLE_TOKENS` - Keyword lists for heuristic rules
- `normalise()` - Text normalisation function used across all matching

### file_handler.py (282 lines)

Handles all file I/O with format detection:

- CSV and XLSX loading with encoding detection
- Xero trial balance format detection (identifies the "Trial Balance" / "As at"
  header pattern and skips the first 4 rows)
- Dr/(Cr) amount parsing for year columns
- Period column detection and parsing
- Helper functions for locating account code and closing balance columns

### integrity_validator.py (382 lines)

Validates that account types and reporting codes are compatible:

- Loads rules from `Account_Types_Head.csv` and
  `Account_Types_per_Financial-Reports.json`
- Checks each account's type against its assigned reporting code head
- Detects accounts that appear in multiple financial reports
- Balance anomaly detection: flags accounts where >= 75% of the balance
  is contrary to the expected direction (debit vs credit)
- Excludes contra accounts (accumulated depreciation, amortisation,
  unexpired interest) from anomaly detection

### audit_heuristics.py (351 lines)

Audits the keyword-based heuristic rules for correctness:

- Parses keyword rules from mapping_logic_v15.py
- Detects incompatible mappings (e.g., a keyword that maps to a code
  incompatible with the account type)
- Generates structured audit findings as JSON

### postprocess_outputs.py (63 lines)

Summarises mapping outputs for quick review. Reads the augmented chart and
produces aggregate counts by reporting code, type, and match quality.

## Template Charts

The `ChartOfAccounts/` directory contains five template charts, each representing
a different Xero entity structure:

| Template | Entity Type |
|----------|-------------|
| `Company.csv` | Pty Ltd companies |
| `Trust.csv` | Trusts |
| `SoleTrader.csv` | Sole traders |
| `Partnership.csv` | Partnerships |
| `XeroHandi.csv` | Xero HandiSoft integration |

Each template defines the canonical set of reporting codes, account types,
and names for that entity structure. The mapper uses these as the reference
for matching and code assignment.

## System Files

- `SystemMappings.csv` - The authoritative reporting code hierarchy. Maps
  every valid reporting code to its parent, head, and display name.
- `Account_Types_Head.csv` - Maps account types (Asset, Liability, etc.)
  to their expected reporting code heads.
- `Account_Types_per_Financial-Reports.json` - Rules for which account types
  belong to which sections of each financial report.

## Financial Report Definitions

The `financial-reports/` directory contains JSON definitions for three standard
Australian financial reports:

1. `Report01_Trading-Statement.json`
2. `Report02_Detailed-Profit-and-Loss.json`
3. `Report03_Balance-Sheet.json`

These define which reporting code heads map to which report sections, used by
the integrity validator to check multi-report appearance and by the rule
generator to produce account type constraints.

## Web Interface (Prototype)

The `web_interface/` directory contains a Flask-based browser UI:

- `server.py` - Flask backend exposing REST API endpoints for file upload,
  validation, and issue resolution
- `index.html` / `app.js` / `styles.css` - Frontend with drag-drop upload,
  interactive validation results, and issue resolution UI
- `complete_standalone.html` - Standalone HTML version that runs entirely
  in the browser (no server required)

This interface is a prototype from an earlier development phase. The product
spec (`prompts/python-web-version_XeroMapper.md`) envisions a more complete
FastAPI + HTMX + Tabulator implementation for the portable application.

## Known Limitations

- **Heuristic coverage**: Keyword rules cover common patterns but miss niche
  account naming conventions. Some mappings rely on fuzzy matching which can
  produce false positives.
- **TYPE_EQ simplification**: Direct Costs and Cost of Sales were previously
  collapsed to "expense" — this was fixed but the distinction between
  `EXP.COS` and `EXP` heads needs careful handling.
- **Template specificity**: The five templates don't cover all possible Xero
  entity configurations. Custom chart structures may need manual overrides.
- **ML integration**: The ML model infrastructure (scikit-learn, xgboost,
  transformers) is declared in dependencies but not fully implemented in the
  current pipeline. See `docs/ML_MODEL_GUIDE.md` for the planned architecture.
- **Test coverage**: No automated test suite exists yet. The `test_backend/`
  directory is empty.
