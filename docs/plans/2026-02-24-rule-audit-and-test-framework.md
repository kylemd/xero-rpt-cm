# Rule Audit & Test Framework Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor 120 keyword heuristic rules from monolithic if/elif chains into a declarative rule engine with SQLite synonym normalisation, then build pytest + HTML tests to verify accuracy.

**Architecture:** Rules extracted from `keyword_match()` and early overrides into `rules.py` as `Rule` dataclass instances with explicit priorities. A `rule_engine.py` evaluates all matching rules and picks the highest-priority winner. A SQLite database handles abbreviation/synonym/typo normalisation before rule evaluation. pytest parametrized tests verify each rule and integration tests run against 7 validated client datasets.

**Tech Stack:** Python 3.12, uv, pytest, pytest-html, SQLite, pandas, dataclasses

**Design doc:** `docs/plans/2026-02-24-rule-audit-and-test-framework-design.md`

---

## Phase 1: Environment & Infrastructure

### Task 1: Set up uv environment

**Files:**
- Modify: `pyproject.toml`

**Step 1: Create venv with uv and install dependencies**

Run:
```bash
uv venv .venv
uv pip install pandas openpyxl pytest pytest-html
```
Expected: Virtual environment created at `.venv/`, packages installed.

**Step 2: Add dev dependencies to pyproject.toml**

Add a `[project.optional-dependencies]` section:
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-html>=4.0.0",
]
```

Also remove the ML/web dependencies that aren't currently used (scikit-learn, xgboost, transformers, flask, flask-cors) to keep the environment lean. The core dependencies should be:
```toml
dependencies = [
    "pandas>=2.3.2",
    "openpyxl>=3.1.2",
]
```

**Step 3: Verify pytest runs**

Run:
```bash
.venv/Scripts/python -m pytest --version
```
Expected: `pytest 8.x.x`

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: set up uv environment with pytest dev dependencies"
```

---

### Task 2: Create Rule dataclass

**Files:**
- Create: `rule_engine.py`
- Test: `tests/test_rule_engine.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Create test directory and write failing test**

Create `tests/__init__.py` (empty).

Create `tests/conftest.py`:
```python
"""Shared test fixtures."""
import pathlib
import pytest

PROJECT_ROOT = pathlib.Path(__file__).parent.parent

@pytest.fixture
def project_root():
    return PROJECT_ROOT
```

Create `tests/test_rule_engine.py`:
```python
"""Tests for the rule engine."""
from rule_engine import Rule


def test_rule_creation():
    rule = Rule(
        name="test_rule",
        code="EXP.VEH",
        priority=70,
        keywords=["motor vehicle"],
    )
    assert rule.name == "test_rule"
    assert rule.code == "EXP.VEH"
    assert rule.priority == 70
    assert rule.keywords == ["motor vehicle"]


def test_rule_defaults():
    rule = Rule(name="minimal", code="EXP", priority=50)
    assert rule.keywords == []
    assert rule.keywords_all == []
    assert rule.keywords_exclude == []
    assert rule.raw_types == set()
    assert rule.canon_types == set()
    assert rule.type_exclude == set()
    assert rule.template is None
    assert rule.owner_context is False
    assert rule.name_only is False
    assert rule.notes == ""
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_rule_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rule_engine'`

**Step 3: Write Rule dataclass**

Create `rule_engine.py`:
```python
"""Declarative rule engine for Xero reporting code assignment.

Rules are defined as dataclass instances with explicit conditions and priorities.
The engine evaluates all matching rules against an account row and returns the
highest-priority match.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Rule:
    """A single keyword-based mapping rule.

    Attributes:
        name:             Unique identifier for this rule.
        code:             Reporting code to assign when this rule matches.
        priority:         Explicit priority (higher wins). Tiers:
                          100+ = type-specific overrides
                          90-99 = high-confidence keywords
                          80-89 = industry-specific
                          70-79 = general categories
                          60-69 = broad patterns
                          50-59 = catch-all
        keywords:         ANY of these must appear in normalised text.
        keywords_all:     ALL of these must appear in normalised text.
        keywords_exclude: NONE of these may appear in normalised text.
        raw_types:        Raw *Type field must be one of these (case-insensitive).
        canon_types:      Canonical type must be one of these.
        type_exclude:     Canonical type must NOT be one of these.
        template:         Only matches when using this template name (e.g. "company").
        owner_context:    If True, requires OWNER_KEYWORDS match in text.
        name_only:        If True, match only against account name (not name+description).
        notes:            Human-readable audit notes.
    """
    name: str
    code: str
    priority: int
    keywords: list[str] = field(default_factory=list)
    keywords_all: list[str] = field(default_factory=list)
    keywords_exclude: list[str] = field(default_factory=list)
    raw_types: set[str] = field(default_factory=set)
    canon_types: set[str] = field(default_factory=set)
    type_exclude: set[str] = field(default_factory=set)
    template: str | None = None
    owner_context: bool = False
    name_only: bool = False
    notes: str = ""
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_rule_engine.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add rule_engine.py tests/
git commit -m "feat: add Rule dataclass for declarative rule definitions"
```

---

### Task 3: Implement rule matching logic

**Files:**
- Modify: `rule_engine.py`
- Modify: `tests/test_rule_engine.py`

**Step 1: Write failing tests for rule matching**

