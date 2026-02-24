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
        notes="Owner keyword + 'drawings' -> equity drawings",
    ),
    Rule(
        name="owner_funds_introduced_company",
        code="LIA.NCL.ADV",
        priority=93,
        keywords=["capital contributed", "funds introduced", "share capital"],
        owner_context=True,
        template="company",
        notes="Owner keyword + capital/funds + Company template -> NCL advance "
              "(companies use liability not equity for shareholder advances)",
    ),
    Rule(
        name="owner_funds_introduced_other",
        code="EQU.ADV",
        priority=92,
        keywords=["capital contributed", "funds introduced", "share capital"],
        owner_context=True,
        notes="Owner keyword + capital/funds + non-Company template -> equity advance",
    ),
]


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
        notes="Gross receipts for revenue types -> trading services",
    ),
    Rule(
        name="covid_grant",
        code="REV.NON",
        priority=90,
        keywords_all=["covid", "grant"],
        notes="Covid-related grants -> non-assessable income. "
              "Also matches 'covid 19' and 'covid-19' after normalisation.",
    ),
    Rule(
        name="jobkeeper",
        code="REV.GRA.GOV",
        priority=90,
        keywords=["jobkeeper", "job keeper", "jobsaver"],
        notes="Government wage subsidies -> government grants",
    ),
    Rule(
        name="cash_flow_boost",
        code="REV.NON",
        priority=90,
        keywords=["cash flow boost", "cashflow boost", "ato cash boost",
                  "cash boost", "non assessable"],
        notes="Government cash flow boost -> non-assessable income",
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
        notes="Reimbursements received -> other income",
    ),
    Rule(
        name="workers_comp_recovery",
        code="REV.OTH",
        priority=78,
        keywords=["workers comp recovery", "workcover recovery",
                  "workers compensation recovery"],
        canon_types={"other income", "revenue", "income"},
        notes="Workers comp recoveries -> other income",
    ),
    Rule(
        name="fbt_reimbursement",
        code="REV.OTH",
        priority=78,
        keywords=["fbt contribution", "fbt reimbursement", "fbt reimburse"],
        canon_types={"other income", "revenue", "income"},
        notes="FBT reimbursements -> other income",
    ),
    Rule(
        name="sale_of_asset_gain",
        code="REV.OTH.GAI",
        priority=80,
        keywords=["sale of fixed asset", "sale of asset",
                  "profit loss on sale of fixed asset"],
        notes="Profit/loss on sale of fixed asset -> other gains",
    ),
    Rule(
        name="sale_proceeds",
        code="REV.OTH.INV",
        priority=78,
        keywords=["sale proceeds", "sale proceed"],
        canon_types={"other income", "revenue", "income"},
        notes="Investment sale proceeds -> other investment income",
    ),
]


# --- Payroll / Employee (Priority 91-95) ---
_payroll_rules = [
    Rule(
        name="wages_direct_cost",
        code="EXP.COS.WAG",
        priority=95,
        keywords=["wages", "salary", "salaries"],
        raw_types={"direct costs", "cost of sales", "purchases"},
        notes="Wages/salary under direct costs type -> COGS wages",
    ),
    Rule(
        name="wages_expense",
        code="EXP.EMP.WAG",
        priority=93,
        keywords=["wages", "salary", "salaries"],
        canon_types={"expense"},
        notes="Wages/salary under expense type -> employee wages",
    ),
    Rule(
        name="super_direct_cost",
        code="EXP.COS",
        priority=93,
        keywords=["superannuation"],
        raw_types={"direct costs", "cost of sales", "purchases"},
        keywords_exclude=["payable"],
        notes="Superannuation under direct costs -> COGS",
    ),
    Rule(
        name="super_expense",
        code="EXP.EMP.SUP",
        priority=91,
        keywords=["superannuation"],
        canon_types={"expense"},
        keywords_exclude=["payable"],
        notes="Superannuation under expense -> employee super",
    ),
    Rule(
        name="super_payable",
        code="LIA.CUR.PAY.EMP",
        priority=92,
        keywords=["superannuation"],
        keywords_all=["superannuation", "payable"],
        notes="Superannuation payable -> employee payables liability",
    ),
    Rule(
        name="super_payable_by_type",
        code="LIA.CUR.PAY.EMP",
        priority=92,
        keywords=["superannuation"],
        raw_types={"current liability"},
        notes="Superannuation under current liability type -> employee payables",
    ),
    Rule(
        name="wages_payable",
        code="LIA.CUR.PAY.EMP",
        priority=95,
        keywords=["wages payable", "withholding", "paygw"],
        notes="Wages payable/withholding/PAYGW -> employee payables liability",
    ),
    Rule(
        name="payroll_payable",
        code="LIA.CUR.PAY.EMP",
        priority=94,
        keywords_all=["payroll", "payable"],
        notes="Payroll payable -> employee payables liability",
    ),
    Rule(
        name="payg_instalment",
        code="LIA.CUR.TAX.INC",
        priority=95,
        keywords=["payg instalment", "payg instalments"],
        notes="PAYG instalment is income tax liability, not payroll",
    ),
]


