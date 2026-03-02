
"""mapping_logic_v15.py – Reporting Code mapper for Xero-style Chart of Accounts.

Run (updated CLI):
    python mapping_logic_v15.py <ClientChartOfAccounts.csv> <ClientTrialBalance.csv> --chart <CHARTNAME> [--industry <Industry>]

Where:
    --chart selects a template CSV in ChartOfAccounts/ by filename (without extension), e.g. --chart Company

Outputs:
    - AugmentedChartOfAccounts.csv alongside the client chart
    - ReportingTree.json documenting inferred ranges from the selected template
"""

import pandas as pd, re, difflib, argparse, pathlib, csv, json, sys
from collections import defaultdict
from file_handler import load_chart_file, load_trial_balance_file, get_account_code_column, get_closing_balance_column
from integrity_validator import IntegrityValidator
from rule_engine import evaluate_rules, MatchContext
from rules import ALL_RULES, OWNER_KEYWORDS as _OWNER_KEYWORDS, AUSTRALIAN_BANKS, VEHICLE_MAKES, AUSTRALIAN_LENDERS, normalise_industry
from spell_corrections import build_spell_checker, correct_account_name
from context_rules import infer_from_context, infer_section

TYPE_EQ = {
    # Removed problematic mappings that collapse distinct types
    # 'direct costs':'expense','cost of sales':'expense','cost of goods sold':'expense'
    # These should maintain distinct heads (EXP.COS vs EXP)
    'purchases':'expense','operating expense':'expense','operating expenses':'expense',
    'overhead':'expense','overheads':'expense',
}

# Vehicle detection tokens (normalized)
VEHICLE_TOKENS = [
    'mv', 'motor vehicle', 'car', 'truck', 'vehicle'
]
VEHICLE_EXPENSE_TOKENS = [
    'fuel', 'petrol', 'oil', 'repairs', 'maintenance', 'repairs maintenance', 'servicing',
    'insurance', 'ctp', 'green slip', 'rego', 'registration', 'parking',
    'road tolls', 'tolls', 'washing', 'cleaning', 'expenses'
]


def strip_noise_suffixes(name:str)->str:
    if pd.isnull(name): return ''
    name=str(name).split(':')[-1]
    name=re.sub(r'\s*-\s*(at cost|closing balance)$','',name,flags=re.I)
    name=re.sub(r'\s*at cost$','',name,flags=re.I)
    return name.strip()

def normalise(text:str)->str:
    text=str(text).lower()
    # Treat ampersands as 'and' for better matching parity with SystemMappings/DefaultChart
    text=re.sub(r'\s*&\s*', ' and ', text)
    # Canonicalize motor vehicle abbreviation variants before punctuation stripping
    # e.g., "M/V", "M - V", or "M V" -> "mv"
    text=re.sub(r'\bm\s*/\s*v\b', 'mv', text)
    text=re.sub(r'\bm\s*-\s*v\b', 'mv', text)
    text=re.sub(r'\bm\s+v\b', 'mv', text)
    # Canonicalize shorthand R&M → 'repairs maintenance'
    text=re.sub(r'\br\s*(?:and|&|/)\s*m\b', 'repairs maintenance', text)
    text=re.sub(r'[^\w\s]',' ',text)
    text=re.sub(r'\s+',' ',text).strip()
    return text

def canonical_type(t:str)->str:
    return TYPE_EQ.get(str(t).strip().lower(), str(t).strip().lower())

def head_from_type(t:str)->str:
    t=canonical_type(t)
    
    # Specific mappings per Account_Types_Head.csv
    if t=='other income':
        return 'REV.OTH'  # Specific mapping to prevent leakage into trading revenue
    if t in {'revenue','income','sales'}:
        return 'REV.TRA'
    if t in {'direct costs','cost of sales','cost of goods sold'}:
        return 'EXP.COS'  # Maintain distinct head for cost of sales
    if t=='expense':
        return 'EXP'
    if t=='current asset':
        return 'ASS.CUR'
    if t=='fixed asset':
        return 'ASS.NCA.FIX'
    if t=='non-current asset':
        return 'ASS.NCA'
    if t=='current liability':
        return 'LIA.CUR'
    if t=='non-current liability':
        return 'LIA.NCL'
    if t in {'asset','bank','accounts receivable','inventory','prepayment'}:
        return 'ASS'  # Generic asset fallback
    if t in {'liability','accounts payable','credit card','term liability','gst','historical','rounding','tracking'}:
        return 'LIA'  # Generic liability fallback
    if t in {'equity','retained earnings'}:
        return 'EQU'
    
    # Default fallback
    return 'EXP'

def _head_group(head: str) -> str:
    """Return the broad group for a reporting code head.

    Groups:
        'PL' — Profit & Loss (REV, EXP) — can cross within
        'BS' — Balance Sheet  (ASS, LIA) — can cross within
        'EQ' — Equity         (EQU)      — never crosses
    """
    root = head.split('.')[0] if head else ''
    if root in {'REV', 'EXP'}:
        return 'PL'
    if root in {'ASS', 'LIA'}:
        return 'BS'
    if root == 'EQU':
        return 'EQ'
    return ''

# High-confidence sources that should bypass the cross-head guard
_CROSS_HEAD_SKIP_SOURCES = frozenset({
    'DefaultChart', 'AlreadyCorrect', 'ExistingCodeValid', 'ExistingCodeValidByName',
})

def similarity(a:str,b:str)->float:
    return difflib.SequenceMatcher(None,a,b).ratio()

# --- Accumulated depreciation/amortisation helpers ---
DEPRECIATION_TOKENS = {'accumulated depreciation','accumulated amortisation','accumulated amortization','depreciation','amortisation','amortization', 'accum dep'}

