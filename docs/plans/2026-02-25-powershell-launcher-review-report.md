# PowerShell Launcher & HTML Review Report — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a drag-and-drop PowerShell launcher that runs the mapping pipeline and opens a standalone HTML review interface for verifying, overriding, and exporting Xero-ready charts.

**Architecture:** PowerShell script (`Run-Mapping.ps1`) identifies dropped files, prompts for template, runs `mapping_logic_v15.py`, then runs `tools/gen_review_report.py` which reads the AugmentedChartOfAccounts.csv and generates a self-contained HTML review page. The HTML uses localStorage for persistence and blob downloads for export (no server needed).

**Tech Stack:** PowerShell 5.1+, Python 3.12 (via `uv run`), pandas, HTML/CSS/JS (inline in generated HTML)

**Design doc:** `docs/plans/2026-02-25-powershell-launcher-review-report-design.md`

---

## Task 1: Create `Run-Mapping.ps1`

**Files:**
- Create: `Run-Mapping.ps1`

**Step 1: Write the PowerShell script**

The script must handle Windows drag-and-drop (paths passed as `$args`). Key behaviours:
- Detect which file is the chart (filename starts with `ChartOfAccounts`, case-insensitive)
- The other file is the trial balance (`.csv` or `.xlsx`)
- Show numbered template menu, read choice
- Run the pipeline from the project root (the script's own directory)
- Run the review report generator
- Open HTML in default browser
- Pause so terminal stays visible

```powershell
# Run-Mapping.ps1 — Drag-and-drop launcher for Xero Report Code Mapping
# Usage: Drag a ChartOfAccounts CSV and a Trial Balance file onto this script.

param()
$ErrorActionPreference = "Stop"

# ── Resolve project root (where this script lives) ──
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition

# ── Validate arguments ──
if ($args.Count -ne 2) {
    Write-Host ""
    Write-Host "  Xero Report Code Mapping" -ForegroundColor Cyan
    Write-Host "  ========================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Usage: Drag TWO files onto this script:" -ForegroundColor Yellow
    Write-Host "    1. ChartOfAccounts CSV  (filename starts with 'ChartOfAccounts')"
    Write-Host "    2. Trial Balance file   (CSV or XLSX)"
    Write-Host ""
    Read-Host "  Press Enter to exit"
    exit 1
}

# ── Resolve full paths ──
$File1 = Resolve-Path $args[0] -ErrorAction Stop | Select-Object -ExpandProperty Path
$File2 = Resolve-Path $args[1] -ErrorAction Stop | Select-Object -ExpandProperty Path

# ── Identify chart vs trial balance ──
$ChartFile = $null
$TBFile = $null

foreach ($f in @($File1, $File2)) {
    $name = [System.IO.Path]::GetFileName($f)
    if ($name -match '^ChartOfAccounts') {
        $ChartFile = $f
    } else {
        $TBFile = $f
    }
}

if (-not $ChartFile -or -not $TBFile) {
    Write-Host ""
    Write-Host "  ERROR: Could not identify files." -ForegroundColor Red
    Write-Host "  One file must start with 'ChartOfAccounts'." -ForegroundColor Red
    Write-Host "  Got: $([System.IO.Path]::GetFileName($File1))" -ForegroundColor Yellow
    Write-Host "       $([System.IO.Path]::GetFileName($File2))" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "  Press Enter to exit"
    exit 1
}

# ── Validate extensions ──
$chartExt = [System.IO.Path]::GetExtension($ChartFile).ToLower()
$tbExt = [System.IO.Path]::GetExtension($TBFile).ToLower()

if ($chartExt -ne '.csv') {
    Write-Host "  ERROR: Chart file must be .csv (got $chartExt)" -ForegroundColor Red
    Read-Host "  Press Enter to exit"
    exit 1
}
if ($tbExt -notin @('.csv', '.xlsx')) {
    Write-Host "  ERROR: Trial balance must be .csv or .xlsx (got $tbExt)" -ForegroundColor Red
    Read-Host "  Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "  Xero Report Code Mapping" -ForegroundColor Cyan
Write-Host "  ========================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Chart:          $([System.IO.Path]::GetFileName($ChartFile))" -ForegroundColor Green
Write-Host "  Trial Balance:  $([System.IO.Path]::GetFileName($TBFile))" -ForegroundColor Green
Write-Host ""

# ── Template selection ──
$templates = @("Company", "Trust", "SoleTrader", "Partnership", "XeroHandi")
Write-Host "  Select template:" -ForegroundColor Yellow
for ($i = 0; $i -lt $templates.Count; $i++) {
    Write-Host "    $($i + 1). $($templates[$i])"
}
Write-Host ""
$choice = Read-Host "  Enter number (1-$($templates.Count))"
$idx = [int]$choice - 1
if ($idx -lt 0 -or $idx -ge $templates.Count) {
    Write-Host "  ERROR: Invalid selection." -ForegroundColor Red
    Read-Host "  Press Enter to exit"
    exit 1
}
$template = $templates[$idx]
Write-Host ""
Write-Host "  Template: $template" -ForegroundColor Green
Write-Host ""

# ── Run mapping pipeline ──
Write-Host "  Running mapping pipeline..." -ForegroundColor Cyan
Push-Location $ProjectRoot
try {
    & uv run python mapping_logic_v15.py "$ChartFile" "$TBFile" --chart $template
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "  ERROR: Mapping pipeline failed (exit code $LASTEXITCODE)." -ForegroundColor Red
        Read-Host "  Press Enter to exit"
        exit 1
    }
} finally {
    Pop-Location
}

# ── Locate augmented output ──
$chartDir = [System.IO.Path]::GetDirectoryName($ChartFile)
$augmented = Join-Path $chartDir "AugmentedChartOfAccounts.csv"
if (-not (Test-Path $augmented)) {
    Write-Host "  ERROR: AugmentedChartOfAccounts.csv not found in $chartDir" -ForegroundColor Red
    Read-Host "  Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "  Generating review report..." -ForegroundColor Cyan

# ── Generate HTML review report ──
Push-Location $ProjectRoot
try {
    & uv run python tools/gen_review_report.py "$augmented" "$ChartFile"
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "  ERROR: Review report generation failed." -ForegroundColor Red
        Read-Host "  Press Enter to exit"
        exit 1
    }
} finally {
    Pop-Location
}

# ── Open HTML in browser ──
$htmlReport = Join-Path $chartDir "ReviewReport.html"
if (Test-Path $htmlReport) {
    Write-Host ""
    Write-Host "  Opening review report in browser..." -ForegroundColor Green
    Start-Process $htmlReport
} else {
    Write-Host "  WARNING: ReviewReport.html not found." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  Done!" -ForegroundColor Green
Write-Host ""
Read-Host "  Press Enter to exit"
```

**Step 2: Smoke-test the script syntax**

Run from bash (we can't fully test drag-and-drop from CLI, but we can verify syntax):
```bash
powershell -NoProfile -File Run-Mapping.ps1 2>&1 | head -10
```
Expected: shows the usage message (no files provided).

**Step 3: Commit**

```bash
git add Run-Mapping.ps1
git commit -m "feat: add PowerShell drag-and-drop launcher"
```

---

## Task 2: Create `tools/gen_review_report.py` — data loading

**Files:**
- Create: `tools/gen_review_report.py`

**Step 1: Write the data loading and CLI entry point**

This script takes two arguments:
1. Path to `AugmentedChartOfAccounts.csv`
2. Path to original client chart (for preserving columns in export)

It loads both CSVs, loads SystemMappings.csv for the code datalist, then calls `generate_html()`.

```python
"""Generate a standalone HTML review report for mapping pipeline output.

Reads AugmentedChartOfAccounts.csv (pipeline output) and the original client
chart, produces a self-contained HTML page where users can:
- Review each account's assigned reporting code
- Override codes with reasons
- Correct account types that disagree with code heads
- Export a Xero-ready ChartOfAccounts CSV
- Export review decisions as JSON for developer review

Run:  uv run python tools/gen_review_report.py <augmented.csv> <original_chart.csv>
Output: ReviewReport.html alongside the augmented CSV
"""
import csv
import html as html_mod
import json
import pathlib
import sys

SYSTEM_MAPPINGS = pathlib.Path(__file__).parent.parent / "SystemFiles" / "SystemMappings.csv"


def load_system_mappings():
    """Return {code: name} and [(code, name)] from SystemMappings.csv."""
    sys_map = {}
    code_list = []
    if SYSTEM_MAPPINGS.exists():
        with open(SYSTEM_MAPPINGS, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                code = row.get("Reporting Code", "").strip()
                desc = row.get("Name", "").strip()
                if code and desc:
                    sys_map[code] = desc
                    code_list.append((code, desc))
    return sys_map, code_list


def load_augmented(path):
    """Load AugmentedChartOfAccounts.csv and return list of account dicts."""
    accounts = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            accounts.append({
                "code": row.get("*Code", "").strip(),
                "name": row.get("*Name", "").strip(),
                "type": row.get("*Type", "").strip(),
                "tax_code": row.get("*Tax Code", "").strip(),
                "description": row.get("Description", "").strip(),
                "dashboard": row.get("Dashboard", "").strip(),
                "expense_claims": row.get("Expense Claims", "").strip(),
                "enable_payments": row.get("Enable Payments", "").strip(),
                "original_code": row.get("Report Code", "").strip(),
                "reporting_name": row.get("Reporting Name", "").strip(),
                "predicted_code": row.get("predictedReportCode", "").strip(),
                "predicted_name": row.get("predictedMappingName", "").strip(),
                "needs_review": row.get("NeedsReview", "").strip(),
                "source": row.get("Source", "").strip(),
            })
    return accounts


def main():
    if len(sys.argv) < 3:
        print("Usage: gen_review_report.py <augmented.csv> <original_chart.csv>")
        sys.exit(1)

    augmented_path = pathlib.Path(sys.argv[1])
    original_path = pathlib.Path(sys.argv[2])

    if not augmented_path.exists():
        print(f"ERROR: {augmented_path} not found")
        sys.exit(1)

    sys_map, code_list = load_system_mappings()
    accounts = load_augmented(augmented_path)

    html_content = generate_html(accounts, sys_map, code_list)

    output_path = augmented_path.with_name("ReviewReport.html")
    output_path.write_text(html_content, encoding="utf-8")

    print(f"Written {len(accounts)} accounts to {output_path}")
    print(f"  File size: {output_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
```

**Step 2: Verify it loads without errors**

```bash
uv run python tools/gen_review_report.py --help 2>&1 || true
```
Expected: shows usage message (no args), exits cleanly.

---

## Task 3: Add `generate_html()` to `tools/gen_review_report.py`

**Files:**
- Modify: `tools/gen_review_report.py` (add the `generate_html` function)

This is the largest task. The HTML structure mirrors the mismatch report but adapted for the review workflow. It has three phases.

**Step 1: Write `generate_html()`**

Add the function between `load_augmented()` and `main()`. The function generates a complete self-contained HTML document with:

**HTML structure:**
1. `<head>` with all CSS (same design language as mismatch report)
2. Summary cards: Total accounts, Needs Review, Overridden, Accepted
3. Toolbar: search, filter by NeedsReview / Source / review status
4. Account table with all rows — decision column has Accept (default) / Override
5. Datalist for code autocomplete from SystemMappings
6. Phase 2: Type correction (same logic as mismatch report)
7. Phase 3: Export — Xero CSV download + Review JSON download
8. `<script>` with all JS

**Key JS functions (port from mismatch report, adapt):**

| Function | Purpose |
|----------|---------|
| `loadDecisions()` / `saveDecisions()` | localStorage persistence |
| `setDecision(id, choice)` | Accept or override |
| `setOverrideCode(id, code, idx)` | Code picker for override |
| `setReason(id, reason)` | Reason textarea |
| `applyFilters()` | Search + filter toolbar |
| `sortTable(col)` | Column sort |
| `updateProgress()` | Summary card counts |
| Phase 2 functions | Same as mismatch report (`startPhase2`, `renderPhase2`, type prediction, etc.) |
| `downloadCSV()` | Xero-format CSV blob download |
| `downloadJSON()` | Review decisions JSON blob download |
| `restoreState()` | Rehydrate from localStorage on load |

**CSS:** Reuse the same design system as the mismatch report (cards, toolbar, table, decision cells, phase2 styles).

**Important differences from mismatch report:**

1. **All rows shown** (not just mismatches) — rows where `NeedsReview === 'Y'` get a yellow highlight
2. **Decision options:** Accept (radio, pre-selected when code looks good) / Override (radio, shows code picker + reason)
3. **No "got vs expected" framing** — instead it's "assigned code" with an optional override
4. **Phase 2 triggers** via a "Start Type Review" button (always visible, not gated on Phase 1 completion) since users may want to check types before reviewing all codes
5. **CSV export** preserves ALL original columns from the augmented CSV, updating `Report Code` with decisions and `*Type` with type corrections. Output columns match Xero import format: `*Code, Report Code, *Name, Reporting Name, *Type, *Tax Code, Description, Dashboard, Expense Claims, Enable Payments`
6. **JSON export** includes only rows where the user made a change (override or type correction)

**The full `generate_html` function** should be written as a single function that returns an HTML string, using the same `parts.append()` pattern as `gen_mismatch_report.py`. The embedded JS and CSS are written inline in f-strings.

Reference `tools/gen_mismatch_report.py` for the exact patterns — specifically:
- `generate_html()` at line 184 for overall structure
- Lines 196-301 for CSS
- Lines 306-488 for table rendering
- Lines 492-1236 for JavaScript (localStorage, decisions, filtering, Phase 2, CSV export)

Adapt each section for the review workflow. The Phase 2 type correction JS (lines 889-1213) can be copied almost verbatim — only `getFinalCode()` needs to change since the data source is different.

**Step 2: Run the generator on the live example**

First run the mapping pipeline on the live data, then generate the report:
```bash
uv run python mapping_logic_v15.py ".dev-info/ChartOfAccounts (3).csv" .dev-info/Trial_Balance.xlsx --chart Company
uv run python tools/gen_review_report.py ".dev-info/AugmentedChartOfAccounts.csv" ".dev-info/ChartOfAccounts (3).csv"
```
Expected: `ReviewReport.html` created in `.dev-info/`, file size > 50KB (116 accounts + all JS/CSS).

**Step 3: Visually verify the HTML**

Open `.dev-info/ReviewReport.html` in browser and verify:
- All 116 accounts visible in table
- NeedsReview rows highlighted
- Accept/Override radio buttons work
- Code autocomplete works in override mode
- Search and filter toolbar works
- Type Review button shows Phase 2
- CSV download produces valid Xero-format file
- JSON download captures only overrides

**Step 4: Commit**

```bash
git add tools/gen_review_report.py
git commit -m "feat: add HTML review report generator for mapping output"
```

---

## Task 4: End-to-end verification with live data

**Step 1: Run the full PowerShell flow**

Test from PowerShell (simulating drag-and-drop by passing args directly):
```powershell
powershell -NoProfile -File Run-Mapping.ps1 ".dev-info\ChartOfAccounts (3).csv" ".dev-info\Trial_Balance.xlsx"
```
Select template 1 (Company) when prompted.

Expected:
1. Files correctly identified (chart and TB)
2. Template menu appears
3. Pipeline runs successfully
4. ReviewReport.html generated
5. Browser opens the report

**Step 2: Verify all output files exist**

```bash
ls -la .dev-info/AugmentedChartOfAccounts.csv .dev-info/ReviewReport.html
```

**Step 3: Run existing test suite (no regressions)**

```bash
uv run pytest tests/ -v
```
Expected: 777 passed, 11 xfailed (unchanged from before).

---

## Task 5: Final commit

**Step 1: Stage and commit all new files**

```bash
git add Run-Mapping.ps1 tools/gen_review_report.py docs/plans/2026-02-25-powershell-launcher-review-report-design.md docs/plans/2026-02-25-powershell-launcher-review-report.md
git commit -m "feat: add PowerShell drag-and-drop launcher and HTML review report

- Run-Mapping.ps1: drag-and-drop entry point with template selection
- tools/gen_review_report.py: generates standalone HTML review page
- Phase 1: code review with Accept/Override per account
- Phase 2: type correction for code-head vs account-type mismatches
- Phase 3: Xero-format CSV export + review decisions JSON export"
```

**Step 2: Verify clean git status**

```bash
git status
git log --oneline -3
```
