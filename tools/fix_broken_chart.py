import argparse
import sys
import pathlib
import pandas as pd
from typing import Dict, List, Tuple, Optional, Set

"""
fix_broken_chart.py — Automate COA standardization and merge against an entity template.

Overview
- Reads a client Chart of Accounts (COA), an entity template (e.g., Company.csv), and an optional BlankAccounts list.
- Aligns client Codes/Names/ReportCodes to the template using exact matches (by Reporting Code first, then by Name).
- Resolves collisions while preserving uniqueness per constraints:
  * If an account is marked blank (no activity) and conflicts with a template default, rename to Code+"OLD" and mark for archive.
  * Otherwise, assign a nearby unique alphanumeric code (e.g., 210A, 210B).
- Appends missing template rows absent in the client.
- Writes the transformed COA (and optional logs) in the client’s schema and column order.

Entities
- An "entity" refers to a specific chart template (Company, Trust, SoleTrader, Partnership, XeroHandi, etc.).
- Compatible template CSVs are stored in the ChartOfAccounts/ folder; the entity you pass must match a filename stem there.
- This script applies consistently across business units/entities that share the compatible schema described in system_prompt_revised_gpt5.md and mapping_logic_v15.py.

Validation
- After each major step, the script prints a short status and checks for common issues (e.g., duplicated codes).

Usage
  python fix_broken_chart.py \
      --input KDM/ChartOfAccounts_Updated_v3.csv \
      --entity Company \
      --template-dir ChartOfAccounts \
      --blank KDM/BlankAccounts_v2.csv \
      --output KDM/ChartOfAccounts_Updated_v4.csv \
      --changes-log KDM/02_Changes_Applied.csv \
      --collisions-log KDM/01_Collisions_Resolved.csv \
      --unmappable-log KDM/04_Unmappable.csv
"""

CLIENT_HEADER = [
    "*Code", "Report Code", "*Name", "Reporting Name", "*Type", "*Tax Code",
    "Description", "Dashboard", "Expense Claims", "Enable Payments", "Balance"
]

# --- Utilities ---------------------------------------------------------------

def _read_csv(path: pathlib.Path) -> pd.DataFrame:
    try:
        # Read as strings; do not coerce numeric so we preserve 479.1, 840H, etc.
        return pd.read_csv(path, dtype=str).fillna("")
    except FileNotFoundError:
        sys.exit(f"Error: File not found: {path}")
    except Exception as e:
        sys.exit(f"Error: Failed to read CSV '{path}': {e}")


def _normalize_client_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map client columns (with asterisks) to a working schema. All values are strings."""
    colmap = {
        "*Code": "Code",
        "Code": "Code",
        "Report Code": "ReportCode",
        "*Name": "Name",
        "Name": "Name",
        "Reporting Name": "ReportingName",
        "*Type": "Type",
        "Type": "Type",
        "*Tax Code": "TaxCode",
        "Tax Code": "TaxCode",
        "Description": "Description",
        "Dashboard": "Dashboard",
        "Expense Claims": "ExpenseClaims",
        "Enable Payments": "EnablePayments",
        "Balance": "Balance",
    }
    out = {}
    for src, dst in colmap.items():
        if src in df.columns:
            out[dst] = df[src].astype(str)
        else:
            out.setdefault(dst, "")
    # Ensure all keys exist
    for key in ["Code","ReportCode","Name","ReportingName","Type","TaxCode",
                "Description","Dashboard","ExpenseClaims","EnablePayments","Balance"]:
        if key not in out:
            out[key] = ""
    return pd.DataFrame(out)[["Code","ReportCode","Name","ReportingName","Type","TaxCode",
                              "Description","Dashboard","ExpenseClaims","EnablePayments","Balance"]]


def _normalize_template_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Template uses 'Code','Reporting Code','Name','Type','Tax Code','Description','Reporting Name'."""
    required = ["Code","Reporting Code","Name","Type","Tax Code","Description","Reporting Name"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        sys.exit(f"Error: Template missing required columns: {missing}")
    # Normalize to same working schema (ReportCode, ReportingName naming)
    return pd.DataFrame({
        "Code": df["Code"].astype(str),
        "ReportCode": df["Reporting Code"].astype(str),
        "Name": df["Name"].astype(str),
        "ReportingName": df["Reporting Name"].astype(str),
        "Type": df["Type"].astype(str),
        "TaxCode": df["Tax Code"].astype(str),
        "Description": df["Description"].astype(str)
    })


def _client_like_row_from_template(trow: pd.Series) -> Dict[str, str]:
    """Map a template row to the client's schema with sensible defaults for flags."""
    return {
        "Code": trow["Code"],
        "ReportCode": trow["ReportCode"],
        "Name": trow["Name"],
        "ReportingName": trow.get("ReportingName", ""),
        "Type": trow["Type"],
        "TaxCode": trow["TaxCode"],
        "Description": trow.get("Description", ""),
        "Dashboard": "No",
        "ExpenseClaims": "No",
        "EnablePayments": "No",
        "Balance": "",
    }


def _normalize_name(text: str) -> str:
    return " ".join("".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text).lower().split())