def extract_accum_base_key(name_raw: str) -> str:
    """Return a normalised base asset phrase for accumulated depreciation names.
    Handles patterns like:
    - 'Less Accumulated Depreciation on Office Equipment' -> 'office equipment'
    - 'Leasehold Improvements Accumulated Depreciation' -> 'leasehold improvements'
    - 'Accumulated Amortisation of Leasehold Improvements' -> 'leasehold improvements'
    - 'Office furniture/equipment:Less accumulated depreciation' -> 'office furniture equipment'
    - 'Furniture and Fittings:Accum. PU depreciation 5' -> 'furniture and fittings'
    Returns empty string when no clear base phrase is detected.
    """
    if pd.isnull(name_raw):
        return ''
    name = str(name_raw).strip()
    nlow = normalise(name)
    # Common prefix/suffix patterns (standard format)
    m = re.search(r"less\s+accumulated\s+(depreciation|amortisation|amortization)\s+(on|of)\s+(.+)$", nlow)
    if m:
        return m.group(3).strip()
    m = re.search(r"^accumulated\s+(depreciation|amortisation|amortization)\s+(on|of)\s+(.+)$", nlow)
    if m:
        return m.group(3).strip()
    # Colon-format: "<base> less [accumulated] depreciation/amortisation"
    # (Xero subaccount syntax "Parent:Less Accum Dep" normalises to "parent less accum dep")
    m = re.search(r"^(.+?)\s+less\s+(?:accumulated\s+)?(?:depreciation|amortisation|amortization)\b", nlow)
    if m:
        return m.group(1).strip()
    # Abbreviated colon-format: "<base> accum[ulated] [qualifier] depreciation"
    m = re.search(r"^(.+?)\s+accum(?:ulated)?\b.*?(?:depreciation|amortisation|amortization)", nlow)
    if m:
        base = m.group(1).strip()
        if len(base) > 2:
            return base
    # Suffix pattern: '<base> accumulated depreciation/amortisation'
    for tok in ['accumulated depreciation','accumulated amortisation','accumulated amortization']:
        if nlow.endswith(tok):
            base = nlow[: max(0, nlow.rfind(tok))].strip()
            return base
    return ''

def build_accum_base_map(defaultchart: pd.DataFrame) -> dict:
    """From the template chart, build mapping from base asset phrase -> .ACC (or .AMO) reporting code."""
    accum_map = {}
    for _, r in defaultchart.iterrows():
        rc = str(r.get('Reporting Code','') or '').strip()
        nm = str(r.get('Name','') or '')
        if not rc:
            continue
        is_acc = rc.endswith('.ACC') or rc.endswith('.AMO')
        if not is_acc:
            continue
        base = extract_accum_base_key(nm)
        if base:
            accum_map[base] = rc
    return accum_map

# ---------------- Range tree builder (integrated from build_reporting_tree.py) ----------------
def _new_node(rep_code: str):
    return {
        "reporting_code": rep_code,
        "min": None,
        "max": None,
        "types": set(),
        "subheaders": {}
    }

def _finalize_and_validate(node):
    subdict = node['subheaders']
    children = [_finalize_and_validate(subdict[k]) for k in sorted(subdict.keys())]
    node['subheaders'] = children
    node['types'] = sorted(list(node['types']))
    valid = True
    for ch in children:
        if node['min'] is None or node['max'] is None or ch['min'] is None or ch['max'] is None:
            continue
        if ch['min'] < node['min'] or ch['max'] > node['max'] or not ch.get('valid', True):
            valid = False
    node['valid'] = valid
    return node

def build_reporting_tree_from_chart(csv_path: pathlib.Path)->dict:
    df = pd.read_csv(csv_path)
    required = {'Code','Reporting Code','Type'}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Malformed template chart '{csv_path.name}': missing required columns {sorted(missing)}")
    df_num = df.copy()
    df_num['Code'] = pd.to_numeric(df_num['Code'], errors='coerce')
    df_num = df_num.dropna(subset=['Code','Reporting Code'])
    df_num['Code'] = df_num['Code'].astype(int)
    df_num['Reporting Code'] = df_num['Reporting Code'].astype(str)
    df_num['Type'] = df_num['Type'].astype(str)

    headers_dict = {}
    for _, row in df_num.iterrows():
        code_val = int(row['Code'])
        rep_code = row['Reporting Code']
        typ = row.get('Type','')
        segs = rep_code.split('.')
        top = segs[0]
        if top not in headers_dict:
            headers_dict[top] = _new_node(top)
        node = headers_dict[top]
        node['min'] = code_val if node['min'] is None else min(node['min'], code_val)
        node['max'] = code_val if node['max'] is None else max(node['max'], code_val)
        if typ:
            node['types'].add(typ)
        prefix = top
        for i in range(1, len(segs)):
            prefix = ".".join(segs[:i+1])
            if prefix not in node['subheaders']:
                node['subheaders'][prefix] = _new_node(prefix)
            child = node['subheaders'][prefix]
            child['min'] = code_val if child['min'] is None else min(child['min'], code_val)
            child['max'] = code_val if child['max'] is None else max(child['max'], code_val)
            if typ:
                child['types'].add(typ)
            node = child
    headers = [_finalize_and_validate(headers_dict[k]) for k in sorted(headers_dict.keys())]
    return {"headers": headers}

