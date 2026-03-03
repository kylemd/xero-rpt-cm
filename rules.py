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

# --- Australian market dictionaries ---
# Flat keyword lists: each entry is lowercase for normalised matching.
# Includes full names, abbreviations, and common brand variants.

AUSTRALIAN_BANKS = [
    # Major four
    "commonwealth bank", "cba", "commbank",
    "westpac", "wbc",
    "anz",
    "nab", "national australia bank",
    # Second-tier & regional
    "macquarie bank", "macquarie", "mqg",
    "bendigo bank", "bendigo", "ben",
    "suncorp",
    "bank of queensland", "boq",
    "bankwest", "bw",
    "ing bank", "ing direct",
    "amp bank", "amp",
    "hsbc",
    "citibank", "citi",
    "st george", "stgeorge", "stg",
    "banksa", "bsa",
    "bank of melbourne", "bom",
    "me bank",
    "ubank",
    "rabobank", "rabo",
    "heritage bank", "heritage",
    "beyond bank", "beyond",
    "great southern bank", "gsb",
    # Payment processors (commonly appear in bank-type accounts)
    "tyro",
    "stripe",
    "square",
]

# Backwards-compat alias — existing rules reference BANK_NAMES
BANK_NAMES = AUSTRALIAN_BANKS

VEHICLE_MAKES = [
    # --- Passenger makes & abbreviations ---
    "toyota", "corolla", "camry", "rav4", "yaris", "prado", "kluger", "landcruiser",
    "mazda", "cx-5", "cx-3", "cx-9", "mazda3", "mazda2", "bt-50",
    "hyundai", "i30", "tucson", "kona", "santa fe", "venue",
    "kia", "sportage", "cerato", "seltos", "carnival", "tasman",
    "ford", "focus", "mustang", "escape", "puma",
    "volkswagen", "vw", "golf", "polo", "tiguan", "t-roc", "amarok",
    "mercedes-benz", "merc", "mb", "c-class", "e-class", "glc", "gle", "a-class",
    "bmw", "3 series", "x3", "x5", "1 series",
    "audi", "a3", "a4", "q5", "q7",
    "subaru", "subi", "forester", "outback", "xv", "impreza", "wrx",
    "mitsubishi", "mitsu", "outlander", "asx", "eclipse cross", "pajero",
    "honda", "cr-v", "hr-v", "civic", "jazz", "accord",
    "nissan", "x-trail", "qashqai", "patrol", "juke",
    "suzuki", "vitara", "swift", "jimny", "s-cross", "baleno",
    "jeep", "wrangler", "grand cherokee", "compass",
    "land rover", "lr", "defender", "discovery", "range rover",
    "lexus", "rx", "nx", "is", "ux",
    "tesla", "model 3", "model y",
    "peugeot", "2008", "3008", "5008",
    "mg", "zs", "hs", "mg3", "mg4",
    # --- Commercial makes & abbreviations ---
    "hilux", "hiace", "landcruiser 70",
    "ranger", "transit", "transit custom",
    "isuzu", "d-max", "mu-x", "n-series", "f-series",
    "hino", "300", "500", "700",
    "mitsubishi fuso", "fuso", "canter", "fighter", "shogun",
    "fiat", "ducato", "scudo",
    "volvo trucks", "fh", "fm", "fe",
    "kenworth", "kw", "t610", "t410",
    "daf", "cf", "lf", "xf",
    "man", "tgs", "tgx", "tge",
    "scania", "p-series", "r-series",
    "sprinter", "actros", "vito",
    "iveco", "daily", "eurocargo",
    "western star", "4700", "4800",
    "ud trucks", "ud", "quon", "croner",
    "mack", "granite", "anthem",
    "freightliner", "cascadia", "coronado",
    "foton", "tunland", "aumark",
    "great wall", "gwm", "ute", "cannon",
    "ram", "1500", "2500",
]

