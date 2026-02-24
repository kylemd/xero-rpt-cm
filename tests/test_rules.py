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
