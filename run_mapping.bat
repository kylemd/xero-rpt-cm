@echo off
echo ========================================
echo Xero Report Code Mapping Tool
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.13+ and try again
    pause
    exit /b 1
)

REM Check if required files exist
if not exist "mapping_logic_v15.py" (
    echo ERROR: mapping_logic_v15.py not found
    echo Please ensure you're running this from the project directory
    pause
    exit /b 1
)

echo Python found. Starting mapping process...
echo.

REM Get input files from user
set /p CHART_FILE="Enter Chart of Accounts file path (CSV/XLSX): "
set /p TRIAL_FILE="Enter Trial Balance file path (CSV/XLSX): "
set /p TEMPLATE="Enter template name (Company/Trust/SoleTrader/Partnership/XeroHandi): "

REM Validate inputs
if "%CHART_FILE%"=="" (
    echo ERROR: Chart of Accounts file path is required
    pause
    exit /b 1
)

if "%TRIAL_FILE%"=="" (
    echo ERROR: Trial Balance file path is required
    pause
    exit /b 1
)

if "%TEMPLATE%"=="" (
    echo ERROR: Template name is required
    pause
    exit /b 1
)

REM Check if files exist
if not exist "%CHART_FILE%" (
    echo ERROR: Chart of Accounts file not found: %CHART_FILE%
    pause
    exit /b 1
)

if not exist "%TRIAL_FILE%" (
    echo ERROR: Trial Balance file not found: %TRIAL_FILE%
    pause
    exit /b 1
)

echo.
echo Files found. Starting validation and mapping...
echo.

REM Run the mapping logic
python mapping_logic_v15.py "%CHART_FILE%" "%TRIAL_FILE%" --chart %TEMPLATE%

echo.
echo ========================================
echo Processing complete!
echo ========================================
echo.
echo Check the following files for results:
echo - AugmentedChartOfAccounts.csv (main output)
echo - integrity_findings.json (validation results)
echo - balance_anomalies.json (balance issues)
echo - ReportingTree.json (inferred ranges)
echo.
pause
