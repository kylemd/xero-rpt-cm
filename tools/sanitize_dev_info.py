"""
Comprehensive sanitization script for .dev-info/old_codebases.

Phases:
  1. Collect all unique Xero shortCodes and build a deterministic mapping
  2. Rename files (shortCodes in filenames -> anonymous IDs)
  3. Replace shortCodes inside file contents
  4. Sanitize PII inside CSV contents (owner names, vehicles, business names, etc.)
  5. Handle special cases (Garden_Life_Pty_Ltd, Kyle Drayton, etc.)

Usage:
  python tools/sanitize_dev_info.py --dry-run   # Preview changes
  python tools/sanitize_dev_info.py              # Execute changes
"""

import argparse
import csv
import io
import re
import sys
from pathlib import Path


# --- Configuration -----------------------------------------------------------

BASE = Path(__file__).resolve().parent.parent / ".dev-info" / "old-codebases"
DATA_ANALYSIS = BASE / "Report Code Mapping - Data Analysis"
OLD_CODEBASE = BASE / "Report Code Mapping - Old"

BULK_CSV_DIRS = [
    OLD_CODEBASE / "all-chart-of-accounts",
    DATA_ANALYSIS / "client-live-chart-of-accounts",
]

TEXT_EXTENSIONS = {".py", ".md", ".csv", ".json", ".txt", ".yaml", ".yml", ".toml", ".html", ".mdc"}


# --- PII Detection Patterns --------------------------------------------------

VEHICLE_MAKES = [
    "Ford", "Toyota", "Holden", "Mazda", "Mitsubishi", "Nissan",
    "Hyundai", "BMW", "Mercedes", "Isuzu", "Kia", "Subaru",
    "Volkswagen", "VW", "Audi", "Suzuki", "Honda", "Lexus",
    "Land Rover", "Range Rover", "Jeep", "Volvo", "Peugeot",
    "Renault", "Fiat", "Tesla", "BYD", "GWM", "LDV",
]
VEHICLE_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(m) for m in VEHICLE_MAKES) + r')\b',
    re.IGNORECASE,
)

INSURANCE_BRANDS = [
    "Hunter Insurance", "Allianz", "QBE", "CGU", "NRMA",
    "AAMI", "Zurich", "AIG", "Vero", "Chubb", "Berkshire",
    "Latitude", "Prospa", "Scottish Pacific", "Judo",
]
INSURANCE_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(b) for b in INSURANCE_BRANDS) + r')\b',
    re.IGNORECASE,
)

BUSINESS_SUFFIX_PATTERN = re.compile(
    r'(.+?)\s*\b(Pty\.?\s*Ltd\.?|Trust|LLC|Inc\.?|Corp\.?|Partnership|P/L)\b',
    re.IGNORECASE,
)

DOLLAR_AMOUNT_PATTERN = re.compile(r'\$[\d,]+\.?\d*')

OWNER_NAME_PATTERN = re.compile(
    r'((?:Owner|Partner|Director|Shareholder|Proprietor|Beneficiary|Trustee)'
    r'(?:\s+\w+)?\s*[-\u2013:]\s*)(.+)',
    re.IGNORECASE,
)

DISTRIBUTION_NAME_PATTERN = re.compile(
    r'((?:Distribution of Profit|Share of Profit|Physical Distribution|'
    r'Opening Balance[s]?|Loan|Funds Introduced|Capital Contributed|'
    r'Dividends Paid|Dividends Payable|Drawings|'
    r'Wages (?:&|and) Salaries|Superannuation|Retained Earnings|'
    r'Current Account|Directors Loan|Shareholder Loan|'
    r'Members Equity|Unit Holder)'
    r'\s*[-\u2013:]\s*)(.+)',
    re.IGNORECASE,
)


# --- Phase 1: ShortCode Collection -------------------------------------------

