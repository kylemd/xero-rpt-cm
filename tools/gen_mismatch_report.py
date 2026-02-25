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

def js_str(s: str) -> str:
    """Escape a string for use inside a JS single-quoted string in an HTML attribute.

    Must handle both JS special chars (\\, ', \\n) and HTML attribute chars (&, ", <, >).
    Order matters: escape backslash first, then single-quote for JS, then html-escape
    for the HTML attribute context.
    """
    s = s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
    return html_mod.escape(s, quote=True)


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


def collect_mismatches(sys_map, file_filter=None):
    mismatches = []
    rule_index = {r.name: r for r in ALL_RULES}

    for csv_file in sorted(FIXTURES_DIR.glob("*_validated_final.csv")):
        if file_filter and file_filter not in csv_file.name:
            continue
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

                    # Original chart code (InputReportingCode where available)
                    input_rc = row.get("InputReportingCode", "").strip()

                    # Balance (DR/CR format)
                    raw_balance = row.get("Balance", "").strip()
                    if raw_balance:
                        try:
                            bal_num = float(raw_balance.replace(",", ""))
                            if bal_num >= 0:
                                balance_fmt = f"${abs(bal_num):,.2f} DR"
                            else:
                                balance_fmt = f"${abs(bal_num):,.2f} CR"
                        except ValueError:
                            balance_fmt = raw_balance  # Show raw if not numeric
                    else:
                        balance_fmt = ""

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
                        "input_reporting_code": input_rc,
                        "balance": balance_fmt,
                        "category": category,
                        "category_detail": category_detail,
                    })

    mismatches.sort(key=lambda m: (m["category"], m["rule_name"], m["name"]))
    return mismatches


