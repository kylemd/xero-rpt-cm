"""Apply user mismatch decisions to validated fixture CSVs.

Reads mismatch_decisions.json and updates ValidatedReportingCode in fixture CSVs
for rows where the user confirmed the rule engine is correct ("got") or chose
a different code ("other").
"""
import csv
import json
import pathlib
import sys

DECISIONS_PATH = pathlib.Path(r"C:\Users\KyleDrayton\Documents\Development\Xero Report Code Mapping\reinforcement-inputs\mismatch_decisions.json")
FIXTURES_DIR = pathlib.Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "validated"


def load_decisions():
    with open(DECISIONS_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_update_map(decisions):
    """Build a mapping of (filename, account_name, type) -> new_validated_code."""
    updates = {}
    for d in decisions:
        decision = d["decision"]
        account_name = d["account_name"]
        account_type = d["type"]

        # Extract filename from the id (format: "filename:code:name_prefix")
        id_parts = d["id"].split(":")
        file_stem = id_parts[0]
        filename = file_stem + ".csv"

        if decision == "got":
            # User confirmed rule engine is correct - use rule_engine_code
            new_code = d["rule_engine_code"]
        elif decision == "other" and d.get("chosen_code"):
            # User chose a different code
            new_code = d["chosen_code"]
        else:
            # "expected" or "other" without a code - skip
            continue

        # Only update if the new code differs from existing validated code
        if new_code != d["validated_code"]:
            key = (filename, account_name, account_type)
            updates[key] = new_code
            print(f"  Will update: {filename} | {account_name} | {account_type}")
            print(f"    {d['validated_code']} -> {new_code}")

    return updates


def apply_updates(updates):
    """Apply updates to fixture CSV files."""
    updated_count = 0

    for csv_file in sorted(FIXTURES_DIR.glob("*_validated_final.csv")):
        # Read all rows
        with open(csv_file, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)

        # Apply updates
        file_updated = False
        for row in rows:
            name = row.get("Name", "").strip()
            acct_type = row.get("Type", "").strip()
            key = (csv_file.name, name, acct_type)

            if key in updates:
                old_val = row.get("ValidatedReportingCode", "")
                new_val = updates[key]
                row["ValidatedReportingCode"] = new_val
                file_updated = True
                updated_count += 1
                print(f"  Updated: {csv_file.name} | {name} | {acct_type}: {old_val} -> {new_val}")

        # Write back if changed
        if file_updated:
            with open(csv_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            print(f"  Saved: {csv_file.name}")

    return updated_count


def main():
    print(f"Reading decisions from: {DECISIONS_PATH}")
    decisions = load_decisions()
    print(f"Found {len(decisions)} decisions\n")

    print("Building update map...")
    updates = build_update_map(decisions)
    print(f"\n{len(updates)} fixture rows to update\n")

    if not updates:
        print("Nothing to update!")
        return

    print("Applying updates...")
    count = apply_updates(updates)
    print(f"\nDone! Updated {count} rows across fixture files.")


if __name__ == "__main__":
    main()
