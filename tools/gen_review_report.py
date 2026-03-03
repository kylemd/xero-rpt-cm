"""Generate a standalone HTML review report for mapping pipeline output.

Reads AugmentedChartOfAccounts.csv (pipeline output) and the original client
chart, produces a self-contained HTML page where users can:
- Review each account's assigned reporting code
- Override codes with reasons
- See expected account type inline (dynamically updates with code decisions)
- Red highlighting for Type/Code mismatches
- Export a Xero-ready ChartOfAccounts CSV
- Export review decisions as JSON for developer review

Run:  uv run python tools/gen_review_report.py <augmented.csv>
Output: ReviewReport.html alongside the augmented CSV
"""
import csv
import html as html_mod
import json
import pathlib
import sys

SYSTEM_MAPPINGS = pathlib.Path(__file__).parent.parent / "SystemFiles" / "SystemMappings.csv"
CHART_OF_ACCOUNTS = pathlib.Path(__file__).parent.parent / "ChartOfAccounts"

_TYPE_NORMALISE = {"other income": "Other Income"}


def load_chart_types(entity_type: str) -> dict:
    """Return {REPORTING_CODE.upper(): XeroType} from ChartOfAccounts/{entity_type}.csv."""
    chart_path = CHART_OF_ACCOUNTS / f"{entity_type}.csv"
    code_type: dict[str, str] = {}
    if chart_path.exists():
        with open(chart_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rc = row.get("Reporting Code", "").strip().upper()
                t = row.get("Type", "").strip()
                t = _TYPE_NORMALISE.get(t.lower(), t)
                if rc and t and rc not in code_type:
                    code_type[rc] = t
    return code_type


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
                "corrected_name": row.get("CorrectedName", "").strip(),
                "has_balance": row.get("HasBalance", "").strip(),
            })
    return accounts


def js_str(s: str) -> str:
    """Escape a string for use inside a JS single-quoted string in an HTML attribute.

    Must handle both JS special chars (\\, ', \\n) and HTML attribute chars (&, ", <, >).
    Order matters: escape backslash first, then single-quote for JS, then html-escape
    for the HTML attribute context.
    """
    s = s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
    return html_mod.escape(s, quote=True)