def _build_template_indexes(tpl: pd.DataFrame) -> Tuple[Dict[str, Dict[str, str]], Dict[str, Dict[str, str]]]:
    """Return (by_reportcode, by_name) maps to template rows as dicts."""
    by_rc: Dict[str, Dict[str, str]] = {}
    by_nm: Dict[str, Dict[str, str]] = {}
    for _, r in tpl.iterrows():
        rd = {
            "Code": r["Code"],
            "ReportCode": r["ReportCode"],
            "Name": r["Name"],
            "ReportingName": r.get("ReportingName",""),
            "Type": r["Type"],
            "TaxCode": r["TaxCode"],
            "Description": r.get("Description",""),
        }
        by_rc[r["ReportCode"]] = rd
        by_nm[_normalize_name(r["Name"]) or r["Name"].lower()] = rd
    return by_rc, by_nm


def _load_blank_accounts(blank_path: Optional[pathlib.Path]) -> Tuple[Set[str], Set[str]]:
    """Read blank accounts list; returns sets of blank codes and blank normalized names."""
    if not blank_path:
        return set(), set()
    bdf = _read_csv(blank_path)
    # Support two common layouts: columns may be ['Account Name','Account #'] or any order; accept both.
    cols = {c.lower(): c for c in bdf.columns}
    code_col = cols.get("account #") or cols.get("account#") or cols.get("code") or list(bdf.columns)[-1]
    name_col = cols.get("account name") or cols.get("name") or list(bdf.columns)[0]
    blank_codes = set(str(x) for x in bdf[code_col].astype(str).tolist())
    blank_names = set(_normalize_name(str(x)) for x in bdf[name_col].astype(str).tolist())
    return blank_codes, blank_names


def _is_blank_account(code: str, name: str, blank_codes: Set[str], blank_names: Set[str]) -> bool:
    if code in blank_codes:
        return True
    if _normalize_name(name) in blank_names:
        return True
    return False


def _find_unique_nearby_code(base_code: str, used: Set[str]) -> str:
    """Return a unique alphanumeric code based on base_code by appending A..Z, then AA..AZ if needed."""
    if base_code not in used:
        return base_code
    suffixes = [chr(c) for c in range(ord('A'), ord('Z')+1)]
    # Try single letter suffixes
    for s in suffixes:
        cand = f"{base_code}{s}"
        if cand not in used:
            return cand
    # Fallback: double-letter suffixes
    for s1 in suffixes:
        for s2 in suffixes:
            cand = f"{base_code}{s1}{s2}"
            if cand not in used:
                return cand
    # Final fallback: numeric sequence
    i = 1
    while True:
        cand = f"{base_code}{i}"
        if cand not in used:
            return cand
        i += 1