def _validate_tree_schema(tree: dict):
    if not isinstance(tree, dict) or 'headers' not in tree or not isinstance(tree['headers'], list):
        raise ValueError("Range tree schema invalid: expected object with 'headers' list")
    def _check_node(n):
        for key in ['reporting_code','min','max','types','subheaders','valid']:
            if key not in n:
                raise ValueError(f"Range tree node missing key '{key}' for {n.get('reporting_code','<unknown>')}")
        if not isinstance(n['reporting_code'], str):
            raise ValueError("Range tree node 'reporting_code' must be a string")
        if n['min'] is not None and not isinstance(n['min'], int):
            raise ValueError("Range tree node 'min' must be int or None")
        if n['max'] is not None and not isinstance(n['max'], int):
            raise ValueError("Range tree node 'max' must be int or None")
        if not isinstance(n['types'], list):
            raise ValueError("Range tree node 'types' must be a list")
        if not isinstance(n['subheaders'], list):
            raise ValueError("Range tree node 'subheaders' must be a list")
        if not isinstance(n['valid'], bool):
            raise ValueError("Range tree node 'valid' must be a bool")
        for ch in n['subheaders']:
            _check_node(ch)
    for h in tree['headers']:
        _check_node(h)

def _flatten_nodes(nodes):
    out=[]
    for n in nodes:
        out.append(n)
        out.extend(_flatten_nodes(n.get('subheaders', [])))
    return out

def _infer_expected_head_lookup(template_df: pd.DataFrame, tree: dict):
    exact_map={}
    for _, r in template_df.iterrows():
        code_val = str(r.get('Code','') or '').strip()
        rc = str(r.get('Reporting Code','') or '').strip()
        if code_val and rc:
            exact_map[code_val] = rc.split('.')[0]
    all_nodes=_flatten_nodes(tree.get('headers', []))
    range_nodes=[n for n in all_nodes if isinstance(n.get('min'), int) and isinstance(n.get('max'), int)]
    def infer(code_str: str)->str:
        cstr=str(code_str or '').strip()
        if not cstr:
            return ''
        if cstr in exact_map:
            return exact_map[cstr]
        if re.fullmatch(r"\d+", cstr):
            ci=int(cstr)
            best=None
            best_span=None
            for n in range_nodes:
                if n['min']<=ci<=n['max']:
                    span=n['max']-n['min']
                    if best is None or span<best_span:
                        best=n; best_span=span
            if best is not None:
                return best['reporting_code'].split('.')[0]
        return ''
    return infer