Append to `tests/test_rule_engine.py`:
```python
from rule_engine import Rule, evaluate_rules, MatchContext


def test_simple_keyword_match():
    rules = [
        Rule(name="vehicle_expense", code="EXP.VEH", priority=70,
             keywords=["motor vehicle"]),
    ]
    ctx = MatchContext(
        normalised_text="motor vehicle fuel",
        raw_type="Expense",
        canon_type="expense",
        template_name="company",
    )
    code, rule_name = evaluate_rules(rules, ctx)
    assert code == "EXP.VEH"
    assert rule_name == "vehicle_expense"


def test_no_match_returns_none():
    rules = [
        Rule(name="vehicle_expense", code="EXP.VEH", priority=70,
             keywords=["motor vehicle"]),
    ]
    ctx = MatchContext(
        normalised_text="office supplies",
        raw_type="Expense",
        canon_type="expense",
        template_name="company",
    )
    code, rule_name = evaluate_rules(rules, ctx)
    assert code is None
    assert rule_name is None


def test_highest_priority_wins():
    rules = [
        Rule(name="generic_expense", code="EXP", priority=50,
             keywords=["insurance"]),
        Rule(name="vehicle_insurance", code="EXP.VEH", priority=70,
             keywords_all=["motor vehicle", "insurance"]),
    ]
    ctx = MatchContext(
        normalised_text="motor vehicle insurance",
        raw_type="Expense",
        canon_type="expense",
        template_name="company",
    )
    code, rule_name = evaluate_rules(rules, ctx)
    assert code == "EXP.VEH"
    assert rule_name == "vehicle_insurance"


def test_type_constraint_filters():
    rules = [
        Rule(name="wages_direct", code="EXP.COS.WAG", priority=95,
             keywords=["wages"],
             raw_types={"direct costs", "cost of sales"}),
    ]
    ctx = MatchContext(
        normalised_text="construction wages",
        raw_type="Expense",
        canon_type="expense",
        template_name="company",
    )
    code, rule_name = evaluate_rules(rules, ctx)
    assert code is None  # Type doesn't match


def test_keywords_exclude():
    rules = [
        Rule(name="depreciation_expense", code="EXP.DEP", priority=70,
             keywords=["depreciation"],
             keywords_exclude=["accumulated"]),
    ]
    ctx = MatchContext(
        normalised_text="accumulated depreciation on vehicles",
        raw_type="Fixed Asset",
        canon_type="fixed asset",
        template_name="company",
    )
    code, rule_name = evaluate_rules(rules, ctx)
    assert code is None  # Excluded by "accumulated"


def test_template_constraint():
    rules = [
        Rule(name="company_funds", code="LIA.NCL.ADV", priority=90,
             keywords=["funds introduced"],
             template="company"),
    ]
    ctx = MatchContext(
        normalised_text="owner a funds introduced",
        raw_type="Equity",
        canon_type="equity",
        template_name="trust",
    )
    code, rule_name = evaluate_rules(rules, ctx)
    assert code is None  # Template doesn't match


def test_owner_context():
    rules = [
        Rule(name="drawings", code="EQU.DRA", priority=90,
             keywords=["drawings"],
             owner_context=True),
    ]
    owner_keywords = ["owner a", "proprietor", "drawings"]
    ctx = MatchContext(
        normalised_text="office supplies drawings account",
        raw_type="Equity",
        canon_type="equity",
        template_name="company",
        owner_keywords=owner_keywords,
    )
    code, rule_name = evaluate_rules(rules, ctx)
    assert code == "EQU.DRA"


def test_canon_type_constraint():
    rules = [
        Rule(name="insurance_general", code="EXP.INS", priority=70,
             keywords=["insurance"],
             canon_types={"expense"}),
    ]
    ctx = MatchContext(
        normalised_text="insurance premium asset",
        raw_type="Current Asset",
        canon_type="current asset",
        template_name="company",
    )
    code, rule_name = evaluate_rules(rules, ctx)
    assert code is None  # Canon type doesn't match
```

**Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_rule_engine.py -v`
Expected: FAIL with `ImportError: cannot import name 'evaluate_rules'`

**Step 3: Implement evaluate_rules and MatchContext**

Add to `rule_engine.py`:
```python
from typing import Optional


@dataclass
class MatchContext:
    """Context passed to rule evaluation.

    Attributes:
        normalised_text:   Normalised account name + description.
        normalised_name:   Normalised account name only (for name_only rules).
        raw_type:          Raw *Type field value.
        canon_type:        Canonical type after TYPE_EQ mapping.
        template_name:     Template chart name (e.g. "company", "trust").
        owner_keywords:    List of owner keyword strings for owner_context check.
    """
    normalised_text: str
    raw_type: str
    canon_type: str
    template_name: str
    normalised_name: str = ""
    owner_keywords: list[str] = field(default_factory=list)


def _rule_matches(rule: Rule, ctx: MatchContext) -> bool:
    """Check whether a single rule's conditions are met."""
    text = ctx.normalised_name if rule.name_only else ctx.normalised_text

    # Keyword conditions
    if rule.keywords and not any(kw in text for kw in rule.keywords):
        return False
    if rule.keywords_all and not all(kw in text for kw in rule.keywords_all):
        return False
    if rule.keywords_exclude and any(kw in text for kw in rule.keywords_exclude):
        return False

    # Type constraints
    raw_lower = ctx.raw_type.strip().lower()
    if rule.raw_types and raw_lower not in rule.raw_types:
        return False
    if rule.canon_types and ctx.canon_type not in rule.canon_types:
        return False
    if rule.type_exclude and ctx.canon_type in rule.type_exclude:
        return False

    # Template constraint
    if rule.template is not None and ctx.template_name.strip().lower() != rule.template:
        return False

    # Owner context
    if rule.owner_context:
        if not any(kw in ctx.normalised_text for kw in ctx.owner_keywords):
            return False

    return True