# --- Vehicle Expenses (Priority 70-75) ---
_vehicle_rules = [
    Rule(
        name="green_slip",
        code="EXP.VEH",
        priority=70,
        keywords=["green slip"],
        canon_types={"expense"},
        notes="Green slip (CTP insurance) -> vehicle expenses",
    ),
    Rule(
        name="mv_fuel",
        code="EXP.VEH",
        priority=72,
        keywords_all=["mv", "fuel"],
        canon_types={"expense"},
        notes="MV fuel -> vehicle expenses",
    ),
    Rule(
        name="motor_vehicle_fuel",
        code="EXP.VEH",
        priority=72,
        keywords_all=["motor vehicle", "fuel"],
        canon_types={"expense"},
        notes="Motor vehicle fuel -> vehicle expenses",
    ),
    Rule(
        name="vehicle_fuel",
        code="EXP.VEH",
        priority=72,
        keywords_all=["vehicle", "fuel"],
        canon_types={"expense"},
        notes="Vehicle fuel -> vehicle expenses",
    ),
    Rule(
        name="mv_interest",
        code="EXP.VEH",
        priority=75,
        keywords_all=["mv", "interest"],
        canon_types={"expense"},
        notes="MV interest -> vehicle expenses",
    ),
    Rule(
        name="motor_vehicle_interest",
        code="EXP.VEH",
        priority=75,
        keywords_all=["motor vehicle", "interest"],
        canon_types={"expense"},
        notes="Motor vehicle interest -> vehicle expenses",
    ),
    Rule(
        name="vehicle_interest",
        code="EXP.VEH",
        priority=75,
        keywords_all=["vehicle", "interest"],
        canon_types={"expense"},
        keywords_exclude=["unexpired"],
        notes="Vehicle interest -> vehicle expenses (excludes UEI)",
    ),
    Rule(
        name="motor_vehicle_insurance",
        code="EXP.VEH",
        priority=75,
        keywords_all=["motor vehicle", "insurance"],
        canon_types={"expense"},
        notes="Motor vehicle insurance -> vehicle expenses",
    ),
    Rule(
        name="vehicle_insurance",
        code="EXP.VEH",
        priority=75,
        keywords_all=["vehicle", "insurance"],
        canon_types={"expense"},
        notes="Vehicle insurance -> vehicle expenses",
    ),
    Rule(
        name="vehicle_rego",
        code="EXP.VEH",
        priority=75,
        keywords_all=["vehicle", "registration"],
        canon_types={"expense"},
        notes="Vehicle registration -> vehicle expenses",
    ),
    Rule(
        name="motor_vehicle_rego",
        code="EXP.VEH",
        priority=75,
        keywords_all=["motor vehicle", "registration"],
        canon_types={"expense"},
        notes="Motor vehicle registration -> vehicle expenses",
    ),
    Rule(
        name="mv_expenses",
        code="EXP.VEH",
        priority=72,
        keywords_all=["mv", "expenses"],
        canon_types={"expense"},
        keywords_exclude=["depreciation", "deprec", "accumulated"],
        notes="MV expenses (excluding depreciation) -> vehicle expenses",
    ),
    Rule(
        name="motor_vehicle_expenses",
        code="EXP.VEH",
        priority=72,
        keywords=["motor vehicle expenses", "motor vehicle running"],
        canon_types={"expense"},
        keywords_exclude=["depreciation", "deprec", "accumulated"],
        notes="Motor vehicle expenses -> vehicle expenses",
    ),
    Rule(
        name="trailer_expense",
        code="EXP.VEH",
        priority=70,
        keywords=["trailer"],
        canon_types={"expense"},
        notes="Trailer expenses -> vehicle expenses",
    ),
]


