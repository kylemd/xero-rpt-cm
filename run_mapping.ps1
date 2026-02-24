# Xero Report Code Mapping Tool - PowerShell Version
# This script provides an interactive way to run the mapping logic

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Xero Report Code Mapping Tool" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.13+ and try again" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if required files exist
if (-not (Test-Path "mapping_logic_v15.py")) {
    Write-Host "ERROR: mapping_logic_v15.py not found" -ForegroundColor Red
    Write-Host "Please ensure you're running this from the project directory" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Starting mapping process..." -ForegroundColor Green
Write-Host ""

# Get input files from user
$chartFile = Read-Host "Enter Chart of Accounts file path (CSV/XLSX)"
$trialFile = Read-Host "Enter Trial Balance file path (CSV/XLSX)"
$template = Read-Host "Enter template name (Company/Trust/SoleTrader/Partnership/XeroHandi)"

# Optional industry input
$industry = Read-Host "Enter industry (optional, press Enter to skip)"

# Validate inputs
if ([string]::IsNullOrWhiteSpace($chartFile)) {
    Write-Host "ERROR: Chart of Accounts file path is required" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

if ([string]::IsNullOrWhiteSpace($trialFile)) {
    Write-Host "ERROR: Trial Balance file path is required" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

if ([string]::IsNullOrWhiteSpace($template)) {
    Write-Host "ERROR: Template name is required" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if files exist
if (-not (Test-Path $chartFile)) {
    Write-Host "ERROR: Chart of Accounts file not found: $chartFile" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not (Test-Path $trialFile)) {
    Write-Host "ERROR: Trial Balance file not found: $trialFile" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Files found. Starting validation and mapping..." -ForegroundColor Green
Write-Host ""

# Build command
$command = "python mapping_logic_v15.py `"$chartFile`" `"$trialFile`" --chart $template"

if (-not [string]::IsNullOrWhiteSpace($industry)) {
    $command += " --industry `"$industry`""
}

# Run the mapping logic
Write-Host "Executing: $command" -ForegroundColor Yellow
Write-Host ""

try {
    Invoke-Expression $command
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Processing complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Check the following files for results:" -ForegroundColor Cyan
    Write-Host "- AugmentedChartOfAccounts.csv (main output)" -ForegroundColor White
    Write-Host "- integrity_findings.json (validation results)" -ForegroundColor White
    Write-Host "- balance_anomalies.json (balance issues)" -ForegroundColor White
    Write-Host "- ReportingTree.json (inferred ranges)" -ForegroundColor White
    Write-Host ""
    
} catch {
    Write-Host "ERROR: Failed to run mapping logic" -ForegroundColor Red
    Write-Host "Error details: $($_.Exception.Message)" -ForegroundColor Red
}

Read-Host "Press Enter to exit"