def collect_all_accounts(file_filter=None):
    """Load every row from every validated fixture CSV.

    Returns a list of dicts used by Phase 2 (type review) and Phase 3 (CSV export).
    """
    accounts = []
    for csv_file in sorted(FIXTURES_DIR.glob("*_validated_final.csv")):
        if file_filter and file_filter not in csv_file.name:
            continue
        with open(csv_file, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                validated = row.get("ValidatedReportingCode", "").strip()
                if not validated:
                    continue
                accounts.append({
                    "code": row.get("Code", "").strip(),
                    "name": row.get("Name", "").strip(),
                    "type": row.get("Type", "").strip(),
                    "validated_rc": validated,
                    "input_rc": row.get("InputReportingCode", "").strip(),
                    "balance": row.get("Balance", "").strip(),
                    "file": csv_file.name,
                })
    return accounts


def generate_html(mismatches, sys_map, code_list, all_accounts=None):
    h = html_mod.escape
    cat_counts = Counter(m["category"] for m in mismatches)
    rule_counts = Counter(m["rule_name"] for m in mismatches)
    file_set = sorted(set(m["file"] for m in mismatches))

    # Embed the full code list as JSON for the autocomplete/datalist
    code_json = json.dumps(code_list, ensure_ascii=False)
    all_accounts_json = json.dumps(all_accounts or [], ensure_ascii=False)

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

/* Phase 2: Type Review */
.phase2-banner {{ background: #f0fdf4; border: 2px solid #16a34a; border-radius: 8px; padding: 20px 24px; margin: 20px 0; text-align: center; }}
.phase2-banner h2 {{ color: #166534; margin-bottom: 6px; }}
.phase2-banner p {{ color: #15803d; margin-bottom: 12px; }}
.phase2-section {{ margin-top: 24px; }}
.phase2-section h2 {{ margin-bottom: 8px; font-size: 1.3em; color: #166534; }}
.phase2-table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.1); font-size: .82em; }}
.phase2-table th {{ background: #166534; color: white; padding: 8px 10px; text-align: left; font-weight: 600; font-size: .8em; }}
.phase2-table td {{ padding: 7px 10px; border-bottom: 1px solid #eee; vertical-align: top; }}
.phase2-table tr:hover td {{ background: #f0fdf4 !important; }}
.phase2-table tr.reviewed td {{ opacity: .55; }}
.phase2-table tr.reviewed:hover td {{ opacity: 1; }}
.phase2-table select {{ padding: 4px 6px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: .9em; }}
.btn-accept {{ padding: 8px 18px; background: #16a34a; color: white; border: none; border-radius: 5px; font-weight: 600; font-size: .9em; cursor: pointer; }}
.btn-accept:hover {{ background: #15803d; }}
.btn-accept-sm {{ padding: 3px 8px; background: #16a34a; color: white; border: none; border-radius: 4px; font-size: .75em; cursor: pointer; margin-left: 4px; }}
.btn-accept-sm:hover {{ background: #15803d; }}

/* Phase 3: CSV Export */
.csv-section {{ margin-top: 24px; background: white; border-radius: 8px; padding: 20px 24px; box-shadow: 0 1px 3px rgba(0,0,0,.1); text-align: center; }}
.csv-section h2 {{ margin-bottom: 8px; color: #1e293b; }}
.btn-download {{ padding: 12px 28px; background: #2563eb; color: white; border: none; border-radius: 6px; font-size: 1em; font-weight: 600; cursor: pointer; }}
.btn-download:hover {{ background: #1d4ed8; }}
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
  <th onclick="sortTable(4)">Xero Code</th>
  <th onclick="sortTable(5)">Balance</th>
  <th onclick="sortTable(6)">Type</th>
  <th onclick="sortTable(7)">Normalised</th>
  <th onclick="sortTable(8)">Got</th>
  <th onclick="sortTable(9)">Expected</th>
  <th onclick="sortTable(10)">Rule</th>
  <th onclick="sortTable(11)">Rule Context</th>
  <th onclick="sortTable(12)">Old Mapper</th>
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
        esc_id = h(row_id)       # for HTML attribute contexts (data-id, data-row-id)
        js_id = js_str(row_id)   # for inline JS string contexts (onchange, oninput)

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
            m["input_reporting_code"], m["balance"],
        ]).lower()

        parts.append(
            f'<tr class="{cat_class}" '
            f'data-id="{esc_id}" '
            f'data-cat="{h(cat)}" '
            f'data-rule="{h(m["rule_name"])}" '
            f'data-file="{h(m["file"])}" '
            f'data-search="{h(search_text)}" '
            f'data-status="pending" '
            f'data-account-name="{h(m["name"])}" '
            f'data-account-type="{h(m["raw_type"])}" '
            f'data-got="{h(m["got"])}" '
            f'data-expected="{h(m["expected"])}" '
            f'data-rule-name="{h(m["rule_name"])}">\n'
        )
        parts.append(f'  <td>{i + 1}</td>\n')
        parts.append(f'  <td><span class="tag {tag_class}">{h(cat)}</span>'
                     f'<br><span class="detail-row">{h(m["category_detail"])}</span></td>\n')
        parts.append(f'  <td style="font-size:.78em">{h(m["file"].replace("_validated_final.csv",""))}</td>\n')
        parts.append(f'  <td><strong>{h(m["name"])}</strong>'
                     f'<br><span class="detail-row">#{h(m["code"])}</span></td>\n')
        irc = m["input_reporting_code"]
        irc_desc = sys_map.get(irc, "") if irc else ""
        parts.append(f'  <td><span class="code" style="color:#6b7280">{h(irc) if irc else "—"}</span>'
                     f'{("<br><span class=detail-row>" + h(irc_desc[:40]) + "</span>") if irc_desc else ""}</td>\n')
        bal = m["balance"]
        bal_class = "green" if "DR" in bal else ("red" if "CR" in bal else "")
        parts.append(f'  <td style="white-space:nowrap;font-size:.82em;font-weight:600'
                     f'{";color:#16a34a" if "DR" in bal else (";color:#dc2626" if "CR" in bal else "")}">'
                     f'{h(bal) if bal else "—"}</td>\n')
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
                     f'onchange="setDecision(\'{js_id}\',\'got\',\'{js_str(m["got"])}\')"> '
                     f'<span class="code got">{h(m["got"])}</span> (Rule Engine)</label>\n')
        parts.append(f'      <label><input type="radio" name="d_{i}" value="expected" '
                     f'onchange="setDecision(\'{js_id}\',\'expected\',\'{js_str(m["expected"])}\')"> '
                     f'<span class="code exp">{h(m["expected"])}</span> (Validated)</label>\n')
        parts.append(f'      <label><input type="radio" name="d_{i}" value="other" '
                     f'onchange="setDecision(\'{js_id}\',\'other\',\'\')"> '
                     f'Other code...</label>\n')
        parts.append(f'    </div>\n')
        parts.append(f'    <div class="other-input" id="other_{i}">\n')
        parts.append(f'      <input type="text" list="codeSuggestions" placeholder="e.g. EXP.OCC" '
                     f'oninput="setOtherCode(\'{js_id}\',this.value, {i})">\n')
        parts.append(f'      <span class="code-desc" id="otherDesc_{i}"></span>\n')
        parts.append(f'    </div>\n')
        parts.append(f'    <div class="reason-label">Reason:</div>\n')
        parts.append(f'    <textarea placeholder="Why is this the right code?" '
                     f'oninput="setReason(\'{js_id}\',this.value)"></textarea>\n')
        parts.append(f'  </td>\n')
        parts.append('</tr>\n')

    parts.append('</tbody>\n</table>\n')

    # ── JAVASCRIPT ──
    parts.append(f"""
<script>
// Global error handler — surface any hidden JS errors visually
window.onerror = function(msg, url, line, col, err) {{
  const d = document.createElement('div');
  d.style.cssText = 'background:#fee2e2;color:#991b1b;padding:12px 16px;margin:8px 0;border-radius:8px;font-family:monospace;font-size:.85em;white-space:pre-wrap';
  d.textContent = 'JS Error: ' + msg + '\\nLine ' + line + ':' + col;
  document.body.prepend(d);
}};

const STORAGE_KEY = 'mismatch_decisions_v1';
const DIR_HANDLE_DB = 'mismatch_dir_handle';
const FILENAME = 'mismatch_decisions.json';
const CODES = {code_json};
const CODE_MAP = Object.fromEntries(CODES);
const ALL_ACCOUNTS = {all_accounts_json};
const TOTAL = {len(mismatches)};
const IS_FILE = location.protocol === 'file:';

// ─── State ───
let decisions = loadDecisions();
let dirHandle = null;      // File System Access directory handle (http only)
let saveTimer = null;      // Debounced auto-save timer
let lastSaveHash = '';     // Track whether data changed since last write

function loadDecisions() {{
  try {{ return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {{}}; }}
  catch {{ return {{}}; }}
}}

function saveDecisions() {{
  localStorage.setItem(STORAGE_KEY, JSON.stringify(decisions));
  updateProgress();
  if (!IS_FILE) scheduleAutoSave();
}}

// ─── Auto-save to file (debounced 2s, http only) ───
function scheduleAutoSave() {{
  if (IS_FILE) return;
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
    const got = row.dataset.got;
    const expected = row.dataset.expected;
    exported.push({{
      id: id,
      account_name: row.dataset.accountName,
      type: row.dataset.accountType,
      rule_engine_code: got,
      validated_code: expected,
      rule_name: row.dataset.ruleName,
      decision: d.choice,
      chosen_code: d.choice === 'got' ? got
                 : d.choice === 'expected' ? expected
                 : d.code,
      reason: d.reason || '',
      timestamp: d.timestamp
    }});
  }});
  return exported;
}}

// ─── Blob download (always works, even on file://) ───
function downloadBlob(json) {{
  const blob = new Blob([json], {{type: 'application/json'}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = FILENAME;
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  // Delay cleanup so browser can start the download
  setTimeout(() => {{
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }}, 500);
  lastSaveHash = json;
  updateSaveStatus('saved', '(downloaded)');
}}

// ─── Save button handler ───
async function saveNow() {{
  // On http with a folder handle, write directly
  if (!IS_FILE && dirHandle) {{
    await writeToFile();
    return;
  }}
  // Otherwise always download as blob
  const data = buildExportData();
  if (data.length === 0) {{ alert('No decisions to save yet.'); return; }}
  downloadBlob(JSON.stringify(data, null, 2));
}}

// ─── File System Access API (http only) ───

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
  if (IS_FILE) {{
    alert('Folder picker requires serving the page over HTTP.\\n\\n'
        + 'Use the Save button to download the JSON instead,\\n'
        + 'or run: python -m http.server 8080\\n'
        + 'then open http://localhost:8080/tests/mismatch_report.html');
    return;
  }}
  if (!('showDirectoryPicker' in window)) {{
    alert('Folder picker is not available in this browser.\\n'
        + 'Use the Save button to download the JSON instead.');
    return;
  }}
  try {{
    dirHandle = await window.showDirectoryPicker({{ mode: 'readwrite' }});
    await storeHandle(dirHandle);
    const btn = document.querySelector('.btn-folder');
    btn.textContent = dirHandle.name;
    btn.classList.add('linked');
    updateSaveStatus('idle', 'Folder: ' + dirHandle.name);
    await writeToFile();
  }} catch (e) {{
    if (e.name !== 'AbortError') {{
      console.error('Folder pick error:', e);
      updateSaveStatus('error', 'Folder pick failed: ' + e.message);
    }}
  }}
}}

async function restoreDirHandle() {{
  if (IS_FILE) return;  // Skip on file:// — API not available
  try {{
    const stored = await loadHandle();
    if (!stored) return;
    const perm = await stored.queryPermission({{ mode: 'readwrite' }});
    if (perm === 'granted') {{
      dirHandle = stored;
    }} else {{
      const req = await stored.requestPermission({{ mode: 'readwrite' }});
      if (req === 'granted') dirHandle = stored;
    }}
    if (dirHandle) {{
      const btn = document.querySelector('.btn-folder');
      btn.textContent = dirHandle.name;
      btn.classList.add('linked');
      updateSaveStatus('idle', 'Folder: ' + dirHandle.name);
    }}
  }} catch {{ /* ignore */ }}
}}

async function writeToFile() {{
  if (IS_FILE || !dirHandle) return;
  const data = buildExportData();
  const json = JSON.stringify(data, null, 2);
  if (json === lastSaveHash) {{ updateSaveStatus('idle', 'Folder: ' + dirHandle.name); return; }}
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
  // Only count decisions for rows that exist in the current report
  const currentIds = new Set();
  document.querySelectorAll('#mismatchTable tbody tr').forEach(r => currentIds.add(r.dataset.id));
  const reviewed = Object.entries(decisions).filter(([id, d]) => d.choice && currentIds.has(id)).length;
  document.getElementById('reviewedCount').textContent = reviewed;
  document.getElementById('reviewedPct').textContent = Math.round(reviewed / TOTAL * 100) + '%';
  checkPhase1Complete();
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

// ─── Phase 2: Type Review ───
const HEAD_FROM_TYPE = {{
  'Current Asset': 'ASS', 'Fixed Asset': 'ASS', 'Inventory': 'ASS',
  'Non-current Asset': 'ASS', 'Prepayment': 'ASS',
  'Equity': 'EQU',
  'Depreciation': 'EXP', 'Direct Costs': 'EXP', 'Expense': 'EXP', 'Overhead': 'EXP',
  'Current Liability': 'LIA', 'Liability': 'LIA', 'Non-current Liability': 'LIA',
  'Other Income': 'REV', 'Revenue': 'REV', 'Sales': 'REV'
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

const TYPE_STORAGE_KEY = 'type_decisions_v1';
let typeDecisions = loadTypeDecisions();
let phase2Active = false;

function loadTypeDecisions() {{
  try {{ return JSON.parse(localStorage.getItem(TYPE_STORAGE_KEY)) || {{}}; }}
  catch {{ return {{}}; }}
}}

function saveTypeDecisions() {{
  localStorage.setItem(TYPE_STORAGE_KEY, JSON.stringify(typeDecisions));
  updatePhase2Progress();
}}

function headFromCode(code) {{
  return code ? code.split('.')[0] : '';
}}

function predictTypeFromCode(code, currentType) {{
  if (!code) return currentType;
  const c = code.toUpperCase();
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
  if (c.startsWith('REV')) {{
    if (currentType === 'Sales')          return 'Sales';
    return 'Revenue';
  }}
  if (c.startsWith('EQU'))               return 'Equity';
  return currentType;
}}

function getFinalCode(acct) {{
  // Build a lookup key matching the mismatch id format
  const rows = document.querySelectorAll('#mismatchTable tbody tr');
  for (const row of rows) {{
    const id = row.dataset.id;
    // Match by file + code + name prefix
    if (id.startsWith(acct.file.replace('.csv','') + ':' + acct.code + ':')) {{
      const d = decisions[id];
      if (d && d.choice) {{
        if (d.choice === 'got') return row.dataset.got;
        if (d.choice === 'expected') return row.dataset.expected;
        if (d.choice === 'other' && d.code) return d.code;
      }}
    }}
  }}
  return acct.validated_rc;
}}

function checkPhase1Complete() {{
  const currentIds = new Set();
  document.querySelectorAll('#mismatchTable tbody tr').forEach(r => currentIds.add(r.dataset.id));
  const reviewed = Object.entries(decisions).filter(([id, d]) => d.choice && currentIds.has(id)).length;
  if (reviewed >= TOTAL && TOTAL > 0 && !phase2Active) {{
    showPhase2Banner();
  }}
}}

function showPhase2Banner() {{
  if (document.getElementById('phase2Banner')) return;
  const banner = document.createElement('div');
  banner.id = 'phase2Banner';
  banner.className = 'phase2-banner';
  banner.innerHTML = '<h2>All mismatches reviewed!</h2>'
    + '<p>Proceed to check account types against reporting codes?</p>'
    + '<button class="btn-download" onclick="startPhase2()">Start Type Review</button>';
  document.querySelector('table').after(banner);
}}

function startPhase2() {{
  phase2Active = true;
  const banner = document.getElementById('phase2Banner');
  if (banner) banner.remove();

  // Build type mismatches
  const typeMismatches = [];
  ALL_ACCOUNTS.forEach((acct, idx) => {{
    if (SYSTEM_TYPES.has(acct.type)) return;
    const finalCode = getFinalCode(acct);
    const codeHead = headFromCode(finalCode);
    const typeHead = HEAD_FROM_TYPE[acct.type];
    if (!typeHead || !codeHead) return;
    if (codeHead !== typeHead) {{
      const predicted = predictTypeFromCode(finalCode, acct.type);
      typeMismatches.push({{
        idx: idx,
        file: acct.file,
        code: acct.code,
        name: acct.name,
        currentType: acct.type,
        finalCode: finalCode,
        codeHead: codeHead,
        predictedType: predicted,
        acctId: acct.file + ':' + acct.code + ':' + acct.name.substring(0, 40)
      }});
    }}
  }});

  renderPhase2(typeMismatches);
}}

function renderPhase2(typeMismatches) {{
  const existing = document.getElementById('phase2Section');
  if (existing) existing.remove();

  const section = document.createElement('div');
  section.id = 'phase2Section';
  section.className = 'phase2-section';

  if (typeMismatches.length === 0) {{
    section.innerHTML = '<h2>Type Review</h2>'
      + '<p style="color:#16a34a;font-weight:600">No type mismatches found — all account types are consistent with their reporting codes.</p>';
    document.querySelector('table').after(section);
    showCSVSection();
    return;
  }}

  let html = '<h2>Type Review <span style="font-weight:400;font-size:.8em;color:#666">('
    + typeMismatches.length + ' accounts)</span></h2>'
    + '<p style="margin-bottom:12px;color:#666;font-size:.9em">These accounts have a reporting code head that disagrees with their Xero account type.</p>'
    + '<div style="margin-bottom:12px"><button class="btn-accept" onclick="acceptAllTypePredictions()">Accept All Predictions</button>'
    + ' <span class="progress-label" id="phase2Progress">0 / ' + typeMismatches.length + '</span></div>'
    + '<table class="phase2-table"><thead><tr>'
    + '<th>#</th><th>File</th><th>Account</th><th>Code</th>'
    + '<th>Current Type</th><th>Code Head</th><th>Predicted Type</th><th>Your Decision</th>'
    + '</tr></thead><tbody>';

  typeMismatches.forEach((tm, i) => {{
    const allowed = ALLOWED_TYPES_BY_HEAD[tm.codeHead] || [];
    const savedDecision = typeDecisions[tm.acctId];
    const selectedType = savedDecision ? savedDecision.newType : '';
    const isDecided = !!selectedType;

    html += '<tr class="' + (isDecided ? 'reviewed' : '') + '" data-type-id="' + escHtml(tm.acctId) + '">'
      + '<td>' + (i + 1) + '</td>'
      + '<td style="font-size:.78em">' + escHtml(tm.file.replace('_validated_final.csv', '')) + '</td>'
      + '<td><strong>' + escHtml(tm.name) + '</strong><br><span class="detail-row">#' + escHtml(tm.code) + '</span></td>'
      + '<td><span class="code">' + escHtml(tm.finalCode) + '</span></td>'
      + '<td style="color:#dc2626;font-weight:600">' + escHtml(tm.currentType) + '</td>'
      + '<td><span class="tag cat">' + escHtml(tm.codeHead) + '</span></td>'
      + '<td style="color:#16a34a;font-weight:600">' + escHtml(tm.predictedType) + '</td>'
      + '<td class="decision-cell"><select onchange="setTypeDecision(\'' + escJs(tm.acctId) + '\',this.value)">';

    html += '<option value="">— choose —</option>';
    allowed.forEach(t => {{
      const sel = (selectedType === t) ? ' selected' : '';
      const marker = (t === tm.predictedType) ? ' (predicted)' : '';
      html += '<option value="' + escHtml(t) + '"' + sel + '>' + escHtml(t) + marker + '</option>';
    }});
    html += '</select>'
      + ' <button class="btn-accept-sm" onclick="acceptTypePrediction(\'' + escJs(tm.acctId) + '\',\'' + escJs(tm.predictedType) + '\',this)">Accept</button>'
      + '</td></tr>';
  }});

  html += '</tbody></table>';
  section.innerHTML = html;
  document.querySelector('#mismatchTable').after(section);
  updatePhase2Progress();
}}

function escHtml(s) {{
  const div = document.createElement('div');
  div.textContent = s || '';
  return div.innerHTML;
}}

function escJs(s) {{
  return (s || '').replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'");
}}

function setTypeDecision(acctId, newType) {{
  if (!newType) {{
    delete typeDecisions[acctId];
  }} else {{
    typeDecisions[acctId] = {{ newType: newType, timestamp: new Date().toISOString() }};
  }}
  const row = document.querySelector('tr[data-type-id="' + acctId + '"]');
  if (row) row.classList.toggle('reviewed', !!newType);
  saveTypeDecisions();
  checkPhase2Complete();
}}

function acceptTypePrediction(acctId, predicted, btn) {{
  typeDecisions[acctId] = {{ newType: predicted, timestamp: new Date().toISOString() }};
  const row = document.querySelector('tr[data-type-id="' + acctId + '"]');
  if (row) {{
    row.classList.add('reviewed');
    const select = row.querySelector('select');
    if (select) select.value = predicted;
  }}
  saveTypeDecisions();
  checkPhase2Complete();
}}

function acceptAllTypePredictions() {{
  document.querySelectorAll('.phase2-table tbody tr').forEach(row => {{
    const acctId = row.dataset.typeId;
    const select = row.querySelector('select');
    if (!select) return;
    // Find the predicted option (has "(predicted)" text)
    for (const opt of select.options) {{
      if (opt.text.includes('(predicted)')) {{
        select.value = opt.value;
        typeDecisions[acctId] = {{ newType: opt.value, timestamp: new Date().toISOString() }};
        row.classList.add('reviewed');
        break;
      }}
    }}
  }});
  saveTypeDecisions();
  checkPhase2Complete();
}}

function updatePhase2Progress() {{
  const el = document.getElementById('phase2Progress');
  if (!el) return;
  const total = document.querySelectorAll('.phase2-table tbody tr').length;
  const decided = Object.keys(typeDecisions).length;
  const relevant = Math.min(decided, total);
  el.textContent = relevant + ' / ' + total;
}}

function checkPhase2Complete() {{
  const total = document.querySelectorAll('.phase2-table tbody tr').length;
  const decided = document.querySelectorAll('.phase2-table tbody tr.reviewed').length;
  if (decided >= total) {{
    showCSVSection();
  }}
}}

function showCSVSection() {{
  if (document.getElementById('csvSection')) return;
  const section = document.createElement('div');
  section.id = 'csvSection';
  section.className = 'csv-section';
  section.innerHTML = '<h2>Export Chart of Accounts</h2>'
    + '<p style="margin-bottom:12px;color:#666;font-size:.9em">Download the updated Chart of Accounts with all code and type corrections applied.</p>'
    + '<button class="btn-download" onclick="downloadCSV()">Download Chart of Accounts CSV</button>';
  const phase2 = document.getElementById('phase2Section');
  if (phase2) phase2.after(section);
  else document.querySelector('#mismatchTable').after(section);
}}

// ─── Phase 3: CSV Export ───
function csvEscape(val) {{
  if (val == null) val = '';
  val = String(val);
  if (val.includes(',') || val.includes('"') || val.includes('\\n') || val.includes('\\r')) {{
    return '"' + val.replace(/"/g, '""') + '"';
  }}
  return val;
}}

function downloadCSV() {{
  const headers = ['*Code', '*Name', '*Type', '*Tax Type', 'Description', 'Dashboard', 'Expense Claims', 'Enable Payments', '*Report Code'];
  const rows = [headers.join(',')];

  ALL_ACCOUNTS.forEach(acct => {{
    const finalCode = getFinalCode(acct);
    const acctId = acct.file + ':' + acct.code + ':' + acct.name.substring(0, 40);
    const td = typeDecisions[acctId];
    const finalType = (td && td.newType) ? td.newType : acct.type;

    rows.push([
      csvEscape(acct.code),
      csvEscape(acct.name),
      csvEscape(finalType),
      '',  // Tax Type — not in fixture data
      '',  // Description
      '',  // Dashboard
      '',  // Expense Claims
      '',  // Enable Payments
      csvEscape(finalCode)
    ].join(','));
  }});

  const csvContent = rows.join('\\r\\n');
  const blob = new Blob([csvContent], {{ type: 'text/csv;charset=utf-8;' }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'ChartOfAccounts_Updated.csv';
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {{
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }}, 500);
}}

// ─── Init ───
try {{
  restoreState();
  applyFilters();
  restoreDirHandle();
  if (IS_FILE) {{
    document.querySelector('.btn-folder').title = 'Requires HTTP server — use Save button to download';
    updateSaveStatus('idle', 'file:// mode — click Save to download JSON');
  }}
  // Auto-trigger Phase 2 if Phase 1 was already complete
  checkPhase1Complete();
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


def main():
    file_filter = sys.argv[1] if len(sys.argv) > 1 else None
    sys_map, code_list = load_system_mappings()
    mismatches = collect_mismatches(sys_map, file_filter)
    all_accounts = collect_all_accounts(file_filter)
    html_content = generate_html(mismatches, sys_map, code_list, all_accounts)
    OUTPUT.write_text(html_content, encoding="utf-8")
    label = f" (filter: {file_filter})" if file_filter else ""
    print(f"Written {len(mismatches)} mismatches to {OUTPUT}{label}")
    print(f"  All accounts: {len(all_accounts)}")
    print(f"  File size: {OUTPUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