def collect_shortcodes() -> dict[str, str]:
    """Collect all unique shortCodes and build a deterministic mapping."""
    shortcodes = set()

    # From bulk CSV directories: {shortCode}_ChartOfAccounts*.csv
    for d in BULK_CSV_DIRS:
        if not d.exists():
            continue
        for f in d.iterdir():
            if f.suffix == ".csv":
                m = re.match(r'^(.+?)_ChartOfAccounts', f.name)
                if m:
                    shortcodes.add(m.group(1))

    # From root-level files in Data Analysis
    if DATA_ANALYSIS.exists():
        for f in DATA_ANALYSIS.iterdir():
            if f.is_file():
                m = re.match(r'^(.+?)_ChartOfAccounts', f.name)
                if m and m.group(1) not in ("ChartOfAccounts",):
                    shortcodes.add(m.group(1))

                for prefix in ("process_", "validate_", "create_final_output_",
                               "apply_validations_", "PROCESSING_SUMMARY_"):
                    if f.name.startswith(prefix):
                        stem = f.stem[len(prefix):]
                        if stem and stem != "ChartOfAccounts_38":
                            shortcodes.add(stem)

        # From output/ directory
        output_dir = DATA_ANALYSIS / "output"
        if output_dir.exists():
            for f in output_dir.iterdir():
                if f.is_file():
                    for prefix in ("alignment_", "template_", "tax_code_issues_",
                                   "tax_code_corrections_", "tax_code_lookup_",
                                   "validation_suggestions_", "validation_summary_"):
                        if f.name.startswith(prefix):
                            stem = f.stem[len(prefix):]
                            if stem and stem not in ("mismatches", "ChartOfAccounts_38"):
                                shortcodes.add(stem)
                    m = re.match(r'^(.+?)_validated_final', f.name)
                    if m:
                        shortcodes.add(m.group(1))

        # From reference/labels/templates/
        ref_dir = DATA_ANALYSIS / "reference" / "labels" / "templates"
        if ref_dir.exists():
            for f in ref_dir.iterdir():
                m = re.match(r'^company_label_template_([A-Za-z0-9_-]+?)(?:_validated)?\.', f.name)
                if m:
                    code = m.group(1)
                    if not re.match(r'^[\dTZ]+$', code):
                        shortcodes.add(code)

    # Filter out false extractions: real Xero shortCodes are 4-5 chars
    # (allow 6 for edge cases like "HD y99" with a space in the filename)
    MAX_SHORTCODE_LEN = 6
    false_extractions = {c for c in shortcodes if len(c) > MAX_SHORTCODE_LEN}
    if false_extractions:
        print(f"  Filtered {len(false_extractions)} false extractions: {sorted(false_extractions)}")
        shortcodes -= false_extractions

    # Build deterministic sorted mapping
    sorted_codes = sorted(shortcodes)
    mapping = {}
    for i, code in enumerate(sorted_codes, start=1):
        mapping[code] = f"client_{i:03d}"
    return mapping


# --- Phase 2 & 3: Safe File Renaming and Content Replacement -----------------
#
# KEY FIX: Instead of str.replace() which matches substrings, we use structured
# replacement that only replaces shortCodes where they appear as complete tokens
# bounded by delimiters (_, start/end of string, path separators, quotes, etc.)

def build_shortcode_regex(shortcode_map: dict[str, str]) -> re.Pattern:
    """Build a single regex that matches any shortCode as a complete token.

    ShortCodes in this codebase appear in specific contexts:
    - As filename prefixes: {code}_ChartOfAccounts...
    - After known prefixes: process_{code}, validate_{code}, etc.
    - In string literals in Python: '{code}', "{code}"
    - In CSV/text content surrounded by delimiters

    We use word-boundary-like logic: the shortCode must be bounded by
    non-alphanumeric characters (or start/end of string).
    """
    # Sort longest first to prefer longer matches
    codes = sorted(shortcode_map.keys(), key=len, reverse=True)
    escaped = [re.escape(c) for c in codes]
    # Match shortCode only when surrounded by non-alphanumeric boundaries
    # (but allow - since some shortCodes start/end with -)
    pattern = r'(?<![A-Za-z0-9])(' + '|'.join(escaped) + r')(?![A-Za-z0-9])'
    return re.compile(pattern)


