"""Verify test fixtures are present and well-formed."""
import pathlib
import csv
import pytest

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures" / "validated"

def test_validated_fixtures_exist():
    files = list(FIXTURES_DIR.glob("*_validated_final.csv"))
    assert len(files) >= 7, f"Expected 7 validated files, found {len(files)}"

@pytest.mark.parametrize("csv_file", list(FIXTURES_DIR.glob("*.csv")),
                         ids=lambda p: p.name)
def test_validated_file_has_required_columns(csv_file):
    with open(csv_file, encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
    required = {"Name", "Type", "ValidatedReportingCode"}
    actual = set(headers)
    missing = required - actual
    assert not missing, f"{csv_file.name} missing columns: {missing}"
