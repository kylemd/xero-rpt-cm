"""Tests for synonym normalisation."""
from synonyms import SynonymDB


def test_create_db(tmp_path):
    with SynonymDB(tmp_path / "test.db") as db:
        db.add("mv", "motor vehicle", "abbreviation")
        assert db.lookup("mv") == "motor vehicle"


def test_lookup_miss(tmp_path):
    with SynonymDB(tmp_path / "test.db") as db:
        assert db.lookup("nonexistent") is None


def test_normalise_text(tmp_path):
    with SynonymDB(tmp_path / "test.db") as db:
        db.add("mv", "motor vehicle", "abbreviation")
        db.add("r and m", "repairs maintenance", "abbreviation")
        result = db.normalise_tokens("mv r and m fuel")
        assert result == "motor vehicle repairs maintenance fuel"


def test_case_insensitive(tmp_path):
    with SynonymDB(tmp_path / "test.db") as db:
        db.add("mv", "motor vehicle", "abbreviation")
        assert db.lookup("MV") == "motor vehicle"
        assert db.lookup("Mv") == "motor vehicle"


def test_add_many(tmp_path):
    with SynonymDB(tmp_path / "test.db") as db:
        db.add_many([
            ("mv", "motor vehicle", "abbreviation"),
            ("dep", "depreciation", "abbreviation"),
            ("super", "superannuation", "abbreviation"),
        ])
        assert db.lookup("mv") == "motor vehicle"
        assert db.lookup("dep") == "depreciation"
        assert db.lookup("super") == "superannuation"
        assert len(db.all_entries()) == 3


def test_add_replaces_duplicate(tmp_path):
    with SynonymDB(tmp_path / "test.db") as db:
        db.add("mv", "motor vehicle", "abbreviation")
        db.add("mv", "moving van", "synonym")
        assert db.lookup("mv") == "moving van"


def test_normalise_empty_string(tmp_path):
    with SynonymDB(tmp_path / "test.db") as db:
        db.add("mv", "motor vehicle", "abbreviation")
        assert db.normalise_tokens("") == ""