def main(args):
    # Initialize integrity validator
    project_root = pathlib.Path(__file__).parent
    validator = IntegrityValidator(project_root)
    
    # Resolve client chart
    client_chart_path = pathlib.Path(args.client_chart)
    if not client_chart_path.exists():
        sys.exit(f"Error: Client chart not found: {client_chart_path}")
    try:
        coa = load_chart_file(client_chart_path)
    except Exception as e:
        sys.exit(f"Error: Failed to read client chart '{client_chart_path.name}': {e}")

    # Resolve template chart from ChartOfAccounts/ by name (normalized)
    templates_dir = pathlib.Path(__file__).parent / 'ChartOfAccounts'
    if not templates_dir.exists():
        sys.exit(f"Error: Templates directory not found: {templates_dir}")
    normalized_target = str(args.chart_template_name or '').lower().strip()
    candidates = {p.stem.lower().strip(): p for p in templates_dir.glob('*.csv')}
    if normalized_target not in candidates:
        available = ", ".join(sorted(candidates.keys()))
        sys.exit(f"Error: No chart template named '{args.chart_template_name}'. Available templates: {available}")
    template_chart_path = candidates[normalized_target]
    try:
        defaultchart = load_chart_file(template_chart_path)
    except Exception as e:
        sys.exit(f"Error: Failed to read template chart '{template_chart_path.name}': {e}")

    # Load SystemMappings from fixed path
    sysmap_path = pathlib.Path(__file__).parent / 'SystemFiles' / 'SystemMappings.csv'
    if not sysmap_path.exists():
        sys.exit(f"Error: System mappings not found at expected path: {sysmap_path}")
    try:
        sysmap=pd.read_csv(sysmap_path)
    except Exception as e:
        sys.exit(f"Error: Failed to read system mappings '{sysmap_path}': {e}")

    # Load trial balance with intelligent sanitization
    trial_path = pathlib.Path(args.client_trialbalance)
    if not trial_path.exists():
        sys.exit(f"Error: Trial balance not found: {trial_path}")
    _tb_name_lower = trial_path.stem.lower()
    if "trial" not in _tb_name_lower or "balance" not in _tb_name_lower:
        sys.exit(
            f"Error: '{trial_path.name}' does not appear to be a Trial Balance.\n"
            f"       The filename must contain both 'Trial' and 'Balance'.\n"
            f"       Please provide the correct Xero Trial Balance export."
        )
    try:
        trial, trial_metadata = load_trial_balance_file(trial_path)
        if trial_metadata.get("format") != "xero_trial_balance":
            sys.exit(
                f"Error: '{trial_path.name}' is not a valid Xero Trial Balance.\n"
                f"       Cell A1 must equal 'Trial Balance'. Found format: {trial_metadata.get('format', 'unknown')}.\n"
                f"       Please provide the correct Xero Trial Balance export."
            )
        print(f"Loaded trial balance: {trial_metadata}")
    except Exception as e:
        sys.exit(f"Error: Failed to read trial balance '{trial_path.name}': {e}")

    # Build spell checker with domain dictionaries
    _extra_known = AUSTRALIAN_BANKS + VEHICLE_MAKES + AUSTRALIAN_LENDERS
    _company_name = trial_metadata.get("company_name", "")
    if _company_name:
        _extra_known.extend(_company_name.lower().split())
    spell_checker = build_spell_checker(extra_known=_extra_known)

    # Run integrity validation on template charts
    print("Validating template charts...")
    template_findings = validator.validate_chart_dataframe(defaultchart, template_chart_path.name)
    if template_findings:
        print(f"WARNING: Found {len(template_findings)} integrity violations in template chart:")
        for finding in template_findings[:5]:  # Show first 5
            print(f"  - {finding['reason']}")
        if len(template_findings) > 5:
            print(f"  ... and {len(template_findings) - 5} more")
    
    # Run integrity validation on client chart
    print("Validating client chart...")
    client_findings = validator.validate_chart_dataframe(coa, client_chart_path.name)
    
    # Write integrity findings to file
    all_findings = template_findings + client_findings
    if all_findings:
        findings_path = client_chart_path.with_name('integrity_findings.json')
        with open(findings_path, 'w', encoding='utf-8') as f:
            json.dump({
                'master_integrity_findings': template_findings,
                'client_integrity_findings': client_findings,
                'summary': validator.get_validation_summary(all_findings)
            }, f, indent=2)
        print(f"Integrity findings written to: {findings_path}")
        
        if args.validate_only:
            print(f"Validation complete. Found {len(all_findings)} integrity violations.")
            return
    
    # Detect balance anomalies
    print("Detecting balance anomalies...")
    balance_anomalies = []
    account_code_col = get_account_code_column(trial)
    period_cols = [col for col in trial.columns if col not in ['AccountCode', 'Account Code', 'Code', 'Account', 'Account Type', 'Debit - Year to date', 'Credit - Year to date']]
    
    if account_code_col and period_cols:
        for _, row in trial.iterrows():
            account_code = str(row.get(account_code_col, '')).strip()
            account_type = str(row.get('Account Type', '')).strip()
            
            if account_code and account_type and account_code != 'nan' and account_type != 'nan':
                period_balances = {}
                for col in period_cols:
                    balance = row.get(col, 0)
                    if pd.notna(balance):
                        period_balances[col] = float(balance)
                
                if len(period_balances) >= 2:
                    anomaly = validator.detect_balance_anomalies(account_code, account_type, period_balances)
                    if anomaly['is_anomaly']:
                        balance_anomalies.append({
                            'account_code': account_code,
                            'account_type': account_type,
                            'severity': anomaly['severity'],
                            'recommendation': anomaly['recommendation'],
                            'periods_checked': anomaly['periods_checked']
                        })
    
    if balance_anomalies:
        anomalies_path = client_chart_path.with_name('balance_anomalies.json')
        with open(anomalies_path, 'w', encoding='utf-8') as f:
            json.dump(balance_anomalies, f, indent=2)
        print(f"Balance anomalies written to: {anomalies_path}")
        print(f"Found {len(balance_anomalies)} balance anomalies")
    
    if args.validate_only:
        print("Validation complete.")
        return

    # Build and validate range tree from template chart, then write JSON next to client chart
    try:
        tree = build_reporting_tree_from_chart(template_chart_path)
    except Exception as e:
        sys.exit(f"Error: Unable to build reporting tree from template '{template_chart_path.name}': {e}")
    try:
        _validate_tree_schema(tree)
    except Exception as e:
        sys.exit(f"Error: Reporting tree schema validation failed: {e}")
    tree_out = client_chart_path.with_name('ReportingTree.json')
    try:
        with tree_out.open('w', encoding='utf-8') as f:
            json.dump(tree, f, indent=2)
    except Exception as e:
        sys.exit(f"Error: Failed to write ReportingTree.json: {e}")

    # lookup bal
    # Use helper functions to detect column names
    account_code_col = get_account_code_column(trial)
    closing_balance_col = get_closing_balance_column(trial)
    
    bal_lookup = {}
    if account_code_col and closing_balance_col:
        for _, r in trial.iterrows():
            if pd.notnull(r[account_code_col]) and pd.notnull(r[closing_balance_col]):
                bal_lookup[str(r[account_code_col]).strip()] = r[closing_balance_col]

    # Determine whether there are any non-zero Direct Costs in Trial Balance (service-only helper)
    direct_cost_nonzero = False
    if 'Account Type' in trial.columns:
        def _parse_amount(x):
            try:
                s=str(x).strip().replace(',', '')
                if s.startswith('(') and s.endswith(')'):
                    s='-'+s[1:-1]
                return float(s)
            except Exception:
                return 0.0
        for _, _r in trial.iterrows():
            if str(_r.get('Account Type','')).strip().lower() == 'direct costs':
                d=_parse_amount(_r.get('Debit - Year to date',0))
                c=_parse_amount(_r.get('Credit - Year to date',0))
                if abs(d) > 1e-9 or abs(c) > 1e-9:
                    direct_cost_nonzero = True
                    break

    # Build allowed reporting codes from SystemMappings and all templates (reject invalid codes)
    allowed_codes=set(sysmap['Reporting Code'].astype(str).str.strip())
    try:
        for p in templates_dir.glob('*.csv'):
            try:
                _df=pd.read_csv(p)
                if 'Reporting Code' in _df.columns:
                    for _rc in _df['Reporting Code']:
                        if pd.notnull(_rc):
                            allowed_codes.add(str(_rc).strip())
            except Exception:
                pass
    except Exception:
        pass

    defaultchart['clean_name']=defaultchart['Name'].apply(strip_noise_suffixes).apply(normalise)
    defaultchart['canonical_type']=defaultchart['Type'].apply(canonical_type)

    dict_code={str(r['Code']).strip(): r['Reporting Code'] for _,r in defaultchart.iterrows() if pd.notnull(r['Reporting Code'])}
    # Enriched by-code lookup for safer matching
    default_by_code={str(r['Code']).strip(): {
        'reporting_code': r['Reporting Code'],
        'clean_name': r['clean_name'],
        'canonical_type': r['canonical_type'],
        'head': str(r['Reporting Code']).split('.')[0] if pd.notnull(r['Reporting Code']) else ''
    } for _,r in defaultchart.iterrows() if pd.notnull(r['Code'])}
    dict_name_type={(r['clean_name'], r['canonical_type']): r['Reporting Code'] for _,r in defaultchart.iterrows() if pd.notnull(r['Reporting Code'])}
    accum_base_to_rc = build_accum_base_map(defaultchart)

    sysmap['IsLeaf']=sysmap['IsLeaf'].astype(str).str.lower().isin(['true','1','yes'])
    leaf_set=set(sysmap[sysmap['IsLeaf']]['Reporting Code'])
    name_to_leaf={normalise(r['Name']): r['Reporting Code'] for _,r in sysmap[sysmap['IsLeaf']].iterrows()}
    name_to_any={normalise(r['Name']): r['Reporting Code'] for _,r in sysmap.iterrows()}
    head_to_leaves=defaultdict(list)
    for _,r in sysmap[sysmap['IsLeaf']].iterrows():
        head_to_leaves[r['Reporting Code'].split('.')[0]].append((r['Reporting Code'], r['Name']))

    prc=[];pname=[];need=[];src=[]
    change_rows=[]
    # Track audited overrides and clarifications derived from optional CorrectCode/CorrectReason inputs.
    # Assumptions:
    # - If input COA contains 'CorrectCode' populated for a row, this is a professional/audited override and
    #   must take precedence over any heuristic or existing client code.
    # - We log these as clarifications using the existing spec (AccountCode, PriorReportCode, NewReportCode, UserComment)
    #   and use Source = 'UserClarified' to align with the enumerated Source values.
    clarifications = []
    overridden_indices = set()
    previous_processed_row = None
    # For second-pass accumulated depreciation pairing
    name_to_predicted_rc = {}
    
    # Normalize *Code to avoid decimals like 200.0
    if '*Code' in coa.columns:
        original_codes=coa['*Code'].astype(str).tolist()
        coerced_codes=[]
        for i,ov in enumerate(original_codes):
            s=str(ov).strip()
            if re.fullmatch(r"(\d+)\.0+", s):
                new=s.split('.',1)[0]
                change_rows.append({'RowNumber': i+2,'FieldName':'Code','OriginalValue': ov,'CorrectedValue': new,'IssueType':'DecimalCode','Notes':'Converted decimal to integer'})
                coerced_codes.append(new)
            else:
                coerced_codes.append(s)
        coa['*Code']=pd.Series(coerced_codes, dtype='string')

    # Build expected head mapping for all client codes using template-driven inference
    try:
        infer_expected_head = _infer_expected_head_lookup(defaultchart, tree)
    except Exception as e:
        sys.exit(f"Error: Failed to initialize expected head inference: {e}")
    expected_head_by_code={}
    for _, r in coa.iterrows():
        code_val=str(r.get('*Code','') or '').strip()
        if code_val and code_val not in expected_head_by_code:
            expected_head_by_code[code_val]=infer_expected_head(code_val)

    spell_log = []
    for idx,row in coa.iterrows():
        existing=str(row['Report Code']).strip() if pd.notnull(row['Report Code']) else ''
        _raw_name = row['*Name']
        _spell_result = correct_account_name(strip_noise_suffixes(_raw_name), spell=spell_checker)
        _corrected_name = _spell_result["corrected"]
        if _spell_result["corrections"]:
            spell_log.append({"idx": idx, "code": row.get("*Code", ""), "original": _raw_name, "corrected": _corrected_name, "corrections": _spell_result["corrections"]})
        clean_nm=normalise(_corrected_name)
        canon_type=canonical_type(row['*Type'])
        head=existing.split('.')[0] if existing else head_from_type(row['*Type'])
        chosen='';reason='';flag=''
        txt_inline=normalise(f"{row['*Name']} {row.get('Description','')}")

        # Define t for use by later steps (7c borrowing costs, etc.)
        t=row['*Type'].strip().lower()

        # 1) DefaultChart Code match (guarded by head and some name similarity)
        if not chosen:
            code_key=str(row['*Code']).strip()
            if code_key in default_by_code and default_by_code[code_key]['reporting_code']:
                candidate=default_by_code[code_key]
                # If this is clearly a direct cost like Subcontractors or Equipment Hire under Direct Costs, prefer EXP.COS
                if candidate['reporting_code']=='EXP' and row['*Type'].strip().lower() in {'direct costs','cost of sales','purchases'} and ('subcontract' in clean_nm or 'equipment hire' in clean_nm or 'hire' in clean_nm):
                    chosen,reason='EXP.COS','DefaultChart'
                elif candidate['head']==head:
                    nm_sim=similarity(clean_nm, candidate['clean_name'])
                    if nm_sim>=0.60:
                        chosen,reason=candidate['reporting_code'],'DefaultChart'
        # 2) Exact (cleaned-name + canonical-type) match in DefaultChart within same head
        if not chosen and (clean_nm, canon_type) in dict_name_type and dict_name_type[(clean_nm,canon_type)]:
            if head==dict_name_type[(clean_nm,canon_type)].split('.')[0]:
                chosen,reason=dict_name_type[(clean_nm,canon_type)],'DefaultChart'

        # 3) Rule engine: declarative keyword rules
        if not chosen:
            ctx = MatchContext(
                normalised_text=txt_inline,
                normalised_name=clean_nm,
                raw_type=row['*Type'].strip(),
                canon_type=canon_type,
                template_name=str(args.chart_template_name or ''),
                owner_keywords=_OWNER_KEYWORDS,
                industry=normalise_industry(str(args.industry or '')),
            )
            rc, rule_name = evaluate_rules(ALL_RULES, ctx)
            if rc:
                chosen, reason = rc, rule_name

        # 3b) Accumulated depreciation/amortisation name-based resolution (before code-based matching)
        if not chosen:
            base_key = extract_accum_base_key(row['*Name'])
            if base_key:
                rc_acc = accum_base_to_rc.get(base_key)
                if not rc_acc:
                    base_rc = name_to_predicted_rc.get(base_key)
                    if base_rc and not base_rc.endswith(('.ACC','.AMO')):
                        rc_acc = base_rc + '.ACC'
                if rc_acc:
                    chosen,reason = rc_acc, 'AccumulatedDepreciationRule'
        # 4) Exact cleaned-Name in SystemMappings (with pre-hyphen trimming on raw name)
        #    Guard: skip if the matched code's root head conflicts with the account type.
        if not chosen:
            raw_name = strip_noise_suffixes(row['*Name'])
            prefix_raw = str(raw_name).split(' - ')[0]
            pre_hyphen = normalise(prefix_raw)
            _dm_code = name_to_leaf.get(pre_hyphen) or name_to_leaf.get(clean_nm)
            if _dm_code:
                _dm_root = _dm_code.split('.')[0]
                _type_root = head_from_type(row['*Type']).split('.')[0]
                if _dm_root == _type_root:
                    chosen,reason=_dm_code,'DirectNameMatch'
        # 4b) If name matches a SystemMappings non-leaf and existing code equals that mapping, keep it
        if not chosen:
            raw_name = strip_noise_suffixes(row['*Name'])
            prefix_raw = str(raw_name).split(' - ')[0]
            pre_hyphen = normalise(prefix_raw)
            existing=str(row['Report Code']).strip() if pd.notnull(row['Report Code']) else ''
            mapped_any = name_to_any.get(pre_hyphen) or name_to_any.get(clean_nm)
            if mapped_any and existing and existing == mapped_any:
                chosen,reason=existing,'ExistingCodeValidByName'
        # 5) Accept existing client leaf (but don't undo stronger direct-cost signals)
        if not chosen and existing in leaf_set:
            # If the name clearly indicates subcontractors/equipment hire and type is a direct cost, prefer EXP.COS
            if (('subcontract' in clean_nm) or ('equipment hire' in clean_nm) or ('hire' in clean_nm)) and row['*Type'].strip().lower() in {'direct costs','cost of sales','purchases'}:
                pass
            else:
                chosen,reason=existing,'AlreadyCorrect'
        # 6) If existing code appears in DefaultChart (prefer leaf-only)
        if not chosen and existing and existing in [r['Reporting Code'] for _,r in defaultchart.iterrows()] and existing in leaf_set:
            # Respect direct-cost intent for subcontractors/equipment hire
            direct_cost_intent = (('subcontract' in clean_nm) or ('equipment hire' in clean_nm) or ('hire' in clean_nm)) and row['*Type'].strip().lower() in {'direct costs','cost of sales','purchases'}
            # Respect motor-vehicle expense intent: require MV token + expense token (expense-only)
            mv_intent = False
            if canon_type=='expense':
                mv_has = any(term in clean_nm for term in VEHICLE_TOKENS)
                mv_exp_has = any(term in clean_nm for term in VEHICLE_EXPENSE_TOKENS) or any(k in clean_nm for k in ['interest','insurance','rego','registration','ctp'])
                if mv_has and mv_exp_has and 'deprec' not in clean_nm:
                    mv_intent = True
            if direct_cost_intent or mv_intent:
                pass
            else:
                chosen,reason=existing,'ExistingCodeValid'

        # 7b) Accumulated depreciation/amortisation name-based resolution
        if not chosen:
            base_key = extract_accum_base_key(row['*Name'])
            if base_key:
                # First try template-derived .ACC/.AMO reporting code for this base
                rc_acc = accum_base_to_rc.get(base_key)
                if not rc_acc:
                    # If missing, try pairing with previously predicted base rc then append .ACC
                    base_rc = name_to_predicted_rc.get(base_key)
                    if base_rc and not base_rc.endswith(('.ACC','.AMO')):
                        rc_acc = base_rc + '.ACC'
                if rc_acc:
                    chosen,reason = rc_acc, 'AccumulatedDepreciationRule'

        # 7c) Specific special-cases from audit
        if not chosen:
            # Borrowing Costs → Prepayments (current asset)
            if ('borrowing costs' in txt_inline) and t in {'current asset'}:
                chosen,reason='ASS.CUR.REC.PRE','KeywordRule'

        if not chosen:
            # Prefer exact-ish match on names when both contain key tokens like accumulated/depreciation
            # Boost similarity when both sides include any ACC_TOKENS, to avoid mismatching to wrong base
            best_rc,best_sc='',0
            for rc,nm in head_to_leaves[head]:
                nm_norm = normalise(nm)
                sc=similarity(clean_nm, nm_norm)
                clean_has_acc = any(tok in clean_nm for tok in DEPRECIATION_TOKENS)
                nm_has_acc = any(tok in nm_norm for tok in DEPRECIATION_TOKENS)
                if clean_has_acc and nm_has_acc:
                    sc = sc + 0.1  # gentle boost
                # Additional check: avoid false fuzzy matches
                if sc>best_sc and sc >= 0.75:
                    clean_nm_words = set(clean_nm.split())
                    nm_words = set(nm_norm.split())
                    if len(clean_nm_words.intersection(nm_words)) > 0:
                        best_rc,best_sc=rc,sc
            if best_sc>=0.75:
                chosen,reason=best_rc,'FuzzyMatch'

        if not chosen:
            chosen,reason,flag=head,'FallbackParent','Y'

        # Cross-head guard: prevent reclassification across incompatible type groups
        # P&L (REV,EXP) can cross within; BS (ASS,LIA) can cross within; EQ never crosses
        if chosen and reason not in _CROSS_HEAD_SKIP_SOURCES:
            acct_group = _head_group(head_from_type(row['*Type']))
            chosen_group = _head_group(chosen)
            if acct_group and chosen_group and acct_group != chosen_group:
                original = chosen
                # Revert to original code if it belongs to the correct group
                if existing and _head_group(existing) == acct_group and existing in leaf_set:
                    chosen, reason = existing, 'CrossHeadGuard'
                else:
                    # Fall back to head-only code from account type
                    chosen = head_from_type(row['*Type'])
                    reason = 'CrossHeadGuard'
                flag = 'Y'
                change_rows.append({'RowNumber': idx+2, 'FieldName': 'predictedReportCode',
                    'OriginalValue': original, 'CorrectedValue': chosen,
                    'IssueType': 'CrossHeadViolation',
                    'Notes': f'Group {chosen_group} from {original} vs account group {acct_group}'})

        # Enforce head consistency using ranges/type
        exp_head=expected_head_by_code.get(str(row.get('*Code','')).strip(),'') if expected_head_by_code else ''
        type_head=head_from_type(row['*Type'])
        if not exp_head:
            exp_head=type_head
        elif type_head and exp_head.split('.')[0] != type_head.split('.')[0]:
            # Template code-range head disagrees with account type at broadest level
            # (e.g., template says LIA range but type is Equity → EQU).  Trust the type.
            exp_head=type_head
        chosen_head = chosen.split('.')[0] if chosen else ''
        if exp_head and chosen_head and exp_head!=chosen_head:
            original=chosen
            if chosen in {'ASS','EXP','REV','LIA','EQU'} or reason=='FallbackParent':
                chosen=exp_head
                reason='TypeRangeCorrection'
                flag='Y'
                change_rows.append({'RowNumber': idx+2,'FieldName':'predictedReportCode','OriginalValue': original,'CorrectedValue': chosen,'IssueType':'TypeRangeMismatch','Notes': f'Corrected head to {exp_head} from {chosen_head}'})
            else:
                flag='Y'
                change_rows.append({'RowNumber': idx+2,'FieldName':'predictedReportCode','OriginalValue': original,'CorrectedValue': original,'IssueType':'TypeRangeMismatch','Notes': f'Predicted head {chosen_head} vs expected {exp_head}'})

        # Audited override handling (optional columns): if 'CorrectCode' exists and is populated, override
        # our chosen code with the audited value and record a clarification. This occurs after all heuristics
        # so that professional judgment always wins.
        if 'CorrectCode' in coa.columns:
            cc_val = row.get('CorrectCode')
            if pd.notnull(cc_val) and str(cc_val).strip() != '':
                prior_code = chosen
                chosen = str(cc_val).strip()
                reason = 'UserClarified'
                flag = ''
                overridden_indices.add(idx)
                clarifications.append({
                    'AccountCode': row.get('*Code'),
                    'PriorReportCode': prior_code,
                    'NewReportCode': chosen,
                    'UserComment': str(row.get('CorrectReason', '')) if 'CorrectReason' in coa.columns else ''
                })

        # Final guard: reject invalid report codes not present in allowed list
        if chosen and (chosen not in allowed_codes):
            flag = 'Y'
            src_reason = 'InvalidCodeRejected'
            # try fallback to head if valid, else blank for review
            head_fallback = chosen.split('.')[0]
            chosen = head_fallback if head_fallback in allowed_codes else ''
            reason = src_reason

        prc.append(chosen)
        map_name=sysmap.loc[sysmap['Reporting Code']==chosen,'Name']
        pname.append(map_name.iloc[0] if not map_name.empty else '')
        need.append(flag)
        src.append(reason)
        
        # Store the current row info for the next iteration
        previous_processed_row = {
            'predictedReportCode': chosen,
            'Name': row['*Name'],
            'Type': row['*Type'],
            'Code': row['*Code']
        }
        name_to_predicted_rc[clean_nm]=chosen

    # Second pass: strengthen accumulated depreciation pairing by name lookup
    for idx,row in coa.iterrows():
        if idx in overridden_indices:
            continue
        txt_full = normalise(str(row['*Name']))
        if not ('deprec' in txt_full or 'amort' in txt_full):
            continue
        # Use extract_accum_base_key for robust base extraction (handles colon-format too)
        base_name = extract_accum_base_key(row['*Name'])
        if not base_name:
            # Fallback: original "on" split for "Less ... on <base>" format
            if txt_full.startswith('less'):
                parts = re.split(r'\bon\b', txt_full)
                base_name = parts[-1].strip() if len(parts)>1 else ''
        if base_name:
            base_rc = name_to_predicted_rc.get(base_name)
            if base_rc and not base_rc.endswith(('.ACC', '.AMO')) and str(prc[idx]) != base_rc + '.ACC':
                prc[idx] = base_rc + '.ACC'
                src[idx] = 'AccumulatedDepreciationRule'
                map_name=sysmap.loc[sysmap['Reporting Code']==prc[idx],'Name']
                if not map_name.empty:
                    pname[idx]=map_name.iloc[0]

    # Pass 2.5: Cross-account context inference
    # Uses active trial balance balances + chart structure to refine head-only fallbacks
    _context_accounts = []
    for idx, row in coa.iterrows():
        _context_accounts.append({
            "code": str(row.get("*Code", "")).strip(),
            "name": str(row.get("*Name", "")),
            "type": str(row.get("*Type", "")),
            "predicted": prc[idx] if isinstance(prc[idx], str) else "",
            "source": src[idx] if isinstance(src[idx], str) else "",
        })

    _context_results = infer_from_context(_context_accounts, bal_lookup, overridden_indices)
    for cr in _context_results:
        i = cr["index"]
        prc[i] = cr["inferred_code"]
        src[i] = cr["reason"]
        need[i] = "Y"  # Still flag for human review

    # Pass 2.6: Section inference from neighbours
    # Re-read predicted codes after anchor inference may have changed them
    for idx in range(len(_context_accounts)):
        _context_accounts[idx]["predicted"] = prc[idx] if isinstance(prc[idx], str) else ""
    _section_results = infer_section(_context_accounts, bal_lookup, overridden_indices)
    for sr in _section_results:
        i = sr["index"]
        # Only apply if anchor inference didn't already refine this account
        if prc[i] in {"ASS", "EXP", "REV", "LIA", "EQU"}:
            prc[i] = sr["inferred_code"]
            src[i] = sr["reason"]
            need[i] = "Y"

    # Third pass: if revenue is service-only (only REV.TRA.SER appears within REV.TRA.*),
    # then reclass any EXP.COS* to EXP, as COGS should not exist for pure service revenue.
    rev_tra_codes={}
    for rc in prc:
        if isinstance(rc, str) and rc.startswith('REV.TRA'):
            rev_tra_codes[rc]=True
    unique_rev_tra=set([rc for rc in rev_tra_codes.keys()])
    # Disable ServiceOnly reclass for Construction industry per instruction
    _norm_industry = normalise_industry(str(args.industry or ''))
    service_only = (_norm_industry != 'construction') and bool(unique_rev_tra) and (not direct_cost_nonzero)
    if service_only:
        for i, rc in enumerate(prc):
            if isinstance(rc, str) and (rc=='EXP.COS' or rc.startswith('EXP.COS.')):
                original=rc
                prc[i] = 'EXP'
                src[i] = 'ServiceOnlyRevenueAdjustment'
                need[i] = 'Y'
                change_rows.append({
                    'RowNumber': i+2,
                    'FieldName': 'predictedReportCode',
                    'OriginalValue': original,
                    'CorrectedValue': prc[i],
                    'IssueType': 'ServiceOnlyCOGSReclass',
                    'Notes': 'COGS not applicable when only service revenue (REV.TRA.SER) exists; moved to EXP'
                })

    coa['predictedReportCode']=prc
    coa['predictedMappingName']=pname
    coa['NeedsReview']=need
    coa['Source']=src

    # Add corrected names column (only populated when corrections applied)
    corrected_names = [""] * len(coa)
    for entry in spell_log:
        corrected_names[entry["idx"]] = entry["corrected"]
    coa['CorrectedName'] = corrected_names

    # HasBalance: 'Y' if trial balance shows activity, else 'N'
    has_balance = []
    for _, row in coa.iterrows():
        acct_code = str(row.get('*Code', '')).strip()
        bal = bal_lookup.get(acct_code, 0)
        has_balance.append('Y' if abs(float(bal or 0)) > 0.01 else 'N')
    coa['HasBalance'] = has_balance

    out=client_chart_path.with_name('AugmentedChartOfAccounts.csv')
    try:
        coa.to_csv(out,index=False)
    except PermissionError:
        # Safe fallback: write timestamped file to avoid lock issues
        ts = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
        out_fallback = client_chart_path.with_name(f'AugmentedChartOfAccounts.{ts}.csv')
        coa.to_csv(out_fallback, index=False)
        out = out_fallback

    # Emit clarification log if any audited overrides were applied
    if clarifications:
        import pandas as _pd
        _pd.DataFrame(clarifications, columns=['AccountCode','PriorReportCode','NewReportCode','UserComment']).to_csv(
            client_chart_path.with_name('ClarificationLog.csv'), index=False
        )

    # Add spell corrections to change report
    for entry in spell_log:
        change_rows.append({
            "RowNumber": entry["idx"] + 1,
            "FieldName": "*Name",
            "OriginalValue": entry["original"],
            "CorrectedValue": entry["corrected"],
            "IssueType": "SpellCorrection",
            "Notes": "; ".join(f"{c['original']}->{c['corrected']} ({c['source']})" for c in entry["corrections"]),
        })

    # Emit change/error report if any
    if change_rows:
        report_path=client_chart_path.with_name('ChangeOrErrorReport.csv')
        cols=['RowNumber','FieldName','OriginalValue','CorrectedValue','IssueType','Notes']
        with report_path.open('w', newline='', encoding='utf-8') as f:
            w=csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
            w.writeheader()
            for r in change_rows:
                w.writerow(r)

    # Use ASCII-only arrow for Windows console safety
    print(f"Saved -> {out}")

if __name__=='__main__':
    ap=argparse.ArgumentParser(description='Reporting Code Mapper')
    ap.add_argument('client_chart', metavar='client_chart', help='Path to client ChartOfAccounts CSV/XLSX')
    ap.add_argument('client_trialbalance', metavar='client_trialbalance', help='Path to client TrialBalance CSV/XLSX')
    ap.add_argument('--chart', dest='chart_template_name', metavar='CHARTNAME', required=True,
                    help='Template name in ChartOfAccounts/ (filename without extension), e.g. Company, Trust, SoleTrader, Partnership, XeroHandi')
    ap.add_argument('--industry', default='', help='Optional industry context, e.g. "Building & Construction"')
    ap.add_argument('--validate-only', action='store_true', help='Only run integrity validation, do not perform mapping')
    main(ap.parse_args())
    # Flush sentinel to signal completion
    print("", flush=True)