def _apply_proposals(client: pd.DataFrame,
                     template_rc_idx: Dict[str, Dict[str, str]],
                     template_nm_idx: Dict[str, Dict[str, str]],
                     blank_codes: Set[str],
                     blank_names: Set[str]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, List[str]]:
    """
    Compute and apply proposals to align client rows to template codes/names.
    Returns: (updated_client, changes_log, collisions_log, warnings)
    """
    used_codes: Set[str] = set(client["Code"].tolist())
    # Proposed updates as per index in client
    proposals: Dict[int, Dict[str, str]] = {}
    warnings: List[str] = []

    # 1) Derive proposals using reporting code, then name
    for idx, r in client.iterrows():
        report_code = r.get("ReportCode", "").strip()
        name_norm = _normalize_name(r.get("Name", ""))
        trow = None
        reason = ""
        if report_code and report_code in template_rc_idx:
            trow = template_rc_idx[report_code]
            reason = "ReportCodeMatch"
        elif name_norm and name_norm in template_nm_idx:
            trow = template_nm_idx[name_norm]
            reason = "NameMatch"
        if trow:
            proposals[idx] = {
                "proposed_Code": trow["Code"],
                "proposed_Name": trow["Name"],
                "proposed_ReportCode": trow["ReportCode"],
                "reason": reason
            }

    # 2) Resolve collisions and archive blanks if needed
    collisions_rows: List[Dict[str, str]] = []
    # Build reverse mapping target->indices
    target_to_rows: Dict[str, List[int]] = {}
    for i, p in proposals.items():
        target_to_rows.setdefault(p["proposed_Code"], []).append(i)

    # Detect direct collisions (same target code for multiple rows)
    for target_code, rows in target_to_rows.items():
        if len(rows) <= 1:
            continue
        # Keep the first as canonical; reassign others
        keep_first = rows[0]
        for dup_idx in rows[1:]:
            cur = client.loc[dup_idx]
            # If blank, archive instead of squeezing into template code
            if _is_blank_account(cur["Code"], cur["Name"], blank_codes, blank_names):
                old_code = cur["Code"]
                arch_code = f"{old_code}OLD"
                proposals[dup_idx] = {
                    "proposed_Code": arch_code,
                    "proposed_Name": cur["Name"],
                    "proposed_ReportCode": cur.get("ReportCode",""),
                    "reason": "ArchiveBlankConflict"
                }
                collisions_rows.append({
                    "conflicting_account_code": target_code,
                    "accounts_involved": f"{cur['Code']} {cur['Name']}",
                    "recommended_resolution": f"Archived blank as {arch_code}"
                })
                used_codes.add(arch_code)
            else:
                # Assign nearby unique alphanumeric code
                near = _find_unique_nearby_code(target_code, used_codes)
                proposals[dup_idx] = {
                    "proposed_Code": near,
                    "proposed_Name": cur["Name"],
                    "proposed_ReportCode": cur.get("ReportCode",""),
                    "reason": "CollisionReassigned"
                }
                collisions_rows.append({
                    "conflicting_account_code": target_code,
                    "accounts_involved": f"{cur['Code']} {cur['Name']}",
                    "recommended_resolution": f"Reassigned to {near}"
                })
                used_codes.add(near)

    # 3) Resolve clashes with existing occupants (target code already taken by some other row not moving)
    for idx, p in list(proposals.items()):
        target_code = p["proposed_Code"]
        if target_code in used_codes and client.loc[idx, "Code"] != target_code:
            # Target is currently used; if the occupant is blank and not moving, archive it; else pick nearby unique.
            # Find occupant row(s)
            occupant_mask = (client["Code"] == target_code)
            if occupant_mask.any():
                occ_idx = occupant_mask[occupant_mask].index.tolist()[0]
                occ_row = client.loc[occ_idx]
                if occ_idx not in proposals and _is_blank_account(occ_row["Code"], occ_row["Name"], blank_codes, blank_names):
                    arch_code = f"{occ_row['Code']}OLD"
                    # Apply archive to occupant directly
                    client.at[occ_idx, "Code"] = arch_code
                    used_codes.discard(target_code)
                    used_codes.add(arch_code)
                    collisions_rows.append({
                        "conflicting_account_code": target_code,
                        "accounts_involved": f"{occ_row['Code']} {occ_row['Name']} (occupant)",
                        "recommended_resolution": f"Archived occupant as {arch_code} to free {target_code}"
                    })
                else:
                    # Cannot free; pick nearby unique
                    near = _find_unique_nearby_code(target_code, used_codes)
                    proposals[idx]["proposed_Code"] = near
                    collisions_rows.append({
                        "conflicting_account_code": target_code,
                        "accounts_involved": f"{client.loc[idx,'Code']} {client.loc[idx,'Name']}",
                        "recommended_resolution": f"Reassigned to {near}"
                    })
                    used_codes.add(near)

    # 4) Apply proposals and build change log
    changes_rows: List[Dict[str, str]] = []
    for idx, p in proposals.items():
        orig_code = client.loc[idx, "Code"]
        orig_name = client.loc[idx, "Name"]
        orig_rc = client.loc[idx, "ReportCode"]
        new_code = p["proposed_Code"]
        new_name = p["proposed_Name"] or orig_name
        new_rc = p["proposed_ReportCode"] or orig_rc
        client.at[idx, "Code"] = new_code
        client.at[idx, "Name"] = new_name
        client.at[idx, "ReportCode"] = new_rc
        change_type = "code_update" if (new_code != orig_code and new_name == orig_name) else (
            "name_update" if (new_code == orig_code and new_name != orig_name) else "code+name_update")
        archive_flag = "TRUE" if new_code.endswith("OLD") else ""
        changes_rows.append({
            "line_number": str(idx + 2),  # +2 to reflect CSV header + 1-based row
            "original_account_code": orig_code,
            "account_name": orig_name,
            "proposed_account_code": new_code,
            "proposed_account_name": new_name,
            "change_type": change_type,
            "reason": p.get("reason",""),
            "mapping_confidence": "High" if p.get("reason") in ("ReportCodeMatch","NameMatch") else "Medium",
            "archive": archive_flag,
        })
        used_codes.add(new_code)

    # Validation: Codes unique after changes
    if client["Code"].duplicated().any():
        warnings.append("Duplicate codes remain after applying proposals. Please review collisions log.")

    changes_df = pd.DataFrame(changes_rows, columns=[
        "line_number","original_account_code","account_name","proposed_account_code",
        "proposed_account_name","change_type","reason","mapping_confidence","archive"
    ])
    collisions_df = pd.DataFrame(collisions_rows, columns=[
        "conflicting_account_code","accounts_involved","recommended_resolution"
    ])

    return client, changes_df, collisions_df, warnings


