"""Generate an interactive HTML report for reviewing integration test mismatches.

Each mismatch row has a decision panel where the reviewer can:
- Pick "Rule Engine is correct", "Validated is correct", or enter a custom code
- Provide a reason/justification
- Decisions persist in localStorage and can be exported to JSON

Run:  uv run python tools/gen_mismatch_report.py
Output: tests/mismatch_report.html
"""
import csv
import html as html_mod
import json
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from rule_engine import evaluate_rules, MatchContext
from rules import ALL_RULES, OWNER_KEYWORDS
from mapping_logic_v15 import normalise, canonical_type

FIXTURES_DIR = pathlib.Path(__file__).parent.parent / "tests" / "fixtures" / "validated"
SYSTEM_MAPPINGS = pathlib.Path(__file__).parent.parent / "SystemFiles" / "SystemMappings.csv"
OUTPUT = pathlib.Path(__file__).parent.parent / "tests" / "mismatch_report.html"


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


def categorise(code, validated):
    got_head = code.split(".")[0]
    exp_head = validated.split(".")[0]
    is_child = validated.startswith(code + ".")
    is_parent = code.startswith(validated + ".")

    if is_parent or (
        validated in ("LIA", "ASS", "EXP", "ASS.CUR", "EQU")
        and len(code) > len(validated)
    ):
        return "Specificity Gap", "Rule gives more specific child code than validator"
    if got_head != exp_head:
        return "Category Mismatch", f"Different top-level: {got_head} vs {exp_head}"
    if is_child:
        return "Specificity Gap", "Validator used more specific child code"
    return "Code Mismatch", "Same category, different sub-classification"


def collect_mismatches(sys_map):
    mismatches = []
    rule_index = {r.name: r for r in ALL_RULES}

    for csv_file in sorted(FIXTURES_DIR.glob("*_validated_final.csv")):
        with open(csv_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                validated = row.get("ValidatedReportingCode", "").strip()
                if not validated:
                    continue
                name = row.get("Name", "")
                raw_type = row.get("Type", "")
                text = normalise(name)
                canon = canonical_type(raw_type)
                ctx = MatchContext(
                    normalised_text=text,
                    normalised_name=text,
                    raw_type=raw_type,
                    canon_type=canon,
                    template_name="company",
                    owner_keywords=OWNER_KEYWORDS,
                )
                code, rule_name = evaluate_rules(ALL_RULES, ctx)
                if code and code != validated:
                    suggested = (
                        row.get("SuggestedReportingCode", "").strip()
                        or row.get("InputReportingCode", "").strip()
                    )
                    match_reason = row.get("MatchReason", "").strip()
                    category, category_detail = categorise(code, validated)
                    r = rule_index.get(rule_name)

                    mismatches.append({
                        "id": f"{csv_file.stem}:{row.get('Code', '')}:{name[:40]}",
                        "file": csv_file.name,
                        "code": row.get("Code", ""),
                        "name": name,
                        "raw_type": raw_type,
                        "canon_type": canon,
                        "normalised": text,
                        "got": code,
                        "got_desc": sys_map.get(code, ""),
                        "expected": validated,
                        "expected_desc": sys_map.get(validated, ""),
                        "rule_name": rule_name,
                        "rule_priority": r.priority if r else "",
                        "rule_keywords": ", ".join(r.keywords) if r and r.keywords else "",
                        "rule_keywords_all": ", ".join(r.keywords_all) if r and r.keywords_all else "",
                        "rule_raw_types": ", ".join(sorted(r.raw_types)) if r and r.raw_types else "any",
                        "rule_canon_types": ", ".join(sorted(r.canon_types)) if r and r.canon_types else "any",
                        "rule_type_exclude": ", ".join(sorted(r.type_exclude)) if r and r.type_exclude else "",
                        "rule_keywords_exclude": ", ".join(r.keywords_exclude) if r and r.keywords_exclude else "",
                        "rule_notes": r.notes if r else "",
                        "old_suggested": suggested,
                        "old_match_reason": match_reason,
                        "category": category,
                        "category_detail": category_detail,
                    })

    mismatches.sort(key=lambda m: (m["category"], m["rule_name"], m["name"]))
    return mismatches


def generate_html(mismatches, sys_map, code_list):
    h = html_mod.escape
    cat_counts = Counter(m["category"] for m in mismatches)
    rule_counts = Counter(m["rule_name"] for m in mismatches)
    file_set = sorted(set(m["file"] for m in mismatches))

    # Embed the full code list as JSON for the autocomplete/datalist
    code_json = json.dumps(code_list, ensure_ascii=False)

    parts = []

    # ── HEAD ──
    parts.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Rule Engine Mismatch Review ({len(mismatches)} items)</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; padding: 20px; }}