def generate_html(accounts, sys_map, code_list, chart_type_map=None):
    """Generate the full HTML review report as a self-contained page."""
    h = html_mod.escape

    # Pre-compute counts
    needs_review_count = sum(1 for a in accounts if a["needs_review"] == "Y")
    inactive_count = sum(1 for a in accounts if a.get("has_balance", "Y") != "Y")
    source_set = sorted(set(a["source"] for a in accounts if a["source"]))

    # Embed data as JSON for JS
    code_json = json.dumps(code_list, ensure_ascii=False)
    chart_type_json = json.dumps(chart_type_map or {}, ensure_ascii=False)
    sys_map_json = json.dumps(sys_map, ensure_ascii=False)
    accounts_json = json.dumps(accounts, ensure_ascii=False)

    parts = []

    # ── HEAD ──
    parts.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Mapping Review Report ({len(accounts)} accounts)</title>
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
.btn-export {{ background: #2563eb; color: white; }}
.btn-export:hover {{ background: #1d4ed8; }}
.btn-json {{ background: #7c3aed; color: white; }}
.btn-json:hover {{ background: #6d28d9; }}
.btn-clear {{ background: #ef4444; color: white; }}
.btn-clear:hover {{ background: #dc2626; }}
.count-label {{ font-size: .85em; color: #666; }}
.progress-label {{ font-size: .85em; font-weight: 600; }}

/* Table */
table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.1); font-size: .82em; }}
th {{ background: #1e293b; color: white; padding: 8px 10px; text-align: left; font-weight: 600; position: sticky; top: 0; z-index: 2; cursor: pointer; white-space: nowrap; font-size: .8em; }}
th:hover {{ background: #334155; }}
td {{ padding: 7px 10px; border-bottom: 1px solid #eee; vertical-align: top; }}
tr:hover td {{ background: #f0f9ff !important; }}
tr.reviewed td {{ opacity: .55; }}
tr.reviewed:hover td {{ opacity: 1; }}

/* NeedsReview highlight */
tr.review-highlight td {{ background: #fefce8; }}
tr.review-highlight:hover td {{ background: #fef9c3 !important; }}

/* Codes */
.code {{ font-family: 'SF Mono','Consolas',monospace; font-weight: 600; white-space: nowrap; font-size: .95em; }}
.code.assigned {{ color: #2563eb; }}
.code.original {{ color: #6b7280; }}
.tag {{ display: inline-block; padding: 2px 7px; border-radius: 10px; font-size: .72em; font-weight: 600; }}
.tag.source {{ background: #dbeafe; color: #1e40af; }}
.tag.review-y {{ background: #fef3c7; color: #92400e; }}
.tag.review-n {{ background: #dcfce7; color: #166534; }}
.detail-row {{ font-size: .76em; color: #666; }}
.hidden {{ display: none; }}

/* Decision column */
.decision-cell {{ min-width: 260px; }}
.decision-cell .radio-group {{ display: flex; flex-direction: column; gap: 4px; margin-bottom: 6px; }}
.decision-cell .radio-group label {{ display: flex; align-items: center; gap: 5px; font-size: .82em; cursor: pointer; padding: 3px 6px; border-radius: 4px; }}
.decision-cell .radio-group label:hover {{ background: #f1f5f9; }}
.decision-cell .radio-group label.selected {{ background: #dbeafe; font-weight: 600; }}
.decision-cell .radio-group input[type=radio] {{ margin: 0; }}
.decision-cell .override-input {{ display: none; margin: 4px 0; }}
.decision-cell .override-input.show {{ display: flex; gap: 4px; align-items: center; flex-wrap: wrap; }}
.decision-cell .override-input input {{ width: 140px; padding: 3px 6px; border: 1px solid #cbd5e1; border-radius: 4px; font-family: monospace; font-size: .85em; }}
.decision-cell .override-input .code-desc {{ font-size: .72em; color: #666; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.decision-cell textarea {{ width: 100%; min-height: 36px; padding: 4px 6px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: .8em; font-family: inherit; resize: vertical; display: none; }}
.decision-cell textarea.show {{ display: block; }}
.decision-cell textarea::placeholder {{ color: #aaa; }}
.decision-cell .reason-label {{ font-size: .72em; color: #888; margin-bottom: 2px; display: none; }}
.decision-cell .reason-label.show {{ display: block; }}

/* Expected Type column */
.expected-type-cell {{ min-width: 150px; }}
.expected-type-cell select {{ padding: 4px 6px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: .88em; width: 100%; }}
.expected-type-cell .type-match {{ color: #16a34a; font-weight: 600; font-size: .88em; }}
.expected-type-cell .type-mismatch {{ color: #dc2626; font-weight: 700; font-size: .88em; }}
td.cell-mismatch {{ background: #fee2e2 !important; }}
tr:hover td.cell-mismatch {{ background: #fecaca !important; }}

/* Export */

/* Import warning banner */
.import-warning {{
  display: flex; align-items: flex-start; gap: 12px;
  background: #fffbeb; border: 1px solid #f59e0b; border-left: 4px solid #f59e0b;
  border-radius: 6px; padding: 12px 16px; margin: 12px 0 16px;
  color: #92400e; font-size: .92em; line-height: 1.5;
}}
.import-warning .warn-icon {{ font-size: 1.2em; flex-shrink: 0; margin-top: 1px; }}
.import-warning strong {{ display: block; margin-bottom: 2px; color: #78350f; }}
</style>
</head>
<body>
""")

    # ── HEADER ──
    parts.append('<h1>Mapping Review Report</h1>\n')
    parts.append(
        f'<p class="subtitle">{len(accounts)} accounts &bull; '
        f'{needs_review_count} flagged for review &bull; '
        f'Decisions save to browser automatically</p>\n'
    )

    # ── IMPORT WARNING ──
    parts.append(
        '<div class="import-warning">'
        '<span class="warn-icon">&#9888;</span>'
        '<div><strong>Already imported this chart into Xero?</strong>'
        'Re-export the Chart of Accounts from Xero before using this report. '
        'Xero may have archived accounts during import, and the exported file '
        'reflects the current live state. Working from an older export may produce '
        'incorrect mappings for accounts that have been archived or modified.</div>'
        '</div>\n'
    )

    # ── SUMMARY CARDS ──
    parts.append('<div class="summary">\n')
    parts.append(f'  <div class="card"><h3>Total Accounts</h3><div class="num blue">{len(accounts)}</div></div>\n')
    parts.append(f'  <div class="card"><h3>Needs Review</h3><div class="num amber">{needs_review_count}</div></div>\n')
    parts.append(f'  <div class="card"><h3>Overridden</h3><div class="num red" id="overriddenCount">0</div></div>\n')
    parts.append(f'  <div class="card"><h3>Accepted</h3><div class="num green" id="acceptedCount">0</div></div>\n')
    parts.append(f'  <div class="card"><h3>Pending</h3><div class="num" id="pendingCount">{len(accounts)}</div>'
                 f'<div class="detail" id="progressPct">0%</div></div>\n')
    parts.append(f'  <div class="card"><h3>Inactive</h3><div class="num" style="color:#9ca3af">{inactive_count}</div>'
                 f'<div class="detail">No balance</div></div>\n')
    parts.append('</div>\n')

    # ── TOOLBAR ──
    parts.append('<div class="toolbar">\n')
    parts.append('  <label>Review:</label>\n  <select id="filterReview" onchange="applyFilters()">\n')
    parts.append('    <option value="">All</option>\n    <option value="Y">Yes</option>\n    <option value="N">No</option>\n  </select>\n')

    parts.append('  <label>Source:</label>\n  <select id="filterSource" onchange="applyFilters()">\n    <option value="">All</option>\n')
    for src in source_set:
        src_count = sum(1 for a in accounts if a["source"] == src)
        parts.append(f'    <option value="{h(src)}">{h(src)} ({src_count})</option>\n')
    parts.append('  </select>\n')

    parts.append('  <label>Activity:</label>\n  <select id="filterActivity" onchange="applyFilters()">\n')
    parts.append('    <option value="active" selected>Active</option>\n    <option value="inactive">Inactive</option>\n    <option value="">All</option>\n  </select>\n')

    parts.append('  <label>Status:</label>\n  <select id="filterStatus" onchange="applyFilters()">\n')
    parts.append('    <option value="">All</option>\n    <option value="pending">Pending</option>\n    <option value="accepted">Accepted</option>\n    <option value="overridden">Overridden</option>\n    <option value="override-no-reason">Override - no reason</option>\n  </select>\n')

    parts.append('  <label>Search:</label>\n')
    parts.append('  <input type="text" id="filterSearch" placeholder="Name, code, type, source..." oninput="applyFilters()">\n')
    parts.append('  <span class="count-label" id="visibleCount"></span>\n')
    parts.append('  <span class="spacer"></span>\n')
    parts.append('  <button class="btn-export" onclick="downloadCSV()">Export CSV</button>\n')
    parts.append('  <button class="btn-json" onclick="downloadJSON()">Export JSON</button>\n')
    parts.append('  <button class="btn-clear" onclick="clearAll()">Clear All</button>\n')
    parts.append('</div>\n')

    # ── DATALIST for code autocomplete ──
    parts.append('<datalist id="codeSuggestions">\n')
    for code, desc in code_list:
        parts.append(f'  <option value="{h(code)}">{h(desc)}</option>\n')
    parts.append('</datalist>\n')

    # ── TABLE ──
    parts.append("""<table id="reviewTable">
<thead>
<tr>
  <th onclick="sortTable(0)" style="width:35px">#</th>
  <th onclick="sortTable(1)">Account Code</th>
  <th onclick="sortTable(2)">Account Name</th>
  <th onclick="sortTable(3)">Type</th>
  <th onclick="sortTable(4)">Original Code</th>
  <th onclick="sortTable(5)">Assigned Code</th>
  <th onclick="sortTable(6)">Source</th>
  <th style="min-width:270px">Your Decision</th>
  <th style="min-width:150px">Expected Type</th>
</tr>
</thead>
<tbody>
""")

    for i, a in enumerate(accounts):
        row_id = f"{a['code']}:{a['name'][:40]}"
        esc_id = h(row_id)
        js_id = js_str(row_id)
        review_class = "review-highlight" if a["needs_review"] == "Y" else ""
        activity = "active" if a.get("has_balance", "Y") == "Y" else "inactive"

        assigned_desc = sys_map.get(a["predicted_code"], "")
        original_desc = sys_map.get(a["original_code"], "")

        search_text = " ".join([
            a["code"], a["name"], a["type"], a["source"],
            a["predicted_code"], a["original_code"], a["needs_review"],
            a["corrected_name"],
        ]).lower()

        parts.append(
            f'<tr class="{review_class}" '
            f'data-id="{esc_id}" '
            f'data-review="{h(a["needs_review"])}" '
            f'data-source="{h(a["source"])}" '
            f'data-search="{h(search_text)}" '
            f'data-status="pending" '
            f'data-predicted="{h(a["predicted_code"])}" '
            f'data-original="{h(a["original_code"])}" '
            f'data-type="{h(a["type"])}" '
            f'data-activity="{activity}">\n'
        )
        parts.append(f'  <td>{i + 1}</td>\n')
        parts.append(f'  <td><span class="code">{h(a["code"])}</span></td>\n')
        if a["corrected_name"]:
            parts.append(f'  <td><strong>{h(a["corrected_name"])}</strong>'
                         f'<br><span class="detail-row" style="font-style:italic">Originally: {h(a["name"])}</span></td>\n')
        else:
            parts.append(f'  <td><strong>{h(a["name"])}</strong></td>\n')
        parts.append(f'  <td>{h(a["type"])}</td>\n')

        # Original code
        oc = a["original_code"]
        parts.append(f'  <td><span class="code original">{h(oc) if oc else "—"}</span>'
                     f'{("<br><span class=detail-row>" + h(original_desc[:50]) + "</span>") if original_desc else ""}</td>\n')

        # Assigned code
        parts.append(f'  <td><span class="code assigned">{h(a["predicted_code"])}</span>'
                     f'{("<br><span class=detail-row>" + h(assigned_desc[:50]) + "</span>") if assigned_desc else ""}</td>\n')

        # Source
        parts.append(f'  <td><span class="tag source">{h(a["source"])}</span></td>\n')

        # Decision cell
        parts.append(f'  <td class="decision-cell" data-row-id="{esc_id}">\n')
        parts.append(f'    <div class="radio-group">\n')
        parts.append(f'      <label><input type="radio" name="d_{i}" value="accept" '
                     f'onchange="setDecision(\'{js_id}\',\'accept\')"> '
                     f'Accept <span class="code assigned">{h(a["predicted_code"])}</span></label>\n')
        parts.append(f'      <label><input type="radio" name="d_{i}" value="override" '
                     f'onchange="setDecision(\'{js_id}\',\'override\')"> '
                     f'Override...</label>\n')
        parts.append(f'    </div>\n')
        parts.append(f'    <div class="override-input" id="override_{i}">\n')
        parts.append(f'      <input type="text" list="codeSuggestions" placeholder="e.g. EXP.OCC" '
                     f'oninput="setOverrideCode(\'{js_id}\',this.value,{i})">\n')
        parts.append(f'      <span class="code-desc" id="overrideDesc_{i}"></span>\n')
        parts.append(f'    </div>\n')
        parts.append(f'    <div class="reason-label" id="reasonLabel_{i}">Reason:</div>\n')
        parts.append(f'    <textarea id="reason_{i}" placeholder="Why override this code?" '
                     f'oninput="setReason(\'{js_id}\',this.value)"></textarea>\n')
        parts.append(f'  </td>\n')
        parts.append(f'  <td class="expected-type-cell" id="expectedType_{i}"></td>\n')
        parts.append('</tr>\n')

    parts.append('</tbody>\n</table>\n')

    # ── JAVASCRIPT ──
    parts.append(f"""
<script>
// Global error handler
window.onerror = function(msg, url, line, col, err) {{
  const d = document.createElement('div');
  d.style.cssText = 'background:#fee2e2;color:#991b1b;padding:12px 16px;margin:8px 0;border-radius:8px;font-family:monospace;font-size:.85em;white-space:pre-wrap';
  d.textContent = 'JS Error: ' + msg + '\\nLine ' + line + ':' + col;
  document.body.prepend(d);
}};

const STORAGE_KEY = 'review_decisions_v1';
const TYPE_STORAGE_KEY = 'review_type_decisions_v2';
const CODES = {code_json};
const CODE_MAP = Object.fromEntries(CODES);
const SYS_MAP = {sys_map_json};
const ACCOUNTS = {accounts_json};
const TOTAL = {len(accounts)};

// ─── State ───
let decisions = loadDecisions();
let typeDecisions = loadTypeDecisions();

function loadDecisions() {{
  try {{ return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {{}}; }}
  catch {{ return {{}}; }}
}}

function saveDecisions() {{
  localStorage.setItem(STORAGE_KEY, JSON.stringify(decisions));
  updateProgress();
}}

function loadTypeDecisions() {{
  try {{ return JSON.parse(localStorage.getItem(TYPE_STORAGE_KEY)) || {{}}; }}
  catch {{ return {{}}; }}
}}

function saveTypeDecisions() {{
  localStorage.setItem(TYPE_STORAGE_KEY, JSON.stringify(typeDecisions));
}}

// ─── Decision handlers ───
function setDecision(id, choice) {{
  if (!decisions[id]) decisions[id] = {{}};
  decisions[id].choice = choice;
  decisions[id].timestamp = new Date().toISOString();
  const row = document.querySelector('tr[data-id="' + CSS.escape(id) + '"]');
  if (!row) return;
  row.dataset.status = choice === 'accept' ? 'accepted' : 'overridden';
  row.classList.add('reviewed');

  // Show/hide override input and reason
  const radios = row.querySelectorAll('input[type=radio]');
  const idx = radios[0].name.split('_')[1];
  const overrideDiv = document.getElementById('override_' + idx);
  const reasonLabel = document.getElementById('reasonLabel_' + idx);
  const reasonArea = document.getElementById('reason_' + idx);

  if (choice === 'override') {{
    overrideDiv.classList.add('show');
    reasonLabel.classList.add('show');
    reasonArea.classList.add('show');
    overrideDiv.querySelector('input').focus();
  }} else {{
    overrideDiv.classList.remove('show');
    reasonLabel.classList.remove('show');
    reasonArea.classList.remove('show');
  }}

  // Highlight selected label
  row.querySelectorAll('.radio-group label').forEach(lbl => lbl.classList.remove('selected'));
  const selectedRadio = row.querySelector('input[value="' + choice + '"]');
  if (selectedRadio) selectedRadio.closest('label').classList.add('selected');
  saveDecisions();
  updateExpectedType(parseInt(idx));
}}

function setOverrideCode(id, code, idx) {{
  if (!decisions[id]) decisions[id] = {{}};
  decisions[id].code = code;
  decisions[id].timestamp = new Date().toISOString();
  const descEl = document.getElementById('overrideDesc_' + idx);
  descEl.textContent = CODE_MAP[code] || '';
  saveDecisions();
  updateExpectedType(idx);
}}

function setReason(id, reason) {{
  if (!decisions[id]) decisions[id] = {{}};
  decisions[id].reason = reason;
  decisions[id].timestamp = new Date().toISOString();
  saveDecisions();
}}

// ─── Progress ───
function updateProgress() {{
  const currentIds = new Set();
  document.querySelectorAll('#reviewTable tbody tr').forEach(r => currentIds.add(r.dataset.id));
  let accepted = 0, overridden = 0;
  Object.entries(decisions).forEach(([id, d]) => {{
    if (!d.choice || !currentIds.has(id)) return;
    if (d.choice === 'accept') accepted++;
    else if (d.choice === 'override') overridden++;
  }});
  const total = currentIds.size;
  const pending = total - accepted - overridden;
  const reviewed = accepted + overridden;
  document.getElementById('acceptedCount').textContent = accepted;
  document.getElementById('overriddenCount').textContent = overridden;
  document.getElementById('pendingCount').textContent = pending;
  document.getElementById('progressPct').textContent = Math.round(reviewed / total * 100) + '%';
}}

// ─── Restore saved state ───
function restoreState() {{
  document.querySelectorAll('#reviewTable tbody tr').forEach(row => {{
    const id = row.dataset.id;
    const d = decisions[id];
    if (!d || !d.choice) return;
    row.dataset.status = d.choice === 'accept' ? 'accepted' : 'overridden';
    row.classList.add('reviewed');
    const radios = row.querySelectorAll('input[type=radio]');
    const idx = radios[0].name.split('_')[1];
    radios.forEach(r => {{
      if (r.value === d.choice) {{
        r.checked = true;
        r.closest('label').classList.add('selected');
      }}
    }});
    if (d.choice === 'override') {{
      const overrideDiv = document.getElementById('override_' + idx);
      overrideDiv.classList.add('show');
      const overrideInput = overrideDiv.querySelector('input');
      if (d.code) overrideInput.value = d.code;
      document.getElementById('overrideDesc_' + idx).textContent = CODE_MAP[d.code] || '';
      document.getElementById('reasonLabel_' + idx).classList.add('show');
      const reasonArea = document.getElementById('reason_' + idx);
      reasonArea.classList.add('show');
      if (d.reason) reasonArea.value = d.reason;
    }}
  }});
  updateProgress();
}}

// ─── Filters ───
function applyFilters() {{
  const review = document.getElementById('filterReview').value;
  const source = document.getElementById('filterSource').value;
  const status = document.getElementById('filterStatus').value;
  const activity = document.getElementById('filterActivity').value;
  const search = document.getElementById('filterSearch').value.toLowerCase();
  const rows = document.querySelectorAll('#reviewTable tbody tr');
  let visible = 0;
  rows.forEach(row => {{
    let statusMatch = true;
    if (status === 'override-no-reason') {{
      const d = decisions[row.dataset.id];
      statusMatch = d && d.choice === 'override' && !d.reason;
    }} else if (status) {{
      statusMatch = row.dataset.status === status;
    }}
    const ok = (!review || row.dataset.review === review)
            && (!source || row.dataset.source === source)
            && statusMatch
            && (!activity || row.dataset.activity === activity || (activity === 'active' && row.dataset.review === 'Y'))
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
  const tbody = document.querySelector('#reviewTable tbody');
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

// ─── Clear ───
function clearAll() {{
  if (!confirm('Clear all decisions? This cannot be undone.')) return;
  decisions = {{}};
  typeDecisions = {{}};
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(TYPE_STORAGE_KEY);
  document.querySelectorAll('#reviewTable tbody tr').forEach(row => {{
    row.dataset.status = 'pending';
    row.classList.remove('reviewed');
    row.querySelectorAll('input[type=radio]').forEach(r => r.checked = false);
    row.querySelectorAll('.radio-group label').forEach(l => l.classList.remove('selected'));
    row.querySelectorAll('.override-input').forEach(d => d.classList.remove('show'));
    row.querySelectorAll('.reason-label').forEach(l => l.classList.remove('show'));
    row.querySelectorAll('textarea').forEach(t => {{ t.value = ''; t.classList.remove('show'); }});
  }});
  updateProgress();
  updateAllExpectedTypes();
}}

// ─── Phase 2: Type Review ───
const HEAD_FROM_TYPE = {{
  'Current Asset': 'ASS', 'Fixed Asset': 'ASS', 'Inventory': 'ASS',
  'Non-current Asset': 'ASS', 'Prepayment': 'ASS',
  'Equity': 'EQU',
  'Depreciation': 'EXP', 'Direct Costs': 'EXP', 'Expense': 'EXP', 'Overhead': 'EXP',
  'Current Liability': 'LIA', 'Liability': 'LIA', 'Non-current Liability': 'LIA',
  'Other Income': 'REV', 'Revenue': 'REV', 'Sales': 'REV'
}};

// Prefix-level constraints: types that require a specific code prefix
const REQUIRED_PREFIX_BY_TYPE = {{
  'Direct Costs': 'EXP.COS',
  'Depreciation': 'EXP.DEP',
  'Fixed Asset': 'ASS.NCA.FIX',
  'Inventory': 'ASS.CUR.INY',
  'Prepayment': 'ASS.CUR.REC.PRE',
  'Revenue': 'REV.TRA',
  'Sales': 'REV.TRA',
  'Current Asset': 'ASS.CUR',
  'Non-current Asset': 'ASS.NCA',
  'Current Liability': 'LIA.CUR',
  'Non-current Liability': 'LIA.NCL',
}};

const ALLOWED_TYPES_BY_HEAD = {{
  'ASS': ['Current Asset', 'Fixed Asset', 'Inventory', 'Non-current Asset', 'Prepayment'],
  'EQU': ['Equity'],
  'EXP': ['Depreciation', 'Direct Costs', 'Expense', 'Overhead'],
  'LIA': ['Current Liability', 'Liability', 'Non-current Liability'],
  'REV': ['Other Income', 'Revenue', 'Sales']
}};

const SYSTEM_TYPES = new Set([
  'Bank', 'Accounts Receivable', 'Accounts Payable', 'GST',
  'Historical', 'Rounding', 'Tracking', 'Unpaid Expense Claims', 'Retained Earnings'
]);

// Authoritative reporting-code → Xero type lookup from the entity's default chart.
// Keys are upper-cased reporting codes; values are Xero type strings.
const CODE_TYPE_MAP = {chart_type_json};

function headFromCode(code) {{
  return code ? code.split('.')[0] : '';
}}

function predictTypeFromCode(code, currentType) {{
  if (!code) return currentType;
  const c = code.toUpperCase();
  // Check authoritative chart lookup first
  if (CODE_TYPE_MAP[c]) return CODE_TYPE_MAP[c];
  if (c.startsWith('ASS.CUR.INY'))       return 'Inventory';
  if (c.startsWith('ASS.NCA.FIX'))       return 'Fixed Asset';
  if (c.startsWith('ASS.CUR.REC.PRE'))   return 'Prepayment';
  if (c.startsWith('ASS.NCA'))            return 'Non-current Asset';
  if (c.startsWith('ASS'))               return 'Current Asset';
  if (c.startsWith('EXP.DEP'))            return 'Depreciation';
  if (c.startsWith('EXP.COS'))            return 'Direct Costs';
  if (c.startsWith('EXP')) {{
    if (currentType === 'Overhead')       return 'Overhead';
    return 'Expense';
  }}
  if (c.startsWith('LIA.NCL'))            return 'Non-current Liability';
  if (c.startsWith('LIA'))               return 'Current Liability';
  if (c.startsWith('REV.OTH'))            return 'Other Income';
  if (c.startsWith('REV.INV'))            return 'Other Income';
  if (c.startsWith('REV')) {{
    if (currentType === 'Sales')          return 'Sales';
    return 'Revenue';
  }}
  if (c.startsWith('EQU'))               return 'Equity';
  return currentType;
}}

function getFinalCode(acct) {{
  const id = acct.code + ':' + (acct.name || '').substring(0, 40);
  const d = decisions[id];
  if (d && d.choice) {{
    if (d.choice === 'override' && d.code) return d.code;
    return acct.predicted_code;
  }}
  return acct.predicted_code;
}}

function escHtml(s) {{
  const div = document.createElement('div');
  div.textContent = s || '';
  return div.innerHTML;
}}

function escJs(s) {{
  return (s || '').replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'");
}}

// ─── Inline Expected Type ───
function updateExpectedType(i) {{
  const acct = ACCOUNTS[i];
  if (!acct) return;
  const cell = document.getElementById('expectedType_' + i);
  if (!cell) return;

  const currentType = acct.type;
  const acctId = acct.code + ':' + (acct.name || '').substring(0, 40);

  // System types: no type review needed
  if (SYSTEM_TYPES.has(currentType)) {{
    cell.innerHTML = '<span class="type-match">' + escHtml(currentType) + '</span>';
    cell.classList.remove('cell-mismatch');
    return;
  }}

  const finalCode = getFinalCode(acct);
  const codeHead = headFromCode(finalCode);
  const typeHead = HEAD_FROM_TYPE[currentType];
  const headMismatch = typeHead && codeHead && codeHead !== typeHead;

  // Prefix-level mismatch: e.g. Direct Costs requires EXP.COS prefix
  const requiredPrefix = REQUIRED_PREFIX_BY_TYPE[currentType];
  const prefixMismatch = !headMismatch && requiredPrefix && finalCode
    && !finalCode.toUpperCase().startsWith(requiredPrefix);
  const hasMismatch = headMismatch || prefixMismatch;

  // Find the Type cell (column 3) in the row
  const row = cell.closest('tr');
  const typeCell = row ? row.cells[3] : null;

  if (!hasMismatch) {{
    cell.innerHTML = '<span class="type-match">' + escHtml(currentType) + '</span>';
    cell.classList.remove('cell-mismatch');
    // Reset Type cell to original value
    if (typeCell) {{
      typeCell.textContent = currentType;
      typeCell.classList.remove('cell-mismatch');
    }}
    // Clear stale type decision if mismatch no longer exists
    if (typeDecisions[acctId]) {{
      delete typeDecisions[acctId];
      saveTypeDecisions();
    }}
    return;
  }}

  // Mismatch: show dropdown with allowed types
  const predicted = predictTypeFromCode(finalCode, currentType);
  const allowed = ALLOWED_TYPES_BY_HEAD[codeHead] || [];
  const savedTd = typeDecisions[acctId];
  const selectedType = (savedTd && savedTd.newType) ? savedTd.newType : predicted;

  let html = '<select onchange="setInlineTypeDecision(\\'' + escJs(acctId) + '\\',this.value,' + i + ')">';
  allowed.forEach(t => {{
    const sel = (t === selectedType) ? ' selected' : '';
    const marker = (t === predicted) ? ' \\u2190 predicted' : '';
    html += '<option value="' + escHtml(t) + '"' + sel + '>' + escHtml(t) + marker + '</option>';
  }});
  html += '</select>';
  cell.innerHTML = html;
  cell.classList.add('cell-mismatch');

  // Update the Type column (col 3) to show suggested override
  if (typeCell && predicted !== currentType) {{
    typeCell.innerHTML = '<span style="text-decoration:line-through;color:#999">' + escHtml(currentType)
      + '</span><br><span style="color:#dc2626;font-weight:700">' + escHtml(selectedType) + '</span>';
    typeCell.classList.add('cell-mismatch');
  }}

}}

function updateAllExpectedTypes() {{
  for (let i = 0; i < ACCOUNTS.length; i++) {{
    try {{ updateExpectedType(i); }} catch (e) {{ console.warn('updateExpectedType(' + i + '):', e); }}
  }}
}}

function setInlineTypeDecision(acctId, newType, idx) {{
  if (!newType) {{
    delete typeDecisions[acctId];
  }} else {{
    typeDecisions[acctId] = {{ newType: newType, timestamp: new Date().toISOString() }};
  }}
  saveTypeDecisions();
  // Update the Type column to reflect the new selection
  if (idx != null) {{
    const acct = ACCOUNTS[idx];
    if (acct) {{
      const row = document.querySelector('tr[data-id="' + CSS.escape(acctId) + '"]');
      if (row && row.cells[3]) {{
        const currentType = acct.type;
        if (newType !== currentType) {{
          row.cells[3].innerHTML = '<span style="text-decoration:line-through;color:#999">' + escHtml(currentType)
            + '</span><br><span style="color:#dc2626;font-weight:700">' + escHtml(newType) + '</span>';
          row.cells[3].classList.add('cell-mismatch');
        }} else {{
          row.cells[3].textContent = currentType;
          row.cells[3].classList.remove('cell-mismatch');
        }}
      }}
    }}
  }}
}}

// ─── Static mismatch: Type vs Original Code ───
function checkStaticMismatches() {{
  document.querySelectorAll('#reviewTable tbody tr').forEach(row => {{
    const type = row.dataset.type;
    const originalCode = row.dataset.original || '';
    if (!type || !originalCode || SYSTEM_TYPES.has(type)) return;

    const typeHead = HEAD_FROM_TYPE[type];
    const codeHead = headFromCode(originalCode);
    if (typeHead && codeHead && typeHead !== codeHead) {{
      // Type cell (col 3) and Original Code cell (col 4)
      row.cells[3].classList.add('cell-mismatch');
      row.cells[4].classList.add('cell-mismatch');
    }}
  }});
}}

// ─── Phase 3: Export ───
function csvEscape(val) {{
  if (val == null) val = '';
  val = String(val);
  if (val.includes(',') || val.includes('"') || val.includes('\\n') || val.includes('\\r')) {{
    return '"' + val.replace(/"/g, '""') + '"';
  }}
  return val;
}}

function downloadCSV() {{
  const headers = ['*Code', 'Report Code', '*Name', 'Reporting Name', '*Type', '*Tax Code', 'Description', 'Dashboard', 'Expense Claims', 'Enable Payments'];
  const rows = [headers.join(',')];

  ACCOUNTS.forEach(acct => {{
    const finalCode = getFinalCode(acct);
    // Preserve original Reporting Name only; clear it if identical to the account name (redundant)
    const reportingName = (acct.reporting_name && acct.reporting_name !== acct.name) ? acct.reporting_name : '';
    const acctId = acct.code + ':' + (acct.name || '').substring(0, 40);
    const td = typeDecisions[acctId];
    let finalType = (td && td.newType) ? td.newType : predictTypeFromCode(finalCode, acct.type);
    // System-typed accounts (Bank, Accounts Receivable, Accounts Payable, GST, Historical,
    // Rounding, Tracking, Unpaid Expense Claims, Retained Earnings) are locked — Xero will
    // error on import if their type is changed. Always preserve the original type.
    if (SYSTEM_TYPES.has(acct.type)) {
      finalType = acct.type;
    } else if (SYSTEM_TYPES.has(finalType)) {
      // A non-system account must never be exported with a system type.
      // GST specifically should become Current Liability; others revert to original.
      finalType = (finalType === 'GST') ? 'Current Liability' : acct.type;
    }

    rows.push([
      csvEscape(acct.code),
      csvEscape(finalCode),
      csvEscape(acct.name),
      csvEscape(reportingName),
      csvEscape(finalType),
      csvEscape(acct.tax_code),
      csvEscape(acct.description),
      csvEscape(acct.dashboard),
      csvEscape(acct.expense_claims),
      csvEscape(acct.enable_payments)
    ].join(','));
  }});

  const csvContent = rows.join('\\r\\n');
  const blob = new Blob([csvContent], {{ type: 'text/csv;charset=utf-8;' }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'ChartOfAccounts_Xero.csv';
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {{
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }}, 500);
}}

function downloadJSON() {{
  const exported = [];
  ACCOUNTS.forEach(acct => {{
    const acctId = acct.code + ':' + (acct.name || '').substring(0, 40);
    const d = decisions[acctId];
    const td = typeDecisions[acctId];
    const hasCodeChange = d && d.choice === 'override' && d.code;
    const hasTypeChange = td && td.newType;
    if (!hasCodeChange && !hasTypeChange) return;

    const finalCode = getFinalCode(acct);
    exported.push({{
      account_code: acct.code,
      account_name: acct.name,
      original_code: acct.original_code,
      assigned_code: acct.predicted_code,
      final_code: finalCode,
      reason: (d && d.reason) ? d.reason : '',
      type_change: hasTypeChange ? td.newType : null,
      timestamp: (d && d.timestamp) ? d.timestamp : ((td && td.timestamp) ? td.timestamp : new Date().toISOString())
    }});
  }});

  if (exported.length === 0) {{
    alert('No changes to export. Override codes or correct types first.');
    return;
  }}

  const json = JSON.stringify(exported, null, 2);
  const blob = new Blob([json], {{ type: 'application/json' }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'review_decisions.json';
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {{
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }}, 500);
}}

// ─── Auto-confirm matches ───
function autoConfirmMatches() {{
  let count = 0;
  document.querySelectorAll('#reviewTable tbody tr').forEach(row => {{
    const id = row.dataset.id;
    const predicted = row.dataset.predicted;
    const original = row.dataset.original;
    const type = row.dataset.type;
    // Skip if no codes, codes differ, or user already made a decision
    if (!predicted || !original || predicted !== original) return;
    if (decisions[id] && decisions[id].choice) return;

    // Skip if the account type is incompatible with the predicted code
    if (type && !SYSTEM_TYPES.has(type)) {{
      const typeHead = HEAD_FROM_TYPE[type];
      const codeHead = headFromCode(predicted);
      // Head-level mismatch (e.g. Revenue type with EXP code)
      if (typeHead && codeHead && typeHead !== codeHead) return;
      // Prefix-level mismatch (e.g. Direct Costs requires EXP.COS prefix)
      const requiredPrefix = REQUIRED_PREFIX_BY_TYPE[type];
      if (requiredPrefix && !predicted.toUpperCase().startsWith(requiredPrefix)) return;
    }}

    // Batch-set the accept decision (without per-row save)
    decisions[id] = {{ choice: 'accept', timestamp: new Date().toISOString(), auto: true }};
    row.dataset.status = 'accepted';
    row.classList.add('reviewed');
    const radios = row.querySelectorAll('input[type=radio]');
    radios.forEach(r => {{
      if (r.value === 'accept') {{
        r.checked = true;
        r.closest('label').classList.add('selected');
      }}
    }});
    count++;
  }});
  if (count > 0) {{
    saveDecisions();
    console.log('Auto-confirmed ' + count + ' accounts where predicted === original and type compatible');
  }}
}}

// ─── Init ───
try {{
  restoreState();
  autoConfirmMatches();
  checkStaticMismatches();
  updateAllExpectedTypes();
  applyFilters();
}} catch (e) {{
  console.error('Init error:', e);
  const d = document.createElement('div');
  d.style.cssText = 'background:#fee2e2;color:#991b1b;padding:12px 16px;margin:8px 0;border-radius:8px;font-family:monospace;font-size:.85em';
  d.textContent = 'Init error: ' + e.message;
  document.body.prepend(d);
}}
</script>
</body>
</html>
""")

    return "".join(parts)


_VALID_ENTITY_TYPES = ["Company", "Trust", "Partnership", "SoleTrader", "XeroHandi"]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate HTML mapping review report.")
    parser.add_argument("augmented_csv", help="Path to AugmentedChartOfAccounts.csv")
    parser.add_argument(
        "--type", dest="entity_type", default="Company",
        choices=_VALID_ENTITY_TYPES,
        help="Entity type to use for type lookups (default: Company)",
    )
    args = parser.parse_args()

    augmented_path = pathlib.Path(args.augmented_csv)

    if not augmented_path.exists():
        print(f"ERROR: {augmented_path} not found")
        sys.exit(1)

    sys_map, code_list = load_system_mappings()
    accounts = load_augmented(augmented_path)
    chart_type_map = load_chart_types(args.entity_type)

    html_content = generate_html(accounts, sys_map, code_list, chart_type_map)
    print(f"  Entity type: {args.entity_type} ({len(chart_type_map)} code-type mappings loaded)")

    output_path = augmented_path.with_name("ReviewReport.html")
    output_path.write_text(html_content, encoding="utf-8")

    print(f"Written {len(accounts)} accounts to {output_path}")
    print(f"  File size: {output_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