def evaluate_rules(
    rules: list[Rule], ctx: MatchContext
) -> tuple[Optional[str], Optional[str]]:
    """Evaluate all rules against a row context, return (code, rule_name) of winner.

    Returns (None, None) if no rule matches.
    """
    candidates = [r for r in rules if _rule_matches(r, ctx)]
    if not candidates:
        return None, None
    winner = max(candidates, key=lambda r: r.priority)
    return winner.code, winner.name
```

**Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_rule_engine.py -v`
Expected: All 10 tests pass

**Step 5: Commit**

```bash
git add rule_engine.py tests/test_rule_engine.py
git commit -m "feat: implement rule evaluation engine with priority-based matching"
```

---

### Task 4: Create SQLite synonym database schema and loader

**Files:**
- Create: `synonyms.py`
- Create: `data/synonyms.sql`
- Test: `tests/test_synonyms.py`

**Step 1: Create data directory and write failing test**

Create `tests/test_synonyms.py`:
```python
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
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_synonyms.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synonyms'`

**Step 3: Implement SynonymDB**

Create `synonyms.py`:
```python
"""SQLite-backed synonym normalisation for accounting terms.

Handles abbreviations (MV → motor vehicle), synonyms (super → superannuation),
typos (ammenities → amenities), and acronyms (SGC → superannuation guarantee charge).
"""
from __future__ import annotations

import pathlib
import sqlite3


class SynonymDB:
    """Manages a SQLite synonym database for text normalisation."""

    def __init__(self, db_path: pathlib.Path | str):
        self.db_path = pathlib.Path(db_path)
        self._conn = sqlite3.connect(str(self.db_path))
        self._create_tables()

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS synonyms (
                id INTEGER PRIMARY KEY,
                term TEXT NOT NULL COLLATE NOCASE,
                canonical TEXT NOT NULL,
                category TEXT NOT NULL,
                domain TEXT DEFAULT NULL,
                notes TEXT DEFAULT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_synonyms_term
                ON synonyms(term COLLATE NOCASE);
        """)
        self._conn.commit()

    def add(self, term: str, canonical: str, category: str,
            domain: str | None = None, notes: str | None = None):
        """Insert or replace a synonym entry."""
        self._conn.execute(
            "INSERT OR REPLACE INTO synonyms (term, canonical, category, domain, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (term.lower(), canonical.lower(), category, domain, notes),
        )
        self._conn.commit()

    def add_many(self, entries: list[tuple[str, str, str]]):
        """Bulk insert (term, canonical, category) tuples."""
        self._conn.executemany(
            "INSERT OR REPLACE INTO synonyms (term, canonical, category) "
            "VALUES (?, ?, ?)",
            [(t.lower(), c.lower(), cat) for t, c, cat in entries],
        )
        self._conn.commit()

    def lookup(self, term: str) -> str | None:
        """Look up a single term. Returns canonical form or None."""
        row = self._conn.execute(
            "SELECT canonical FROM synonyms WHERE term = ? COLLATE NOCASE",
            (term.lower(),),
        ).fetchone()
        return row[0] if row else None

    def normalise_tokens(self, text: str) -> str:
        """Replace known tokens in text with their canonical forms.

        Tries longest multi-word matches first, then single words.
        """
        words = text.lower().split()
        result = []
        i = 0
        while i < len(words):
            matched = False
            # Try decreasing phrase lengths (max 4 words)
            for length in range(min(4, len(words) - i), 0, -1):
                phrase = " ".join(words[i : i + length])
                canonical = self.lookup(phrase)
                if canonical is not None:
                    result.append(canonical)
                    i += length
                    matched = True
                    break
            if not matched:
                result.append(words[i])
                i += 1
        return " ".join(result)

    def all_entries(self) -> list[dict]:
        """Return all synonym entries as dicts."""
        rows = self._conn.execute(
            "SELECT term, canonical, category, domain, notes FROM synonyms"
        ).fetchall()
        return [
            {"term": r[0], "canonical": r[1], "category": r[2],
             "domain": r[3], "notes": r[4]}
            for r in rows
        ]

    def close(self):
        self._conn.close()
```

**Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_synonyms.py -v`
Expected: All 4 tests pass

**Step 5: Commit**

```bash
git add synonyms.py tests/test_synonyms.py
git commit -m "feat: add SQLite synonym database for term normalisation"
```

---

### Task 5: Seed synonym database with initial data

**Files:**
- Create: `data/seed_synonyms.py`
- Create: `data/` directory

**Step 1: Write the seed script**

Create `data/seed_synonyms.py`:
```python
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
```

**Step 2: Run the seed script**

Run:
```bash
.venv/Scripts/python data/seed_synonyms.py
```
Expected: `Seeded XX synonyms to data/synonyms.db`

**Step 3: Write a test to verify seed data**

Append to `tests/test_synonyms.py`:
```python
import pathlib

def test_seed_db_exists():
    db_path = pathlib.Path(__file__).parent.parent / "data" / "synonyms.db"
    assert db_path.exists(), "Run 'python data/seed_synonyms.py' first"
    db = SynonymDB(db_path)
    entries = db.all_entries()
    assert len(entries) >= 40  # we seeded at least 40+ entries
    # Spot-check a few
    assert db.lookup("mv") == "motor vehicle"
    assert db.lookup("acc dep") == "accumulated depreciation"
    assert db.lookup("ammenities") == "amenities"
    db.close()
