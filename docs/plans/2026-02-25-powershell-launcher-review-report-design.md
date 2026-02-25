# PowerShell Launcher & HTML Review Report

**Date:** 2026-02-25
**Branch:** `feature/type-review-csv-export`

## Problem

Users currently run the mapping pipeline via CLI and get CSV output with no
interactive review step. They need a drag-and-drop workflow that runs the
pipeline and opens an HTML review interface where they can verify assigned
codes, override them, correct account types, and export a Xero-ready chart.

## New Files

| File | Purpose |
|------|---------|
| `Run-Mapping.ps1` | PowerShell drag-and-drop entry point |
| `tools/gen_review_report.py` | Reads pipeline output, generates standalone HTML review page |

## Flow

```
User drags ChartOfAccounts.csv + TrialBalance onto Run-Mapping.ps1
  |
  +-- 1. Identify files (chart starts with "ChartOfAccounts", TB is the other)
  +-- 2. Prompt template selection (numbered menu: Company, Trust, etc.)
  +-- 3. Run: uv run python mapping_logic_v15.py <chart> <tb> --chart <template>
  +-- 4. Run: uv run python tools/gen_review_report.py <AugmentedChart.csv> <original_chart>
  +-- 5. Open generated HTML in default browser (file://)
  +-- 6. Pause: "Press any key to exit"
```

## File Identification

- **Chart:** filename starts with `ChartOfAccounts` (case-insensitive), `.csv`
- **Trial Balance:** the other file, `.csv` or `.xlsx`
- If ambiguous: prompt user to confirm which is which

## Run-Mapping.ps1

- Accepts 2 files via `$args` (drag-and-drop passes paths as arguments)
- Validates both files exist and have supported extensions
- Shows numbered template menu, reads user choice
- Changes to project root directory to run `uv run python`
- Captures pipeline exit code; aborts on failure
- Locates AugmentedChartOfAccounts.csv in same directory as input chart
- Runs gen_review_report.py to produce HTML alongside the augmented CSV
- Opens HTML with `Start-Process`
- Pauses before exit so the terminal stays open

## HTML Review Report (gen_review_report.py)

### Input

- `AugmentedChartOfAccounts.csv` (pipeline output: has `predictedReportCode`,
  `predictedMappingName`, `NeedsReview`, `Source` columns merged onto the
  original chart columns)
- Original client chart path (for preserving original columns in export)

### Phase 1: Code Review

Shows every account row in a table:

| Column | Source |
|--------|--------|
| Account code | `*Code` from augmented CSV |
| Account name | `*Name` |
| Account type | `*Type` |
| Original report code | `Report Code` from input chart |
| Assigned code | `predictedReportCode` |
| Assigned name | `predictedMappingName` |
| Source | `Source` column (rule engine, template, etc.) |
| NeedsReview | Highlighted when `Y` |

Decision panel per row:
- **Accept** (default) — keep the assigned code
- **Override** — pick a different code from datalist + provide reason

Summary cards: total accounts, needs-review count, overridden count.
Toolbar: search, filter by NeedsReview / Source / status.

Decisions persist in localStorage.

### Phase 2: Type Correction

After Phase 1 review, check each account's code head against its `*Type`:
- If code head (ASS/EQU/EXP/LIA/REV) disagrees with type, show in type
  review table
- Predict the correct type from the code
- User can accept prediction or pick from allowed types
- Same interface as the mismatch report's Phase 2

### Phase 3: Export

Two export buttons:

1. **"Download Xero Chart CSV"** — standard Xero import format:
   `*Code, Report Code, *Name, Reporting Name, *Type, *Tax Code, Description,
   Dashboard, Expense Claims, Enable Payments`
   - `Report Code` updated with user's final code decisions
   - `*Type` updated with user's type corrections
   - All other columns preserved from original input chart

2. **"Save Review JSON"** — all override decisions with reasons, for
   developer review:
   ```json
   [
     {
       "account_code": "400",
       "account_name": "Sales",
       "original_code": "REV",
       "assigned_code": "REV.TRA.SER",
       "final_code": "REV.TRA.GOO",
       "reason": "This client sells goods not services",
       "type_change": null,
       "timestamp": "2026-02-25T10:30:00Z"
     }
   ]
   ```

### Key Differences from Mismatch Report

| Aspect | Mismatch report | Review report |
|--------|----------------|---------------|
| Data source | Test fixture validated CSVs | AugmentedChartOfAccounts.csv |
| Shows | Only mismatched rows | All accounts |
| Comparison | Rule engine vs. human-validated | Assigned vs. original chart code |
| Decisions | Rule Engine / Validated / Other | Accept / Override |
| CSV output | Fixture-oriented | Standard Xero import format |
| Type review | Triggered after all mismatches reviewed | Triggered after code review |

## Output Files

All written alongside the input chart:

| File | When |
|------|------|
| `AugmentedChartOfAccounts.csv` | Always (pipeline output) |
| `ReviewReport.html` | Always (gen_review_report.py) |
| `ChartOfAccounts_Updated.csv` | User clicks export in HTML |
| `review_decisions.json` | User clicks save in HTML |