AUSTRALIAN_LENDERS = [
    # Major banks (as lenders)
    "commonwealth bank", "cba",
    "westpac", "wbc",
    "anz",
    "nab",
    "macquarie", "mqg",
    "st george", "stg",
    "bankwest", "bw",
    "suncorp",
    # Non-bank mortgage lenders
    "pepper money", "pepper",
    "liberty",
    "firstmac",
    "resimac",
    "la trobe",
    "bluestone",
    "think tank",
    "bmm",
    "prospa",
    "judo",
    "plenti",
    "wisr",
    # Equipment & asset finance
    "nmef",
    "capital finance",
    "angle finance",
    "metro finance",
    "rapid finance",
    "cnhi",
    "agco",
    "dll",
    "flexirent", "humm",
    "flexigroup",
    # Credit card brands
    "visa",
    "mastercard", "mc",
    "american express", "amex",
    "diners club", "diners",
    "altitude",
    "platinum",
    "low rate",
    "qantas money",
    "coles",
    "afterpay",
    # Vehicle finance
    "toyota finance", "tfs",
    "nissan finance", "nfs",
    "ally",
    "bmw financial", "bmw fs",
    "mbfs",
    "vw finance", "vw fs",
    "stratton",
    "motor finance wizard", "mfw",
    "loan market",
    "mortgage choice",
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
        keywords=["capital contributed", "funds introduced"],
        keywords_exclude=["share capital"],
        owner_context=True,
        template="company",
        type_exclude={"equity"},
        notes="Owner keyword + capital/funds + Company template -> NCL advance "
              "(companies use liability not equity for shareholder advances). "
              "Excludes equity accounts and 'share capital' (which is EQU.SHA.ORD).",
    ),
    Rule(
        name="owner_funds_introduced_other",
        code="EQU.ADV",
        priority=92,
        keywords=["capital contributed", "funds introduced"],
        keywords_exclude=["share capital"],
        owner_context=True,
        notes="Owner keyword + capital/funds + non-Company template -> equity advance. "
              "Excludes 'share capital' (handled by share_capital_equity rule).",
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
        keywords=["grant", "government", "service nsw"],
        canon_types={"other income", "revenue", "income"},
        keywords_exclude=["covid"],
        notes="Government grants/subsidies on revenue types. "
              "'government' added per user decision (Government subsidies = REV.GRA.GOV).",
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
        keywords=["fbt contribution", "fbt employee contribution",
                  "fbt reimbursement", "fbt reimburse"],
        canon_types={"other income", "revenue", "income"},
        notes="FBT reimbursements/employee contributions -> other income. "
              "'fbt employee contribution' catches 'FBT Employee contribution income' "
              "where 'employee' separates fbt from contribution.",
    ),
    Rule(
        name="small_business_restructure_gain",
        code="REV.OTH",
        priority=78,
        keywords=["gain on small business restructure",
                  "small business restructure", "small business restructuring"],
        keywords_exclude=["fund", "reserve"],
        canon_types={"other income", "revenue", "income"},
        notes="Gain on small business restructure -> other income. "
              "Debt-forgiveness gains under SBR are assessable other income. "
              "Excludes 'fund'/'reserve' to avoid clashing with "
              "small_business_restructuring_reserve (EQU.RES).",
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
    Rule(
        name="product_income",
        code="REV.TRA.GOO",
        priority=85,
        keywords=["product income", "sales of product"],
        canon_types={"revenue", "income"},
        notes="Product income/sales of product -> trading goods revenue",
    ),
    Rule(
        name="rental_income",
        code="REV.INV.REN",
        priority=80,
        keywords=["rental income", "rental"],
        canon_types={"other income", "revenue", "income"},
        keywords_exclude=["parental"],
        notes="Rental income -> investment rental income. "
              "Per user decision: revenue/income + 'rental' = REV.INV.REN. "
              "Excludes 'parental' to prevent substring match on 'Paid Parental Leave'.",
    ),

    # Commission income
    Rule(
        name="commission_income",
        code="REV.OTH.COM",
        priority=72,
        keywords=["commission"],
        canon_types={"revenue", "income", "other income"},
        notes="Commission income -> other income commissions.",
    ),

    # Surcharge income (only on Other Income type; Revenue surcharges are trading)
    Rule(
        name="surcharge_income",
        code="REV.OTH",
        priority=72,
        keywords=["surcharge"],
        canon_types={"other income"},
        notes="Surcharge income on Other Income type -> other income. "
              "Revenue-typed surcharges (e.g. Square Surcharges) stay as trading.",
    ),

    # Rebates / refunds income
    Rule(
        name="rebates_refunds_income",
        code="REV.OTH",
        priority=68,
        keywords=["rebate", "refund"],
        canon_types={"revenue", "income", "other income"},
        keywords_exclude=["deposit"],
        notes="Rebates/refunds on income type -> other income.",
    ),

    # Deposit income
    Rule(
        name="deposit_income",
        code="REV.OTH",
        priority=65,
        keywords=["deposit"],
        canon_types={"revenue", "income", "other income"},
        notes="Deposit income -> other income.",
    ),

    # Sale of business
    Rule(
        name="sale_of_business",
        code="REV.OTH.INV",
        priority=78,
        keywords=["sale of business"],
        type_exclude={"equity", "current asset", "non-current asset", "fixed asset"},
        notes="Sale of business -> gain on disposal of investments. "
              "Excludes asset/equity types (e.g. 'Goodwill on Sale of Business' on equity).",
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
        keywords=["payg instalment", "payg instalments", "paygi"],
        notes="PAYG instalment / PAYGI (PAYG Income Tax Instalments) -> income tax liability. "
              "PAYGI is the common abbreviation used in Xero account names.",
    ),
    Rule(
        name="payg_withholding_payable",
        code="LIA.CUR.PAY.EMP",
        priority=95,
        keywords=["payg withholding", "payg withholdings"],
        canon_types={"current liability", "liability"},
        notes="PAYG Withholdings Payable -> employee payables. "
              "Validated as EMP across 4 of 5 client datasets.",
    ),
    Rule(
        name="payroll_clearing",
        code="LIA.CUR.PAY.EMP",
        priority=94,
        keywords=["payroll clearing"],
        canon_types={"current liability", "liability"},
        notes="Payroll clearing accounts represent employee entitlements",
    ),
    Rule(
        name="leave_payable",
        code="LIA.CUR.PAY.EMP",
        priority=93,
        keywords=["leave"],
        keywords_all=["payable"],
        canon_types={"current liability", "liability"},
        notes="Leave payable (annual, long service, Q leave, TOIL) is employee entitlement",
    ),
    Rule(
        name="employee_provision",
        code="LIA.CUR.PAY.EMP",
        priority=93,
        keywords=["salary", "wages", "toil", "annual leave", "long service"],
        keywords_all=["provision"],
        canon_types={"current liability", "liability"},
        notes="Provisions for employee-related items are employee entitlements",
    ),
    Rule(
        name="payroll_tax_payable",
        code="LIA.CUR.TAX",
        priority=96,
        keywords=["payroll tax"],
        canon_types={"current liability", "liability"},
        notes="Payroll tax payable is a tax liability, NOT an employee entitlement. "
              "Higher priority than payroll_payable to prevent PAY.EMP assignment.",
    ),
    Rule(
        name="payroll_tax_expense",
        code="EXP.EMP",
        priority=85,
        keywords=["payroll tax"],
        canon_types={"expense"},
        notes="Payroll tax expense correlates with employee remuneration but is not "
              "wages directly paid to employees, hence EXP.EMP not EXP.EMP.WAG.",
    ),
    Rule(
        name="sgc_payable",
        code="LIA.CUR.TAX",
        priority=93,
        keywords=["sgc", "scg", "superannuation guarantee"],
        keywords_exclude=["sge", "employer"],
        canon_types={"current liability", "liability"},
        notes="SGC (Superannuation Guarantee Charge) -> tax liability. "
              "Paid to ATO as a penalty/charge. Includes common misspelling SCG. "
              "Excludes SGE (Super Guarantee Employer) which is an employee payable.",
    ),
    Rule(
        name="sge_employer_payable",
        code="LIA.CUR.PAY.EMP",
        priority=94,
        keywords=["sge", "super guarantee employer", "superannuation guarantee employer"],
        canon_types={"current liability", "liability"},
        notes="SGE (Super Guarantee Employer) -> employee payables liability. "
              "ATO account name for outstanding employer superannuation contributions "
              "owing to employees. Priority above sgc_payable to prevent SGC match.",
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
        name="mv_insurance",
        code="EXP.VEH",
        priority=75,
        keywords_all=["mv", "insurance"],
        canon_types={"expense"},
        notes="MV insurance -> vehicle expenses. "
              "'MV' = motor vehicle abbreviation (e.g. 'MV - Insurance').",
    ),
    Rule(
        name="registration_insurance",
        code="EXP.VEH",
        priority=75,
        keywords_all=["registration", "insurance"],
        canon_types={"expense"},
        notes="Registration and insurance -> vehicle expenses. "
              "Registration + insurance combination is vehicle-related.",
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
                  "to director", "to directors", "director s loan"],
        keywords_all=["loan"],
        raw_types={"current asset", "asset"},
        notes="Loan TO director on current asset -> current director loan. "
              "'director s loan' catches normalised apostrophe form of \"director's loan\".",
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
        name="director_loan_generic_nca",
        code="ASS.NCA.DIR",
        priority=95,
        keywords_all=["director", "loan"],
        raw_types={"non-current liability", "non current liability",
                   "current liability", "liability"},
        notes="Director loan on liability type -> reclassify as NCA director loan. "
              "Per user decision: directors loans should always be assets (Div7A). "
              "Type must be corrected in the review interface.",
    ),
    Rule(
        name="director_loan_generic_ca",
        code="ASS.CUR.DIR",
        priority=94,
        keywords_all=["director", "loan"],
        raw_types={"current asset", "asset"},
        notes="Director loan on current asset type -> current director loan. "
              "Catches generic 'YYYY Director Loan' names that don't include 'to'.",
    ),
    Rule(
        name="div7a_loan_nca",
        code="ASS.NCA.DIR",
        priority=97,
        keywords=["div7a", "div 7a", "division 7a"],
        keywords_all=["loan"],
        raw_types={"non-current asset", "non current asset", "asset",
                   "current asset",
                   "non-current liability", "non current liability",
                   "current liability", "liability"},
        notes="Division 7A loan -> non-current director loan asset. "
              "Div7A (ITAA 1936 s.109) requires company loans to directors/associates "
              "to be at market terms. These are always assets (loans TO directors). "
              "Catches 'Div7A loan 2016', 'Div 7A Loan - 2025', etc. "
              "Type guard covers all common Xero account types for Div7A accounts "
              "(NCA, CA, or incorrectly-typed liability accounts).",
    ),
    Rule(
        name="div7a_loan_ca",
        code="ASS.CUR.DIR",
        priority=98,
        keywords=["div7a", "div 7a", "division 7a"],
        keywords_all=["loan"],
        raw_types={"current asset", "asset"},
        notes="Division 7A loan on current asset type -> current director loan. "
              "Priority 98 (above div7a_loan_nca at 97) so CA type wins for CA accounts.",
    ),
    Rule(
        name="directors_loan_from",
        code="LIA.NCL.LOA",
        priority=80,
        keywords=["director's loan", "directors loan", "director s loan"],
        keywords_exclude=["to director"],
        notes="Director's loan (FROM director) -> non-current loan liability. "
              "Lower priority fallback — Div7A rule above catches most cases.",
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
        name="upe_asset",
        code="ASS.CUR.REL",
        priority=88,
        keywords=["upe", "unpaid present entitlement"],
        raw_types={"current asset", "non-current asset", "non current asset", "asset"},
        notes="UPE (Unpaid Present Entitlement) -> current related party receivable. "
              "A UPE arises when a trust has distributed income to a beneficiary "
              "but not yet paid it. For the recipient entity this is ASS.CUR.REL. "
              "For the trust side it would be LIA.CUR.REL. "
              "Per user decision: account 884.2 (test-client-5).",
    ),
    Rule(
        name="trust_distribution_receivable",
        code="ASS.CUR.REL",
        priority=85,
        keywords=["trust distribution receivable", "distribution receivable",
                  "trust distribution payable receivable"],
        raw_types={"current asset", "asset"},
        notes="Trust distribution receivable -> related party current asset. "
              "Distributions from a related trust not yet received are "
              "receivable from a related party (ASS.CUR.REL). "
              "Per user decision: account 650 (test-client-5).",
    ),
    Rule(
        name="unsecured_related_loan",
        code="LIA.CUR.REL",
        priority=78,
        keywords_all=["loan", "unsecured"],
        raw_types={"current liability", "non-current liability",
                   "non current liability", "liability"},
        notes="Unsecured loans on liability type -> current related party liability. "
              "Unsecured intercompany loans are typically demand loans (callable immediately) "
              "and are commonly between related entities. Classified as CUR. "
              "Per user decisions: accounts 882, 885 (test-client-5).",
    ),
    Rule(
        name="related_party_nca",
        code="ASS.NCA.REL",
        priority=85,
        keywords=["related party"],
        raw_types={"non-current asset", "non current asset"},
        notes="Explicit 'related party' on NCA type -> related party NCA. "
              "Catches accounts like 'Related Party Receivables/Loan (NCA)'.",
    ),
    Rule(
        name="related_party_ca",
        code="ASS.CUR.REL",
        priority=85,
        keywords=["related party"],
        raw_types={"current asset", "asset"},
        notes="Explicit 'related party' on current asset type -> related party CA.",
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
        code="ASS.NCA.LOA",
        priority=60,
        keywords=["loan"],
        raw_types={"non-current asset", "non current asset"},
        notes="Generic loan on non-current asset -> NCA loan. "
              "Not related-party by default (needs qualifying context like a name).",
    ),
    Rule(
        name="generic_loan_ca",
        code="ASS.CUR.REL",
        priority=60,
        keywords=["loan"],
        raw_types={"current asset", "asset"},
        notes="Generic loan on current asset -> related party CA",
    ),

    # --- Dictionary-powered rules ---
    Rule(
        name="vehicle_make_finance_liability",
        code="LIA.NCL.HPA",
        priority=78,
        keywords=VEHICLE_MAKES,
        keywords_all=["finance"],
        canon_types={"non-current liability", "current liability", "liability"},
        notes="Vehicle make + finance -> hire purchase liability",
    ),
    Rule(
        name="vehicle_make_loan_liability",
        code="LIA.NCL.HPA",
        priority=78,
        keywords=VEHICLE_MAKES,
        keywords_all=["loan"],
        keywords_exclude=AUSTRALIAN_BANKS,
        canon_types={"non-current liability", "current liability", "liability"},
        notes="Vehicle make + loan -> hire purchase liability. "
              "Catches 'Loan - Toyota Kluger', 'Loan - Tesla Model 3' etc. "
              "Excludes Australian bank names to prevent false positives where "
              "a model code (e.g. 'x3') appears as a substring in a bank account "
              "number (e.g. 'Citibank Loan xx3415'). "
              "Companion to vehicle_make_finance_liability.",
    ),
    Rule(
        name="lender_liability",
        code="LIA.NCL.LOA",
        priority=72,
        keywords=AUSTRALIAN_LENDERS,
        canon_types={"non-current liability", "current liability", "liability"},
        keywords_exclude=["fee", "charge", "interest expense",
                          "car", "motor vehicle", "vehicle", "mv"],
        notes="Recognised Australian lender name -> loan liability. "
              "Excludes vehicle context (may be asset side of finance arrangement).",
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
        keywords_exclude=["fee", "fees", "stripe", "bank", "pre paid", "prepaid"],
        notes="GST (not on expense accounts, not fees, not prepaid) -> GST tax liability",
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
        name="fbt_expense",
        code="EXP.FBT",
        priority=80,
        keywords=["fringe benefit tax", "fbt expense", "fbt payable"],
        canon_types={"expense"},
        keywords_exclude=["reimbursement", "reimburse"],
        notes="Fringe benefit tax expense -> EXP.FBT. SystemMappings leaf code. "
              "Excludes reimbursements which go to REV.OTH via fbt_reimbursement.",
    ),
    Rule(
        name="income_tax_expense",
        code="EXP.INC",
        priority=80,
        keywords=["income tax expense", "income tax", "deferred tax expense"],
        canon_types={"expense"},
        keywords_exclude=["withholding", "payg"],
        notes="Income tax expense -> EXP.INC. SystemMappings leaf code. "
              "Excludes withholding tax (different treatment).",
    ),
    Rule(
        name="accrued_income_liability",
        code="LIA.CUR.DEF",
        priority=80,
        keywords=["accrued income"],
        raw_types={"current liability", "liability"},
        notes="Accrued income on liability type -> deferred income",
    ),
    Rule(
        name="deferred_income",
        code="LIA.CUR.DEF",
        priority=78,
        keywords=["deferred income", "deferred revenue", "unearned revenue",
                  "income in advance", "advance billing"],
        canon_types={"current liability", "liability"},
        notes="Deferred/unearned income -> LIA.CUR.DEF. SystemMappings leaf code. "
              "Supplements accrued_income_liability which only catches 'accrued income'.",
    ),
    Rule(
        name="ato_integrated_account",
        code="LIA.CUR.TAX",
        priority=90,
        keywords=["ato integrated"],
        canon_types={"current liability", "liability"},
        notes="ATO ICA is a mixed tax account (PAYG, GST, FTC) — assign to tax parent. "
              "Cannot determine deeper sub-level from name alone.",
    ),

    # Income tax instalments
    Rule(
        name="income_tax_instalments",
        code="LIA.CUR.TAX.INC",
        priority=85,
        keywords=["income tax instalment", "tax instalment"],
        canon_types={"current liability", "liability"},
        notes="Income tax instalments -> income tax liability. "
              "Guarded to liability types only (some charts mistype as asset). "
              "PAYGI/PAYG Instalments handled by payg_instalment rule (p=95).",
    ),

    # ATO payable / ICA
    Rule(
        name="ato_payable_ica",
        code="LIA.CUR.TAX",
        priority=85,
        keywords=["ato payable", "ato ica", "integrated client"],
        notes="ATO payable / ICA -> tax liability.",
    ),

    # ATO income tax liability
    Rule(
        name="ato_income_tax_liability",
        code="LIA.CUR.TAX.INC",
        priority=85,
        keywords=["ato income tax", "income tax account"],
        notes="ATO income tax / income tax account -> income tax liability.",
    ),

    # Unlodged BAS
    Rule(
        name="unlodged_bas",
        code="LIA.CUR.TAX",
        priority=80,
        keywords=["unlodged bas"],
        notes="Unlodged BAS -> tax liability.",
    ),
]