```

**Step 4: Run test**

Run: `.venv/Scripts/python -m pytest tests/test_synonyms.py -v`
Expected: All 5 tests pass

**Step 5: Commit**

```bash
git add data/ tests/test_synonyms.py
git commit -m "feat: seed synonym database with initial abbreviations, typos, and acronyms"
```

---

## Phase 2: Rule Extraction & Audit

Each task below extracts a category of rules from `mapping_logic_v15.py` into `rules.py`,
auditing and fixing each one. The 120 rules are grouped by functional category.

### Task 6: Create rules.py with bank/credit card rules (Rules 1-3)

**Files:**
- Create: `rules.py`
- Test: `tests/test_rules.py`

**Step 1: Write failing tests**

Create `tests/test_rules.py`:
```python
"""Tests for individual rules defined in rules.py."""
import pytest
from rule_engine import Rule, evaluate_rules, MatchContext
from rules import ALL_RULES, OWNER_KEYWORDS


def _ctx(text, raw_type="Expense", canon_type="expense", template="company"):
    return MatchContext(
        normalised_text=text,
        normalised_name=text,
        raw_type=raw_type,
        canon_type=canon_type,
        template_name=template,
        owner_keywords=OWNER_KEYWORDS,
    )


class TestBankRules:
    """Rules 1-3: Bank and credit card detection."""

    def test_bank_credit_card_by_name(self):
        ctx = _ctx("amplify credit card", raw_type="Bank", canon_type="bank")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.PAY"

    def test_bank_visa(self):
        ctx = _ctx("westpac visa", raw_type="Bank", canon_type="bank")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.PAY"

    def test_bank_amex(self):
        ctx = _ctx("american express platinum", raw_type="Bank", canon_type="bank")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.PAY"

    def test_bank_default(self):
        ctx = _ctx("westpac cheque account", raw_type="Bank", canon_type="bank")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.CUR.CAS.BAN"

    def test_liability_credit_card(self):
        ctx = _ctx("visa credit card", raw_type="Current Liability",
                    canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.PAY"
```

**Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_rules.py::TestBankRules -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rules'`

**Step 3: Create rules.py with bank rules**

Create `rules.py`:
```python
"""Declarative keyword rules for Xero reporting code assignment.

Each Rule instance defines conditions and an output reporting code.
Rules are evaluated by rule_engine.evaluate_rules() — highest priority wins.

Migrated from mapping_logic_v15.py keyword_match() and early overrides.
"""
from rule_engine import Rule

# --- Shared keyword lists ---
OWNER_KEYWORDS = [
    "owner a", "owner b", "proprietor", "drawings",
    "capital contributed", "funds introduced",
]

CREDIT_CARD_NAMES = [
    "amplify", "credit card", "visa", "mastercard",
    "american express", "amex",
]

BANK_NAMES = [
    "westpac", "nab", "anz", "cba", "macquarie", "stripe", "amplify",
]

VEHICLE_TOKENS = [
    "mv", "motor vehicle", "car", "truck", "vehicle",
]

VEHICLE_EXPENSE_TOKENS = [
    "fuel", "petrol", "oil", "repairs", "maintenance",
    "repairs maintenance", "servicing", "insurance", "ctp",
    "green slip", "rego", "registration", "parking",
    "road tolls", "tolls", "washing", "cleaning", "expenses",
]

COMMON_FIRST_NAMES = [
    "trent", "john", "mary", "peter", "sarah", "david",
    "michael", "james", "robert", "jennifer", "susan", "william",
]

PAYROLL_KW = [
    "payroll", "wages payable", "superannuation", "payg", "withholding",
]


# ============================================================
# RULES — grouped by category, ordered by priority within each
# ============================================================

# --- Bank / Credit Card (Priority 100+) ---
_bank_rules = [
    Rule(
        name="bank_credit_card",
        code="LIA.CUR.PAY",
        priority=105,
        keywords=CREDIT_CARD_NAMES,
        raw_types={"bank"},
        notes="Bank type account with credit card name → current payable",
    ),
    Rule(
        name="bank_default",
        code="ASS.CUR.CAS.BAN",
        priority=100,
        raw_types={"bank"},
        keywords_exclude=CREDIT_CARD_NAMES,
        notes="Bank type account without credit card name → bank account asset",
    ),
    Rule(
        name="liability_credit_card",
        code="LIA.CUR.PAY",
        priority=100,
        keywords=CREDIT_CARD_NAMES,
        raw_types={"current liability", "liability"},
        notes="Credit card name on a liability account → current payable",
    ),
]


# --- Collect all rules ---
ALL_RULES: list[Rule] = [
    *_bank_rules,
]
```

**Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_rules.py::TestBankRules -v`
Expected: All 5 pass

**Step 5: Commit**

```bash
git add rules.py tests/test_rules.py
git commit -m "feat: extract bank/credit card rules (3 rules) into declarative rules.py"
```

---

### Task 7: Extract owner/proprietor rules (Rules 4-7)

**Files:**
- Modify: `rules.py`
- Modify: `tests/test_rules.py`

**Step 1: Write failing tests**

Append to `tests/test_rules.py`:
```python
class TestOwnerRules:
    """Rules 4-7: Owner/proprietor account detection.

    Audit fix: COMMON_FIRST_NAMES matching (rule 7) is too aggressive.
    'St John's Ambulance' should NOT match. We add a word-boundary check
    by requiring the name token to appear as a standalone word AND
    requiring asset/equity type context.
    """

    def test_drawings(self):
        ctx = _ctx("owner a drawings", raw_type="Equity", canon_type="equity")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EQU.DRA"

    def test_funds_introduced_company(self):
        ctx = _ctx("owner a funds introduced", raw_type="Equity",
                    canon_type="equity", template="company")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.NCL.ADV"

    def test_funds_introduced_trust(self):
        ctx = _ctx("owner a funds introduced", raw_type="Equity",
                    canon_type="equity", template="trust")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EQU.ADV"

    def test_first_name_not_false_positive(self):
        """'St John's Ambulance' should NOT be classified as drawings."""
        ctx = _ctx("st johns ambulance donation", raw_type="Expense",
                    canon_type="expense")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code != "EQU.DRA", f"False positive: matched as {name}"

    def test_first_name_not_false_positive_peterson(self):
        """'Peterson Supplies' should NOT be classified as drawings."""
        ctx = _ctx("peterson supplies", raw_type="Expense",
                    canon_type="expense")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code != "EQU.DRA", f"False positive: matched as {name}"
```

**Step 2: Run tests, verify failures**

Run: `.venv/Scripts/python -m pytest tests/test_rules.py::TestOwnerRules -v`
Expected: FAIL (rules don't exist yet)

**Step 3: Add owner rules to rules.py**

Append to `rules.py` before the `ALL_RULES` collection:
```python
# --- Owner / Proprietor (Priority 90-95) ---
# Audit fix: removed COMMON_FIRST_NAMES catch-all (old rule 7).
# It was too aggressive — "St John's" matched "john", "Peterson" matched "peter".
# Owner detection should rely on OWNER_KEYWORDS which are specific enough.
_owner_rules = [
    Rule(
        name="owner_drawings",
        code="EQU.DRA",
        priority=95,
        keywords=["drawings"],
        owner_context=True,
        notes="Owner keyword + 'drawings' → equity drawings",
    ),
    Rule(
        name="owner_funds_introduced_company",
        code="LIA.NCL.ADV",
        priority=93,
        keywords=["capital contributed", "funds introduced", "share capital"],
        owner_context=True,
        template="company",
        notes="Owner keyword + capital/funds + Company template → NCL advance "
              "(companies use liability not equity for shareholder advances)",
    ),
    Rule(
        name="owner_funds_introduced_other",
        code="EQU.ADV",
        priority=92,
        keywords=["capital contributed", "funds introduced", "share capital"],
        owner_context=True,
        notes="Owner keyword + capital/funds + non-Company template → equity advance",
    ),
]
```

Update `ALL_RULES`:
```python
ALL_RULES: list[Rule] = [
    *_bank_rules,
    *_owner_rules,
]
```

**Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_rules.py::TestOwnerRules -v`
Expected: All 5 pass (including the two false-positive guards)

**Step 5: Commit**

```bash
git add rules.py tests/test_rules.py
git commit -m "feat: extract owner/proprietor rules, remove aggressive first-name matching

Audit fix: COMMON_FIRST_NAMES rule removed. It caused false positives
on accounts like 'St John's Ambulance' and 'Peterson Supplies'."
```

---

### Task 8: Extract revenue/grants rules (Rules 9-18)

**Files:**
- Modify: `rules.py`
- Modify: `tests/test_rules.py`

**Step 1: Write failing tests**

Append to `tests/test_rules.py`:
```python
class TestRevenueRules:
    """Rules 9-18: Revenue, grants, government income.

    Audit fixes:
    - 'grant' keyword now requires type guard (other income/revenue)
    - 'apprentice' removed from grants rule (apprentice wages is EXP.EMP)
    """

    def test_gross_receipts(self):
        ctx = _ctx("gross receipts", raw_type="Revenue", canon_type="revenue")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "REV.TRA.SER"

    def test_covid_grant(self):
        ctx = _ctx("covid 19 grant income", raw_type="Other Income",
                    canon_type="other income")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "REV.NON"

    def test_jobkeeper(self):
        ctx = _ctx("jobkeeper payments", raw_type="Other Income",
                    canon_type="other income")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "REV.GRA.GOV"

    def test_cash_flow_boost(self):
        ctx = _ctx("ato cash flow boost", raw_type="Other Income",
                    canon_type="other income")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "REV.NON"

    def test_grant_with_type_guard(self):
        """'grant' should only match as government grant for revenue types."""
        ctx = _ctx("government grant", raw_type="Other Income",
                    canon_type="other income")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "REV.GRA.GOV"

    def test_grant_not_false_positive_on_expense(self):
        """'Grant' in an expense context should NOT become a government grant."""
        ctx = _ctx("grant smith consulting fee", raw_type="Expense",
                    canon_type="expense")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code != "REV.GRA.GOV", f"False positive: matched as {name}"

    def test_apprentice_wages_not_grant(self):
        """'Apprentice Wages' should NOT be classified as a government grant."""
        ctx = _ctx("apprentice wages", raw_type="Direct Costs",
                    canon_type="direct costs")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code != "REV.GRA.GOV", f"False positive: matched as {name}"

    def test_reimbursement(self):
        ctx = _ctx("insurance reimbursement", raw_type="Other Income",
                    canon_type="other income")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "REV.OTH"

    def test_sale_of_asset_gain(self):
        ctx = _ctx("profit on sale of fixed asset", raw_type="Other Income",
                    canon_type="other income")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "REV.OTH.GAI"
```

**Step 2: Run tests, verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_rules.py::TestRevenueRules -v`
Expected: FAIL

**Step 3: Add revenue rules to rules.py**

Append before `ALL_RULES`:
```python
# --- Revenue / Grants / Government Income (Priority 80-90) ---
# Audit fixes:
# - 'grant' keyword now guarded by type check (other income / revenue only)
# - 'apprentice' removed from grants rule (apprentice wages is EXP.EMP.WAG)
# - 'rebate' removed from grants rule (too broad — insurance rebate is EXP.INS)
_revenue_rules = [
    Rule(
        name="gross_receipts",
        code="REV.TRA.SER",
        priority=85,
        keywords=["gross receipts"],
        canon_types={"revenue", "income", "other income"},
        notes="Gross receipts for revenue types → trading services",
    ),
    Rule(
        name="covid_grant",
        code="REV.NON",
        priority=90,
        keywords_all=["covid", "grant"],
        notes="Covid-related grants → non-assessable income. "
              "Also matches 'covid 19' and 'covid-19' after normalisation.",
    ),
    Rule(
        name="jobkeeper",
        code="REV.GRA.GOV",
        priority=90,
        keywords=["jobkeeper", "job keeper", "jobsaver"],
        notes="Government wage subsidies → government grants",
    ),
    Rule(
        name="cash_flow_boost",
        code="REV.NON",
        priority=90,
        keywords=["cash flow boost", "cashflow boost", "ato cash boost",
                  "cash boost", "non assessable"],
        notes="Government cash flow boost → non-assessable income",
    ),
    Rule(
        name="government_grant",
        code="REV.GRA.GOV",
        priority=80,
        keywords=["grant", "service nsw"],
        canon_types={"other income", "revenue", "income"},
        keywords_exclude=["covid"],
        notes="Audit fix: 'grant' now guarded by revenue/other income type. "
              "'apprentice' and 'rebate' removed (too broad).",
    ),
    Rule(
        name="reimbursement_income",
        code="REV.OTH",
        priority=75,
        keywords=["reimburse", "reimbursement"],
        canon_types={"other income", "revenue", "income"},
        notes="Reimbursements received → other income",
    ),
    Rule(
        name="workers_comp_recovery",
        code="REV.OTH",
        priority=78,
        keywords=["workers comp recovery", "workcover recovery",
                  "workers compensation recovery"],
        canon_types={"other income", "revenue", "income"},
        notes="Workers comp recoveries → other income",
    ),
    Rule(
        name="fbt_reimbursement",
        code="REV.OTH",
        priority=78,
        keywords=["fbt contribution", "fbt reimbursement", "fbt reimburse"],
        canon_types={"other income", "revenue", "income"},
        notes="FBT reimbursements → other income",
    ),
    Rule(
        name="sale_of_asset_gain",
        code="REV.OTH.GAI",
        priority=80,
        keywords=["sale of fixed asset", "sale of asset",
                  "profit loss on sale of fixed asset"],
        notes="Profit/loss on sale of fixed asset → other gains",
    ),
    Rule(
        name="sale_proceeds",
        code="REV.OTH.INV",
        priority=78,
        keywords=["sale proceeds", "sale proceed"],
        canon_types={"other income", "revenue", "income"},
        notes="Investment sale proceeds → other investment income",
    ),
]
```

Update `ALL_RULES`:
```python
ALL_RULES: list[Rule] = [
    *_bank_rules,
    *_owner_rules,
    *_revenue_rules,
]
```

**Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_rules.py::TestRevenueRules -v`
Expected: All 9 pass

**Step 5: Commit**

```bash
git add rules.py tests/test_rules.py
git commit -m "feat: extract revenue/grant rules with audit fixes

- 'grant' now requires revenue/other income type guard
- 'apprentice' removed from grants (apprentice wages is EXP.EMP)
- 'rebate' removed from grants (insurance rebate is EXP.INS)"
```

---

### Task 9: Extract payroll/employee rules (Rules 25-32)

**Files:**
- Modify: `rules.py`
- Modify: `tests/test_rules.py`

Follow the same pattern as Tasks 6-8:
1. Write tests covering wages (direct cost vs expense), superannuation routing, payroll liabilities, PAYG
2. Add rules to `_payroll_rules` list
3. Key rules:
   - `wages_direct_cost` → `EXP.COS.WAG` (priority 95, raw_types: direct costs/cost of sales/purchases)
   - `wages_expense` → `EXP.EMP.WAG` (priority 93, canon_types: expense)
   - `super_direct_cost` → `EXP.COS` (priority 93, raw_types: direct costs)
   - `super_expense` → `EXP.EMP.SUP` (priority 91, canon_types: expense)
   - `super_payable` → `LIA.CUR.PAY.EMP` (priority 92, keywords: superannuation+payable or raw_types: current liability)
   - `wages_payable` → `LIA.CUR.PAY.EMP` (priority 95, keywords: wages payable/withholding/paygw)
   - `payg_instalment` → `LIA.CUR.TAX.INC` (priority 95, keywords: payg instalment)
4. Run tests, commit

---

### Task 10: Extract vehicle expense rules (Rules 33-36)

Follow same pattern. Key rules:
- `green_slip` → `EXP.VEH` (priority 70, keywords: green slip, canon_types: expense)
- `vehicle_interest` → `EXP.VEH` (priority 75, keywords_all: [vehicle_token, interest], canon_types: expense)
- `vehicle_insurance` → `EXP.VEH` (priority 75, keywords_all: [vehicle_token, insurance/rego/ctp], canon_types: expense)
- `vehicle_expense_combined` → `EXP.VEH` (priority 72, requires vehicle_token AND expense_token, excludes deprec)
- `trailer_expense` → `EXP.VEH` (priority 70, keywords: trailer, canon_types: expense)

---

### Task 11: Extract loan/hire purchase rules (Rules 20-24, 81-82, 87-99)

Follow same pattern. Audit fix for rule 20: company loans should check account type to determine direction.
- `loan_to_pty` → `ASS.NCA.REL` only if asset type; add separate rule for liability types
- `director_loan_to` → `ASS.NCA.DIR`
- `director_loan_from` → `LIA.NCL.LOA`
- HP/chattel mortgage rules with current/non-current routing
- Generic loan fallback rules by type

---

### Task 12: Extract tax/GST rules (Rules 40-43)

Follow same pattern:
- `gst_liability` → `LIA.CUR.TAX.GST`
- `bas_payable` → `LIA.CUR.TAX`
- `bas_clearing` → `LIA.CUR.TAX`
- `accrued_income_liability` → `LIA.CUR.DEF`

---

### Task 13: Extract general expense rules (Rules 44-79)

This is the largest batch (~35 rules). Follow the same pattern, grouping into sub-categories:
- Materials/subcontractor rules
- Training/uniform/staff rules (with audit fix for broad 'staff' catch-all)
- Insurance (workers comp vs general)
- Utilities (phone/internet/power)
- Administrative/office
- Professional fees
- Depreciation/amortisation
- Travel (national/international)
- Fines/penalties
- Advertising/marketing
- Bank fees
- Cleaning
- Cost of sales catch-all (audit: fix dead code at line 550)

---

### Task 14: Extract equity/shares/retained earnings rules (Rules 83-86)

Follow same pattern:
- `ordinary_shares` → `EQU.SHA.ORD`
- `paid_up_capital` → `EQU.SHA.ORD`
- `shares_asset` → `ASS.NCA.INV.SHA`
- `retained_earnings` → `EQU.RET`

---

### Task 15: Extract remaining rules (Rules 8, 19, 37-39, 80, 93-95, 120)

Follow same pattern for uncategorized rules:
- Cash/petty cash
- Sundry debtors/retentions
- Preliminary expenses
- Industry-specific (building & construction)
- Premium funding
- WIPAA
- Borrowing costs
- Accumulated depreciation (contextual — may need special handling)

---

### Task 16: Remove dead code and duplicates

**Files:**
- Modify: `rules.py` (verify no duplicate rules)
- Modify: `mapping_logic_v15.py`

**Step 1: Verify no duplicate rules in rules.py**

Write a test:
```python
def test_no_duplicate_rule_names():
    names = [r.name for r in ALL_RULES]
    assert len(names) == len(set(names)), f"Duplicate names: {[n for n in names if names.count(n) > 1]}"
```

**Step 2: Remove the duplicate elif blocks from mapping_logic_v15.py (lines 934-939)**

These are now handled by the rule table. The entire `keyword_match` function and early overrides
will be replaced in Task 17.

**Step 3: Commit**

---

### Task 17: Rewire mapping_logic_v15.py to use rule engine

**Files:**
- Modify: `mapping_logic_v15.py`

**Step 1: Replace keyword_match() calls with rule engine**

The main loop currently has:
1. Step 1: Bank keyword match (line 873-876)
2. Step 1b: Early overrides (lines 879-939)
3. Step 7: keyword_match() (lines 1011-1014)

Replace all three with:
```python
from rule_engine import evaluate_rules, MatchContext
from rules import ALL_RULES, OWNER_KEYWORDS

# ... in the main loop ...
if not chosen:
    ctx = MatchContext(
        normalised_text=txt_inline,
        normalised_name=normalise(strip_noise_suffixes(row['*Name'])),
        raw_type=row['*Type'].strip(),
        canon_type=canon_type,
        template_name=str(args.chart_template_name or ''),
        owner_keywords=OWNER_KEYWORDS,
    )
    rc, rule_name = evaluate_rules(ALL_RULES, ctx)
    if rc:
        chosen, reason = rc, rule_name
```

**Step 2: Keep the non-keyword pipeline steps unchanged**

These stay as-is:
- Accumulated depreciation logic (steps 1c, 7b)
- DefaultChart code/name matching (steps 2-6)
- Head consistency enforcement
- Post-processing passes

**Step 3: Remove the old keyword_match function entirely**

Delete the `keyword_match()` function (lines 275-622) and the early override block (lines 879-939).
Keep the utility functions: `normalise()`, `canonical_type()`, `head_from_type()`, etc.

**Step 4: Run the mapper on the example data to verify it still works**

Run:
```bash
.venv/Scripts/python mapping_logic_v15.py examples/ChartOfAccounts_NoArchive.csv examples/Demo_Company__AU__-_Trial_Balance.xlsx --chart Company
```
Expected: Produces AugmentedChartOfAccounts.csv without errors

**Step 5: Commit**

```bash
git add mapping_logic_v15.py
git commit -m "refactor: replace keyword_match and early overrides with rule engine

The 120 if/elif heuristic rules are now in rules.py as declarative Rule
instances evaluated by rule_engine.py. Each rule has explicit priority,
type constraints, and keyword conditions."
```

---

## Phase 3: Test Framework

### Task 18: Write rule integrity tests

**Files:**
- Create: `tests/test_rules_integrity.py`

**Step 1: Write tests that validate every rule's code against SystemMappings**

```python
"""Verify every rule's output code is valid and type-compatible."""
import pandas as pd
import pathlib
import json
import pytest
from rules import ALL_RULES

PROJECT_ROOT = pathlib.Path(__file__).parent.parent


@pytest.fixture(scope="module")
def system_mappings():
    return pd.read_csv(PROJECT_ROOT / "SystemFiles" / "SystemMappings.csv")


@pytest.fixture(scope="module")
def type_rules():
    with open(PROJECT_ROOT / "SystemFiles" / "Account_Types_per_Financial-Reports.json") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def allowed_codes(system_mappings):
    return set(system_mappings["Reporting Code"].astype(str).str.strip())


@pytest.mark.parametrize("rule", ALL_RULES, ids=lambda r: r.name)
def test_rule_code_exists(rule, allowed_codes):
    """Every rule's output code must exist in SystemMappings."""
    assert rule.code in allowed_codes, (
        f"Rule '{rule.name}' outputs code '{rule.code}' "
        f"which does not exist in SystemMappings.csv"
    )


@pytest.mark.parametrize("rule", ALL_RULES, ids=lambda r: r.name)
def test_rule_code_type_compatible(rule, type_rules):
    """If a rule declares type constraints, its output code must be allowed for those types."""
    types_to_check = rule.raw_types | rule.canon_types
    if not types_to_check:
        pytest.skip("Rule has no type constraints")
    for account_type in types_to_check:
        type_key = account_type.strip().title()  # Match JSON keys
        if type_key not in type_rules:
            continue  # Unknown type, skip
        allowed = set(type_rules[type_key].get("allowed_codes", []))
        prefixes = set(type_rules[type_key].get("allowed_prefixes", []))
        code_prefix = rule.code.split(".")[0]
        code_ok = rule.code in allowed or code_prefix in prefixes
        assert code_ok, (
            f"Rule '{rule.name}' outputs '{rule.code}' which is not allowed "
            f"for type '{account_type}'. Allowed: {sorted(allowed)[:10]}..."
        )
```

**Step 2: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_rules_integrity.py -v`
Expected: All pass (if any fail, fix the rule's code or type constraint)

**Step 3: Commit**

```bash
git add tests/test_rules_integrity.py
git commit -m "test: add rule integrity tests (code validity and type compatibility)"
```

---

### Task 19: Extract validated datasets into test fixtures

**Files:**
- Create: `tests/fixtures/validated/` directory
- Copy validated_final CSVs from `.dev-info/`

**Step 1: Copy validated data**

```bash
mkdir -p tests/fixtures/validated
cp ".dev-info/old-codebases/Report Code Mapping - Data Analysis/output/"*_validated_final.csv tests/fixtures/validated/
```

**Step 2: Write a manifest test**

Create `tests/test_fixtures.py`:
```python
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
    required = {"Name", "Type", "SuggestedReportingCode", "ValidatedReportingCode"}
    actual = set(headers)
    missing = required - actual
    assert not missing, f"{csv_file.name} missing columns: {missing}"
```

**Step 3: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_fixtures.py -v`
Expected: All pass

**Step 4: Commit**

```bash
git add tests/fixtures/ tests/test_fixtures.py
git commit -m "test: add validated client datasets as test fixtures"
```

---

### Task 20: Write integration tests with HTML report

**Files:**
- Create: `tests/test_integration.py`
- Create: `pytest.ini` or `pyproject.toml` pytest config

**Step 1: Add pytest config to pyproject.toml**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--html=tests/report.html --self-contained-html"
```

**Step 2: Write integration test**

Create `tests/test_integration.py`:
```python
"""Integration tests: run mapper rules against validated client datasets.

Each row in the validated CSVs has:
- Name, Type: the input account
- SuggestedReportingCode: what the old mapper suggested
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
    """Load all validated rows across all fixture files."""
    rows = []
    for csv_file in sorted(FIXTURES_DIR.glob("*_validated_final.csv")):
        with open(csv_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                validated = row.get("ValidatedReportingCode", "").strip()
                if validated:  # Skip rows without a validated code
                    rows.append({
                        "file": csv_file.name,
                        "code": row.get("Code", ""),
                        "name": row.get("Name", ""),
                        "type": row.get("Type", ""),
                        "suggested": row.get("SuggestedReportingCode", ""),
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

    # If the rule engine produced a code, check it matches validated
    # If no match (None), we flag it but don't fail — some rows require
    # template/fuzzy matching which is outside the rule engine's scope
    if code is not None:
        assert code == row["validated"], (
            f"Mismatch: name='{row['name']}', type='{row['type']}'\n"
            f"  Rule engine: {code} (via {rule_name})\n"
            f"  Validated:   {row['validated']}\n"
            f"  Old mapper:  {row['suggested']}"
        )
```

**Step 3: Run tests with HTML report**

Run:
```bash
.venv/Scripts/python -m pytest tests/test_integration.py -v --html=tests/report.html --self-contained-html
```
Expected: Some tests pass, some fail (mismatches for user review). HTML report generated.

**Step 4: Commit**

```bash
git add tests/test_integration.py pyproject.toml
git commit -m "test: add integration tests against validated datasets with HTML report"
```

---

## Summary

| Phase | Tasks | What it delivers |
|-------|-------|-----------------|
| 1: Infrastructure | 1-5 | uv env, Rule dataclass, engine, synonym DB |
| 2: Rule extraction | 6-17 | 120 rules migrated to rules.py, audited, bugs fixed |
| 3: Tests | 18-20 | Rule integrity, per-rule unit tests, integration + HTML report |

**Known audit fixes applied during extraction:**
1. COMMON_FIRST_NAMES removed (false positives on "St John's", "Peterson")
2. 'grant' keyword guarded by revenue/other income type
3. 'apprentice' removed from grants rule
4. Company loan direction fixed with type-aware routing
5. Broad 'staff' catch-all given lower priority
6. Duplicate elif blocks removed (trailer, council rates)
7. Dead code removed (cost of sales inside expense guard)
8. Operator precedence made explicit
