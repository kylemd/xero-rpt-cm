"""Integration tests: run mapper rules against validated client datasets.

Each row in the validated CSVs has:
- Name, Type: the input account
- SuggestedReportingCode (or InputReportingCode): what the old mapper suggested
- ValidatedReportingCode: what a human corrected it to

We run our new rule engine on each row and compare to ValidatedReportingCode.
Mismatches are reported in the HTML output for user re-verification.
"""
import csv
import pathlib
import pytest
from rule_engine import evaluate_rules, MatchContext
from rules import ALL_RULES, OWNER_KEYWORDS
from mapping_logic_v15 import normalise, canonical_type

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures" / "validated"


def _load_validated_rows():
    """Load all validated rows across all fixture files.

    Handles different CSV column layouts:
    - Some files use 'SuggestedReportingCode', others use 'InputReportingCode'
    - All files have 'Name', 'Type', 'ValidatedReportingCode', 'MatchReason'
    """
    rows = []
    for csv_file in sorted(FIXTURES_DIR.glob("*_validated_final.csv")):
        with open(csv_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                validated = row.get("ValidatedReportingCode", "").strip()
                if validated:  # Skip rows without a validated code
                    # Handle different column names for suggested code
                    suggested = (
                        row.get("SuggestedReportingCode", "").strip()
                        or row.get("InputReportingCode", "").strip()
                    )
                    rows.append({
                        "file": csv_file.name,
                        "code": row.get("Code", ""),
                        "name": row.get("Name", ""),
                        "type": row.get("Type", ""),
                        "suggested": suggested,
                        "validated": validated,
                        "match_reason": row.get("MatchReason", ""),
                    })
    return rows


VALIDATED_ROWS = _load_validated_rows()


@pytest.mark.parametrize(
    "row",
    VALIDATED_ROWS,
    ids=lambda r: f"{r['file']}:{r['code']}:{r['name'][:30]}",
)
def test_rule_engine_vs_validated(row):
    """Compare rule engine output to human-validated code."""
    text = normalise(row["name"])
    ctx = MatchContext(
        normalised_text=text,
        normalised_name=text,
        raw_type=row["type"],
        canon_type=canonical_type(row["type"]),
        template_name="company",  # Most validated data is for company charts
        owner_keywords=OWNER_KEYWORDS,
    )
    code, rule_name = evaluate_rules(ALL_RULES, ctx)

    # If the rule engine produced a code, check it matches validated.
    # If no match (None), we skip — some rows require template/fuzzy matching
    # which is outside the rule engine's scope.
    if code is None:
        pytest.skip(
            f"No rule matched: name='{row['name']}', type='{row['type']}' "
            f"(validated={row['validated']}, old_suggested={row['suggested']})"
        )
    else:
        assert code == row["validated"], (
            f"Mismatch: name='{row['name']}', type='{row['type']}'\n"
            f"  Rule engine: {code} (via {rule_name})\n"
            f"  Validated:   {row['validated']}\n"
            f"  Old mapper:  {row['suggested']}"
        )
