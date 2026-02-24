"""Tests for synonym normalisation."""
from synonyms import SynonymDB


def test_create_db(tmp_path):
    db = SynonymDB(tmp_path / "test.db")
    db.add("mv", "motor vehicle", "abbreviation")
    assert db.lookup("mv") == "motor vehicle"


def test_lookup_miss(tmp_path):
    db = SynonymDB(tmp_path / "test.db")
    assert db.lookup("nonexistent") is None


def test_normalise_text(tmp_path):
    db = SynonymDB(tmp_path / "test.db")
    db.add("mv", "motor vehicle", "abbreviation")
    db.add("r and m", "repairs maintenance", "abbreviation")
    result = db.normalise_tokens("mv r and m fuel")
    assert "motor vehicle" in result
    assert "repairs maintenance" in result
    assert "fuel" in result


def test_case_insensitive(tmp_path):
    db = SynonymDB(tmp_path / "test.db")
    db.add("mv", "motor vehicle", "abbreviation")
    assert db.lookup("MV") == "motor vehicle"
    assert db.lookup("Mv") == "motor vehicle"