def rename_file_safe(old_path: Path, shortcode_map: dict[str, str],
                     sc_regex: re.Pattern, dry_run: bool) -> Path:
    """Rename a file using regex-based shortCode replacement (no substring issues)."""
    new_name = sc_regex.sub(lambda m: shortcode_map[m.group(1)], old_path.name)

    if new_name != old_path.name:
        new_path = old_path.parent / new_name
        if dry_run:
            print(f"  RENAME: {old_path.name} -> {new_name}")
        else:
            old_path.rename(new_path)
        return new_path
    return old_path


def replace_shortcodes_safe(content: str, shortcode_map: dict[str, str],
                            sc_regex: re.Pattern) -> str:
    """Replace shortCodes in text using regex (no substring matching)."""
    return sc_regex.sub(lambda m: shortcode_map[m.group(1)], content)


def process_text_file_shortcodes(path: Path, shortcode_map: dict[str, str],
                                 sc_regex: re.Pattern, dry_run: bool) -> int:
    """Replace shortCodes inside a text file. Returns count of replacements."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return 0

    new_content = replace_shortcodes_safe(content, shortcode_map, sc_regex)
    if new_content != content:
        changes = len(sc_regex.findall(content))
        if dry_run:
            print(f"  CONTENT: {path.name} ({changes} shortCode replacements)")
        else:
            path.write_text(new_content, encoding="utf-8")
        return changes
    return 0


# --- Phase 4: CSV PII Sanitization -------------------------------------------

_vehicle_counter = 0
_business_counter = 0
_person_counter = 0
_insurance_counter = 0

_vehicle_cache: dict[str, str] = {}
_business_cache: dict[str, str] = {}
_person_cache: dict[str, str] = {}
_insurance_cache: dict[str, str] = {}


def reset_pii_counters():
    global _vehicle_cache, _business_cache, _person_cache, _insurance_cache
    _vehicle_cache = {}
    _business_cache = {}
    _person_cache = {}
    _insurance_cache = {}


def get_vehicle_replacement(original: str) -> str:
    global _vehicle_counter
    key = original.strip().lower()
    if key not in _vehicle_cache:
        _vehicle_counter += 1
        _vehicle_cache[key] = f"Vehicle {_vehicle_counter}"
    return _vehicle_cache[key]


def get_business_replacement(original: str) -> str:
    global _business_counter
    key = original.strip().lower()
    if key not in _business_cache:
        _business_counter += 1
        _business_cache[key] = f"Entity {_business_counter}"
    return _business_cache[key]


def get_person_replacement(original: str) -> str:
    global _person_counter
    key = original.strip().lower()
    if key not in _person_cache:
        _person_counter += 1
        _person_cache[key] = f"Person {_person_counter}"
    return _person_cache[key]


def get_insurance_replacement(original: str) -> str:
    global _insurance_counter
    key = original.strip().lower()
    if key not in _insurance_cache:
        _insurance_counter += 1
        _insurance_cache[key] = f"Insurer {_insurance_counter}"
    return _insurance_cache[key]


def sanitize_account_name(name: str) -> tuple[str, list[str]]:
    """Sanitize a single account name field."""
    if not name or not name.strip():
        return name, []

    original = name
    changes = []

    # 1. Business names (Pty Ltd, Trust, etc.)
    m = BUSINESS_SUFFIX_PATTERN.search(name)
    if m:
        biz_name = m.group(0)
        replacement = get_business_replacement(biz_name)
        name = name.replace(biz_name, replacement)
        changes.append(f"business: '{biz_name}' -> '{replacement}'")

    # 2. Owner/partner/director names
    m = OWNER_NAME_PATTERN.match(name)
    if m:
        prefix = m.group(1)
        person_name = m.group(2).strip()
        if person_name and not re.match(r'^[A-B\d]$|^Partner\s+\d+$|^Owner\s+[A-Z]$', person_name, re.I):
            replacement = get_person_replacement(person_name)
            name = prefix + replacement
            changes.append(f"person: '{person_name}' -> '{replacement}'")

    # 3. Distribution/loan names
    if not changes:
        m = DISTRIBUTION_NAME_PATTERN.match(name)
        if m:
            prefix = m.group(1)
            entity_name = m.group(2).strip()
            if entity_name and len(entity_name) > 2:
                if BUSINESS_SUFFIX_PATTERN.search(entity_name):
                    replacement = get_business_replacement(entity_name)
                else:
                    replacement = get_person_replacement(entity_name)
                name = prefix + replacement
                changes.append(f"entity: '{entity_name}' -> '{replacement}'")

    # 4. Vehicle references
    if VEHICLE_PATTERN.search(name) and not changes:
        vehicle_desc = name
        for sep in [' - ', ' \u2013 ', ': ']:
            if sep in name:
                parts = name.split(sep, 1)
                if VEHICLE_PATTERN.search(parts[1]):
                    vehicle_desc = parts[1].strip()
                    replacement = get_vehicle_replacement(vehicle_desc)
                    name = parts[0] + sep + replacement
                    changes.append(f"vehicle: '{vehicle_desc}' -> '{replacement}'")
                    break
                elif VEHICLE_PATTERN.search(parts[0]) and not VEHICLE_PATTERN.search(parts[1]):
                    vehicle_desc = parts[0].strip()
                    replacement = get_vehicle_replacement(vehicle_desc)
                    name = replacement + sep + parts[1]
                    changes.append(f"vehicle: '{vehicle_desc}' -> '{replacement}'")
                    break
        else:
            if VEHICLE_PATTERN.search(name) and not changes:
                replacement = get_vehicle_replacement(name)
                changes.append(f"vehicle: '{name}' -> '{replacement}'")
                name = replacement

    # 5. Insurance company names
    if INSURANCE_PATTERN.search(name) and not changes:
        ins_desc = name
        for sep in [' - ', ' \u2013 ', ': ']:
            if sep in name:
                parts = name.split(sep, 1)
                if INSURANCE_PATTERN.search(parts[1]):
                    ins_desc = parts[1].strip()
                    replacement = get_insurance_replacement(ins_desc)
                    name = parts[0] + sep + replacement
                    changes.append(f"insurance: '{ins_desc}' -> '{replacement}'")
                    break
                elif INSURANCE_PATTERN.search(parts[0]):
                    ins_desc = parts[0].strip()
                    replacement = get_insurance_replacement(ins_desc)
                    name = replacement + sep + parts[1]
                    changes.append(f"insurance: '{ins_desc}' -> '{replacement}'")
                    break
        else:
            replacement = get_insurance_replacement(name)
            changes.append(f"insurance: '{name}' -> '{replacement}'")
            name = replacement

    return name, changes


def sanitize_description(desc: str) -> tuple[str, list[str]]:
    """Sanitize a description field."""
    if not desc or not desc.strip():
        return desc, []

    changes = []

    if DOLLAR_AMOUNT_PATTERN.search(desc):
        new_desc = DOLLAR_AMOUNT_PATTERN.sub("[amount]", desc)
        if new_desc != desc:
            changes.append("amount: redacted in description")
            desc = new_desc

    m = BUSINESS_SUFFIX_PATTERN.search(desc)
    if m:
        biz = m.group(0)
        replacement = get_business_replacement(biz)
        desc = desc.replace(biz, replacement)
        changes.append(f"business in desc: '{biz}' -> '{replacement}'")

    return desc, changes


def sanitize_csv_file(path: Path, dry_run: bool) -> int:
    """Sanitize PII in a chart of accounts CSV."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"  ERROR reading {path}: {e}")
        return 0

    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        return 0

    header = rows[0]
    name_col = None
    reporting_name_col = None
    desc_col = None

    for i, h in enumerate(header):
        h_lower = h.strip().lower().replace("*", "")
        if h_lower == "name":
            name_col = i
        elif h_lower == "reporting name":
            reporting_name_col = i
        elif h_lower == "description":
            desc_col = i

    if name_col is None:
        return 0

    total_changes = 0
    all_changes = []

    for row_idx in range(1, len(rows)):
        row = rows[row_idx]
        if not row or len(row) <= name_col:
            continue

        old_name = row[name_col]
        new_name, changes = sanitize_account_name(old_name)
        if changes:
            row[name_col] = new_name
            total_changes += len(changes)
            all_changes.extend(changes)

        if reporting_name_col is not None and len(row) > reporting_name_col:
            old_rname = row[reporting_name_col]
            new_rname, rchanges = sanitize_account_name(old_rname)
            if rchanges:
                row[reporting_name_col] = new_rname
                total_changes += len(rchanges)

        if desc_col is not None and len(row) > desc_col:
            old_desc = row[desc_col]
            new_desc, dchanges = sanitize_description(old_desc)
            if dchanges:
                row[desc_col] = new_desc
                total_changes += len(dchanges)
                all_changes.extend(dchanges)

    if total_changes > 0:
        if dry_run:
            print(f"  PII: {path.name} ({total_changes} changes)")
            for c in all_changes[:10]:
                print(f"        {c}")
            if len(all_changes) > 10:
                print(f"        ... and {len(all_changes) - 10} more")
        else:
            output = io.StringIO()
            writer = csv.writer(output, lineterminator="\n")
            writer.writerows(rows)
            path.write_text(output.getvalue(), encoding="utf-8")

    return total_changes


