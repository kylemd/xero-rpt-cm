"""Seed the synonym database with initial normalisation data.

Sources:
- Existing normalise() ad-hoc replacements from mapping_logic_v15.py
- VEHICLE_TOKENS, VEHICLE_EXPENSE_TOKENS, BANK_NAMES, CREDIT_CARD_NAMES
- Common Australian accounting abbreviations
- Known typos from validated datasets

Run:  python data/seed_synonyms.py
Output: data/synonyms.db
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from synonyms import SynonymDB

DB_PATH = pathlib.Path(__file__).parent / "synonyms.db"

# (term, canonical, category)
SEED_DATA = [
    # --- Abbreviations from normalise() ---
    ("m/v", "motor vehicle", "abbreviation"),
    ("m v", "motor vehicle", "abbreviation"),
    ("m-v", "motor vehicle", "abbreviation"),
    ("mv", "motor vehicle", "abbreviation"),
    ("r&m", "repairs maintenance", "abbreviation"),
    ("r and m", "repairs maintenance", "abbreviation"),
    ("r/m", "repairs maintenance", "abbreviation"),

    # --- Vehicle abbreviations ---
    ("motor veh", "motor vehicle", "abbreviation"),
    ("mot veh", "motor vehicle", "abbreviation"),
    ("veh", "vehicle", "abbreviation"),

    # --- Depreciation abbreviations ---
    ("acc dep", "accumulated depreciation", "abbreviation"),
    ("accum dep", "accumulated depreciation", "abbreviation"),
    ("a/d", "accumulated depreciation", "abbreviation"),
    ("accum depn", "accumulated depreciation", "abbreviation"),
    ("dep", "depreciation", "abbreviation"),
    ("depn", "depreciation", "abbreviation"),
    ("depre", "depreciation", "abbreviation"),

    # --- Amortisation abbreviations ---
    ("accum amort", "accumulated amortisation", "abbreviation"),
    ("amort", "amortisation", "abbreviation"),

    # --- Superannuation ---
    ("super", "superannuation", "abbreviation"),
    ("superann", "superannuation", "abbreviation"),
    ("sgc", "superannuation guarantee charge", "acronym"),

    # --- Payroll ---
    ("paygw", "payg withholding", "abbreviation"),

    # --- GST ---
    ("gst", "goods and services tax", "acronym"),

    # --- Plant & Equipment ---
    ("p and e", "plant and equipment", "abbreviation"),
    ("p&e", "plant and equipment", "abbreviation"),
    ("office equip", "office equipment", "abbreviation"),
    ("comp equip", "computer equipment", "abbreviation"),

    # --- Common typos ---
    ("ammenities", "amenities", "typo"),
    ("amenties", "amenities", "typo"),
    ("maintainance", "maintenance", "typo"),
    ("maintanance", "maintenance", "typo"),
    ("expences", "expenses", "typo"),
    ("insurence", "insurance", "typo"),
    ("advertisment", "advertisement", "typo"),
    ("advertisments", "advertisements", "typo"),
    ("recievables", "receivables", "typo"),
    ("recievable", "receivable", "typo"),
    ("payements", "payments", "typo"),
    ("stationary", "stationery", "typo"),  # common confusion
    ("telecomunications", "telecommunications", "typo"),

    # --- Accounting synonyms ---
    ("debtors", "receivables", "synonym"),
    ("creditors", "payables", "synonym"),
    ("p and l", "profit and loss", "abbreviation"),
    ("p&l", "profit and loss", "abbreviation"),
    ("b/s", "balance sheet", "abbreviation"),
    ("pty ltd", "proprietary limited", "synonym"),
    ("pty", "proprietary", "abbreviation"),
    ("fbt", "fringe benefits tax", "acronym"),
    ("bas", "business activity statement", "acronym"),
    ("ato", "australian taxation office", "acronym"),
    ("ctp", "compulsory third party", "acronym"),
    ("wip", "work in progress", "abbreviation"),
    ("wipaa", "work in progress at actual", "abbreviation"),
    ("hp", "hire purchase", "abbreviation"),
    ("uei", "unexpired interest", "abbreviation"),
]


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
    db = SynonymDB(DB_PATH)
    db.add_many(SEED_DATA)
    print(f"Seeded {len(SEED_DATA)} synonyms to {DB_PATH}")
    db.close()


if __name__ == "__main__":
    main()