# --- General Expenses (Priority 65-80) ---
# Audit fix: removed broad 'staff' catch-all. Staff-related rules now
# require specific context (amenities, training, uniforms, etc.)
_general_expense_rules = [
    # Directors / Trustee fees
    Rule(
        name="directors_fees_expense",
        code="EXP",
        priority=82,
        keywords=["director fee", "director fees", "directors fees",
                  "trustee fee", "trustee fees"],
        canon_types={"expense"},
        notes="Directors/trustee fees -> general expense. SystemMappings "
              "explicitly excludes these from EXP.EMP.WAG.",
    ),

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
        name="contractor_expense",
        code="EXP",
        priority=72,
        keywords=["contractor", "contractors", "contract work"],
        canon_types={"expense"},
        keywords_exclude=["subtrade", "subcontract", "sub contractor"],
        notes="Contractor payments -> general expense. SystemMappings EXP.EMP.WAG "
              "excludes subcontractors; EXP root includes 'Consultants'.",
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
    Rule(
        name="employee_reimbursement",
        code="EXP.EMP",
        priority=72,
        keywords=["employee reimbursement", "staff reimbursement"],
        canon_types={"expense"},
        notes="Employee reimbursement expense -> EXP.EMP. "
              "Reimbursements to employees are employment costs.",
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
        keywords=["advertising", "marketing", "sponsorship"],
        canon_types={"expense"},
        notes="Advertising/marketing/sponsorship -> advertising expense. "
              "'sponsorship' added per user decision (strongly implies advertising).",
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
        keywords=["accounting", "accountancy", "bookkeeping", "consulting", "legal"],
        canon_types={"expense"},
        notes="Professional fees: accounting, accountancy, bookkeeping, consulting, legal. "
              "'accountancy' and 'bookkeeping' added per user decision.",
    ),
    Rule(
        name="audit_fees",
        code="EXP.AUD",
        priority=75,
        keywords=["auditor", "audit fee"],
        canon_types={"expense"},
        notes="Audit fees/remuneration -> audit expense",
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
        name="filing_fees",
        code="EXP.ADM",
        priority=73,
        keywords=["filing fee", "filing fees", "filling fee", "filling fees", "asic"],
        canon_types={"expense"},
        notes="Filing fees (ASIC regulatory fee) -> admin expense. "
              "'Filling fee/s' is a common client misspelling of 'Filing fee/s'.",
    ),
    Rule(
        name="subscription_expense",
        code="EXP.ADM",
        priority=72,
        keywords=["subscription", "subscriptions", "dues"],
        canon_types={"expense"},
        notes="Subscriptions and dues -> administrative expense. "
              "SystemMappings EXP root includes 'Licences and subscriptions'.",
    ),
    Rule(
        name="formation_expense",
        code="EXP.AMO",
        priority=72,
        keywords=["formation expense", "formation cost", "incorporation"],
        canon_types={"expense"},
        keywords_exclude=["written off", "writtenoff", "write off"],
        notes="Formation/incorporation expenses -> amortisation expense (EXP.AMO). "
              "Formation costs are black-hole expenditure deductible over 5 years "
              "(ITAA 97 s.40-880); EXP.AMO correctly reflects the annual amortisation. "
              "Excludes write-off variants handled by balance sheet rules.",
    ),
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
        keywords=["cleaning", "cleaner", "laundry"],
        canon_types={"expense"},
        keywords_exclude=["vehicle", "car", "mv", "motor vehicle"],
        notes="Cleaning/laundry/cleaner -> occupancy expense (excludes vehicle washing)",
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
        keywords=["long service leave", "long service"],
        canon_types={"expense"},
        notes="Long service leave expense -> employee expenses. "
              "Broadened from requiring 'levy' to match all long service leave variants.",
    ),
    Rule(
        name="qleave_expense",
        code="EXP.EMP",
        priority=73,
        keywords=["qleave", "q leave"],
        canon_types={"expense"},
        notes="QLeave (Queensland Long Service Leave) -> employee expenses. "
              "Has direct correlation with employee remuneration.",
    ),

    # Client gifts / lead generation / graphic design (advertising)
    Rule(
        name="client_gift_advertising",
        code="EXP.ADV",
        priority=75,
        keywords=["client gift", "client gifts"],
        canon_types={"expense"},
        notes="Client gifts -> advertising/marketing. "
              "Under ATO rules, client gifts are deductible as advertising "
              "unless over $300 per item (which would be entertainment). "
              "Per user decision: account 410.1.",
    ),
    Rule(
        name="lead_generation_advertising",
        code="EXP.ADV",
        priority=75,
        keywords=["lead gen", "lead generation", "lead generating"],
        canon_types={"expense"},
        notes="Lead generation -> advertising/marketing expense. "
              "Per user decision: account 413.",
    ),
    Rule(
        name="graphic_design_advertising",
        code="EXP.ADV",
        priority=75,
        keywords=["graphic design", "graphics design", "graphic designer",
                  "graphic design expense", "graphics"],
        canon_types={"expense"},
        keywords_exclude=["software", "subscription"],
        notes="Graphic design -> advertising/marketing expense. "
              "Graphics design work is typically for marketing materials. "
              "Per user decision: account 430.",
    ),
    Rule(
        name="recruitment_employee",
        code="EXP.EMP",
        priority=75,
        keywords=["recruitment", "recruiting", "recruiter"],
        canon_types={"expense"},
        keywords_exclude=["advertising"],
        notes="Recruitment costs -> employee expenses. "
              "Costs to obtain new employees are part of employment costs. "
              "Excludes 'advertising' so 'Advertising - Recruitment' stays as EXP.ADV. "
              "Per user decision: account 467.",
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

    # Cost of goods/sales
    Rule(
        name="cost_of_sales_name",
        code="EXP.COS",
        priority=78,
        keywords=["cost of sales"],
        canon_types={"expense", "direct costs"},
        notes="Cost of Sales in name -> COGS. Per user decision: type=Direct Costs "
              "and name includes 'cost of sales' matches this code specifically.",
    ),
    Rule(
        name="cos_abbreviation",
        code="EXP.COS",
        priority=76,
        keywords=["- cos", "-cos"],
        raw_types={"direct costs", "cost of sales", "purchases"},
        keywords_exclude=["cost"],
        notes="COS abbreviation after dash on direct costs type -> COGS. "
              "Excludes 'cost' to avoid false positive on 'Freight Cost for Purchases'.",
    ),
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

    # Rent
    Rule(
        name="rent_expense",
        code="EXP.REN",
        priority=72,
        keywords=[" rent"],
        canon_types={"expense"},
        keywords_exclude=["hire", "truck", "vehicle", "plant", "equipment"],
        notes="Rent expense. Uses ' rent' (leading space) to avoid false positives on "
              "'parental' (no space before 'rent'). Excludes equipment/vehicle hire. "
              "Per user decision: type=Expense + name contains 'rent' = EXP.REN.",
    ),

    # Tax adjustments / Extraordinary
    Rule(
        name="tax_adjustment_expense",
        code="EXP.EXT",
        priority=75,
        keywords=["tax adjustment"],
        canon_types={"expense"},
        notes="Tax adjustment expense is an extraordinary item — journal to reconcile "
              "P&L to taxable income. Per user decision.",
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
    Rule(
        name="entertainment_default",
        code="EXP.ENT.NON",
        priority=73,
        keywords=["entertainment"],
        canon_types={"expense"},
        keywords_exclude=["client meeting", "client meal", "meal entertainment",
                          "not deductible", "non deductible", "meals"],
        notes="Entertainment (generic) -> non-deductible by default. "
              "All business entertainment is non-deductible unless it is a client "
              "meeting/meal (EXP.ENT). Priority below client_entertainment (78) "
              "and entertainment_non_deductible (82) which handle specific cases. "
              "Excludes 'meals' to avoid matching 'Meals and entertainment' accounts "
              "which may be validated as employee expenses (EXP.EMP).",
    ),

    # Bad debts (from early overrides)
    Rule(
        name="doubtful_debt_provision",
        code="EXP.BAD.DOU",
        priority=78,
        keywords=["provision for doubtful", "provision for bad", "doubtful debt provision"],
        canon_types={"expense"},
        notes="Provision for doubtful debts -> EXP.BAD.DOU. SystemMappings "
              "distinguishes provision from write-off (EXP.BAD).",
    ),
    Rule(
        name="bad_debts",
        code="EXP.BAD",
        priority=78,
        keywords=["bad debt"],
        notes="Bad debt expense",
    ),

    # Operating expense (low priority catch-all)
    Rule(
        name="operating_expense",
        code="EXP.OPR",
        priority=65,
        keywords=["operating expense", "operating expenses", "operational expense"],
        canon_types={"expense"},
        notes="Operating expenses -> EXP.OPR. SystemMappings leaf code for "
              "expenses associated with production of goods/services.",
    ),

    # Bank charges (generic — no specific bank name required)
    Rule(
        name="bank_charges",
        code="EXP",
        priority=68,
        keywords=["bank fee", "bank fees", "bank charges", "bank charge"],
        canon_types={"expense"},
        notes="Generic bank fees/charges -> general expense. "
              "SystemMappings EXP.INT explicitly excludes bank fees.",
    ),

    # Consultancy / Management (supplements professional_fees for broader patterns)
    Rule(
        name="consultancy_fees",
        code="EXP.PRO",
        priority=72,
        keywords=["consultancy", "consultant"],
        canon_types={"expense"},
        keywords_exclude=["bookkeeping", "accounting"],
        notes="Consultancy/consultant -> professional fees. "
              "Supplements professional_fees which has 'consulting'.",
    ),
    Rule(
        name="management_fees",
        code="EXP.PRO",
        priority=72,
        keywords=["management fee", "management fees"],
        canon_types={"expense"},
        notes="Management fees -> professional fees.",
    ),

    # Collection / Debt recovery
    Rule(
        name="collection_expense",
        code="EXP.PRO",
        priority=72,
        keywords=["collection cost", "collection costs", "debt collection",
                  "collection fee", "collection fees"],
        canon_types={"expense"},
        notes="Collection/debt recovery costs -> professional fees. "
              "SystemMappings EXP.BAD excludes 'Debt collection fees'.",
    ),

    # Delivery / Freight
    Rule(
        name="delivery_freight",
        code="EXP.COS",
        priority=72,
        keywords=["delivery cost", "delivery costs", "freight", "cartage"],
        canon_types={"expense"},
        notes="Delivery/freight/cartage -> cost of sales. "
              "SystemMappings EXP.COS includes 'Direct freight and cartage'.",
    ),

    # Discount allowed
    Rule(
        name="discount_allowed",
        code="EXP.COS",
        priority=65,
        keywords=["discount allowed", "discounts allowed"],
        canon_types={"expense"},
        notes="Discount allowed -> cost of sales (customer discounts reduce revenue).",
    ),

    # Instant asset write-off
    Rule(
        name="instant_asset_writeoff",
        code="EXP.DEP",
        priority=78,
        keywords=["immediately write off", "instant write off", "instant asset",
                  "low value asset", "low value pool",
                  "assets <$20,000", "assets under $20,000", "assets below $20,000",
                  "assets <$20000", "assets under $20000"],
        canon_types={"expense", "depreciation"},
        notes="Instant asset write-off -> depreciation expense. "
              "Under ATO instant asset write-off threshold, assets are fully written off "
              "as immediate depreciation. Catches named thresholds like 'Assets <$20,000'.",
    ),
    Rule(
        name="asset_woff_writeoff",
        code="EXP.DEP",
        priority=77,
        keywords_all=["asset"],
        keywords=["woff", "write off", "writeoff"],
        canon_types={"expense", "depreciation"},
        keywords_exclude=["depreciation", "deprec", "accumulated", "sale"],
        notes="Asset + write-off abbreviation -> depreciation expense. "
              "Catches 'asset woff', 'asset write off' shorthand accounts "
              "used for instant asset write-off under ATO threshold rules.",
    ),

    # Leasing
    Rule(
        name="leasing_expense",
        code="EXP.REN.OPE",
        priority=72,
        keywords=["leasing", "lease charge", "lease charges",
                  "lease payment", "lease payments"],
        canon_types={"expense"},
        keywords_exclude=["leasehold"],
        notes="Leasing charges/payments -> operating lease payments. "
              "SystemMappings EXP.REN.OPE is for operating leases.",
    ),

    # Licences, permits (expense type — distinct from intangible asset)
    Rule(
        name="license_permit_expense",
        code="EXP.ADM",
        priority=72,
        keywords=["licence", "license", "licencing", "licensing", "permit"],
        canon_types={"expense"},
        keywords_exclude=["driver", "driving"],
        notes="Licences/permits on expense -> administrative expense. "
              "Distinct from intangible_asset_keywords which handles asset types.",
    ),

    # Other employment expense
    Rule(
        name="employment_expense_other",
        code="EXP.EMP",
        priority=65,
        keywords=["employment expense", "other employment"],
        canon_types={"expense"},
        notes="Other/general employment expense -> employment costs.",
    ),

    # Security
    Rule(
        name="security_expense",
        code="EXP.OCC",
        priority=72,
        keywords=["security"],
        canon_types={"expense"},
        keywords_exclude=["bond", "deposit"],
        notes="Security costs -> occupancy expense. "
              "SystemMappings EXP.OCC includes 'Security'.",
    ),

    # Storage
    Rule(
        name="storage_expense",
        code="EXP.REN",
        priority=68,
        keywords=["storage"],
        canon_types={"expense"},
        notes="Storage fees -> rental/lease. Renting storage space is a lease expense.",
    ),

    # Tool replacements (repairs & maintenance)
    Rule(
        name="tool_replacement",
        code="EXP.REP",
        priority=72,
        keywords=["tool replacement", "replacement tool"],
        canon_types={"expense"},
        notes="Tool replacements -> repairs & maintenance. "
              "SystemMappings EXP.REP includes 'Plant and machinery renewal'.",
    ),

    # Water / sewerage
    Rule(
        name="water_sewerage",
        code="EXP.UTI",
        priority=72,
        keywords=["water", "sewerage", "sewage"],
        canon_types={"expense"},
        keywords_exclude=["waterproof"],
        notes="Water/sewerage -> utilities. SystemMappings EXP.UTI includes 'Water'.",
    ),

    # Administration fees
    Rule(
        name="ato_administration_fee",
        code="EXP.NON",
        priority=80,
        keywords=["administration fee", "admin fee", "administrations fee"],
        keywords_all=["ato"],
        canon_types={"expense"},
        notes="ATO administration fee -> non-deductible expense. "
              "Administration fees charged by the ATO (e.g. SGC admin fees, "
              "late lodgement fees) are treated as penalties/fines (EXP.NON). "
              "Priority 80 outranks administration_fee (73) for ATO-specific names.",
    ),
    Rule(
        name="administration_fee",
        code="EXP.ADM",
        priority=73,
        keywords=["administration fee", "admin fee", "administrations fee"],
        canon_types={"expense"},
        notes="Administration fees -> administrative expense.",
    ),

    # Data processing
    Rule(
        name="data_processing_expense",
        code="EXP.ADM",
        priority=68,
        keywords=["data processing"],
        canon_types={"expense"},
        notes="Data processing charges -> administrative expense.",
    ),

    # Magazines / periodicals
    Rule(
        name="magazines_periodicals",
        code="EXP.ADM",
        priority=65,
        keywords=["magazine", "magazines", "periodical", "periodicals"],
        canon_types={"expense"},
        notes="Magazines/periodicals -> administrative expense.",
    ),

    # Parking
    Rule(
        name="parking_expense",
        code="EXP.VEH",
        priority=68,
        keywords=["parking"],
        canon_types={"expense"},
        keywords_exclude=["airport"],
        notes="Parking -> vehicle expense. "
              "Airport parking is travel (handled by travel rules).",
    ),

    # Dividends (from early overrides)
    Rule(
        name="dividends_equity",
        code="EQU.RET.DIV.ORD",
        priority=80,
        keywords=["dividend"],
        canon_types={"equity"},
        notes="Dividend on equity type -> ordinary dividends from retained earnings. "
              "Per user decision: equity + 'dividend' = EQU.RET.DIV.ORD.",
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

    # Stock movement / adjustment
    Rule(
        name="stock_movement_expense",
        code="EXP.COS",
        priority=72,
        keywords=["stock movement", "stock adjust"],
        notes="Stock movement/adjustment -> cost of sales.",
    ),

    # COGS prefix (broad)
    Rule(
        name="cogs_prefix",
        code="EXP.COS",
        priority=75,
        keywords=["cogs", "cost of goods"],
        keywords_exclude=["cost of goods sold"],
        notes="COGS / cost of goods (not 'cost of goods sold') -> cost of sales.",
    ),

    # Cost of Goods Sold (specific phrase)
    Rule(
        name="cost_of_goods_sold_specific",
        code="EXP.COS.PUR",
        priority=78,
        keywords=["cost of goods sold"],
        notes="Cost of goods sold (specific) -> purchases.",
    ),

    # Shareholder salaries (must outprioritise wages_expense P93)
    Rule(
        name="shareholder_salaries",
        code="EXP.EMP.SHA",
        priority=95,
        keywords=["shareholder salar", "shareholder wage"],
        notes="Shareholder salaries/wages -> shareholder salaries.",
    ),

    # Foreign currency gains/losses
    Rule(
        name="bank_revaluation_forex",
        code="EXP.FOR",
        priority=78,
        keywords=["bank revaluation", "bank revaluations",
                  "fx revaluation", "currency revaluation",
                  "foreign currency gain", "foreign currency loss",
                  "foreign exchange gain", "foreign exchange loss",
                  "realised forex", "unrealised forex",
                  "realised foreign currency", "unrealised foreign currency"],
        canon_types={"expense", "direct costs"},
        notes="Bank/currency revaluations and forex gains/losses -> EXP.FOR. "
              "Bank account revaluations arise from foreign currency movements. "
              "Restricted to expense types; income-typed forex accounts use REV.OTH. "
              "Per user decision: 'Bank Revaluations' -> foreign currency gains/losses.",
    ),
    Rule(
        name="forex_other_income",
        code="REV.OTH",
        priority=78,
        keywords=["foreign currency gain", "foreign currency loss",
                  "foreign exchange gain", "foreign exchange loss",
                  "realised forex", "unrealised forex",
                  "realised foreign currency", "unrealised foreign currency",
                  "fx gain", "fx loss"],
        canon_types={"other income", "revenue", "income"},
        notes="Forex gains/losses on income-typed accounts -> other income. "
              "Xero may book unrealised/realised currency gains under Other Income. "
              "Companion to bank_revaluation_forex which handles expense-typed accounts.",
    ),
]


# --- Equity / Shares / Retained Earnings (Priority 75-85) ---
_equity_rules = [
    Rule(
        name="share_capital_equity",
        code="EQU.SHA.ORD",
        priority=90,
        keywords=["share capital"],
        canon_types={"equity"},
        notes="Share capital on equity -> ordinary shares. "
              "Higher priority than owner_funds_introduced which now excludes equity.",
    ),
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
        name="fully_part_paid_shares",
        code="EQU.SHA.ORD",
        priority=83,
        keywords=["fully paid shares", "partly paid shares", "part paid shares",
                  "fully paid ordinary", "partly paid ordinary",
                  "fully/part paid shares"],
        canon_types={"equity"},
        notes="Fully/partly paid shares -> ordinary share capital. "
              "Per user decision: 'fully paid shares' and 'part paid shares' are "
              "alternative terms for share capital (EQU.SHA.ORD).",
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
    Rule(
        name="asset_revaluation_reserve",
        code="EQU.RES.REV",
        priority=80,
        keywords=["revaluation reserve", "asset revaluation"],
        canon_types={"equity"},
        notes="Asset revaluation reserve -> equity revaluation reserve. "
              "Per SystemMappings.csv row 94.",
    ),
    Rule(
        name="small_business_restructuring_reserve",
        code="EQU.RES",
        priority=80,
        keywords=["small business restructuring fund", "restructuring fund",
                  "restructure fund", "solvency reserve"],
        canon_types={"equity"},
        notes="Small Business Restructuring fund -> general reserves. "
              "SBR funds set aside from retained earnings are general reserves "
              "(EQU.RES) per SystemMappings: 'General reserves where entity sets "
              "aside part of retained earnings for a specified purpose'.",
    ),
    Rule(
        name="historical_adjustment_equity",
        code="EQU.RET",
        priority=78,
        keywords=["historical adjustment"],
        canon_types={"equity", "current liability", "liability", "historical"},
        notes="Historical adjustments relate to prior-year adjustments and represent "
              "movements in retained earnings regardless of Xero account type. "
              "Type must be corrected in the review interface. Per user decision.",
    ),
    Rule(
        name="tax_adjustment_reserve",
        code="EQU.RET",
        priority=78,
        keywords=["tax adjustment reserve", "tax adjustment"],
        canon_types={"equity"},
        notes="Tax adjustment reserve impacts retained earnings. The journal reconciling "
              "P&L to taxable income should have no overall impact on retained earnings. "
              "Per user decision.",
    ),
    Rule(
        name="opening_balance_equity",
        code="EQU.RET",
        priority=78,
        keywords=["opening balance"],
        canon_types={"equity"},
        notes="Opening balance equity -> retained earnings. SystemMappings "
              "EQU.RET includes 'Retained earnings brought forward'.",
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

    # Rental bonds held (money held on behalf of clients = liability)
    Rule(
        name="rental_bonds_held",
        code="LIA.CUR.PAY",
        priority=82,
        keywords=["rental bond", "rental bonds", "security bond", "security bonds"],
        keywords_all=["held"],
        raw_types={"current liability", "current asset", "asset", "liability"},
        keywords_exclude=["expense", "cost", "income"],
        notes="Rental bonds HELD -> current payable liability. "
              "Requires 'held' in name: distinguishes bonds held on behalf of clients "
              "(liability) from bonds paid as a deposit (asset, e.g. 'Rental Bond - "
              "Term Deposit' or 'Rental Bond - Sublease'). "
              "Cross-type: accepts current asset type when Xero incorrectly books "
              "client-held bonds as assets. Per user decision: account 607.",
    ),

    # Sundry debtors / Retentions
    Rule(
        name="sundry_debtors",
        code="ASS.CUR.REC",
        priority=75,
        keywords=["sundry debtor"],
        notes="Sundry debtors/debtor -> current receivables (not trade). "
              "Per user decision: sundry != trade, but IS a receivable.",
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

    # Trade / Sundry creditors
    Rule(
        name="trade_creditors",
        code="LIA.CUR.PAY.TRA",
        priority=90,
        keywords=["trade creditor"],
        canon_types={"current liability", "liability"},
        notes="Trade creditors/payables -> trade payables",
    ),
    Rule(
        name="sundry_creditors",
        code="LIA.CUR.PAY",
        priority=85,
        keywords=["sundry creditor"],
        canon_types={"current liability", "liability"},
        keywords_exclude=["trade", "ato", "fbt", "tax"],
        notes="Sundry creditors -> payables (not trade). "
              "Excludes ATO/FBT/tax variants (those are LIA.CUR.TAX). "
              "Per user decision: sundry != trade, but IS a payable.",
    ),
    Rule(
        name="fees_payable",
        code="LIA.CUR.PAY",
        priority=75,
        keywords=["fees payable", "fee payable"],
        canon_types={"current liability", "liability"},
        keywords_exclude=["ato", "tax", "fbt"],
        notes="'Fees Payable' (e.g. Accounting Fees Payable) -> current payable. "
              "Per user decision: account 810 (test-client-5).",
    ),

    # Fixed assets — furniture, PPE, motor vehicle
    Rule(
        name="furniture_fittings_asset",
        code="ASS.NCA.FIX.PLA",
        priority=78,
        keywords=["furniture", "fittings"],
        canon_types={"fixed asset"},
        keywords_exclude=["depreciation", "accumulated", "deprec", "accum"],
        notes="Furniture & fittings -> plant & equipment fixed assets. "
              "Per user decision: falls under ASS.NCA.FIX.PLA.",
    ),
    Rule(
        name="ppe_asset",
        code="ASS.NCA.FIX.PLA",
        priority=78,
        keywords=["plant & equipment", "plant and equipment", "property plant"],
        canon_types={"fixed asset"},
        keywords_exclude=["depreciation", "accumulated", "deprec", "accum"],
        notes="Property, Plant & Equipment -> fixed assets plant. "
              "Per user decision: name clearly belongs in ASS.NCA.FIX.PLA.",
    ),
    Rule(
        name="motor_vehicle_fixed_asset",
        code="ASS.NCA.FIX.VEH",
        priority=80,
        keywords=["motor vehicle", "mv"],
        canon_types={"fixed asset"},
        keywords_exclude=["depreciation", "accumulated", "deprec", "accum",
                          "car limit", "over limit"],
        notes="Motor vehicle fixed assets -> vehicle assets. "
              "Excludes depreciation variants and 'over car limit' tax pool accounts.",
    ),

    # Inventory
    Rule(
        name="inventory_asset",
        code="ASS.CUR.INY",
        priority=80,
        keywords=["inventory"],
        raw_types={"inventory"},
        notes="Inventory type accounts -> inventory assets",
    ),

    # Preliminary expenses
    Rule(
        name="preliminary_expenses",
        code="ASS.NCA",
        priority=75,
        keywords=["preliminary expenses"],
        notes="Preliminary expenses -> non-current asset",
    ),

    # Term deposits
    Rule(
        name="term_deposit_nca",
        code="ASS.NCA.INV.TER",
        priority=78,
        keywords=["term deposit"],
        canon_types={"non-current asset"},
        notes="Term deposit on non-current asset -> ASS.NCA.INV.TER. "
              "SystemMappings leaf code for long-term deposits.",
    ),
    Rule(
        name="term_deposit_ca",
        code="ASS.CUR.TER",
        priority=78,
        keywords=["term deposit"],
        canon_types={"current asset", "asset"},
        keywords_exclude=["rental bond", "bond"],
        notes="Term deposit on current asset -> ASS.CUR.TER. "
              "SystemMappings leaf code for short-term deposits. "
              "Excludes rental bonds (security deposits, not financial term deposits).",
    ),

    # Intangible assets
    Rule(
        name="intangible_asset_keywords",
        code="ASS.NCA.INT",
        priority=72,
        keywords=["franchise", "website", "customer list", "branding",
                  "patent", "trademark", "copyright", "licence", "license"],
        canon_types={"non-current asset", "fixed asset"},
        keywords_exclude=["accumulated", "amortis", "depreciation", "deprec", "accum"],
        notes="Intangible asset keywords -> ASS.NCA.INT. SystemMappings "
              "includes franchises, websites, customer lists, branding. "
              "Excludes accumulated amortisation/depreciation accounts.",
    ),

    # Prepaid / Prepayments
    Rule(
        name="prepaid_asset",
        code="ASS.CUR.REC.PRE",
        priority=72,
        keywords=["pre paid", "prepaid", "prepayment"],
        keywords_exclude=["stock", "interest"],
        notes="Prepaid/prepayment -> current prepaid receivable. "
              "Catches 'Pre-paid GST', 'Prepaid Insurance', etc. "
              "Excludes stock (inventory) and interest (expense) prepayments.",
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

    # Stock on hand
    Rule(
        name="stock_on_hand",
        code="ASS.CUR.INY",
        priority=78,
        keywords=["stock on hand", "stock in hand"],
        canon_types={"current asset", "inventory"},
        notes="Stock on hand -> inventory asset.",
    ),

    # Stock (general, on asset types)
    Rule(
        name="stock_asset_general",
        code="ASS.CUR.INY",
        priority=65,
        keywords=["stock"],
        canon_types={"current asset", "inventory"},
        keywords_exclude=["closing", "opening", "movement", "adjust",
                          "depreciation", "prepaid", "transit"],
        notes="General 'stock' on asset type -> inventory. "
              "Excludes opening/closing/movement/adjusting/prepaid/transit entries.",
    ),

    # Formation / incorporation costs (asset)
    Rule(
        name="formation_costs_asset",
        code="ASS.NCA.INT",
        priority=78,
        keywords=["formation cost", "formation costs",
                  "formation expense", "formation expenses",
                  "incorporation cost", "incorporation costs",
                  "establishment cost", "establishment costs"],
        canon_types={"non-current asset", "fixed asset"},
        keywords_exclude=["less", "written off", "write off", "amortis"],
        notes="Formation/incorporation/establishment costs on NCA -> intangibles. "
              "Extends to 'formation expenses' (the plural and 'expense' noun variant) "
              "per user decision: formation expenses as NCA are always intangibles. "
              "Excludes 'less written off' accounts (accumulated amortisation -> ASS.NCA.INT.AMO).",
    ),
    Rule(
        name="formation_costs_written_off",
        code="ASS.NCA.INT.AMO",
        priority=89,
        keywords=["formation cost", "formation costs",
                  "formation expense", "formation expenses",
                  "incorporation cost", "establishment cost"],
        keywords_all=["less"],
        canon_types={"non-current asset", "fixed asset", "asset"},
        notes="'Formation Costs - Less Written Off' -> accumulated amortisation of intangibles "
              "(ASS.NCA.INT.AMO). The 'less' prefix indicates this is the contra-asset "
              "reducing the gross formation costs on the balance sheet. "
              "Per user decision: account 731 (test-client-5).",
    ),

    # General pool / SBE pool
    Rule(
        name="general_pool_asset",
        code="ASS.NCA.FIX",
        priority=78,
        keywords=["general pool", "sbe pool", "small business pool"],
        keywords_exclude=["accumulated", "deprec", "amort", "accum"],
        notes="General pool / SBE pool -> fixed assets. "
              "Excludes accumulated depreciation entries.",
    ),

    # Investment asset (generic)
    Rule(
        name="investment_asset_generic",
        code="ASS.NCA.INV",
        priority=68,
        keywords=["investment"],
        canon_types={"non-current asset"},
        keywords_exclude=["property", "shares", "unit trust", "managed fund"],
        notes="Generic 'investment' on NCA type -> financial assets. "
              "Excludes specific investment types.",
    ),

    # Goodwill
    Rule(
        name="goodwill_asset",
        code="ASS.NCA.INT.GOO",
        priority=80,
        keywords=["goodwill"],
        keywords_exclude=["accumulated", "amortis", "deprec", "accum",
                          "sale of business"],
        type_exclude={"equity", "revenue", "income", "other income", "expense"},
        notes="Goodwill -> intangible goodwill. "
              "Excludes accumulated amortisation/depreciation and non-asset types.",
    ),
]


# --- Industry aliases & normalisation ---
INDUSTRY_ALIASES: dict[str, str] = {
    "building": "construction",
    "builder": "construction",
    "construction": "construction",
    "auto": "auto",
    "automotive": "auto",
    "auto dealer": "auto",
    "motor dealer": "auto",
    "car dealer": "auto",
    "motor vehicle dealer": "auto",
}


def normalise_industry(raw: str) -> str:
    """Normalise a raw industry string to a canonical key.

    Returns empty string for unknown or unset industries.
    """
    if not raw:
        return ""
    key = raw.strip().lower()
    return INDUSTRY_ALIASES.get(key, "")


# --- Industry-specific rules ---
_industry_rules: list[Rule] = [
    Rule(
        name="construction_revenue_services",
        code="REV.TRA.SER",
        priority=82,
        keywords=["revenue", "income", "sales", "fees", "receipts"],
        canon_types={"revenue", "income", "other income", "sales"},
        industries={"construction"},
        notes="Construction: all revenue is trading services.",
    ),
    Rule(
        name="construction_subcontractors_cos",
        code="EXP.COS",
        priority=82,
        keywords=["subcontract"],
        industries={"construction"},
        notes="Construction: subcontractors are cost of sales.",
    ),
    Rule(
        name="construction_materials_cos",
        code="EXP.COS.PUR",
        priority=82,
        keywords=["material", "materials", "supplies"],
        canon_types={"expense", "direct costs"},
        industries={"construction"},
        notes="Construction: materials/supplies are purchases (cost of sales).",
    ),
    Rule(
        name="auto_mv_expenses_cos",
        code="EXP.COS",
        priority=82,
        keywords=["motor vehicle", "vehicle"],
        canon_types={"expense", "direct costs"},
        keywords_exclude=["depreciation", "deprec", "accumulated", "amort"],
        industries={"auto"},
        notes="Auto dealers: MV expenses are cost of sales, not overhead.",
    ),

    # --- Auto dealer: revenue subtype rules ---
    # For auto dealers, generic "sales" / "consignment" revenue is sale of goods (cars).
    # Service-type keywords (warranty, delivery, extras) stay as trading services.
    Rule(
        name="auto_sales_goods",
        code="REV.TRA.GOO",
        priority=84,
        keywords=["sales", "consignment sale"],
        canon_types={"revenue", "income", "sales"},
        industries={"auto"},
        keywords_exclude=["warranty", "delivery", "extras", "service",
                          "rental", "rent", "fee"],
        notes="Auto dealers: sales/consignment revenue is sale of goods (vehicles).",
    ),
    Rule(
        name="auto_service_revenue",
        code="REV.TRA.SER",
        priority=84,
        keywords=["warranty", "delivery", "extras", "service"],
        canon_types={"revenue", "income", "sales"},
        industries={"auto"},
        notes="Auto dealers: warranty/delivery/service items are trading services.",
    ),
    Rule(
        name="auto_consignment_fees_commission",
        code="REV.OTH.COM",
        priority=84,
        keywords=["consignment fee", "consignment fees"],
        canon_types={"revenue", "income", "other income", "sales"},
        industries={"auto"},
        notes="Auto dealers: consignment fees received are commission income.",
    ),
    Rule(
        name="auto_car_rental_revenue",
        code="REV.TRA.SER",
        priority=86,
        keywords=["car rental", "car rentals", "vehicle rental"],
        canon_types={"revenue", "income", "sales"},
        industries={"auto"},
        notes="Auto dealers: car rentals are trading services, not investment rental.",
    ),
    Rule(
        name="auto_transport_towing_cos",
        code="EXP.COS",
        priority=82,
        keywords=["transport", "towing"],
        canon_types={"expense", "direct costs"},
        industries={"auto"},
        notes="Auto dealers: transport & towing is cost of sales (getting cars to lot).",
    ),
]


# --- Collect all rules ---
ALL_RULES: list[Rule] = [
    *_industry_rules,
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
