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
        name="bank_petty_cash",
        code="ASS.CUR.CAS.FLO",
        priority=102,
        raw_types={"bank"},
        keywords=["petty cash"],
        notes="Bank type + petty cash -> cash flow asset (per SystemMappings.csv)",
    ),
    Rule(
        name="bank_cc_abbreviation",
        code="LIA.CUR.PAY",
        priority=104,
        keywords=[" cc"],
        raw_types={"bank"},
        notes="Bank account with 'CC' abbreviation (credit card) -> current payable. "
              "Uses ' cc' (with leading space) to avoid substring false positives.",
    ),
    Rule(
        name="bank_default",
        code="ASS.CUR.CAS.BAN",
        priority=100,
        raw_types={"bank"},
        keywords_exclude=[*CREDIT_CARD_NAMES, " cc"],
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
        name="owner_drawings_company",
        code="LIA.NCL.DRA",
        priority=96,
        keywords=["drawings"],
        owner_context=True,
        template="company",
        type_exclude={"equity"},
        notes="Owner keyword + 'drawings' on Company template -> liability drawings "
              "(companies report owner drawings as liabilities not equity). "
              "Excludes Equity type accounts which should stay as EQU.DRA.",
    ),
    Rule(
        name="owner_drawings",
        code="EQU.DRA",
        priority=95,
        keywords=["drawings"],
        owner_context=True,
        notes="Owner keyword + 'drawings' -> equity drawings (non-company fallback)",
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
        type_exclude={"expense"},
        notes="Profit/loss on sale of fixed asset -> other gains (not on expense type)",
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
        code="EXP.COS",
        priority=95,
        keywords=["wages", "salary", "salaries"],
        raw_types={"direct costs", "cost of sales", "purchases"},
        notes="Wages/salary under direct costs type -> COGS. "
              "Note: EXP.COS.WAG is not a valid Xero reporting code.",
    ),
    Rule(
        name="wages_expense",
        code="EXP.EMP.WAG",
        priority=93,
        keywords=["wages", "salary", "salaries"],
        canon_types={"expense"},
        keywords_exclude=["non salary"],
        notes="Wages/salary under expense type -> employee wages. "
              "Excludes 'non salary' qualifier (e.g. 'Contractor Expenses (non salary)').",
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
        keywords=["wages payable", "paygw"],
        raw_types={"current liability", "liability"},
        notes="Wages payable/PAYGW -> employee payables liability. "
              "Audit fix: removed 'withholding' (too broad — caught ABN withholding, "
              "voluntary withholding credits, withholding tax). Added type guard.",
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
        name="director_loan_to_ca",
        code="ASS.CUR.DIR",
        priority=96,
        keywords=["loan to director", "loans to director", "loans to directors",
                  "to director", "to directors"],
        keywords_all=["loan"],
        raw_types={"current asset", "asset"},
        notes="Loan TO director on current asset -> current director loan",
    ),
    Rule(
        name="director_loan_to",
        code="ASS.NCA.DIR",
        priority=95,
        keywords=["loan to director", "loans to director", "loans to directors",
                  "to director", "to directors"],
        keywords_all=["loan"],
        notes="Loan TO director (fallback) -> non-current director loan asset",
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
        name="hp_interest_expense",
        code="EXP.INT",
        priority=87,
        keywords=["hire purchase", "hp", "chattel mortgage"],
        canon_types={"expense"},
        notes="HP/chattel mortgage on expense type -> interest expense",
    ),
    Rule(
        name="hp_uei_current",
        code="LIA.CUR.HPA.UEI",
        priority=86,
        keywords=["hire purchase", "hp"],
        keywords_all=["int"],
        raw_types={"current liability"},
        keywords_exclude=["unexpired"],
        notes="HP + interest/int abbreviation on current liability -> current UEI. "
              "'int' catches both 'interest' (contains 'int') and 'Int' abbreviation.",
    ),
    Rule(
        name="hp_current",
        code="LIA.CUR.HPA",
        priority=85,
        keywords=["hire purchase", "hp"],
        raw_types={"current liability"},
        keywords_exclude=["unexpired", "interest", " int"],
        notes="Hire purchase on current liability -> current HPA. "
              "Excludes interest/int abbreviation (caught by hp_uei_current).",
    ),
    Rule(
        name="hp_non_current",
        code="LIA.NCL.HPA",
        priority=85,
        keywords=["hire purchase", "hp"],
        raw_types={"non-current liability", "non current liability", "liability"},
        keywords_exclude=["unexpired", "interest"],
        notes="Hire purchase on non-current/generic liability -> non-current HPA",
    ),
    Rule(
        name="hp_fallback",
        code="LIA.NCL.HPA",
        priority=80,
        keywords=["hire purchase", "hp"],
        keywords_exclude=["unexpired", "interest"],
        type_exclude={"expense"},
        notes="Hire purchase fallback -> non-current HPA (excludes expense type)",
    ),
    Rule(
        name="chattel_mortgage",
        code="LIA.NCL.CHM",
        priority=85,
        keywords=["chattel mortgage"],
        keywords_exclude=["unexpired", "interest"],
        type_exclude={"expense"},
        notes="Chattel mortgage -> non-current chattel mortgage. "
              "Changed from HPA to CHM per validated data.",
    ),
    Rule(
        name="chattel_mortgage_uei",
        code="LIA.NCL.CHM.UEI",
        priority=89,
        keywords=["chattel mortgage"],
        keywords_all=["unexpired"],
        notes="Chattel mortgage + unexpired interest -> chattel mortgage UEI. "
              "Higher priority than generic uei_non_current to use CHM-specific code.",
    ),
    Rule(
        name="uei_non_current",
        code="LIA.NCL.HPA.UEI",
        priority=88,
        keywords=["unexpired interest"],
        notes="Unexpired interest -> non-current UEI (HP fallback). "
              "Validators consistently classify UEI as non-current regardless of type "
              "(UEI is contra to the full HP liability which is non-current).",
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
        code="LIA.NCL.LOA",
        priority=60,
        keywords=["loan"],
        raw_types={"non-current liability", "non current liability"},
        notes="Generic loan on non-current liability -> non-current loan",
    ),
    Rule(
        name="generic_loan_cl",
        code="LIA.NCL.LOA",
        priority=60,
        keywords=["loan"],
        raw_types={"current liability", "liability"},
        notes="Generic loan on current/generic liability -> non-current loan "
              "(most loans are long-term even when typed as current liability)",
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


# --- General Expenses (Priority 65-80) ---
# Audit fix: removed broad 'staff' catch-all. Staff-related rules now
# require specific context (amenities, training, uniforms, etc.)
_general_expense_rules = [
    # Materials / COS
    Rule(
        name="closing_stock",
        code="EXP.COS.CLO",
        priority=78,
        keywords=["closing"],
        canon_types={"expense", "direct costs"},
        notes="Closing stock/materials -> cost of sales closing. "
              "Higher priority than materials_purchase to catch 'Closing Raw Materials'.",
    ),
    Rule(
        name="materials_purchase",
        code="EXP.COS.PUR",
        priority=75,
        keywords=["materials", "building materials"],
        canon_types={"expense", "direct costs"},
        keywords_exclude=["closing"],
        notes="Materials/building materials -> cost of purchases (excludes closing stock)",
    ),
    Rule(
        name="amortisation",
        code="EXP.AMO",
        priority=75,
        keywords=["amortis"],
        canon_types={"expense"},
        notes="Amortisation expense",
    ),
    Rule(
        name="subcontractor_direct",
        code="EXP.COS",
        priority=78,
        keywords=["subtrades", "subcontract"],
        raw_types={"direct costs", "cost of sales", "purchases"},
        notes="Subcontractor under direct costs -> COGS",
    ),
    Rule(
        name="subcontractor_expense",
        code="EXP",
        priority=72,
        keywords=["subtrades", "subcontract"],
        canon_types={"expense"},
        notes="Subcontractor under expense -> general expense",
    ),
    Rule(
        name="labour_hire_direct",
        code="EXP.COS",
        priority=78,
        keywords=["labour hire"],
        raw_types={"direct costs", "cost of sales", "purchases"},
        notes="Labour hire under direct costs -> COGS",
    ),

    # Training / Uniforms / Employee
    Rule(
        name="training_education",
        code="EXP.EMP",
        priority=72,
        keywords=["education", "training", "conference", "cpd"],
        canon_types={"expense"},
        notes="Training/education/conference -> employee expenses",
    ),
    Rule(
        name="uniforms_clothing",
        code="EXP.EMP",
        priority=72,
        keywords=["uniform", "clothing", "protective clothing"],
        canon_types={"expense"},
        notes="Uniforms/clothing -> employee expenses",
    ),

    # Equipment hire
    Rule(
        name="car_hire_expense",
        code="EXP.VEH",
        priority=72,
        keywords_all=["car", "hire"],
        canon_types={"expense"},
        keywords_exclude=["purchase"],
        notes="Car hire -> vehicle expenses",
    ),
    Rule(
        name="equipment_hire_direct",
        code="EXP.COS",
        priority=75,
        keywords=["hire"],
        keywords_all=["hire"],
        canon_types={"direct costs"},
        keywords_exclude=["purchase", "labour"],
        notes="Equipment/plant hire under direct costs -> COGS. "
              "keywords 'hire' excludes 'hire purchase' via keywords_exclude.",
    ),
    Rule(
        name="equipment_hire_expense",
        code="EXP",
        priority=68,
        keywords_all=["hire"],
        canon_types={"expense"},
        keywords_exclude=["purchase", "labour", "car"],
        notes="Equipment hire under expense -> general expense (excludes car hire)",
    ),

    # Home warranty (construction)
    Rule(
        name="home_warranty",
        code="EXP.COS",
        priority=78,
        keywords=["home warranty"],
        notes="Home warranty insurance -> cost of sales (construction)",
    ),

    # Tools and misc
    Rule(
        name="tools_misc_direct",
        code="EXP.COS.PUR",
        priority=75,
        keywords_all=["tools", "miscellaneous"],
        raw_types={"direct costs", "cost of sales", "purchases"},
        notes="Tools and miscellaneous under direct costs -> COGS purchases",
    ),

    # Donations
    Rule(
        name="donations",
        code="EXP",
        priority=65,
        keywords=["donation", "charity"],
        canon_types={"expense"},
        notes="Donations/charity -> general expense",
    ),

    # Advertising / Marketing
    Rule(
        name="advertising",
        code="EXP.ADV",
        priority=72,
        keywords=["advertising", "marketing"],
        canon_types={"expense"},
        notes="Advertising/marketing -> advertising expense",
    ),
    Rule(
        name="branding",
        code="EXP.ADV",
        priority=72,
        keywords=["rebrand", "re-brand", "rebranding", "branding", "brand"],
        canon_types={"expense"},
        notes="Branding/rebranding -> advertising expense",
    ),
    Rule(
        name="gifts",
        code="EXP",
        priority=68,
        keywords=["gift", "gifts"],
        canon_types={"expense"},
        notes="Gifts/donations -> general expense (not advertising)",
    ),

    # Professional fees
    Rule(
        name="professional_fees",
        code="EXP.PRO",
        priority=72,
        keywords=["accounting", "consulting", "legal"],
        canon_types={"expense"},
        notes="Accounting/consulting/legal -> professional fees",
    ),

    # Insurance
    Rule(
        name="workers_comp_insurance",
        code="EXP.EMP",
        priority=78,
        keywords=["workers compensation", "workcover", "workers cover",
                  "workers comp"],
        keywords_all=["insurance"],
        canon_types={"expense"},
        notes="Workers comp + insurance -> employee expenses",
    ),
    Rule(
        name="car_insurance",
        code="EXP.VEH",
        priority=75,
        keywords_all=["car", "insurance"],
        canon_types={"expense"},
        notes="Car insurance -> vehicle expense (not general insurance). "
              "Car + insurance = vehicle expense per user decision.",
    ),
    Rule(
        name="general_insurance",
        code="EXP.INS",
        priority=70,
        keywords=["insurance"],
        canon_types={"expense"},
        notes="General insurance -> insurance expense",
    ),

    # Utilities
    Rule(
        name="phone_internet",
        code="EXP.UTI",
        priority=72,
        keywords=["phone", "mobile", "telephone", "internet"],
        canon_types={"expense"},
        notes="Phone/mobile/internet -> utilities",
    ),
    Rule(
        name="power_heating",
        code="EXP.UTI",
        priority=72,
        keywords=["light", "power", "electricity", "gas", "heating"],
        canon_types={"expense"},
        keywords_exclude=["flight", "flights", "highlight", "spotlight"],
        notes="Light/power/electricity/gas -> utilities. "
              "Excludes 'flight' (which contains 'light').",
    ),

    # Administration
    Rule(
        name="office_admin",
        code="EXP.ADM",
        priority=70,
        keywords=["office expenses", "printing", "stationery", "postage"],
        canon_types={"expense"},
        notes="Office expenses/printing/stationery/postage -> admin",
    ),
    Rule(
        name="council_rates",
        code="EXP.OCC",
        priority=72,
        keywords_all=["council"],
        keywords=["rate", "rates", "fee", "fees"],
        notes="Council rates/fees -> occupancy",
    ),

    # Staff (specific, NOT catch-all)
    Rule(
        name="staff_amenities",
        code="EXP.EMP",
        priority=72,
        keywords=["staff amenities", "amenities", "amenties"],
        canon_types={"expense"},
        notes="Staff amenities -> employee expenses. "
              "Audit fix: broad 'staff' catch-all removed.",
    ),
    Rule(
        name="staff_training",
        code="EXP.EMP",
        priority=73,
        keywords=["staff training"],
        canon_types={"expense"},
        notes="Staff training -> employee expenses",
    ),

    # Bank/merchant fees
    Rule(
        name="bank_fees",
        code="EXP",
        priority=65,
        keywords=BANK_NAMES,
        keywords_all=["fee"],
        canon_types={"expense"},
        notes="Bank name + fee -> general expense",
    ),
    Rule(
        name="merchant_fees",
        code="EXP",
        priority=65,
        keywords_all=["merchant", "fee"],
        canon_types={"expense"},
        notes="Merchant fees -> general expense",
    ),

    # Cleaning
    Rule(
        name="cleaning",
        code="EXP.OCC",
        priority=65,
        keywords=["cleaning", "laundry"],
        canon_types={"expense"},
        keywords_exclude=["vehicle", "car", "mv", "motor vehicle"],
        notes="Cleaning/laundry -> occupancy expense (excludes vehicle washing)",
    ),

    # Depreciation
    Rule(
        name="depreciation_expense",
        code="EXP.DEP",
        priority=72,
        keywords=["depreciation", "deprec"],
        canon_types={"expense"},
        keywords_exclude=["accumulated"],
        notes="Depreciation expense (excludes accumulated dep)",
    ),

    # Travel
    Rule(
        name="travel_international",
        code="EXP.TRA.INT",
        priority=75,
        keywords_all=["travel", "international"],
        canon_types={"expense"},
        notes="International travel -> international travel expense",
    ),
    Rule(
        name="travel_domestic",
        code="EXP.TRA.NAT",
        priority=73,
        keywords=["travel", "accommodation"],
        canon_types={"expense"},
        keywords_exclude=["international"],
        notes="Domestic travel/accommodation (not international) -> national travel. "
              "Priority raised above training_education to win when both match.",
    ),

    # Work safety
    Rule(
        name="work_safety",
        code="EXP.EMP",
        priority=72,
        keywords=["work safety", "safety"],
        canon_types={"expense"},
        notes="Work safety -> employee expenses",
    ),
    Rule(
        name="long_service_leave",
        code="EXP.EMP",
        priority=72,
        keywords_all=["long service", "levy"],
        canon_types={"expense"},
        notes="Long service leave levy -> employee expenses",
    ),

    # Fines/penalties
    Rule(
        name="fines_penalties",
        code="EXP.NON",
        priority=72,
        keywords=["fine", "fines", "penalty", "penalties"],
        canon_types={"expense"},
        notes="Fines/penalties -> non-deductible expense",
    ),

    # Cost of goods sold catch-all
    Rule(
        name="cost_of_goods_sold",
        code="EXP.COS",
        priority=60,
        keywords=["cost of goods sold"],
        notes="Cost of goods sold -> COGS (catch-all)",
    ),
    Rule(
        name="cost_of_sales_type",
        code="EXP.COS",
        priority=55,
        raw_types={"cost of sales"},
        notes="Cost of sales type catch-all -> COGS",
    ),

    # Interest expense (from early overrides)
    Rule(
        name="ato_interest_expense",
        code="EXP.INT",
        priority=82,
        keywords=["interest"],
        keywords_all=["ato"],
        canon_types={"expense"},
        notes="ATO interest charges -> interest expense. "
              "ATO interest was deductible pre-June 2025; grandfathered as EXP.INT "
              "to avoid affecting prior reporting periods.",
    ),
    Rule(
        name="interest_expense",
        code="EXP.INT",
        priority=80,
        keywords=["interest expense"],
        canon_types={"expense"},
        notes="Interest expense -> interest expense",
    ),

    # Entertainment (from early overrides)
    Rule(
        name="client_entertainment",
        code="EXP.ENT",
        priority=78,
        keywords=["client meeting", "client meetings", "client meal",
                  "meal entertainment"],
        canon_types={"expense"},
        notes="Client meetings/meals -> entertainment",
    ),
    Rule(
        name="entertainment_non_deductible",
        code="EXP.ENT.NON",
        priority=82,
        keywords=["not deductible", "non deductible", "non-deductible",
                  "not-deductible"],
        keywords_all=["entertainment"],
        canon_types={"expense"},
        notes="Entertainment + non-deductible -> non-deductible entertainment",
    ),

    # Bad debts (from early overrides)
    Rule(
        name="bad_debts",
        code="EXP.BAD",
        priority=78,
        keywords=["bad debt"],
        notes="Bad debt expense",
    ),

    # Dividends (from early overrides)
    Rule(
        name="dividends_paid_equity",
        code="EQU.RET.DIV",
        priority=80,
        keywords=["dividends paid"],
        canon_types={"equity"},
        notes="Dividends paid on equity -> retained earnings dividends",
    ),
    Rule(
        name="dividend_payable_expense",
        code="EXP.DIV",
        priority=80,
        keywords=["dividend paid or payable", "dividends paid or payable"],
        canon_types={"expense"},
        notes="Dividend paid/payable on expense -> dividend expense",
    ),
    Rule(
        name="dividend_payable_by_keyword",
        code="EXP.DIV",
        priority=78,
        keywords_all=["dividend", "payable"],
        canon_types={"expense"},
        notes="Dividend + payable on expense -> dividend expense",
    ),
]


# --- Equity / Shares / Retained Earnings (Priority 75-85) ---
_equity_rules = [
    Rule(
        name="ordinary_shares",
        code="EQU.SHA.ORD",
        priority=85,
        keywords=["ordinary shares"],
        notes="Ordinary shares -> equity shares",
    ),
    Rule(
        name="paid_up_capital",
        code="EQU.SHA.ORD",
        priority=83,
        keywords=["paid up capital"],
        notes="Issued/paid up capital -> equity ordinary shares",
    ),
    Rule(
        name="issued_paid_capital",
        code="EQU.SHA.ORD",
        priority=83,
        keywords_all=["issued", "paid", "capital"],
        notes="Issued and paid capital -> equity ordinary shares",
    ),
    Rule(
        name="shares_asset",
        code="ASS.NCA.INV.SHA",
        priority=80,
        keywords=["shares"],
        raw_types={"asset", "current asset", "non-current asset", "non current asset"},
        notes="Shares on asset accounts -> investment shares",
    ),
    Rule(
        name="retained_earnings_type",
        code="EQU.RET",
        priority=85,
        raw_types={"retained earnings"},
        notes="Retained Earnings type -> equity retained earnings",
    ),
    Rule(
        name="retained_earnings_keyword",
        code="EQU.RET",
        priority=80,
        keywords=["profit", "earnings"],
        keywords_all=["retained"],
        notes="'Retained' + 'profit' or 'earnings' -> equity retained earnings. "
              "Uses keywords for any match and keywords_all for retained.",
    ),
    Rule(
        name="accumulated_losses",
        code="EQU.RET",
        priority=80,
        keywords_all=["accumulated", "loss"],
        notes="Accumulated losses -> equity retained earnings",
    ),
]


# --- Remaining / Uncategorized (Priority 65-80) ---
_remaining_rules = [
    # Cash
    Rule(
        name="cash_on_hand",
        code="ASS.CUR.CAS.FLO",
        priority=78,
        keywords=["cash on hand", "petty cash", "undeposited funds"],
        notes="Cash/petty cash/undeposited funds -> cash flow asset. "
              "Per SystemMappings.csv: ASS.CUR.CAS.FLO is 'Cash on Hand'.",
    ),

    # Sundry debtors / Retentions
    Rule(
        name="sundry_debtors",
        code="ASS.CUR.REC",
        priority=75,
        keywords=["sundry debtors"],
        notes="Sundry debtors -> current receivables",
    ),
    Rule(
        name="retentions_receivable",
        code="ASS.CUR.REC",
        priority=75,
        keywords=["retention receivable", "retentions receivable"],
        notes="Retentions receivable -> current receivables",
    ),
    Rule(
        name="retention_debtor",
        code="ASS.CUR.REC",
        priority=73,
        keywords_all=["retention"],
        keywords=["receiv", "debtor"],
        notes="Retention + receivable/debtor -> current receivables",
    ),

    # Preliminary expenses
    Rule(
        name="preliminary_expenses",
        code="ASS.NCA",
        priority=75,
        keywords=["preliminary expenses"],
        notes="Preliminary expenses -> non-current asset",
    ),

    # WIPAA
    Rule(
        name="wipaa_cost",
        code="EXP.COS",
        priority=78,
        keywords=["wipaa"],
        raw_types={"direct costs", "cost of sales", "purchases",
                   "expense", "operating expense", "operating expenses"},
        notes="WIPAA under P&L types -> cost of sales",
    ),
    Rule(
        name="wipaa_asset",
        code="ASS.CUR.INY.WIP",
        priority=75,
        keywords=["wipaa"],
        notes="WIPAA on balance sheet -> WIP inventory asset. "
              "Lower priority than wipaa_cost so P&L types match first.",
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
    *_general_expense_rules,
    *_equity_rules,
    *_remaining_rules,
]