def _append_missing_template_rows(client: pd.DataFrame, template: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Append template rows whose Codes are not present in the client. Returns (updated_client, count_added)."""
    existing_codes = set(client["Code"].tolist())
    add_rows: List[Dict[str, str]] = []
    for _, r in template.iterrows():
        code = r["Code"]
        if code not in existing_codes:
            add_rows.append(_client_like_row_from_template(r))
    if add_rows:
        client = pd.concat([client, pd.DataFrame(add_rows)], ignore_index=True)
    return client, len(add_rows)


def _write_client_csv_like(path: pathlib.Path, df: pd.DataFrame) -> None:
    # Map back to client header and order
    out = pd.DataFrame({
        "*Code": df["Code"],
        "Report Code": df["ReportCode"],
        "*Name": df["Name"],
        "Reporting Name": df["ReportingName"],
        "*Type": df["Type"],
        "*Tax Code": df["TaxCode"],
        "Description": df["Description"],
        "Dashboard": df["Dashboard"],
        "Expense Claims": df["ExpenseClaims"],
        "Enable Payments": df["EnablePayments"],
        "Balance": df["Balance"],
    })
    try:
        out.to_csv(path, index=False)
    except Exception as e:
        sys.exit(f"Error: Failed to write output CSV '{path}': {e}")


# --- CLI --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Fix/standardize a client COA against an entity template and append missing items.")
    ap.add_argument("--input", required=True, help="Path to client ChartOfAccounts CSV (e.g., ChartOfAccounts_Updated_v3.csv)")
    ap.add_argument("--output", required=True, help="Path to write the transformed COA (e.g., ChartOfAccounts_Updated_v4.csv)")
    ap.add_argument("--entity", required=False, default="Company", help="Entity/template name (filename stem in --template-dir), e.g., Company")
    ap.add_argument("--template-dir", required=False, default="ChartOfAccounts", help="Directory containing entity templates")
    ap.add_argument("--blank", required=False, default="", help="Optional BlankAccounts CSV path for archive decisions")
    ap.add_argument("--changes-log", required=False, default="", help="Optional path to write changes log CSV")
    ap.add_argument("--collisions-log", required=False, default="", help="Optional path to write collisions log CSV")
    ap.add_argument("--unmappable-log", required=False, default="", help="Optional path to write unmappable CSV (reserved)")
    args = ap.parse_args()

    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output)
    template_dir = pathlib.Path(args.template_dir)
    if not template_dir.exists():
        sys.exit(f"Error: Template directory not found: {template_dir}")

    # Resolve template path from entity name
    template_path = template_dir / f"{args.entity}.csv"
    if not template_path.exists():
        # Offer available options
        candidates = sorted([p.stem for p in template_dir.glob("*.csv")])
        sys.exit(f"Error: No template named '{args.entity}'. Available templates: {', '.join(candidates)}")

    blank_path = pathlib.Path(args.blank) if args.blank else None

    # 1) Read inputs
    client_raw = _read_csv(input_path)
    template_raw = _read_csv(template_path)
    blank_codes, blank_names = _load_blank_accounts(blank_path)

    # 2) Normalize
    client = _normalize_client_columns(client_raw)
    template = _normalize_template_columns(template_raw)
    print(f"Loaded client rows: {len(client)}; template rows: {len(template)}")
    # Validation success: both dataframes have the working columns present

    # 3) Build template indices
    tpl_by_rc, tpl_by_nm = _build_template_indexes(template)

    # 4) Apply proposals and resolve collisions
    client_updated, changes_df, collisions_df, warnings = _apply_proposals(client, tpl_by_rc, tpl_by_nm, blank_codes, blank_names)
    print(f"Applied {len(changes_df)} change proposals; collisions resolved: {len(collisions_df)}")
    if warnings:
        for w in warnings:
            print(f"WARNING: {w}")
    # Success: No unhandled exceptions and client codes are intended to be unique post-resolution

    # 5) Append missing template rows
    client_final, add_count = _append_missing_template_rows(client_updated, template)
    print(f"Appended {add_count} missing template rows.")
    # Success: All template codes should now be present

    # 6) Final uniqueness validation
    dups = client_final["Code"].duplicated(keep=False)
    if dups.any():
        dup_codes = sorted(set(client_final.loc[dups, "Code"].tolist()))
        print(f"ERROR: Duplicate codes remain after processing: {dup_codes}")
        print("Action: Review collisions log or rerun with a blank-accounts list to free canonical codes.")
        # We still write outputs to facilitate manual review

    # 7) Write outputs
    _write_client_csv_like(output_path, client_final)
    if args.changes_log:
        try:
            changes_df.to_csv(args.changes_log, index=False)
        except Exception as e:
            print(f"WARNING: Failed to write changes log: {e}")
    if args.collisions_log:
        try:
            collisions_df.to_csv(args.collisions_log, index=False)
        except Exception as e:
            print(f"WARNING: Failed to write collisions log: {e}")

    print(f"Saved -> {output_path}")
    print("Done.")


if __name__ == "__main__":
    main()
