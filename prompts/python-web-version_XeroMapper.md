# XeroMapper Portable — Product Specification (Markdown)

**Owner:** [Redacted]
**Audience:** Advanced Systems Engineer (packaging, deployment, hardening)  
**Version:** v0.1 (Draft)  
**Last updated:** 2025-09-05 (Australia/Sydney)

---

## 0) Executive Summary

Build a **zero‑install, portable Windows application** that runs a Python core to process two user‑supplied files (CSV and/or XLSX), presents an **interactive review UI in the user’s default browser** (served from `127.0.0.1`), allows inline corrections, and then exports:
- a final **Augmented Chart of Accounts** file,
- a **Clarification Log** of user edits (who/what/why),
- a **Change/Error Report** for diagnostics, and
- a **Reporting Tree** JSON for downstream systems.

The app must run under **standard user permissions** (no admin), make **no registry or system changes**, and require **no installation**. Distribution is via a **network share**, with hot‑swappable heuristic/rules files to allow maintenance without rebuilding the EXE.

---

## 1) Goals & Non‑Goals

### Goals
1. **Zero‑install**: run as a self‑contained EXE (or onedir folder) from a network share or local user profile.
2. **Interactive verification**: show predicted outputs in an in‑browser editable grid; collect and apply user corrections before exporting.
3. **Deterministic, auditable processing**: produce CSV/JSON outputs and a machine‑readable log of overrides with timestamps and rationale.
4. **Hot‑swappable heuristics**: business rules & mappings live in external CSV/YAML under `Resources/` so they can be updated without rebuilding.
5. **Robust file I/O**: support **CSV** and **XLSX** inputs; preserve column order and datatypes where feasible; safe writes with atomic/temporary files.
6. **No external network dependency**: the app works offline; UI binds to `127.0.0.1` only.

### Non‑Goals
- Rewriting the logic in JavaScript or hosting a central web service.
- Embedding within Excel (Python‑in‑Excel is out of scope).
- Enterprise telemetry/analytics beyond basic local usage logging.

---

## 2) Primary User Workflows

### 2.1 Run & Upload
1. User double‑clicks `XeroMapper.exe` (or shortcut to it).  
2. App starts a local server on `127.0.0.1:<port>` and opens default browser automatically.  
3. User selects **Input A** (Client Chart of Accounts) and **Input B** (e.g., Trial Balance / second required file), either CSV or XLSX.  
4. App validates file structure (see §6) and displays any blocking/non‑blocking issues.

### 2.2 Review & Correct
1. App runs mapping/heuristics and renders a **review grid** with:
   - Predicted report code/description fields,
   - Validation flags (e.g., `NeedsReview`),
   - Editable columns: `CorrectCode`, `CorrectReason` (dropdowns / text), optional `Notes`.
2. User filters to flagged rows, applies corrections inline.
3. Clicking **Apply Corrections** reruns a light reconcile and previews final counts/impacts.

### 2.3 Export & Logs
1. User clicks **Export** → app writes outputs:
   - `AugmentedChartOfAccounts.csv`
   - `ClarificationLog.csv`
   - `ChangeOrErrorReport.csv`
   - `ReportingTree.json`
2. App shows a confirmation page with file paths. Optional “Open folder” button.
3. A minimal local `usage.log` line is appended (date/time, app version, success/error codes).

---

## 3) Inputs & Outputs

### 3.1 Inputs (user‑provided)
- **Input A:** *Client Chart of Accounts* — CSV **or** XLSX.  
- **Input B:** *Complementary file* (e.g., Trial Balance) — CSV **or** XLSX.

> **Column expectations:** defined in `Resources/config/schema.yaml` with flexible **field mapping** to accommodate client headings. Example (illustrative):
```yaml
expected_fields:
  chart_of_accounts:
    - { field: "AccountNumber", aliases: ["Account No", "Acct #"], required: true }
    - { field: "AccountName", aliases: ["Name", "Description"], required: true }
    - { field: "Type", aliases: ["Account Type"], required: false, enum: ["Asset","Liability","Equity","Income","Expense"] }
  trial_balance:
    - { field: "AccountNumber", required: true }
    - { field: "Balance", aliases: ["Closing Balance","Amount"], required: true, type: number }
```

### 3.2 Outputs (app‑generated)
- `AugmentedChartOfAccounts.csv` — enriched rows with predicted/confirmed mapping results.
- `ClarificationLog.csv` — deltas from predictions, including `RowID`, `Field`, `OldValue`, `NewValue`, `Reason`, `User`, `Timestamp`.
- `ChangeOrErrorReport.csv` — warnings, validation failures, unhandled edge cases.
- `ReportingTree.json` — hierarchical structure for reporting systems (JSON‑serializable).

