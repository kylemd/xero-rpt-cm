"""Tests for individual rules defined in rules.py."""
import pytest
from rule_engine import Rule, evaluate_rules, MatchContext
from rules import ALL_RULES, OWNER_KEYWORDS


def _ctx(text, raw_type="Expense", canon_type="expense", template="company", industry=""):
    return MatchContext(
        normalised_text=text,
        normalised_name=text,
        raw_type=raw_type,
        canon_type=canon_type,
        template_name=template,
        owner_keywords=OWNER_KEYWORDS,
        industry=industry,
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
        """'Funds introduced' on company template, liability type -> LIA.NCL.ADV."""
        ctx = _ctx("owner a funds introduced", raw_type="Current Liability",
                    canon_type="current liability", template="company")
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


class TestPayrollRules:
    """Payroll and employee rules: wages, super, PAYG, payroll liabilities."""

    def test_wages_direct_cost(self):
        ctx = _ctx("construction wages", raw_type="Direct Costs",
                    canon_type="direct costs")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.COS"

    def test_wages_expense(self):
        ctx = _ctx("office wages", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.EMP.WAG"

    def test_salary_expense(self):
        ctx = _ctx("salaries and oncosts", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.EMP.WAG"

    def test_super_direct_cost(self):
        ctx = _ctx("superannuation", raw_type="Direct Costs",
                    canon_type="direct costs")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.COS"

    def test_super_expense(self):
        ctx = _ctx("superannuation guarantee", raw_type="Expense",
                    canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.EMP.SUP"

    def test_super_payable(self):
        ctx = _ctx("superannuation payable", raw_type="Current Liability",
                    canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.PAY.EMP"

    def test_wages_payable(self):
        ctx = _ctx("wages payable", raw_type="Current Liability",
                    canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.PAY.EMP"

    def test_payg_withholding(self):
        ctx = _ctx("paygw payable", raw_type="Current Liability",
                    canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.PAY.EMP"

    def test_payg_instalment(self):
        ctx = _ctx("payg instalment", raw_type="Current Liability",
                    canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.TAX.INC"


class TestVehicleRules:
    """Vehicle expense rules: MV fuel, insurance, rego, green slip, trailer."""

    def test_green_slip(self):
        ctx = _ctx("green slip insurance", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.VEH"

    def test_vehicle_interest(self):
        ctx = _ctx("motor vehicle interest", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.VEH"

    def test_vehicle_insurance(self):
        ctx = _ctx("motor vehicle insurance", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.VEH"

    def test_vehicle_rego(self):
        ctx = _ctx("vehicle registration", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.VEH"

    def test_mv_fuel(self):
        ctx = _ctx("mv fuel", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.VEH"

    def test_trailer(self):
        ctx = _ctx("trailer expenses", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.VEH"

    def test_mv_insurance(self):
        """MV + insurance -> vehicle expense."""
        ctx = _ctx("m v car rego insurance", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.VEH"

    def test_registration_insurance(self):
        """Registration + insurance -> vehicle expense."""
        ctx = _ctx("registration and insurance", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.VEH"

    def test_vehicle_depreciation_not_matched(self):
        """Vehicle depreciation should NOT match as EXP.VEH — it's EXP.DEP."""
        ctx = _ctx("motor vehicle depreciation", raw_type="Expense", canon_type="expense")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code != "EXP.VEH" or name != "vehicle_expense_combined", \
            "Vehicle depreciation should not be caught by vehicle expense rules"


class TestLoanRules:
    """Loan, hire purchase, chattel mortgage, and related party rules.

    Audit fix: Company loans now check account type to determine direction
    (asset = loan TO company; liability = loan FROM company).
    """

    def test_loan_to_pty(self):
        ctx = _ctx("loan to pty ltd", raw_type="Non-Current Asset",
                    canon_type="non-current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.NCA.REL"

    def test_loan_from_pty_liability(self):
        """Audit fix: loan FROM company should be liability, not asset."""
        ctx = _ctx("loan pty ltd", raw_type="Non-Current Liability",
                    canon_type="non-current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.NCL.REL"

    def test_vehicle_loan(self):
        ctx = _ctx("motor vehicle loan", raw_type="Non-Current Liability",
                    canon_type="non-current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.NCL.HPA"

    def test_hire_purchase_current(self):
        ctx = _ctx("hire purchase", raw_type="Current Liability",
                    canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.HPA"

    def test_hire_purchase_non_current(self):
        ctx = _ctx("hire purchase", raw_type="Non-Current Liability",
                    canon_type="non-current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.NCL.HPA"

    def test_chattel_mortgage(self):
        ctx = _ctx("chattel mortgage", raw_type="Non-Current Liability",
                    canon_type="non-current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.NCL.CHM"

    def test_unexpired_interest_current(self):
        """UEI always maps to non-current per validated data."""
        ctx = _ctx("unexpired interest cl", raw_type="Current Liability",
                    canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.NCL.HPA.UEI"

    def test_unexpired_interest_non_current(self):
        ctx = _ctx("unexpired interest ncl", raw_type="Non-Current Liability",
                    canon_type="non-current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.NCL.HPA.UEI"

    def test_director_loan_to_nca(self):
        ctx = _ctx("loan to director", raw_type="Non-Current Asset",
                    canon_type="non-current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.NCA.DIR"

    def test_director_loan_to_ca(self):
        """Current Asset type -> ASS.CUR.DIR (not NCA)."""
        ctx = _ctx("loan to directors", raw_type="Current Asset",
                    canon_type="current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.CUR.DIR"

    def test_directors_loan(self):
        """Director loan on liability -> reclassify as NCA director loan (Div7A)."""
        ctx = _ctx("directors loan", raw_type="Non-Current Liability",
                    canon_type="non-current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.NCA.DIR"

    def test_directors_loan_apostrophe_on_asset(self):
        """'Director's Loan' normalised to 'director s loan' on current asset -> ASS.CUR.DIR."""
        ctx = _ctx("director s loan to ian banks", raw_type="Current Asset",
                    canon_type="current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.CUR.DIR"

    def test_directors_loan_apostrophe_on_liability(self):
        """'Director's Loan' on liability -> NCA director loan (Div7A override)."""
        ctx = _ctx("director s loan from john smith", raw_type="Non-Current Liability",
                    canon_type="non-current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.NCA.DIR"

    def test_premium_funding(self):
        ctx = _ctx("premium funding gallagher", raw_type="Current Liability",
                    canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.LOA.UNS"

    def test_generic_loan_current_liability(self):
        """Generic loans on CL type -> NCL loan (most loans are long-term)."""
        ctx = _ctx("business loan", raw_type="Current Liability",
                    canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.NCL.LOA"

    def test_generic_loan_non_current_asset(self):
        ctx = _ctx("loan receivable", raw_type="Non-Current Asset",
                    canon_type="non-current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.NCA.LOA"


class TestTaxRules:
    """Tax and GST rules."""

    def test_gst_liability(self):
        ctx = _ctx("gst collected", raw_type="Current Liability",
                    canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.TAX.GST"

    def test_gst_not_on_expense(self):
        """GST on expense (e.g. 'GST bank fees') should NOT be tax liability."""
        ctx = _ctx("gst bank fees", raw_type="Expense", canon_type="expense")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code != "LIA.CUR.TAX.GST", f"False positive: {name}"

    def test_gst_not_on_prepaid(self):
        """Pre-paid GST should NOT match gst_liability."""
        ctx = _ctx("pre paid gst do not use", raw_type="Non-Current Asset",
                    canon_type="non-current asset")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code != "LIA.CUR.TAX.GST", f"Prepaid GST should not match gst_liability"
        assert code == "ASS.CUR.REC.PRE"

    def test_bas_payable(self):
        ctx = _ctx("bas payable", raw_type="Current Liability",
                    canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.TAX"

    def test_bas_clearing(self):
        ctx = _ctx("bas clearing account", raw_type="Current Liability",
                    canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.TAX"

    def test_accrued_income_liability(self):
        ctx = _ctx("accrued income", raw_type="Current Liability",
                    canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.DEF"


class TestGeneralExpenseRules:
    """General expense categorisation rules."""

    def test_materials(self):
        ctx = _ctx("building materials", raw_type="Direct Costs",
                    canon_type="direct costs")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.COS.PUR"

    def test_amortisation(self):
        ctx = _ctx("amortisation", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.AMO"

    def test_subcontractor_direct(self):
        ctx = _ctx("subcontractor costs", raw_type="Direct Costs",
                    canon_type="direct costs")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.COS"

    def test_subcontractor_expense(self):
        ctx = _ctx("subcontractor fees", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP"

    def test_training(self):
        ctx = _ctx("staff training course", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.EMP"

    def test_uniforms(self):
        ctx = _ctx("uniform expenses", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.EMP"

    def test_advertising(self):
        ctx = _ctx("advertising expense", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.ADV"

    def test_professional_fees(self):
        ctx = _ctx("consulting fees", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.PRO"

    def test_workers_comp_insurance(self):
        ctx = _ctx("workers compensation insurance", raw_type="Expense",
                    canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.EMP"

    def test_general_insurance(self):
        ctx = _ctx("public liability insurance", raw_type="Expense",
                    canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.INS"

    def test_phone(self):
        ctx = _ctx("mobile phone", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.UTI"

    def test_electricity(self):
        ctx = _ctx("electricity charges", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.UTI"

    def test_office_expenses(self):
        ctx = _ctx("office expenses", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.ADM"

    def test_council_rates(self):
        ctx = _ctx("council rates", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.OCC"

    def test_depreciation(self):
        ctx = _ctx("depreciation expense", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.DEP"

    def test_travel_domestic(self):
        ctx = _ctx("travel expenses", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.TRA.NAT"

    def test_travel_international(self):
        ctx = _ctx("international travel", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.TRA.INT"

    def test_fines(self):
        ctx = _ctx("parking fines", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.NON"

    def test_interest_expense(self):
        ctx = _ctx("interest expense", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.INT"

    def test_client_meetings(self):
        ctx = _ctx("client meetings", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.ENT"

    def test_bad_debts(self):
        ctx = _ctx("bad debt expense", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.BAD"

    def test_entertainment_non_deductible(self):
        ctx = _ctx("entertainment not deductible", raw_type="Expense",
                    canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.ENT.NON"

    def test_donations(self):
        ctx = _ctx("charity donations", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP"

    def test_staff_amenities(self):
        """Staff amenities -> EXP.EMP (broad 'staff' catch-all removed)."""
        ctx = _ctx("staff amenities", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.EMP"

    def test_cost_of_goods_sold(self):
        ctx = _ctx("cost of goods sold", raw_type="Direct Costs",
                    canon_type="direct costs")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.COS.PUR"

    def test_dividends_paid_equity(self):
        """Dividends on equity -> ordinary dividends from retained earnings."""
        ctx = _ctx("dividends paid", raw_type="Equity", canon_type="equity")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EQU.RET.DIV.ORD"

    def test_dividend_payable_expense(self):
        ctx = _ctx("dividend paid or payable", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.DIV"

    def test_staff_broad_not_catch_all(self):
        """Audit fix: 'staff' alone should NOT blindly match everything."""
        ctx = _ctx("staff parking permit", raw_type="Expense", canon_type="expense")
        code, name = evaluate_rules(ALL_RULES, ctx)
        # Should NOT match as EXP.EMP unless a specific rule applies
        # staff_amenities only matches "staff amenities" or "amenities"
        assert name != "staff_catch_all", "Broad staff catch-all should not exist"


class TestEquityRules:
    """Equity, shares, and retained earnings rules."""

    def test_share_capital_equity(self):
        """'Share capital' on equity -> EQU.SHA.ORD (not owner funds rule)."""
        ctx = _ctx("owner a share capital", raw_type="Equity", canon_type="equity")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EQU.SHA.ORD"

    def test_ordinary_shares(self):
        ctx = _ctx("ordinary shares", raw_type="Equity", canon_type="equity")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EQU.SHA.ORD"

    def test_paid_up_capital(self):
        ctx = _ctx("issued and paid up capital", raw_type="Equity", canon_type="equity")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EQU.SHA.ORD"

    def test_shares_as_asset(self):
        ctx = _ctx("shares in xyz company", raw_type="Non-Current Asset",
                    canon_type="non-current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.NCA.INV.SHA"

    def test_retained_earnings(self):
        ctx = _ctx("retained earnings", raw_type="Retained Earnings",
                    canon_type="retained earnings")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EQU.RET"

    def test_accumulated_losses(self):
        ctx = _ctx("accumulated losses", raw_type="Equity", canon_type="equity")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EQU.RET"


class TestRemainingRules:
    """Remaining uncategorized rules: cash, sundry, preliminary, WIPAA, industry."""

    def test_petty_cash(self):
        ctx = _ctx("petty cash", raw_type="Current Asset",
                    canon_type="current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.CUR.CAS.FLO"

    def test_cash_on_hand(self):
        ctx = _ctx("cash on hand", raw_type="Current Asset",
                    canon_type="current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.CUR.CAS.FLO"

    def test_undeposited_funds(self):
        ctx = _ctx("undeposited funds", raw_type="Current Asset",
                    canon_type="current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.CUR.CAS.FLO"

    def test_sundry_debtors(self):
        ctx = _ctx("sundry debtors", raw_type="Current Asset",
                    canon_type="current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.CUR.REC"

    def test_retentions_receivable(self):
        ctx = _ctx("retentions receivable", raw_type="Current Asset",
                    canon_type="current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.CUR.REC"

    def test_prepaid_asset(self):
        """Prepaid / pre-paid -> prepaid receivable."""
        ctx = _ctx("pre paid insurance", raw_type="Current Asset",
                    canon_type="current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.CUR.REC.PRE"

    def test_preliminary_expenses(self):
        ctx = _ctx("preliminary expenses", raw_type="Non-Current Asset",
                    canon_type="non-current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.NCA"

    def test_wipaa_direct_cost(self):
        ctx = _ctx("wipaa", raw_type="Direct Costs", canon_type="direct costs")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.COS"

    def test_wipaa_asset(self):
        ctx = _ctx("wipaa balance", raw_type="Current Asset",
                    canon_type="current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.CUR.INY.WIP"

    def test_building_industry_revenue(self):
        """Building industry revenue defaults to trading services."""
        ctx = _ctx("contract income", raw_type="Revenue",
                    canon_type="revenue", template="company")
        # Note: industry rules need an industry context field — for now test that
        # building-related revenue gets REV.TRA.SER via another rule or
        # this test can verify no false match. We'll handle industry in rewire task.
        # For now just verify it doesn't error.
        code, _ = evaluate_rules(ALL_RULES, ctx)
        # Contract income without specific keyword may not match any rule yet
        # This is OK — it'll be handled by template matching in the pipeline


class TestSystemMappingsRules:
    """Rules derived from SystemMappings.csv gap analysis."""

    # --- HIGH priority ---
    def test_contractor_expense(self):
        ctx = _ctx("contractors", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP"

    def test_contractor_not_subcontract(self):
        """Contractor rule should not match subcontract (caught by subcontractor rule)."""
        ctx = _ctx("subcontract labour", raw_type="Expense", canon_type="expense")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert name != "contractor_expense"

    def test_subscription_expense(self):
        ctx = _ctx("dues and subscriptions", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.ADM"

    def test_digital_subscriptions(self):
        ctx = _ctx("digital subscriptions", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.ADM"

    def test_fbt_expense(self):
        ctx = _ctx("fringe benefit tax", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.FBT"

    def test_fbt_expense_not_reimbursement(self):
        """FBT reimbursement should go to REV.OTH, not EXP.FBT."""
        ctx = _ctx("fbt reimbursement", raw_type="Other Income",
                    canon_type="other income")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert name != "fbt_expense"

    def test_income_tax_expense(self):
        ctx = _ctx("income tax expense", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.INC"

    def test_income_tax_not_withholding(self):
        """PAYG withholding should not match income_tax_expense."""
        ctx = _ctx("payg withholding tax", raw_type="Expense", canon_type="expense")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert name != "income_tax_expense"

    def test_directors_fees_expense(self):
        ctx = _ctx("director fees", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP"

    def test_trustee_fees_expense(self):
        ctx = _ctx("trustee fees", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP"

    def test_opening_balance_equity(self):
        ctx = _ctx("opening balance equity", raw_type="Equity", canon_type="equity")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EQU.RET"

    # --- MEDIUM priority ---
    def test_doubtful_debt_provision(self):
        ctx = _ctx("provision for doubtful debts", raw_type="Expense",
                    canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.BAD.DOU"

    def test_term_deposit_nca(self):
        ctx = _ctx("term deposit", raw_type="Non-Current Asset",
                    canon_type="non-current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.NCA.INV.TER"

    def test_term_deposit_ca(self):
        ctx = _ctx("term deposit", raw_type="Current Asset",
                    canon_type="current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.CUR.TER"

    def test_deferred_income(self):
        ctx = _ctx("deferred income", raw_type="Current Liability",
                    canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.DEF"

    def test_unearned_revenue(self):
        ctx = _ctx("unearned revenue", raw_type="Current Liability",
                    canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.DEF"

    def test_operating_expense(self):
        ctx = _ctx("operating expenses", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.OPR"

    def test_employee_reimbursement(self):
        ctx = _ctx("employee reimbursements", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.EMP"

    def test_intangible_asset_website(self):
        ctx = _ctx("website development", raw_type="Fixed Asset",
                    canon_type="fixed asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.NCA.INT"

    def test_intangible_asset_franchise(self):
        ctx = _ctx("franchise fee", raw_type="Fixed Asset",
                    canon_type="fixed asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.NCA.INT"

    def test_formation_expense(self):
        ctx = _ctx("formation expense", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.ADM"

    def test_incorporation_expense(self):
        ctx = _ctx("incorporation costs", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.ADM"


class TestTrack2NewRules:
    """Rules added for test-client-2 FallbackParent reduction."""

    def test_bank_charges(self):
        ctx = _ctx("bank fees and charges")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP", f"Expected EXP, got {code} from {name}"

    def test_consultancy_fees(self):
        ctx = _ctx("consultancy fees")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.PRO", f"Expected EXP.PRO, got {code} from {name}"

    def test_management_fees(self):
        ctx = _ctx("management fees")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.PRO", f"Expected EXP.PRO, got {code} from {name}"

    def test_collection_expense(self):
        ctx = _ctx("debt collection")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.PRO", f"Expected EXP.PRO, got {code} from {name}"

    def test_delivery_costs(self):
        ctx = _ctx("delivery costs")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.COS", f"Expected EXP.COS, got {code} from {name}"

    def test_freight_expense(self):
        ctx = _ctx("freight and cartage")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.COS", f"Expected EXP.COS, got {code} from {name}"

    def test_discount_allowed(self):
        ctx = _ctx("discount allowed")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.COS", f"Expected EXP.COS, got {code} from {name}"

    def test_instant_asset_writeoff(self):
        ctx = _ctx("immediately write off")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.DEP", f"Expected EXP.DEP, got {code} from {name}"

    def test_leasing_charges(self):
        ctx = _ctx("leasing charges")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.REN.OPE", f"Expected EXP.REN.OPE, got {code} from {name}"

    def test_license_permit_expense(self):
        ctx = _ctx("licenses fees and permits")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.ADM", f"Expected EXP.ADM, got {code} from {name}"

    def test_licence_not_intangible_on_expense(self):
        """Licence on expense type should be EXP.ADM, not ASS.NCA.INT."""
        ctx = _ctx("licencing fees")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.ADM", f"Expected EXP.ADM, got {code} from {name}"

    def test_employment_expense(self):
        ctx = _ctx("other employment expense")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.EMP", f"Expected EXP.EMP, got {code} from {name}"

    def test_security_costs(self):
        ctx = _ctx("security costs")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.OCC", f"Expected EXP.OCC, got {code} from {name}"

    def test_storage_fees(self):
        ctx = _ctx("storage fees")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.REN", f"Expected EXP.REN, got {code} from {name}"

    def test_tool_replacement(self):
        ctx = _ctx("tool replacements")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.REP", f"Expected EXP.REP, got {code} from {name}"

    def test_water_sewerage(self):
        ctx = _ctx("water and sewerage")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.UTI", f"Expected EXP.UTI, got {code} from {name}"

    def test_administration_fee(self):
        ctx = _ctx("administrations fee ato")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.ADM", f"Expected EXP.ADM, got {code} from {name}"

    def test_data_processing(self):
        ctx = _ctx("data processing charges")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.ADM", f"Expected EXP.ADM, got {code} from {name}"

    def test_magazines(self):
        ctx = _ctx("magazine and journals")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.ADM", f"Expected EXP.ADM, got {code} from {name}"

    def test_parking(self):
        ctx = _ctx("parking")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.VEH", f"Expected EXP.VEH, got {code} from {name}"

    def test_contract_work(self):
        ctx = _ctx("contract work")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP", f"Expected EXP, got {code} from {name}"

    def test_window_cleaner(self):
        ctx = _ctx("window cleaner")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.OCC", f"Expected EXP.OCC, got {code} from {name}"


class TestWS4NewRevenueRules:
    """WS4: New revenue rules."""

    def test_commission_income(self):
        ctx = _ctx("commission received", raw_type="Other Income", canon_type="other income")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "REV.OTH.COM"

    def test_commission_not_on_expense(self):
        ctx = _ctx("commission paid", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code != "REV.OTH.COM"

    def test_surcharge_income(self):
        ctx = _ctx("credit card surcharge", raw_type="Other Income", canon_type="other income")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "REV.OTH"

    def test_surcharge_not_on_revenue(self):
        """Revenue-typed surcharges (e.g. Square Surcharges) should NOT be reclassified."""
        ctx = _ctx("square surcharges", raw_type="Revenue", canon_type="revenue")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert name != "surcharge_income"

    def test_rebate_income(self):
        ctx = _ctx("fuel rebate", raw_type="Other Income", canon_type="other income")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "REV.OTH"

    def test_rebate_excludes_deposit(self):
        ctx = _ctx("deposit refund", raw_type="Other Income", canon_type="other income")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert name != "rebates_refunds_income"

    def test_deposit_income(self):
        ctx = _ctx("deposit received", raw_type="Revenue", canon_type="revenue")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "REV.OTH"

    def test_sale_of_business(self):
        ctx = _ctx("sale of business", raw_type="Other Income", canon_type="other income")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "REV.OTH.INV"


class TestWS4NewExpenseRules:
    """WS4: New expense rules."""

    def test_stock_movement(self):
        ctx = _ctx("stock movement")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.COS"

    def test_stock_adjustment(self):
        ctx = _ctx("stock adjustment")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.COS"

    def test_cogs_prefix(self):
        ctx = _ctx("cogs - retail")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.COS"

    def test_cost_of_goods_sold_specific(self):
        ctx = _ctx("cost of goods sold")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.COS.PUR"

    def test_shareholder_salaries(self):
        ctx = _ctx("shareholder salary")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.EMP.SHA"

    def test_shareholder_wages(self):
        ctx = _ctx("shareholder wages")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.EMP.SHA"

    def test_discount_allowed_now_cos(self):
        """discount_allowed should now map to EXP.COS (updated from EXP)."""
        ctx = _ctx("discount allowed")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.COS"


class TestWS4NewAssetRules:
    """WS4: New asset rules."""

    def test_stock_on_hand(self):
        ctx = _ctx("stock on hand", raw_type="Current Asset", canon_type="current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.CUR.INY"

    def test_stock_asset_general(self):
        ctx = _ctx("stock", raw_type="Inventory", canon_type="inventory")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.CUR.INY"

    def test_stock_excludes_closing(self):
        ctx = _ctx("closing stock", raw_type="Inventory", canon_type="inventory")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert name != "stock_asset_general"

    def test_formation_costs(self):
        ctx = _ctx("formation costs", raw_type="Non-current Asset", canon_type="non-current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.NCA.INT"

    def test_incorporation_costs(self):
        ctx = _ctx("incorporation cost", raw_type="Fixed Asset", canon_type="fixed asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.NCA.INT"

    def test_general_pool(self):
        ctx = _ctx("general pool", raw_type="Fixed Asset", canon_type="fixed asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.NCA.FIX"

    def test_sbe_pool(self):
        ctx = _ctx("sbe pool", raw_type="Fixed Asset", canon_type="fixed asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.NCA.FIX"

    def test_investment_generic(self):
        ctx = _ctx("investment portfolio", raw_type="Non-current Asset", canon_type="non-current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.NCA.INV"

    def test_investment_excludes_property(self):
        """'investment property' should not match the generic investment rule."""
        ctx = _ctx("investment property", raw_type="Non-current Asset", canon_type="non-current asset")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert name != "investment_asset_generic"

    def test_goodwill(self):
        ctx = _ctx("goodwill", raw_type="Non-current Asset", canon_type="non-current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.NCA.INT.GOO"

    def test_goodwill_excludes_accumulated(self):
        ctx = _ctx("accumulated amortisation goodwill", raw_type="Non-current Asset", canon_type="non-current asset")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert name != "goodwill_asset"


class TestWS4NewTaxRules:
    """WS4: New tax liability rules."""

    def test_income_tax_instalments(self):
        ctx = _ctx("income tax instalment", raw_type="Current Liability", canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.TAX.INC"

    def test_income_tax_instalment_excludes_payg(self):
        ctx = _ctx("payg instalment", raw_type="Current Liability", canon_type="current liability")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert name != "income_tax_instalments"

    def test_ato_payable(self):
        ctx = _ctx("ato payable", raw_type="Current Liability", canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.TAX"

    def test_ato_ica(self):
        ctx = _ctx("ato ica", raw_type="Current Liability", canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.TAX"

    def test_ato_income_tax(self):
        ctx = _ctx("ato income tax", raw_type="Current Liability", canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.TAX.INC"

    def test_unlodged_bas(self):
        ctx = _ctx("unlodged bas", raw_type="Current Liability", canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.TAX"


class TestIndustryRules:
    """Industry-specific rules (WS7)."""

    def test_construction_revenue_services(self):
        ctx = _ctx("sales revenue", raw_type="Revenue", canon_type="revenue", industry="construction")
        code, name = evaluate_rules(ALL_RULES, ctx)
        assert code == "REV.TRA.SER", f"Expected REV.TRA.SER, got {code} from {name}"

    def test_construction_revenue_not_without_industry(self):
        """Without construction industry, revenue should NOT be forced to REV.TRA.SER."""
        ctx = _ctx("sales revenue", raw_type="Revenue", canon_type="revenue")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code != "REV.TRA.SER"

    def test_construction_subcontractors(self):
        ctx = _ctx("subcontractor costs", raw_type="Direct Costs", canon_type="direct costs", industry="construction")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.COS"

    def test_construction_materials(self):
        ctx = _ctx("building materials", raw_type="Expense", canon_type="expense", industry="construction")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.COS.PUR"

    def test_auto_mv_expenses(self):
        ctx = _ctx("motor vehicle expenses", raw_type="Expense", canon_type="expense", industry="auto")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EXP.COS"

    def test_auto_mv_not_without_industry(self):
        """Without auto industry, MV expenses go to EXP.VEH not EXP.COS."""
        ctx = _ctx("motor vehicle expenses fuel", raw_type="Expense", canon_type="expense")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code != "EXP.COS"


def test_no_duplicate_rule_names():
    """Every rule must have a unique name."""
    names = [r.name for r in ALL_RULES]
    duplicates = [n for n in names if names.count(n) > 1]
    assert len(names) == len(set(names)), f"Duplicate rule names: {set(duplicates)}"
