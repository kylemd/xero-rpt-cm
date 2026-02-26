"""Tests for spell correction preprocessing."""
import pytest
from spell_corrections import (
    ABBREVIATIONS, ACCOUNTING_TERMS,
    build_spell_checker, correct_account_name,
)


class TestAbbreviations:
    def test_scg_expands_to_sgc(self):
        result = correct_account_name("ATO - SCG payable", spell=None)
        assert "sgc" in result["corrected"].lower()

    def test_lsl_expands(self):
        result = correct_account_name("LSL Provision", spell=None)
        assert "long service leave" in result["corrected"].lower()

    def test_no_change_when_no_abbreviation(self):
        result = correct_account_name("Trade Debtors", spell=None)
        assert result["corrected"] == "Trade Debtors"
        assert result["corrections"] == []


class TestSpellChecker:
    @pytest.fixture
    def spell(self):
        return build_spell_checker(extra_known=[])

    def test_revalution_corrected(self, spell):
        result = correct_account_name("Asset Revalution Reserve", spell=spell)
        assert "revaluation" in result["corrected"].lower()
        assert len(result["corrections"]) == 1
        assert result["corrections"][0]["original"] == "Revalution"

    def test_known_terms_not_corrected(self, spell):
        result = correct_account_name("PAYG Withholding", spell=spell)
        # PAYG should not be corrected to an English word
        assert "payg" in result["corrected"].lower()

    def test_bank_names_whitelisted(self):
        from rules import AUSTRALIAN_BANKS
        spell = build_spell_checker(extra_known=AUSTRALIAN_BANKS)
        result = correct_account_name("Westpac Business Account", spell=spell)
        assert "westpac" in result["corrected"].lower()
        assert result["corrections"] == []

    def test_business_name_whitelisted(self):
        spell = build_spell_checker(extra_known=["acmecorp", "invigor8"])
        result = correct_account_name("Invigor8 Loan Account", spell=spell)
        assert result["corrections"] == []


class TestBuildSpellChecker:
    def test_accounting_terms_are_known(self):
        spell = build_spell_checker(extra_known=[])
        unknown = spell.unknown(["payg", "ato", "gst", "asic", "fbt"])
        assert len(unknown) == 0

    def test_extra_known_words_added(self):
        spell = build_spell_checker(extra_known=["westpac", "commbank"])
        unknown = spell.unknown(["westpac", "commbank"])
        assert len(unknown) == 0