**Default output location:**  
- Preferred: **same directory as Input A** in a new subfolder `XeroMapper_Output_YYYYMMDD_HHMMSS`.  
- Fallback (permission denied): `%USERPROFILE%\Documents\XeroMapper\Output\…`.

Writes are **atomic**: create temp file then move/replace on success.

---

## 4) Constraints (Hard Requirements)

- **OS:** Windows 10/11 x64, standard user (no admin).  
- **Zero‑install:** no MSI, no installers, no registry edits, no services. Pure portable EXE/folder.  
- **Network share execution:** must run from `\\server\share\…` (IT may prefer a local cache—see §9).  
- **No firewall prompts:** local server binds to `127.0.0.1` only (not `0.0.0.0`).  
- **No outbound internet dependency:** all assets served locally.  
- **Path lengths:** assume default Windows long‑paths **disabled** → keep app folder structure shallow; target total path length **< 200 chars**.  
- **Memory/size:** must process up to ~**200k rows** combined input within **≤ 2 GB RAM**.  
- **Performance targets:** typical dataset (≤ 50k rows) end‑to‑end ≤ **30s** on mid‑range office PCs.  
- **File locks:** never hold exclusive locks on source folders longer than needed; tolerate OneDrive/AV latency.  
- **Logging privacy:** no PII beyond filenames and aggregated counts; user edits captured only in output logs.  
- **Accessibility:** UI keyboard‑navigable; high‑contrast theme toggle.  
- **No installation of dependencies** on user machines. All Python libs bundled.

---

## 5) Architecture

### 5.1 High‑Level
- **Core:** Python 3.11 runtime bundled by **PyInstaller**. Core module exposes `run_mapping(df_a, df_b, config) -> results`.
- **Web layer (local only):** **FastAPI** + **Jinja2** templates + **HTMX** for partial updates.  
  - Editable grid via **Tabulator** (static JS/CSS shipped with the app).  
- **I/O adapters:** CSV via `pandas.read_csv`, XLSX via `pandas.read_excel` (engine: `openpyxl`).  
- **Rules/config:** externalized under `Resources/` (CSV/YAML).  
- **Packaging:** `--onedir` portable folder (preferred); optional `--onefile` if strictly required.

### 5.2 Process Flow
```
User → EXE → start local server (127.0.0.1:PORT) → open browser
     → upload files → validate schema → run core mapping
     → render grid → user edits → apply & revalidate
     → export outputs (atomic write) → show success + paths
```

### 5.3 Security Posture
- Server listens **only** on loopback.  
- CSRF not required (no cross‑site access), but anti‑replay token per session is acceptable.  
- No cookies beyond session nonce; no credentials.  
- All file paths normalized; prevent directory traversal.  
- Outputs confined to allowed directories (see §3.2).

---

## 6) Validation & Error Handling

### 6.1 Pre‑run validation
- File presence & type (CSV/XLSX).
- Schema validation against `schema.yaml` with:
  - **Blocking** errors (missing required fields) → must fix before run.
  - **Non‑blocking** warnings (extra columns, type coercions) → proceed with flags.
- Row count limits and basic sanity checks (e.g., non‑numeric balances).

### 6.2 Runtime safeguards
- Timeouts for long‑running heuristics with clear messaging.
- Try/except around I/O; descriptive error pages with **copyable diagnostics** (error code + context).

### 6.3 Post‑run consistency
- Counts of mapped/unmapped; balance reconciliation checks where relevant.
- Conflicts report (e.g., duplicate account numbers mapping to different codes).

**Standard error codes** (examples):
- `XM-VAL-001`: Missing required column `<name>`
- `XM-IO-002`: Cannot read file (permission/lock)
- `XM-CORE-010`: Heuristic rule failure `<rule_id>`
- `XM-OUT-020`: Failed to write output (disk full/perms)

---

## 7) UX Spec (Browser UI)

- **Home/Upload**: two file pickers, schema preview, Validate button.  
- **Review**: editable grid with: row selection, filter chips (Errors/Warnings/All), inline dropdowns for `CorrectCode`, text for `CorrectReason`.  
- **Summary**: counts, quick charts (optional), Export button.  
- **Help**: link to embedded markdown (from `Resources/help.md`).  
- **Keyboard**: Enter to edit/commit; Ctrl+F for filter; Esc to cancel.  
- **Theme**: light/dark toggle persisted to local storage.

---

## 8) Configuration & Hot‑Swap Rules

