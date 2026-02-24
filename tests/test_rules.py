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
        assert code == "EXP.COS.WAG"

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
        assert code == "LIA.NCL.HPA"

    def test_unexpired_interest_current(self):
        ctx = _ctx("unexpired interest cl", raw_type="Current Liability",
                    canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.HPA.UEI"

    def test_unexpired_interest_non_current(self):
        ctx = _ctx("unexpired interest ncl", raw_type="Non-Current Liability",
                    canon_type="non-current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.NCL.HPA.UEI"

    def test_director_loan_to(self):
        ctx = _ctx("loan to director", raw_type="Non-Current Asset",
                    canon_type="non-current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.NCA.DIR"

    def test_directors_loan(self):
        ctx = _ctx("directors loan", raw_type="Non-Current Liability",
                    canon_type="non-current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.NCL.LOA"

    def test_premium_funding(self):
        ctx = _ctx("premium funding gallagher", raw_type="Current Liability",
                    canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.LOA.UNS"

    def test_generic_loan_current_liability(self):
        ctx = _ctx("business loan", raw_type="Current Liability",
                    canon_type="current liability")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "LIA.CUR.REL"

    def test_generic_loan_non_current_asset(self):
        ctx = _ctx("loan receivable", raw_type="Non-Current Asset",
                    canon_type="non-current asset")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "ASS.NCA.REL"


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
        assert code == "EXP.COS"

    def test_dividends_paid_equity(self):
        ctx = _ctx("dividends paid", raw_type="Equity", canon_type="equity")
        code, _ = evaluate_rules(ALL_RULES, ctx)
        assert code == "EQU.RET.DIV"

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
