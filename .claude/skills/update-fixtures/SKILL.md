---
name: update-fixtures
description: Run integration tests, generate the mismatch review report, and apply a decisions JSON to update validated fixtures. Usage - /update-fixtures [decisions_json_path]
---

Workflow for updating `tests/fixtures/validated/` after rule changes. Follow these steps in order — do not skip or reorder them.

## Steps

### If no decisions JSON is provided:

1. Run integration tests and report mismatch count:
   ```
   uv run pytest tests/test_integration.py -v --no-header 2>&1 | tail -30
   ```

2. Generate the mismatch review report:
   ```
   uv run python tools/gen_mismatch_report.py
   ```

3. Open the report:
   ```
   start "" "tests/mismatch_report.html"
   ```

4. Tell the user:
   - How many mismatches were found
   - That they should review the HTML report, make decisions, and export a `decisions.json`
   - To re-invoke this skill with the path to that JSON once ready: `/update-fixtures <path/to/decisions.json>`

### If a decisions JSON path is provided:

1. Verify the file exists and is valid JSON before proceeding.

2. Apply the decisions to update fixture CSVs:
   ```
   uv run python tools/apply_decisions.py "<decisions_json_path>"
   ```

3. Re-run integration tests to confirm the fixture update resolved mismatches:
   ```
   uv run pytest tests/test_integration.py -v --no-header 2>&1 | tail -20
   ```

4. Report the before/after mismatch counts and any remaining failures.

## Important

- Never edit `tests/fixtures/validated/*.csv` directly — always use `apply_decisions.py`
- The `xfail` tests are permanently anonymised and should not be investigated or fixed
