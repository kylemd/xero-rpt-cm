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