# --- Loan / Hire Purchase / Related Party (Priority 75-95) ---
# Audit fix: company loans now check account type to determine direction
_loan_rules = [
    Rule(
        name="director_loan_to",
        code="ASS.NCA.DIR",
        priority=95,
        keywords=["loan to director", "loans to director", "loans to directors",
                  "to director", "to directors"],
        keywords_all=["loan"],
        notes="Loan TO director -> director loan asset",
    ),
    Rule(
        name="directors_loan_from",
        code="LIA.NCL.LOA",
        priority=94,
        keywords=["director's loan", "directors loan"],
        notes="Director's loan (FROM director) -> non-current loan liability",
    ),
    Rule(
        name="loan_to_pty",
        code="ASS.NCA.REL",
        priority=90,
        keywords_all=["loan"],
        keywords=["pty", "pty ltd", "pty limited"],
        raw_types={"non-current asset", "non current asset", "current asset", "asset"},
        notes="Audit fix: Loan + pty on ASSET type -> related party asset. "
              "Direction determined by account type, not just keyword.",
    ),
    Rule(
        name="loan_from_pty",
        code="LIA.NCL.REL",
        priority=90,
        keywords_all=["loan"],
        keywords=["pty", "pty ltd", "pty limited"],
        raw_types={"non-current liability", "non current liability",
                   "current liability", "liability"},
        notes="Audit fix: Loan + pty on LIABILITY type -> related party liability",
    ),
    Rule(
        name="vehicle_loan",
        code="LIA.NCL.HPA",
        priority=88,
        keywords_all=["loan"],
        keywords=["motor vehicle", "car"],
        notes="Vehicle loan -> hire purchase liability (non-current)",
    ),
    Rule(
        name="hp_current",
        code="LIA.CUR.HPA",
        priority=85,
        keywords=["hire purchase", "hp"],
        raw_types={"current liability", "liability"},
        keywords_exclude=["unexpired", "interest"],
        notes="Hire purchase on current liability -> current HPA",
    ),
    Rule(
        name="hp_non_current",
        code="LIA.NCL.HPA",
        priority=85,
        keywords=["hire purchase", "hp"],
        raw_types={"non-current liability", "non current liability"},
        keywords_exclude=["unexpired", "interest"],
        notes="Hire purchase on non-current liability -> non-current HPA",
    ),
    Rule(
        name="hp_fallback",
        code="LIA.NCL.HPA",
        priority=80,
        keywords=["hire purchase", "hp"],
        keywords_exclude=["unexpired", "interest"],
        notes="Hire purchase fallback (ambiguous type) -> non-current HPA",
    ),
    Rule(
        name="chattel_mortgage",
        code="LIA.NCL.HPA",
        priority=85,
        keywords=["chattel mortgage"],
        keywords_exclude=["unexpired", "interest"],
        notes="Chattel mortgage -> non-current HPA",
    ),
    Rule(
        name="uei_current",
        code="LIA.CUR.HPA.UEI",
        priority=88,
        keywords=["unexpired interest"],
        raw_types={"current liability", "liability"},
        notes="Unexpired interest on current liability -> current UEI",
    ),
    Rule(
        name="uei_non_current",
        code="LIA.NCL.HPA.UEI",
        priority=88,
        keywords=["unexpired interest"],
        raw_types={"non-current liability", "non current liability"},
        notes="Unexpired interest on non-current liability -> non-current UEI",
    ),
    Rule(
        name="uei_fallback",
        code="LIA.NCL.HPA.UEI",
        priority=83,
        keywords=["unexpired interest"],
        notes="Unexpired interest fallback -> non-current UEI",
    ),
    Rule(
        name="premium_funding",
        code="LIA.CUR.LOA.UNS",
        priority=80,
        keywords=["premium funding", "iqumulate", "gallagher"],
        raw_types={"current liability", "liability"},
        notes="Premium funding (insurance financing) -> unsecured current loan",
    ),
    Rule(
        name="generic_loan_ncl",
        code="LIA.NCL.REL",
        priority=60,
        keywords=["loan"],
        raw_types={"non-current liability", "non current liability"},
        notes="Generic loan on non-current liability -> related party NCL",
    ),
    Rule(
        name="generic_loan_cl",
        code="LIA.CUR.REL",
        priority=60,
        keywords=["loan"],
        raw_types={"current liability", "liability"},
        notes="Generic loan on current liability -> related party CL",
    ),
    Rule(
        name="generic_loan_nca",
        code="ASS.NCA.REL",
        priority=60,
        keywords=["loan"],
        raw_types={"non-current asset", "non current asset"},
        notes="Generic loan on non-current asset -> related party NCA",
    ),
    Rule(
        name="generic_loan_ca",
        code="ASS.CUR.REL",
        priority=60,
        keywords=["loan"],
        raw_types={"current asset", "asset"},
        notes="Generic loan on current asset -> related party CA",
    ),
]


# --- Tax / GST (Priority 80-85) ---
_tax_rules = [
    Rule(
        name="gst_liability",
        code="LIA.CUR.TAX.GST",
        priority=85,
        keywords=["gst", "goods and services tax"],
        type_exclude={"expense"},
        keywords_exclude=["fee", "fees", "stripe", "bank"],
        notes="GST (not on expense accounts, not fees) -> GST tax liability",
    ),
    Rule(
        name="bas_payable",
        code="LIA.CUR.TAX",
        priority=83,
        keywords=["bas payable"],
        notes="BAS payable -> tax liability",
    ),
    Rule(
        name="bas_clearing",
        code="LIA.CUR.TAX",
        priority=83,
        keywords=["bas clearing"],
        notes="BAS clearing account -> tax liability",
    ),
    Rule(
        name="accrued_income_liability",
        code="LIA.CUR.DEF",
        priority=80,
        keywords=["accrued income"],
        raw_types={"current liability", "liability"},
        notes="Accrued income on liability type -> deferred income",
    ),
]


# --- Collect all rules ---
ALL_RULES: list[Rule] = [
    *_bank_rules,
    *_owner_rules,
    *_revenue_rules,
    *_payroll_rules,
    *_vehicle_rules,
    *_loan_rules,
    *_tax_rules,
]
