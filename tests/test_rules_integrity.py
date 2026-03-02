"""Verify every rule's output code is valid and type-compatible.

Validates that:
1. Every rule's output code exists in SystemFiles/SystemMappings.csv
2. Every rule's output code is type-compatible with its declared type constraints
   (i.e. the code's prefix is allowed for every account type the rule can match)
"""
import pandas as pd
import pathlib
import json
import pytest
from rules import ALL_RULES

PROJECT_ROOT = pathlib.Path(__file__).parent.parent


@pytest.fixture(scope="module")
def system_mappings():
    return pd.read_csv(PROJECT_ROOT / "SystemFiles" / "SystemMappings.csv")


@pytest.fixture(scope="module")
def type_rules():
    with open(
        PROJECT_ROOT / "SystemFiles" / "Account_Types_per_Financial-Reports.json"
    ) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def allowed_codes(system_mappings):
    return set(system_mappings["Reporting Code"].astype(str).str.strip())


# ---------------------------------------------------------------------------
# Test 1: Every rule's output code must exist in SystemMappings.csv
# ---------------------------------------------------------------------------

# Known missing codes that are valid Xero codes not present in SystemMappings.csv.
# EXP.COS.WAG is a legitimate direct-cost wages code used in practice but
# not listed as a leaf in SystemMappings.csv (which only has EXP.EMP.WAG).
XFAIL_CODE_EXISTS = {
    "wages_direct_cost",  # EXP.COS.WAG — valid in Xero but absent from SystemMappings
}


@pytest.mark.parametrize("rule", ALL_RULES, ids=lambda r: r.name)
def test_rule_code_exists(rule, allowed_codes):
    """Every rule's output code must exist in SystemMappings."""
    if rule.name in XFAIL_CODE_EXISTS:
        pytest.xfail(
            f"Rule '{rule.name}' outputs code '{rule.code}' which is a known "
            f"valid Xero code not present in SystemMappings.csv"
        )
    assert rule.code in allowed_codes, (
        f"Rule '{rule.name}' outputs code '{rule.code}' "
        f"which does not exist in SystemMappings.csv"
    )


# ---------------------------------------------------------------------------
# Test 2: Type compatibility — if a rule declares type constraints, its output
# code must be allowed for those types per the JSON spec.
# ---------------------------------------------------------------------------

# Known cross-type rules where the code intentionally doesn't match all declared
# types. These rules accept broad type sets for matching flexibility but output
# a code for a specific balance sheet section.
XFAIL_TYPE_COMPAT = {
    # loan_to_pty accepts {current asset, non-current asset, asset} but outputs
    # ASS.NCA.REL (non-current). This is intentional: loans to related parties
    # are classified as NCA regardless of the raw type's current/non-current tag.
    ("loan_to_pty", "current asset"): (
        "Intentionally maps current asset loans to NCA related party"
    ),
    # shares_asset accepts {asset, current asset, non-current asset} but outputs
    # ASS.NCA.INV.SHA (non-current investment). Share investments are always
    # classified as non-current regardless of raw type.
    ("shares_asset", "current asset"): (
        "Share investments always classified as NCA regardless of raw type"
    ),
    # director_loan_generic_nca intentionally reclassifies director loans from
    # liability to asset type (Div7A). Type must be corrected in review interface.
    ("director_loan_generic_nca", "non-current liability"): (
        "Div7A: director loans always assets regardless of Xero type"
    ),
    ("director_loan_generic_nca", "current liability"): (
        "Div7A: director loans always assets regardless of Xero type"
    ),
    ("director_loan_generic_nca", "liability"): (
        "Div7A: director loans always assets regardless of Xero type"
    ),
    # historical_adjustment_equity intentionally assigns EQU.RET to liability-typed
    # accounts. Historical adjustments are retained earnings regardless of Xero type.
    ("historical_adjustment_equity", "current liability"): (
        "Historical adjustments are retained earnings regardless of Xero type"
    ),
    ("historical_adjustment_equity", "liability"): (
        "Historical adjustments are retained earnings regardless of Xero type"
    ),
    ("historical_adjustment_equity", "historical"): (
        "Historical adjustments are retained earnings regardless of Xero type"
    ),
    # auto_consignment_fees_commission intentionally reclassifies Revenue-typed
    # consignment fees to REV.OTH.COM (commission). Type change prompted in review.
    ("auto_consignment_fees_commission", "revenue"): (
        "Auto: consignment fees are commissions; type change to Other Income prompted in review"
    ),
    ("auto_consignment_fees_commission", "income"): (
        "Auto: consignment fees are commissions; type change to Other Income prompted in review"
    ),
    ("auto_consignment_fees_commission", "sales"): (
        "Auto: consignment fees are commissions; type change to Other Income prompted in review"
    ),
}


def _code_allowed_for_type(code: str, type_key: str, type_rules: dict) -> bool:
    """Check if a code is allowed for a given type, using both exact and prefix matching."""
    if type_key not in type_rules:
        return True  # Unknown type, can't validate

    entry = type_rules[type_key]
    allowed_codes = set(entry.get("allowed_codes", []))
    allowed_prefixes = set(entry.get("allowed_prefixes", []))

    # Exact code match
    if code in allowed_codes:
        return True

    # Prefix match: check if any prefix of the code is in allowed_prefixes
    code_parts = code.split(".")
    for i in range(len(code_parts)):
        prefix = ".".join(code_parts[: i + 1])
        if prefix in allowed_prefixes:
            return True

    return False


@pytest.mark.parametrize("rule", ALL_RULES, ids=lambda r: r.name)
def test_rule_code_type_compatible(rule, type_rules):
    """If a rule declares type constraints, its output code must be allowed for those types."""
    types_to_check = rule.raw_types | rule.canon_types
    if not types_to_check:
        pytest.skip("Rule has no type constraints")

    failures = []
    for account_type in types_to_check:
        type_key = account_type.strip().title()  # Match JSON keys
        xfail_key = (rule.name, account_type.strip().lower())

        if xfail_key in XFAIL_TYPE_COMPAT:
            continue  # Skip known intentional cross-type mappings

        if type_key not in type_rules:
            continue  # Unknown type, skip

        if not _code_allowed_for_type(rule.code, type_key, type_rules):
            entry = type_rules[type_key]
            allowed = sorted(entry.get("allowed_codes", []))[:10]
            prefixes = sorted(entry.get("allowed_prefixes", []))
            failures.append(
                f"  type '{account_type}' (key '{type_key}'): "
                f"code '{rule.code}' not in allowed codes {allowed}... "
                f"or prefixes {prefixes}"
            )

    if failures:
        detail = "\n".join(failures)
        pytest.fail(
            f"Rule '{rule.name}' has type-incompatible code '{rule.code}':\n{detail}"
        )