# --- Phase 5: Special Cases ---------------------------------------------------

def handle_special_cases(dry_run: bool) -> int:
    changes = 0

    # 1. Garden_Life_Pty_Ltd in filename
    garden_life_file = DATA_ANALYSIS / "Garden_Life_Pty_Ltd_-_Trial_Balance_20251201.xlsx"
    if garden_life_file.exists():
        new_name = "Sample_Company_-_Trial_Balance_20251201.xlsx"
        new_path = garden_life_file.parent / new_name
        if dry_run:
            print(f"  SPECIAL: {garden_life_file.name} -> {new_name}")
        else:
            garden_life_file.rename(new_path)
        changes += 1

    # Replace "Garden Life" / "Garden_Life_Pty_Ltd" in file contents (case-insensitive)
    garden_regex = re.compile(r'Garden[_ ]Life(?:[_ ]Pty[_ ]Ltd)?', re.IGNORECASE)
    for root_dir in [DATA_ANALYSIS, OLD_CODEBASE]:
        if not root_dir.exists():
            continue
        for f in root_dir.rglob("*"):
            if f.is_file() and f.suffix in TEXT_EXTENSIONS and ".venv" not in str(f):
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    new_content = garden_regex.sub("Sample_Company", content)
                    if new_content != content:
                        if dry_run:
                            print(f"  SPECIAL: Replaced 'Garden Life' references in {f.name}")
                        else:
                            f.write_text(new_content, encoding="utf-8")
                        changes += 1
                except Exception:
                    pass

    # 2. Kyle Drayton in Old codebase prompts
    old_prompt = OLD_CODEBASE / "prompts" / "python-web-version_XeroMapper.md"
    if old_prompt.exists():
        try:
            content = old_prompt.read_text(encoding="utf-8", errors="replace")
            new_content = content.replace("Kyle Drayton", "[Redacted]")
            if new_content != content:
                if dry_run:
                    print(f"  SPECIAL: Replaced 'Kyle Drayton' in {old_prompt.name}")
                else:
                    old_prompt.write_text(new_content, encoding="utf-8")
                changes += 1
        except Exception:
            pass

    # Hardcoded paths
    old_expert = OLD_CODEBASE / "prompts" / "python_expert.md"
    if old_expert.exists():
        try:
            content = old_expert.read_text(encoding="utf-8", errors="replace")
            new_content = re.sub(
                r'C:\\Users\\KyleDrayton\\[^\s`]+',
                'ReportCodeMapping',
                content,
            )
            if new_content != content:
                if dry_run:
                    print(f"  SPECIAL: Replaced hardcoded paths in {old_expert.name}")
                else:
                    old_expert.write_text(new_content, encoding="utf-8")
                changes += 1
        except Exception:
            pass

    return changes


