---
name: process-client
description: Run the full Xero mapping pipeline on a client folder and open the ReviewReport. Usage - /process-client <folder_path> [--type Company|Trust|Partnership|SoleTrader|XeroHandi]
---

Run the Xero report code mapping pipeline on a client folder, then generate and open the ReviewReport.

## Steps

1. Identify input files in the specified folder:
   - Chart of Accounts: the `.csv` file that is NOT named `AugmentedChartOfAccounts.csv` or `ChangeOrErrorReport.csv`
   - Trial Balance: the `.xlsx` file (or `.csv` if no xlsx present)
   - If multiple candidates exist, prefer the file with "ChartOfAccounts" in its name

2. Determine entity type from the `--type` argument (default: `Company`). Valid values: `Company`, `Trust`, `Partnership`, `SoleTrader`, `XeroHandi`

3. Run the mapping pipeline:
   ```
   uv run python mapping_logic_v15.py "<chart_path>" "<trial_balance_path>" --chart <type>
   ```

4. Generate the review report:
   ```
   uv run python tools/gen_review_report.py "<folder>/AugmentedChartOfAccounts.csv" --type <type>
   ```

5. Open the report:
   ```
   start "" "<folder>/ReviewReport.html"
   ```

6. Report to the user:
   - Account count written
   - Any integrity warnings from the pipeline output
   - Path to the ReviewReport.html
   - Any balance anomalies detected
