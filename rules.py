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
        notes="Bank type account with credit card name -> current payable",
    ),
    Rule(
        name="bank_default",
        code="ASS.CUR.CAS.BAN",
        priority=100,
        raw_types={"bank"},
        keywords_exclude=CREDIT_CARD_NAMES,
        notes="Bank type account without credit card name -> bank account asset",
    ),
    Rule(
        name="liability_credit_card",
        code="LIA.CUR.PAY",
        priority=100,
        keywords=CREDIT_CARD_NAMES,
        raw_types={"current liability", "liability"},
        notes="Credit card name on a liability account -> current payable",
    ),
]


# --- Collect all rules ---
ALL_RULES: list[Rule] = [
    *_bank_rules,
]