- `Resources/config/schema.yaml` — input schema & column aliases.  
- `Resources/rules/*.csv|yaml` — heuristics, keyword lists, mappings (e.g., bank/CC tokens).  
- `Resources/templates/` — Jinja2 HTML templates.  
- **Reload behavior:** rules read at process start; optional **“Reload rules”** button for admins to re‑read files without restart.

**Update policy:** Replacing files under `Resources/` on the share **does not** require rebuilding the EXE.

---

## 9) Packaging & Deployment

### 9.1 PyInstaller (preferred `--onedir`)
```
pyinstaller app.py --onedir --name XeroMapper ^
  --hidden-import openpyxl ^
  --add-data "Resources;Resources" ^
  --add-data "templates;templates" ^
  --collect-all jinja2 --collect-all fastapi
```
- Deliver `dist/XeroMapper/` folder to `\\Share\XeroMapper\current\`.

### 9.2 Optional local cache launcher (faster; still zero‑install)
Create `Launch_XeroMapper.cmd` and distribute the shortcut:
```bat
@echo off
set SRC=\\Share\XeroMapper\current
set DST=%LOCALAPPDATA%\XeroMapper\current
if not exist "%DST%" mkdir "%DST%"
robocopy "%SRC%" "%DST%" /MIR /R:1 /W:1 >nul
start "" "%DST%\XeroMapper.exe"
```
- Benefits: avoids AV rescans and network latency; still no admin rights.

### 9.3 Code signing (optional but recommended)
- Sign `XeroMapper.exe` with org cert to reduce SmartScreen prompts. If not possible, keep a stable publisher & path.

---

## 10) Performance & Resource Targets

- **Cold start:** ≤ 3s from EXE to browser open on i5/8GB.  
- **Run time:** ≤ 30s for 50k rows total; ≤ 90s for 200k rows.  
- **RAM ceiling:** stay under 2GB. Use chunked reads for large CSVs if needed.  
- **Disk I/O:** buffered writes; avoid temp files on network shares when possible (use `%TEMP%` then move).

---

## 11) Observability & Support

- `logs/usage.log` in `%APPDATA%\XeroMapper\`:
  - timestamp, version, result code, file counts. No PII contents.  
- `Export` step writes a small `run_manifest.json` alongside outputs summarizing versions, rule files’ checksums, and counts.  
- **Diagnostics bundle**: button to zip recent logs + last run manifest for support.

**SLOs (internal):**
- P0: app fails to start → same‑day rollback (replace share folder with prior version).  
- P1: mapping errors affecting outputs → hot‑fix `Resources/rules/` or ship patch EXE within 1 business day.

---

## 12) Testing & Acceptance

### 12.1 Unit/Component
- Core heuristics with pytest + small fixtures (edge cases: accumulated depreciation, COGS vs service reclass, bank vs credit‑card detection).

### 12.2 Integration
- CSV + XLSX ingest variations; mixed encodings; thousands separators; blank rows.  
- Concurrency: multiple users launching from the share simultaneously.

### 12.3 UAT Criteria
- Process three reference datasets without manual intervention, then apply specified overrides and reproduce expected outputs bit‑for‑bit.  
- All blocking/non‑blocking validations behave as spec’d.  
- No firewall prompts; no writes outside allowed paths; works under standard user.

---

## 13) Risks & Mitigations

- **AV/SmartScreen friction:** prefer `--onedir` + local cache launcher; consider code signing.  
- **Path length errors:** keep tree shallow; validate output path length; warn user early.  
- **Locked files on network shares:** retry with backoff; write to local temp then move.  
- **Large XLSX memory use:** encourage CSV where possible; support chunked CSV; cap XLSX row limits in config.  
- **Rules drift:** version rule files; include checksum in `run_manifest.json` for reproducibility.

---

## 14) Roadmap (Future Enhancements)

- “Open in Excel” export with formatting.  
- Role‑based presets for column mappings per client.  
- Optional read‑only CLI mode for batch processing (no UI).  
- Incremental port of selected heuristics to a browser‑side worker if pure‑web is later desired.

---

## 15) Deliverables

1. Portable app folder `XeroMapper/` with `XeroMapper.exe`, `Resources/`, `templates/`, `static/`.  
2. `pyinstaller.spec` and build script.  
3. `Resources/config/schema.yaml` and initial `Resources/rules/*.csv|yaml`.  
4. `Launch_XeroMapper.cmd` (optional).  
5. This specification (`XeroMapper_Portable_Spec.md`).

---

## 16) Open Questions

- Confirm maximum expected dataset sizes (rows/columns).  
- Confirm whether outputs must always mirror the input directory (vs user Documents fallback).  
- Confirm corporate policy on code signing for internal tools.  
- Any requirement to store user display name in `ClarificationLog.csv` (if so, permissible source?).

---

**End of Spec**

