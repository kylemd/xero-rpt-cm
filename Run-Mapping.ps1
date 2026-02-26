# Run-Mapping.ps1 — Launcher for Xero Report Code Mapping
# Usage:
#   Interactive:  Double-click to open, then drag files into the terminal window when prompted.
#   CLI:          .\Run-Mapping.ps1 -Chart "path\to\ChartOfAccounts.csv" -TrialBalance "path\to\TB.xlsx" -Template Company

param(
    [string]$Chart,
    [string]$TrialBalance,
    [ValidateSet("Company", "Trust", "SoleTrader", "Partnership", "XeroHandi")]
    [string]$Template
)
$ErrorActionPreference = "Stop"

# ── Resolve project root (where this script lives) ──
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition

# ── Banner ──
Write-Host ""
Write-Host "  Xero Report Code Mapping" -ForegroundColor Cyan
Write-Host "  ========================" -ForegroundColor Cyan
Write-Host ""

# ── Collect file paths (skip prompts if arguments supplied) ──
if ($Chart) {
    $ChartFile = $Chart.Trim().Trim('"').Trim("'")
} else {
    Write-Host "  Drag your ChartOfAccounts CSV into this window and press Enter:" -ForegroundColor Yellow
    $ChartRaw = Read-Host "  "
    Write-Host ""
    $ChartFile = $ChartRaw.Trim().Trim('"').Trim("'")
}

if ($TrialBalance) {
    $TBFile = $TrialBalance.Trim().Trim('"').Trim("'")
} else {
    Write-Host "  Drag your Trial Balance file (CSV or XLSX) and press Enter:" -ForegroundColor Yellow
    $TBRaw = Read-Host "  "
    Write-Host ""
    $TBFile = $TBRaw.Trim().Trim('"').Trim("'")
}

# ── Validate files exist ──
if (-not (Test-Path $ChartFile)) {
    Write-Host "  ERROR: File not found: $ChartFile" -ForegroundColor Red
    Read-Host "  Press Enter to exit"
    exit 1
}
if (-not (Test-Path $TBFile)) {
    Write-Host "  ERROR: File not found: $TBFile" -ForegroundColor Red
    Read-Host "  Press Enter to exit"
    exit 1
}

# Resolve to full paths
$ChartFile = (Resolve-Path $ChartFile).Path
$TBFile = (Resolve-Path $TBFile).Path

# ── Validate chart filename ──
$chartName = [System.IO.Path]::GetFileName($ChartFile)
if ($chartName -notmatch '^ChartOfAccounts') {
    Write-Host "  ERROR: First file must start with 'ChartOfAccounts'." -ForegroundColor Red
    Write-Host "  Got: $chartName" -ForegroundColor Yellow
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

Write-Host "  Chart:          $chartName" -ForegroundColor Green
Write-Host "  Trial Balance:  $([System.IO.Path]::GetFileName($TBFile))" -ForegroundColor Green
Write-Host ""

# ── Template selection (skip prompt if -Template supplied) ──
if (-not $Template) {
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
    $Template = $templates[$idx]
}
Write-Host ""
Write-Host "  Template: $Template" -ForegroundColor Green
Write-Host ""

# ── Run mapping pipeline ──
Write-Host "  Running mapping pipeline..." -ForegroundColor Cyan
Push-Location $ProjectRoot
try {
    & uv run python mapping_logic_v15.py "$ChartFile" "$TBFile" --chart $Template
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
    & uv run python tools/gen_review_report.py "$augmented"
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

# ── Determine if running in CLI mode (all args provided) ──
$cliMode = $Chart -and $TrialBalance

Write-Host ""
Write-Host "  Done!" -ForegroundColor Green
Write-Host ""
if (-not $cliMode) {
    Read-Host "  Press Enter to exit"
}
