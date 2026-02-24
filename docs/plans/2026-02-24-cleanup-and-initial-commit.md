# Cleanup & Initial Commit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clean the repo of stale artifacts, configure gitignore, write proper documentation, and make the initial commit.

**Architecture:** Delete stale files, remove cache/dot folders from `.dev-info`, write comprehensive `.gitignore`, rewrite `README.md`, create `docs/ARCHITECTURE.md`, then commit.

**Tech Stack:** Git, bash

---

### Task 1: Delete stale artifacts from project root

**Files:**
- Delete: `out.json`
- Delete: `ReportingTree.json`
- Delete: `integrity_findings.json`
- Delete: `heuristic_audit_findings.json`
- Delete: `test_balance_detection.html`
- Delete: `temp_existing_codes.txt`
- Delete: `ChartOfAccounts (6).csv`
- Delete: `ManualJournal (2).csv`
- Delete: `ManualJournal_2025-06-30.csv`
- Delete: `ManualJournal_2025-06-30_fixed.csv`
- Delete: `ManualJournal_2026-06-30.csv`
- Delete: `ManualJournal_2026-06-30_fixed.csv`
- Delete: `BUG_FIXES_SUMMARY.md`
- Delete: `IMPLEMENTATION_SUMMARY.md`
- Delete: `COMPLETE_STANDALONE_README.md`
- Delete: `DEPLOYMENT.md`
- Delete: `STANDALONE_USAGE.md`
- Delete: `.cursorignore`
- Delete: `rule.mdc`

**Step 1: Delete all listed files**

```bash
cd "/c/Users/KyleDrayton/Documents/Development/Xero Report Code Mapping"
rm -f out.json ReportingTree.json integrity_findings.json \
  heuristic_audit_findings.json test_balance_detection.html \
  temp_existing_codes.txt "ChartOfAccounts (6).csv" \
  "ManualJournal (2).csv" ManualJournal_2025-06-30.csv \
  ManualJournal_2025-06-30_fixed.csv ManualJournal_2026-06-30.csv \
  ManualJournal_2026-06-30_fixed.csv \
  BUG_FIXES_SUMMARY.md IMPLEMENTATION_SUMMARY.md \
  COMPLETE_STANDALONE_README.md DEPLOYMENT.md STANDALONE_USAGE.md \
  .cursorignore rule.mdc
```

**Step 2: Verify deletion**

```bash
ls *.json *.html temp_* *SUMMARY* *STANDALONE* DEPLOYMENT* rule.mdc .cursorignore 2>/dev/null
```

Expected: No output (all deleted).

---

### Task 2: Delete cache/dot folders

**Step 1: Delete root-level cache dirs**

```bash
rm -rf __pycache__ .cursor
```

**Step 2: Delete cache dirs inside .dev-info**

```bash
rm -rf ".dev-info/old-codebases/Report Code Mapping - Data Analysis/.venv"
rm -rf ".dev-info/old-codebases/Report Code Mapping - Old/.venv"
rm -rf ".dev-info/old-codebases/Report Code Mapping - Old/.cursor"
rm -rf ".dev-info/old-codebases/Report Code Mapping - Old/.git"
find .dev-info -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
```

**Step 3: Delete any __pycache__ in web_interface/**

```bash
rm -rf web_interface/__pycache__
```

**Step 4: Verify no stale cache dirs remain**

```bash
find . -maxdepth 1 -type d -name "__pycache__" -o -name ".cursor"
find .dev-info -type d \( -name ".venv" -o -name ".cursor" -o -name ".git" -o -name "__pycache__" \) 2>/dev/null
```

Expected: No output.

---

### Task 3: Write .gitignore

**Files:**
- Modify: `.gitignore`

**Step 1: Write the comprehensive .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
build/
dist/
wheels/

# Virtual environments
.venv/
.rcm_env/

# IDE / Editor
.cursor/
.vscode/
*.swp
*.swo

# Client data (never commit live charts or journals)
Clients/
ManualJournal*.csv
/ChartOfAccounts*.csv
!ChartOfAccounts/
*Trial_Balance*.xlsx

# Generated outputs (produced per-run alongside client inputs)
ReportingTree.json
out.json
AugmentedChartOfAccounts*
ChangeOrErrorReport*
ClarificationLog*
*_findings.json
temp_*.txt

# Development reference (archival old codebases, too large for git)
.dev-info/

# OS
Thumbs.db
.DS_Store
```

Note: `/ChartOfAccounts*.csv` uses a leading slash to only match root-level files
like `ChartOfAccounts (6).csv`. The `!ChartOfAccounts/` line ensures the template
directory is NOT ignored. `*Trial_Balance*.xlsx` catches any trial balance exports.

---

### Task 4: Write README.md

**Files:**
- Modify: `README.md`

Replace with a clean, accurate entry point covering: what the project does,
repository layout, setup (conda env), usage (CLI), and pointers to docs/.

Content should reflect:
- Project uses conda env `ReportCodeMapping` (not uv)
- Main entry point: `mapping_logic_v15.py`
- Template charts in `ChartOfAccounts/`
- System files in `SystemFiles/`
- Web interface exists but is a prototype
- `docs/` contains staff guide, ML guide, architecture

---

### Task 5: Write docs/ARCHITECTURE.md

**Files:**
- Create: `docs/ARCHITECTURE.md`

Consolidate the useful content from the deleted docs into a single architecture
overview. Should cover:

1. **Pipeline overview** - How mapping_logic_v15.py processes a client chart
2. **Key modules** - mapping_logic_v15.py, file_handler.py, integrity_validator.py,
   audit_heuristics.py, postprocess_outputs.py
3. **Data flow** - Client chart + trial balance in, augmented chart + reporting tree out
4. **Template charts** - What ChartOfAccounts/*.csv are and how they're used
5. **System files** - SystemMappings.csv, Account_Types_Head.csv, financial report JSONs
6. **Web interface** - Current state (Flask prototype)
7. **Known limitations** - From the bug fixes and implementation summaries

---

### Task 6: Remove uv artifacts

**Files:**
- Delete: `uv.lock`
- Modify: `pyproject.toml` (remove uv-specific config if any, update to reflect conda)

The project has moved from uv to conda. The `uv.lock` (125KB) is no longer relevant.
`pyproject.toml` should be updated to remove the Python version pin of >=3.13 if the
conda env uses a different version, and the description placeholder should be filled in.

---

### Task 7: Update memory files

Save project structure, conventions, and key decisions to auto-memory so future
sessions have context.

---

### Task 8: Initial git commit

**Step 1: Verify git status looks clean**

```bash
git status
```

Review untracked and modified files. Ensure no client data or cache dirs appear.

**Step 2: Stage all files**

```bash
git add -A
```

**Step 3: Review staged files**

```bash
git diff --cached --stat
```

Verify nothing sensitive is staged.

**Step 4: Commit**

```bash
git commit -m "Initial commit: clean baseline with proper gitignore and documentation

- Core mapping pipeline: mapping_logic_v15.py, file_handler.py,
  integrity_validator.py, audit_heuristics.py
- Template charts: Company, Partnership, SoleTrader, Trust, XeroHandi
- System files: SystemMappings.csv, Account_Types_Head.csv,
  financial report JSONs
- Web interface prototype (Flask + HTML/JS/CSS)
- Comprehensive .gitignore for client data, generated outputs,
  and development artifacts
- Documentation: README, ARCHITECTURE, STAFF_GUIDE, ML_MODEL_GUIDE

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

**Step 5: Verify**

```bash
git log --oneline -1
git status
```

Expected: Clean working tree (only .dev-info and .venv as untracked, both gitignored).
