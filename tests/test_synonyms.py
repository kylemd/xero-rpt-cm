"""Tests for synonym normalisation."""
import pathlib

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


def test_seed_db_exists():
    db_path = pathlib.Path(__file__).parent.parent / "data" / "synonyms.db"
    assert db_path.exists(), "Run 'python data/seed_synonyms.py' first"
    with SynonymDB(db_path) as db:
        entries = db.all_entries()
        assert len(entries) >= 40  # we seeded at least 40+ entries
        # Spot-check a few
        assert db.lookup("mv") == "motor vehicle"
        assert db.lookup("acc dep") == "accumulated depreciation"
        assert db.lookup("ammenities") == "amenities"
