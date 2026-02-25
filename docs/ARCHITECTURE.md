# Architecture

## Pipeline Overview

The system assigns Xero reporting codes to a client's Chart of Accounts by
matching each account against template charts, a declarative rule engine, and
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

Internally, the mapper delegates keyword classification to the rule engine:

```
normalise(account_name)
        |
  MatchContext (text, type, template, owner keywords)
        |
  evaluate_rules(ALL_RULES, ctx)   ← rules.py (~130 rules)
        |                             synonyms.py (term normalisation)
  (code, rule_name) or None
```

## Core Modules

### mapping_logic_v15.py (~800 lines)

The main entry point. Orchestrates the full pipeline:

1. **Normalisation** - Strips punctuation, lowercases account names, builds
   searchable text from name + description fields.
2. **Template matching** - Compares client accounts against the selected
   template chart using `difflib.SequenceMatcher` for fuzzy name matching.
3. **Rule engine** - Delegates keyword classification to `evaluate_rules()`,
   which tests all declarative rules against the normalised account context.
4. **Code range inference** - Builds a reporting tree from the template chart,
   mapping account code ranges to reporting code hierarchy.
5. **Integrity validation** - Runs type/code compatibility checks via
   `IntegrityValidator`.
6. **Output generation** - Writes augmented chart, change report, and
   reporting tree JSON.

Key data structures:
- `TYPE_EQ` - Account type equivalence mapping
- `OWNER_KEYWORDS`, `VEHICLE_TOKENS` - Keyword lists shared with rule engine
- `normalise()` - Text normalisation function used across all matching

### rule_engine.py (117 lines)

Declarative rule engine built on a `Rule` dataclass. Each rule specifies:

- `keywords` / `keywords_all` - Terms that must appear in the normalised name
- `keywords_exclude` - Terms that disqualify a match
- `raw_types` / `canon_types` / `type_exclude` - Account type constraints
- `code` - The reporting code to assign
- `priority` - Higher priority wins when multiple rules match

`evaluate_rules()` tests all rules against a `MatchContext` and returns the
highest-priority match. Priority tiers:

| Tier | Range | Examples |
|------|-------|---------|
| Type-specific | 100+ | Entity-specific overrides |
| High-confidence | 90-99 | Strong keyword + type matches |
| Industry | 80-89 | Farm, vehicle, professional |
| General | 70-79 | Common account patterns |
| Broad | 60-69 | Generic loans, catch-all expenses |
| Fallback | 50-59 | Last-resort mappings |

### rules.py (~1,290 lines)

~130 declarative rules organised by category:

- Bank / credit card accounts
- Owner / proprietor (funds introduced, drawings, profit distribution)
- Revenue / grants
- Payroll / employment costs
- Vehicle expenses
- Loans / hire purchase (with direction detection: to vs from)
- Tax / GST
- General expenses (~40 rules)
- Equity / shares
- Prepaid assets, related party, miscellaneous

Each rule was extracted from the original monolithic `keyword_match()` function
in `mapping_logic_v15.py`, with audit fixes applied (aggressive first-name
matching removed, grant/apprentice misclassification fixed, etc.).

### synonyms.py (105 lines)

SQLite-backed synonym normalisation for accounting terms:

- Abbreviations: MV -> motor vehicle, super -> superannuation
- Typos: ammenities -> amenities
- Acronyms: SGC -> superannuation guarantee charge

The database (`data/synonyms.db`) is seeded by `data/seed_synonyms.py` with
~100 initial entries. The `SynonymDB` class is a context manager providing
`lookup()` and `normalise_text()` methods.

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

## Test Suite

The `tests/` directory contains a comprehensive pytest suite:

| Suite | File | Tests | Coverage |
|-------|------|-------|----------|
| Rule engine | `test_rule_engine.py` | Rule creation, matching, priority | Core evaluator logic |
| Rule correctness | `test_rules.py` | ~100 individual rule tests | Every rule category |
| Integrity | `test_rules_integrity.py` | Code validity, type compatibility | All rules vs SystemMappings |
| Integration | `test_integration.py` | Rule engine vs validated datasets | 7 client files, ~1,260 rows |
| Synonyms | `test_synonyms.py` | DB creation, lookup, normalisation | SynonymDB class |

Validated fixture CSVs in `tests/fixtures/validated/` contain human-reviewed
reporting codes for real (anonymised) client charts. Integration tests compare
rule engine output against these fixtures.

Current status: **770 passed, 11 xfailed**. The 10 anonymisation-related
xfails are accounts where distinguishing signals (director names, car brands,
beneficiary identifiers) were replaced with "Person XXXX" during data
sanitisation.

## Tools

| Script | Purpose |
|--------|---------|
| `tools/fix_broken_chart.py` | Repair misaligned chart CSV files against a template |
| `tools/generate_account_type_rules.py` | Regenerate account type rules from financial report JSONs |
| `tools/gen_mismatch_report.py` | Generate interactive HTML report for reviewing integration test mismatches |
| `tools/apply_decisions.py` | Apply user mismatch decisions to validated fixture CSVs |
| `tools/sanitize_dev_info.py` | Anonymise client PII in development data |

### Mismatch review workflow

1. Run integration tests to identify mismatches
2. `gen_mismatch_report.py` produces an interactive HTML report
3. User reviews each mismatch, choosing "Rule engine correct", "Validated correct", or a custom code
4. Decisions are exported as JSON
5. `apply_decisions.py` updates fixture CSVs with the decisions
6. Rule changes are applied manually based on the decision reasons

## Web Interface (Prototype)

The `web_interface/` directory contains a Flask-based browser UI:

- `server.py` - Flask backend exposing REST API endpoints for file upload,
  validation, and issue resolution
- `index.html` / `app.js` / `styles.css` - Frontend with drag-drop upload,
  interactive validation results, and issue resolution UI
- `complete_standalone.html` - Standalone HTML version that runs entirely
  in the browser (no server required)

This interface is a prototype from an earlier development phase. The CLI
(`mapping_logic_v15.py`) is the primary interface. The product spec
(`prompts/python-web-version_XeroMapper.md`) envisions a more complete
FastAPI + HTMX + Tabulator implementation for a future portable application.

## Known Limitations

- **Heuristic coverage**: Keyword rules cover common patterns but miss niche
  account naming conventions. Some mappings rely on fuzzy matching which can
  produce false positives.
- **TYPE_EQ simplification**: Direct Costs and Cost of Sales were previously
  collapsed to "expense" — this was fixed but the distinction between
  `EXP.COS` and `EXP` heads needs careful handling.
- **Template specificity**: The five templates don't cover all possible Xero
  entity configurations. Custom chart structures may need manual overrides.
- **ML integration**: The ML model infrastructure is designed but not yet
  implemented in the pipeline. See `docs/ML_MODEL_GUIDE.md` for the planned
  architecture.
- **Anonymisation ceiling**: 10 integration test cases are permanently
  unfixable because data anonymisation destroyed the distinguishing signals
  (director names, car brands, beneficiary numbering). These are marked as
  `xfail` in the test suite.
