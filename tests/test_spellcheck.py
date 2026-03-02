"""Tests for spell correction preprocessing."""
import pytest
from spell_corrections import (
    ABBREVIATIONS, ACCOUNTING_TERMS,
    build_spell_checker, correct_account_name,
)


class TestAbbreviations:
    def test_scg_expands_to_sgc(self):
        result = correct_account_name("SCG payable", spell=None)
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


class TestDashSeparator:
    """Spell correction should only apply to text before ' - ' separator."""

    @pytest.fixture
    def spell(self):
        return build_spell_checker(extra_known=[])

    def test_hendra_preserved(self, spell):
        result = correct_account_name("Motor Vehicle Expenses - Hendra", spell=spell)
        assert "Hendra" in result["corrected"]

    def test_vieira_preserved(self, spell):
        result = correct_account_name("Loan - M Vieira", spell=spell)
        assert "Vieira" in result["corrected"]

    def test_prefix_still_corrected(self, spell):
        result = correct_account_name("Revalution Reserve - XYZ Corp", spell=spell)
        assert "revaluation" in result["corrected"].lower()
        assert "XYZ Corp" in result["corrected"]

    def test_no_separator_still_works(self, spell):
        result = correct_account_name("Revalution Reserve", spell=spell)
        assert "revaluation" in result["corrected"].lower()


class TestAcronymWhitelist:
    """Australian acronyms should not be spell-corrected."""

    @pytest.fixture
    def spell(self):
        return build_spell_checker(extra_known=[])

    def test_eftpos_not_corrected(self, spell):
        result = correct_account_name("EFTPOS Charges", spell=spell)
        assert "EFTPOS" in result["corrected"]
        assert all(c["original"] != "EFTPOS" for c in result["corrections"])

    def test_ctp_not_corrected(self, spell):
        result = correct_account_name("CTP Insurance", spell=spell)
        assert "CTP" in result["corrected"]
        assert all(c["original"] != "CTP" for c in result["corrections"])

    def test_sbe_not_corrected(self, spell):
        result = correct_account_name("SBE Pool", spell=spell)
        assert "SBE" in result["corrected"]
        assert all(c["original"] != "SBE" for c in result["corrections"])


class TestTrialBalanceCompanyName:
    def test_metadata_includes_company_name(self):
        """Trial balance metadata should include the company name from row 1."""
        import pathlib
        from file_handler import load_trial_balance_file
        tb_path = pathlib.Path(".dev-info/test-client/Trial_Balance.xlsx")
        if not tb_path.exists():
            pytest.skip("Test client trial balance not available")
        _, metadata = load_trial_balance_file(tb_path)
        assert "company_name" in metadata
        assert isinstance(metadata["company_name"], str)
        assert len(metadata["company_name"]) > 0