# --- Main Orchestrator --------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Sanitize .dev-info old codebases")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without modifying files")
    args = parser.parse_args()
    dry_run = args.dry_run

    if not BASE.exists():
        print(f"ERROR: {BASE} does not exist")
        sys.exit(1)

    print("=" * 70)
    print("PHASE 1: Collecting shortCodes")
    print("=" * 70)
    shortcode_map = collect_shortcodes()
    print(f"Found {len(shortcode_map)} unique shortCodes")
    for code, anon in list(shortcode_map.items())[:5]:
        print(f"  {code} -> {anon}")
    if len(shortcode_map) > 5:
        print(f"  ... and {len(shortcode_map) - 5} more")

    # Build the safe regex for shortCode replacement
    sc_regex = build_shortcode_regex(shortcode_map)

    print()
    print("=" * 70)
    print("PHASE 2: Renaming files")
    print("=" * 70)
    rename_count = 0

    for d in BULK_CSV_DIRS:
        if not d.exists():
            continue
        print(f"\n  Directory: {d.name}")
        for f in sorted(d.iterdir()):
            if f.is_file():
                new_path = rename_file_safe(f, shortcode_map, sc_regex, dry_run)
                if new_path != f:
                    rename_count += 1

    if DATA_ANALYSIS.exists():
        print(f"\n  Directory: Data Analysis (root)")
        for f in sorted(DATA_ANALYSIS.iterdir()):
            if f.is_file() and sc_regex.search(f.name):
                new_path = rename_file_safe(f, shortcode_map, sc_regex, dry_run)
                if new_path != f:
                    rename_count += 1

    output_dir = DATA_ANALYSIS / "output"
    if output_dir.exists():
        print(f"\n  Directory: Data Analysis/output")
        for f in sorted(output_dir.iterdir()):
            if f.is_file() and sc_regex.search(f.name):
                new_path = rename_file_safe(f, shortcode_map, sc_regex, dry_run)
                if new_path != f:
                    rename_count += 1

    ref_dir = DATA_ANALYSIS / "reference" / "labels" / "templates"
    if ref_dir.exists():
        print(f"\n  Directory: Data Analysis/reference/labels/templates")
        for f in sorted(ref_dir.iterdir()):
            if f.is_file() and sc_regex.search(f.name):
                new_path = rename_file_safe(f, shortcode_map, sc_regex, dry_run)
                if new_path != f:
                    rename_count += 1

    print(f"\n  Total files renamed: {rename_count}")

    print()
    print("=" * 70)
    print("PHASE 3: Replacing shortCodes in file contents")
    print("=" * 70)
    content_changes = 0

    for root_dir in [DATA_ANALYSIS, OLD_CODEBASE]:
        if not root_dir.exists():
            continue
        for f in sorted(root_dir.rglob("*")):
            if (f.is_file()
                    and f.suffix in TEXT_EXTENSIONS
                    and ".venv" not in str(f)
                    and ".git" not in str(f)):
                content_changes += process_text_file_shortcodes(
                    f, shortcode_map, sc_regex, dry_run
                )

    print(f"\n  Total content shortCode replacements: {content_changes}")

    print()
    print("=" * 70)
    print("PHASE 4: Sanitizing PII in CSV contents")
    print("=" * 70)
    pii_changes = 0

    csv_files = []
    for d in BULK_CSV_DIRS:
        if d.exists():
            csv_files.extend(sorted(d.glob("*.csv")))
    if DATA_ANALYSIS.exists():
        csv_files.extend(sorted(DATA_ANALYSIS.glob("*.csv")))
    if output_dir.exists():
        csv_files.extend(sorted(output_dir.glob("*.csv")))
    if ref_dir.exists():
        csv_files.extend(sorted(ref_dir.glob("*.csv")))

    print(f"  Scanning {len(csv_files)} CSV files...")
    files_with_pii = 0
    for csv_file in csv_files:
        reset_pii_counters()
        changes = sanitize_csv_file(csv_file, dry_run)
        if changes > 0:
            files_with_pii += 1
            pii_changes += changes

    print(f"\n  Files with PII sanitized: {files_with_pii}")
    print(f"  Total PII replacements: {pii_changes}")

    print()
    print("=" * 70)
    print("PHASE 5: Special cases")
    print("=" * 70)
    special_changes = handle_special_cases(dry_run)
    print(f"  Special case fixes: {special_changes}")

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  ShortCodes mapped:              {len(shortcode_map)}")
    print(f"  Files renamed:                  {rename_count}")
    print(f"  Content shortCode replacements: {content_changes}")
    print(f"  CSV files with PII fixed:       {files_with_pii}")
    print(f"  PII replacements:               {pii_changes}")
    print(f"  Special case fixes:             {special_changes}")

    if dry_run:
        print("\n  *** DRY RUN -- no files were modified ***")
        print("  Run without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