h1 {{ margin-bottom: 4px; font-size: 1.5em; }}
.subtitle {{ color: #666; margin-bottom: 16px; font-size: .9em; }}

/* Summary */
.summary {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }}
.card {{ background: white; border-radius: 8px; padding: 14px 18px; box-shadow: 0 1px 3px rgba(0,0,0,.1); min-width: 150px; }}
.card h3 {{ font-size: .78em; color: #888; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 2px; }}
.card .num {{ font-size: 1.8em; font-weight: 700; }}
.card .num.green {{ color: #16a34a; }} .card .num.red {{ color: #dc2626; }}
.card .num.amber {{ color: #d97706; }} .card .num.blue {{ color: #2563eb; }}
.card .detail {{ font-size: .78em; color: #999; }}

/* Toolbar */
.toolbar {{ background: white; border-radius: 8px; padding: 14px 16px; box-shadow: 0 1px 3px rgba(0,0,0,.1); margin-bottom: 16px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }}
.toolbar label {{ font-weight: 600; font-size: .85em; }}
.toolbar select, .toolbar input[type=text] {{ padding: 5px 8px; border: 1px solid #ddd; border-radius: 4px; font-size: .85em; }}
.toolbar input[type=text] {{ width: 220px; }}
.toolbar .spacer {{ flex: 1; }}
.toolbar button {{ padding: 6px 14px; border: none; border-radius: 5px; font-size: .85em; font-weight: 600; cursor: pointer; }}
.btn-save {{ background: #2563eb; color: white; }}
.btn-save:hover {{ background: #1d4ed8; }}
.btn-save.saved {{ background: #16a34a; }}
.btn-folder {{ background: #7c3aed; color: white; }}
.btn-folder:hover {{ background: #6d28d9; }}
.btn-folder.linked {{ background: #059669; }}
.btn-clear {{ background: #ef4444; color: white; }}
.btn-clear:hover {{ background: #dc2626; }}
.btn-import {{ background: #64748b; color: white; }}
.btn-import:hover {{ background: #475569; }}
.save-status {{ font-size: .82em; color: #888; max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.count-label {{ font-size: .85em; color: #666; }}
.progress-label {{ font-size: .85em; font-weight: 600; }}

/* Table */
table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.1); font-size: .82em; }}
th {{ background: #1e293b; color: white; padding: 8px 10px; text-align: left; font-weight: 600; position: sticky; top: 0; z-index: 2; cursor: pointer; white-space: nowrap; font-size: .8em; }}
th:hover {{ background: #334155; }}
td {{ padding: 7px 10px; border-bottom: 1px solid #eee; vertical-align: top; }}
tr:hover td {{ background: #f0f9ff !important; }}
tr.specificity td {{ background: #fefce8; }}
tr.category-mismatch td {{ background: #fef2f2; }}
tr.reviewed td {{ opacity: .55; }}
tr.reviewed:hover td {{ opacity: 1; }}

/* Codes */
.code {{ font-family: 'SF Mono','Consolas',monospace; font-weight: 600; white-space: nowrap; font-size: .95em; }}
.code.got {{ color: #dc2626; }} .code.exp {{ color: #16a34a; }}
.tag {{ display: inline-block; padding: 2px 7px; border-radius: 10px; font-size: .72em; font-weight: 600; }}
.tag.spec {{ background: #fef3c7; color: #92400e; }}
.tag.cat {{ background: #fee2e2; color: #991b1b; }}
.tag.code-m {{ background: #dbeafe; color: #1e40af; }}
.kw-badge {{ display: inline-block; background: #e2e8f0; padding: 1px 4px; border-radius: 3px; font-size: .72em; margin: 1px; font-family: monospace; }}
.detail-row {{ font-size: .76em; color: #666; }}
.notes {{ font-size: .76em; color: #555; font-style: italic; max-width: 280px; }}
.hidden {{ display: none; }}

/* Decision column */
.decision-cell {{ min-width: 260px; }}
.decision-cell .radio-group {{ display: flex; flex-direction: column; gap: 4px; margin-bottom: 6px; }}
.decision-cell .radio-group label {{ display: flex; align-items: center; gap: 5px; font-size: .82em; cursor: pointer; padding: 3px 6px; border-radius: 4px; }}
.decision-cell .radio-group label:hover {{ background: #f1f5f9; }}
.decision-cell .radio-group label.selected {{ background: #dbeafe; font-weight: 600; }}
.decision-cell .radio-group input[type=radio] {{ margin: 0; }}
.decision-cell .other-input {{ display: none; margin: 4px 0; }}
.decision-cell .other-input.show {{ display: flex; gap: 4px; align-items: center; }}
.decision-cell .other-input input {{ width: 120px; padding: 3px 6px; border: 1px solid #cbd5e1; border-radius: 4px; font-family: monospace; font-size: .85em; }}
.decision-cell .other-input .code-desc {{ font-size: .72em; color: #666; max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.decision-cell textarea {{ width: 100%; min-height: 40px; padding: 4px 6px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: .8em; font-family: inherit; resize: vertical; }}
.decision-cell textarea::placeholder {{ color: #aaa; }}
.decision-cell .reason-label {{ font-size: .72em; color: #888; margin-bottom: 2px; }}
.decided-badge {{ display: inline-block; background: #dcfce7; color: #166534; padding: 1px 6px; border-radius: 8px; font-size: .7em; font-weight: 600; margin-left: 4px; }}
</style>
</head>
<body>
""")

    # ── HEADER ──
    parts.append(f'<h1>Rule Engine Mismatch Review</h1>\n')
    parts.append(
        f'<p class="subtitle">{len(file_set)} validated client files &bull; '
        f'{len(mismatches)} mismatches &bull; '
        f'<span class="tag spec">Specificity Gap</span> '
        f'<span class="tag cat">Category Mismatch</span> '
        f'<span class="tag code-m">Code Mismatch</span> &bull; '
        f'Decisions save to browser automatically</p>\n'
    )

    # ── SUMMARY CARDS ──
    parts.append('<div class="summary">\n')
    parts.append(f'  <div class="card"><h3>Total</h3><div class="num red">{len(mismatches)}</div></div>\n')
    parts.append(f'  <div class="card"><h3>Specificity</h3><div class="num amber">{cat_counts.get("Specificity Gap",0)}</div></div>\n')
    parts.append(f'  <div class="card"><h3>Category</h3><div class="num red">{cat_counts.get("Category Mismatch",0)}</div></div>\n')
    parts.append(f'  <div class="card"><h3>Code</h3><div class="num blue">{cat_counts.get("Code Mismatch",0)}</div></div>\n')
    parts.append(f'  <div class="card"><h3>Reviewed</h3><div class="num green" id="reviewedCount">0</div>'
                 f'<div class="detail" id="reviewedPct">0%</div></div>\n')
    parts.append(f'  <div class="card"><h3>Rules</h3><div class="num">{len(rule_counts)}</div></div>\n')
    parts.append('</div>\n')

    # ── TOOLBAR ──
    parts.append('<div class="toolbar">\n')
    parts.append('  <label>Category:</label>\n  <select id="filterCat" onchange="applyFilters()">\n    <option value="">All</option>\n')
    for cat in ["Specificity Gap", "Category Mismatch", "Code Mismatch"]:
        c = cat_counts.get(cat, 0)
        if c:
            parts.append(f'    <option value="{h(cat)}">{h(cat)} ({c})</option>\n')
    parts.append('  </select>\n')

    parts.append('  <label>Rule:</label>\n  <select id="filterRule" onchange="applyFilters()">\n    <option value="">All</option>\n')
    for rule, count in rule_counts.most_common():
        parts.append(f'    <option value="{h(rule)}">{h(rule)} ({count})</option>\n')
    parts.append('  </select>\n')

    parts.append('  <label>File:</label>\n  <select id="filterFile" onchange="applyFilters()">\n    <option value="">All</option>\n')
    for f in file_set:
        short = f.replace("_validated_final.csv", "")
        fc = sum(1 for m in mismatches if m["file"] == f)
        parts.append(f'    <option value="{h(f)}">{h(short)} ({fc})</option>\n')
    parts.append('  </select>\n')

    parts.append('  <label>Status:</label>\n  <select id="filterStatus" onchange="applyFilters()">\n')
    parts.append('    <option value="">All</option>\n    <option value="pending">Pending</option>\n    <option value="reviewed">Reviewed</option>\n  </select>\n')

    parts.append('  <label>Search:</label>\n')
    parts.append('  <input type="text" id="filterSearch" placeholder="Name, code, type..." oninput="applyFilters()">\n')
    parts.append('  <span class="count-label" id="visibleCount"></span>\n')
    parts.append('  <span class="spacer"></span>\n')
    parts.append('  <span class="save-status" id="saveStatus"></span>\n')
    parts.append('  <button class="btn-folder" onclick="pickFolder()">Set Save Folder</button>\n')
    parts.append('  <button class="btn-save" onclick="saveNow()">Save</button>\n')
    parts.append('  <button class="btn-import" onclick="document.getElementById(\'importFile\').click()">Import</button>\n')
    parts.append('  <input type="file" id="importFile" accept=".json" style="display:none" onchange="importJSON(event)">\n')
    parts.append('  <button class="btn-clear" onclick="clearAll()">Clear All</button>\n')
    parts.append('</div>\n')

    # ── DATALIST for code autocomplete ──
    parts.append('<datalist id="codeSuggestions">\n')
    for code, desc in code_list:
        parts.append(f'  <option value="{h(code)}">{h(desc)}</option>\n')
    parts.append('</datalist>\n')

    # ── TABLE ──
    parts.append("""<table id="mismatchTable">
<thead>
<tr>
  <th onclick="sortTable(0)" style="width:35px">#</th>
  <th onclick="sortTable(1)">Category</th>
  <th onclick="sortTable(2)">File</th>
  <th onclick="sortTable(3)">Account</th>
  <th onclick="sortTable(4)">Type</th>
  <th onclick="sortTable(5)">Normalised</th>
  <th onclick="sortTable(6)">Got</th>
  <th onclick="sortTable(7)">Expected</th>
  <th onclick="sortTable(8)">Rule</th>
  <th onclick="sortTable(9)">Rule Context</th>
  <th onclick="sortTable(10)">Old Mapper</th>
  <th style="min-width:270px">Your Decision</th>
</tr>
</thead>
<tbody>
""")

    for i, m in enumerate(mismatches):
        cat = m["category"]
        cat_class = "specificity" if cat == "Specificity Gap" else ("category-mismatch" if cat == "Category Mismatch" else "")
        tag_class = "spec" if cat == "Specificity Gap" else ("cat" if cat == "Category Mismatch" else "code-m")
        row_id = m["id"]
        esc_id = h(row_id)

        # Rule context cell
        ctx_parts = []
        if m["rule_keywords"]:
            kws = m["rule_keywords"].split(", ")
            ctx_parts.append("kw: " + " ".join(f'<span class="kw-badge">{h(k)}</span>' for k in kws))
        if m["rule_keywords_all"]:
            kws = m["rule_keywords_all"].split(", ")
            ctx_parts.append("kw_all: " + " ".join(f'<span class="kw-badge">{h(k)}</span>' for k in kws))
        if m["rule_keywords_exclude"]:
            ctx_parts.append(f'exclude: <span class="kw-badge">{h(m["rule_keywords_exclude"])}</span>')
        ctx_parts.append(f'types: {h(m["rule_raw_types"])}')
        if m["rule_type_exclude"]:
            ctx_parts.append(f'type_exclude: {h(m["rule_type_exclude"])}')
        ctx_parts.append(f'priority: {m["rule_priority"]}')
        rule_ctx_html = "<br>".join(ctx_parts)
        if m["rule_notes"]:
            rule_ctx_html += f'<br><em class="notes">{h(m["rule_notes"][:200])}</em>'

        search_text = " ".join([
            m["name"], m["raw_type"], m["got"], m["expected"],
            m["normalised"], m["rule_name"], m["category"],
        ]).lower()

        parts.append(
            f'<tr class="{cat_class}" '
            f'data-id="{esc_id}" '
            f'data-cat="{h(cat)}" '
            f'data-rule="{h(m["rule_name"])}" '
            f'data-file="{h(m["file"])}" '
            f'data-search="{h(search_text)}" '
            f'data-status="pending">\n'
        )
        parts.append(f'  <td>{i + 1}</td>\n')
        parts.append(f'  <td><span class="tag {tag_class}">{h(cat)}</span>'
                     f'<br><span class="detail-row">{h(m["category_detail"])}</span></td>\n')
        parts.append(f'  <td style="font-size:.78em">{h(m["file"].replace("_validated_final.csv",""))}</td>\n')
        parts.append(f'  <td><strong>{h(m["name"])}</strong>'
                     f'<br><span class="detail-row">Xero: {h(m["code"])}</span></td>\n')
        parts.append(f'  <td>{h(m["raw_type"])}'
                     f'<br><span class="detail-row">{h(m["canon_type"])}</span></td>\n')
        parts.append(f'  <td style="font-family:monospace;font-size:.78em">{h(m["normalised"][:60])}</td>\n')
        parts.append(f'  <td><span class="code got">{h(m["got"])}</span>'
                     f'<br><span class="detail-row">{h(m["got_desc"][:50])}</span></td>\n')
        parts.append(f'  <td><span class="code exp">{h(m["expected"])}</span>'
                     f'<br><span class="detail-row">{h(m["expected_desc"][:50])}</span></td>\n')
        parts.append(f'  <td><strong>{h(m["rule_name"])}</strong></td>\n')
        parts.append(f'  <td>{rule_ctx_html}</td>\n')
        parts.append(f'  <td style="font-size:.78em">{h(m["old_suggested"])}'
                     f'<br><span class="detail-row">{h(m["old_match_reason"][:50])}</span></td>\n')

        # Decision cell
        parts.append(f'  <td class="decision-cell" data-row-id="{esc_id}">\n')
        parts.append(f'    <div class="radio-group">\n')
        parts.append(f'      <label><input type="radio" name="d_{i}" value="got" '
                     f'onchange="setDecision(\'{esc_id}\',\'got\',\'{h(m["got"])}\')"> '
                     f'<span class="code got">{h(m["got"])}</span> (Rule Engine)</label>\n')
        parts.append(f'      <label><input type="radio" name="d_{i}" value="expected" '
                     f'onchange="setDecision(\'{esc_id}\',\'expected\',\'{h(m["expected"])}\')"> '
                     f'<span class="code exp">{h(m["expected"])}</span> (Validated)</label>\n')
        parts.append(f'      <label><input type="radio" name="d_{i}" value="other" '
                     f'onchange="setDecision(\'{esc_id}\',\'other\',\'\')"> '
                     f'Other code...</label>\n')
        parts.append(f'    </div>\n')
        parts.append(f'    <div class="other-input" id="other_{i}">\n')
        parts.append(f'      <input type="text" list="codeSuggestions" placeholder="e.g. EXP.OCC" '
                     f'oninput="setOtherCode(\'{esc_id}\',this.value, {i})">\n')
        parts.append(f'      <span class="code-desc" id="otherDesc_{i}"></span>\n')
        parts.append(f'    </div>\n')
        parts.append(f'    <div class="reason-label">Reason:</div>\n')
        parts.append(f'    <textarea placeholder="Why is this the right code?" '
                     f'oninput="setReason(\'{esc_id}\',this.value)"></textarea>\n')
        parts.append(f'  </td>\n')
        parts.append('</tr>\n')

    parts.append('</tbody>\n</table>\n')

    # ── JAVASCRIPT ──
    parts.append(f"""
<script>
const STORAGE_KEY = 'mismatch_decisions_v1';
const DIR_HANDLE_DB = 'mismatch_dir_handle';
const FILENAME = 'mismatch_decisions.json';
const CODES = {code_json};
const CODE_MAP = Object.fromEntries(CODES);
const TOTAL = {len(mismatches)};

// ─── State ───
let decisions = loadDecisions();
let dirHandle = null;      // File System Access directory handle
let saveTimer = null;      // Debounced auto-save timer
let lastSaveHash = '';     // Track whether data changed since last write

function loadDecisions() {{
  try {{ return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {{}}; }}
  catch {{ return {{}}; }}
}}

function saveDecisions() {{
  localStorage.setItem(STORAGE_KEY, JSON.stringify(decisions));
  updateProgress();
  scheduleAutoSave();
}}

// ─── Auto-save to file (debounced 2s after last change) ───
function scheduleAutoSave() {{
  if (saveTimer) clearTimeout(saveTimer);
  updateSaveStatus('unsaved');
  saveTimer = setTimeout(() => writeToFile(), 2000);
}}

function updateSaveStatus(state, detail) {{
  const el = document.getElementById('saveStatus');
  const btn = document.querySelector('.btn-save');
  if (state === 'saved') {{
    el.textContent = 'Saved ' + (detail || '');
    el.style.color = '#16a34a';
    btn.classList.add('saved');
    setTimeout(() => btn.classList.remove('saved'), 1500);
  }} else if (state === 'unsaved') {{
    el.textContent = 'Unsaved changes...';
    el.style.color = '#d97706';
    btn.classList.remove('saved');
  }} else if (state === 'error') {{
    el.textContent = detail || 'Save failed';
    el.style.color = '#dc2626';
  }} else if (state === 'idle') {{
    el.textContent = detail || '';
    el.style.color = '#888';
  }}
}}

// ─── Build export array ───
function buildExportData() {{
  const rows = document.querySelectorAll('#mismatchTable tbody tr');
  const exported = [];
  rows.forEach(row => {{
    const id = row.dataset.id;
    const d = decisions[id];
    if (!d || !d.choice) return;
    const cells = row.querySelectorAll('td');
    exported.push({{
      id: id,
      account_name: cells[3].querySelector('strong').textContent,
      type: cells[4].childNodes[0].textContent.trim(),
      rule_engine_code: cells[6].querySelector('.code').textContent,
      validated_code: cells[7].querySelector('.code').textContent,
      rule_name: cells[8].textContent.trim(),
      decision: d.choice,
      chosen_code: d.choice === 'got' ? cells[6].querySelector('.code').textContent
                 : d.choice === 'expected' ? cells[7].querySelector('.code').textContent
                 : d.code,
      reason: d.reason || '',
      timestamp: d.timestamp
    }});
  }});
  return exported;
}}

// ─── File System Access API ───

// IndexedDB helpers for persisting the directory handle across sessions
function openHandleDB() {{
  return new Promise((resolve, reject) => {{
    const req = indexedDB.open(DIR_HANDLE_DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore('handles');
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  }});
}}

async function storeHandle(handle) {{
  const db = await openHandleDB();
  const tx = db.transaction('handles', 'readwrite');
  tx.objectStore('handles').put(handle, 'saveDir');
  return new Promise(r => {{ tx.oncomplete = r; }});
}}

async function loadHandle() {{
  const db = await openHandleDB();
  const tx = db.transaction('handles', 'readonly');
  const req = tx.objectStore('handles').get('saveDir');
  return new Promise((resolve, reject) => {{
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => resolve(null);
  }});
}}

async function pickFolder() {{
  try {{
    dirHandle = await window.showDirectoryPicker({{ mode: 'readwrite' }});
    await storeHandle(dirHandle);
    const btn = document.querySelector('.btn-folder');
    btn.textContent = dirHandle.name;
    btn.classList.add('linked');
    updateSaveStatus('idle', 'Folder: ' + dirHandle.name);
    // Immediately save current state
    await writeToFile();
  }} catch (e) {{
    if (e.name !== 'AbortError') updateSaveStatus('error', 'Folder pick failed');
  }}
}}

async function restoreDirHandle() {{
  try {{
    const stored = await loadHandle();
    if (!stored) return;
    // Verify permission is still granted
    const perm = await stored.queryPermission({{ mode: 'readwrite' }});
    if (perm === 'granted') {{
      dirHandle = stored;
      const btn = document.querySelector('.btn-folder');
      btn.textContent = dirHandle.name;
      btn.classList.add('linked');
      updateSaveStatus('idle', 'Folder: ' + dirHandle.name);
    }} else {{
      // Try requesting — will show a prompt first time
      const req = await stored.requestPermission({{ mode: 'readwrite' }});
      if (req === 'granted') {{
        dirHandle = stored;
        const btn = document.querySelector('.btn-folder');
        btn.textContent = dirHandle.name;
        btn.classList.add('linked');
        updateSaveStatus('idle', 'Folder: ' + dirHandle.name);
      }}
    }}
  }} catch {{ /* ignore — will need manual pick */ }}
}}

async function writeToFile() {{
  const data = buildExportData();
  const json = JSON.stringify(data, null, 2);
  // Skip if nothing changed
  if (json === lastSaveHash) {{ updateSaveStatus('idle', dirHandle ? 'Folder: ' + dirHandle.name : ''); return; }}

  if (dirHandle) {{
    // Write directly to folder
    try {{
      const fileHandle = await dirHandle.getFileHandle(FILENAME, {{ create: true }});
      const writable = await fileHandle.createWritable();
      await writable.write(json);
      await writable.close();
      lastSaveHash = json;
      const now = new Date().toLocaleTimeString();
      updateSaveStatus('saved', now + ' (' + data.length + ' decisions)');
    }} catch (e) {{
      updateSaveStatus('error', 'Write failed: ' + e.message);
    }}
  }} else {{
    // No folder set — just note unsaved
    if (data.length > 0) {{
      updateSaveStatus('idle', 'Pick a save folder to auto-commit');
    }}
  }}
}}

async function saveNow() {{
  if (!dirHandle) {{
    // Fallback: download via blob if no folder set
    const data = buildExportData();
    if (data.length === 0) {{ alert('No decisions to save.'); return; }}
    const json = JSON.stringify(data, null, 2);
    if ('showSaveFilePicker' in window) {{
      try {{
        const fh = await window.showSaveFilePicker({{
          suggestedName: FILENAME,
          types: [{{ description: 'JSON', accept: {{ 'application/json': ['.json'] }} }}]
        }});
        const w = await fh.createWritable();
        await w.write(json);
        await w.close();
        lastSaveHash = json;
        updateSaveStatus('saved', new Date().toLocaleTimeString());
      }} catch (e) {{
        if (e.name !== 'AbortError') updateSaveStatus('error', e.message);
      }}
    }} else {{
      // Legacy fallback
      const blob = new Blob([json], {{type: 'application/json'}});
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = FILENAME;
      a.click();
      URL.revokeObjectURL(a.href);
      updateSaveStatus('saved', '(downloaded)');
    }}
  }} else {{
    await writeToFile();
  }}
}}

// ─── Decision handlers ───
function setDecision(id, choice, code) {{
  if (!decisions[id]) decisions[id] = {{}};
  decisions[id].choice = choice;
  decisions[id].code = code;
  decisions[id].timestamp = new Date().toISOString();
  const row = document.querySelector(`tr[data-id="${{id}}"]`);
  if (row) {{
    row.dataset.status = 'reviewed';
    row.classList.add('reviewed');
  }}
  // Show/hide other input
  const radios = row.querySelectorAll('input[type=radio]');
  const idx = radios[0].name.split('_')[1];
  const otherDiv = document.getElementById('other_' + idx);
  if (choice === 'other') {{
    otherDiv.classList.add('show');
    otherDiv.querySelector('input').focus();
  }} else {{
    otherDiv.classList.remove('show');
  }}
  // Highlight selected label
  row.querySelectorAll('.radio-group label').forEach(lbl => lbl.classList.remove('selected'));
  const selectedRadio = row.querySelector(`input[value="${{choice}}"]`);
  if (selectedRadio) selectedRadio.closest('label').classList.add('selected');
  saveDecisions();
}}

function setOtherCode(id, code, idx) {{
  if (!decisions[id]) decisions[id] = {{}};
  decisions[id].code = code;
  decisions[id].timestamp = new Date().toISOString();
  const descEl = document.getElementById('otherDesc_' + idx);
  descEl.textContent = CODE_MAP[code] || '';
  saveDecisions();
}}

function setReason(id, reason) {{
  if (!decisions[id]) decisions[id] = {{}};
  decisions[id].reason = reason;
  decisions[id].timestamp = new Date().toISOString();
  saveDecisions();
}}

// ─── Progress ───
function updateProgress() {{
  const reviewed = Object.values(decisions).filter(d => d.choice).length;
  document.getElementById('reviewedCount').textContent = reviewed;
  document.getElementById('reviewedPct').textContent = Math.round(reviewed / TOTAL * 100) + '%';
}}

// ─── Restore saved state on load ───
function restoreState() {{
  document.querySelectorAll('#mismatchTable tbody tr').forEach(row => {{
    const id = row.dataset.id;
    const d = decisions[id];
    if (!d || !d.choice) return;
    row.dataset.status = 'reviewed';
    row.classList.add('reviewed');
    const radios = row.querySelectorAll('input[type=radio]');
    const idx = radios[0].name.split('_')[1];
    radios.forEach(r => {{
      if (r.value === d.choice) {{
        r.checked = true;
        r.closest('label').classList.add('selected');
      }}
    }});
    if (d.choice === 'other') {{
      const otherDiv = document.getElementById('other_' + idx);
      otherDiv.classList.add('show');
      const otherInput = otherDiv.querySelector('input');
      if (d.code) otherInput.value = d.code;
      document.getElementById('otherDesc_' + idx).textContent = CODE_MAP[d.code] || '';
    }}
    if (d.reason) {{
      const textarea = row.querySelector('.decision-cell textarea');
      if (textarea) textarea.value = d.reason;
    }}
  }});
  updateProgress();
}}

// ─── Filters ───
function applyFilters() {{
  const cat = document.getElementById('filterCat').value;
  const rule = document.getElementById('filterRule').value;
  const file = document.getElementById('filterFile').value;
  const status = document.getElementById('filterStatus').value;
  const search = document.getElementById('filterSearch').value.toLowerCase();
  const rows = document.querySelectorAll('#mismatchTable tbody tr');
  let visible = 0;
  rows.forEach(row => {{
    const ok = (!cat || row.dataset.cat === cat)
            && (!rule || row.dataset.rule === rule)
            && (!file || row.dataset.file === file)
            && (!status || row.dataset.status === status)
            && (!search || row.dataset.search.includes(search));
    if (ok) {{
      row.classList.remove('hidden');
      visible++;
      row.querySelector('td').textContent = visible;
    }} else {{
      row.classList.add('hidden');
    }}
  }});
  document.getElementById('visibleCount').textContent = visible + ' / ' + rows.length;
}}

let sortDir = {{}};
function sortTable(col) {{
  const tbody = document.querySelector('#mismatchTable tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  sortDir[col] = !(sortDir[col] || false);
  rows.sort((a, b) => {{
    const at = a.cells[col].textContent.trim().toLowerCase();
    const bt = b.cells[col].textContent.trim().toLowerCase();
    return sortDir[col] ? at.localeCompare(bt, undefined, {{numeric: true}})
                        : bt.localeCompare(at, undefined, {{numeric: true}});
  }});
  let n = 0;
  rows.forEach(row => {{
    tbody.appendChild(row);
    if (!row.classList.contains('hidden')) {{ n++; row.querySelector('td').textContent = n; }}
  }});
}}

// ─── Import / Clear ───
function importJSON(event) {{
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function(e) {{
    try {{
      const data = JSON.parse(e.target.result);
      if (Array.isArray(data)) {{
        data.forEach(item => {{
          decisions[item.id] = {{
            choice: item.decision,
            code: item.chosen_code,
            reason: item.reason,
            timestamp: item.timestamp
          }};
        }});
      }} else {{
        Object.assign(decisions, data);
      }}
      saveDecisions();
      restoreState();
      alert('Imported ' + (Array.isArray(data) ? data.length : Object.keys(data).length) + ' decisions');
    }} catch(err) {{
      alert('Error importing: ' + err.message);
    }}
  }};
  reader.readAsText(file);
  event.target.value = '';
}}

function clearAll() {{
  if (!confirm('Clear all decisions? This cannot be undone.')) return;
  decisions = {{}};
  localStorage.removeItem(STORAGE_KEY);
  document.querySelectorAll('#mismatchTable tbody tr').forEach(row => {{
    row.dataset.status = 'pending';
    row.classList.remove('reviewed');
    row.querySelectorAll('input[type=radio]').forEach(r => r.checked = false);
    row.querySelectorAll('.radio-group label').forEach(l => l.classList.remove('selected'));
    row.querySelectorAll('.other-input').forEach(d => d.classList.remove('show'));
    row.querySelectorAll('textarea').forEach(t => t.value = '');
  }});
  updateProgress();
}}

// ─── Init ───
restoreState();
applyFilters();
restoreDirHandle();
</script>
</body>
</html>
""")

    return "".join(parts)


def main():
    sys_map, code_list = load_system_mappings()
    mismatches = collect_mismatches(sys_map)
    html_content = generate_html(mismatches, sys_map, code_list)
    OUTPUT.write_text(html_content, encoding="utf-8")
    print(f"Written {len(mismatches)} mismatches to {OUTPUT}")
    print(f"File size: {OUTPUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
