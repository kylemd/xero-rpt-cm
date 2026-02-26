"""Cross-account context rules for refining ambiguous code assignments.

Detects anchor accounts (e.g., Goodwill with active trial balance) and
infers codes for nearby ambiguous accounts based on chart structure.
"""
from typing import Dict, List, Set


# Head-only codes that are candidates for refinement
HEAD_ONLY_CODES = {"ASS", "EXP", "REV", "LIA", "EQU"}

# Sources that indicate a head-only fallback (no specific rule matched)
FALLBACK_SOURCES = {"FallbackParent", "FallbackHead", "TypeOnly"}

# Account names that should never be promoted by section inference
# (clearing/generic accounts that are intentionally at head level)
SECTION_INFERENCE_EXCLUSIONS = [
    "opening balance", "historical adjustment", "rounding",
    "suspense", "clearing", "unallocated",
]

# Context anchors: when an anchor account is detected with an active balance,
# nearby accounts matching the inference keywords get refined.
CONTEXT_ANCHORS = [
    {
        "anchor_name": "goodwill_intangibles",
        "anchor_keywords": ["goodwill"],
        "nearby_keywords": ["legal", "capital", "acquisition", "formation",
                            "incorporation", "stamp duty"],
        "nearby_fallback_heads": {"ASS"},
        "inferred_code": "ASS.NCA.INT",
        "proximity": 50,
        "notes": "Business acquisition costs near active goodwill -> intangibles",
    },
    {
        "anchor_name": "land_buildings",
        "anchor_keywords": ["land", "building", "property"],
        "nearby_keywords": ["improvement", "fitout", "fit out", "renovation",
                            "refurbishment", "leasehold"],
        "nearby_fallback_heads": {"ASS"},
        "inferred_code": "ASS.NCA.FIX.PLA",
        "proximity": 30,
        "notes": "Improvements near active land/buildings -> fixed assets",
    },
]


def _parse_code_number(code_str: str) -> float:
    """Parse an account code string to a numeric value for proximity checks."""
    try:
        return float(code_str.replace(",", "").strip())
    except (ValueError, TypeError):
        return float("nan")


def detect_anchors(
    accounts: List[Dict],
    bal_lookup: Dict[str, float],
) -> List[Dict]:
    """Detect anchor accounts that have active trial balance balances.

    Args:
        accounts: List of account dicts with 'code', 'name', 'predicted' keys.
        bal_lookup: {account_code: closing_balance} from trial balance.

    Returns:
        List of detected anchor dicts with anchor_name, account index, code number.
    """
    detected = []
    for i, acct in enumerate(accounts):
        name_lower = acct["name"].lower()
        code = acct["code"]
        balance = bal_lookup.get(code, 0.0)

        # Skip if no active balance
        if not balance or balance == 0.0:
            continue

        for anchor in CONTEXT_ANCHORS:
            if any(kw in name_lower for kw in anchor["anchor_keywords"]):
                detected.append({
                    "anchor_name": anchor["anchor_name"],
                    "anchor_index": i,
                    "anchor_code": code,
                    "anchor_code_num": _parse_code_number(code),
                    "anchor_config": anchor,
                })
    return detected


def infer_from_context(
    accounts: List[Dict],
    bal_lookup: Dict[str, float],
    overridden_indices: Set[int],
) -> List[Dict]:
    """Run cross-account context inference on head-only fallback accounts.

    Args:
        accounts: List of account dicts with 'code', 'name', 'predicted', 'source'.
        bal_lookup: {account_code: closing_balance} from trial balance.
        overridden_indices: Set of indices to skip (audited overrides).

    Returns:
        List of inference result dicts with code, inferred_code, reason.
    """
    anchors = detect_anchors(accounts, bal_lookup)
    if not anchors:
        return []

    results = []
    for i, acct in enumerate(accounts):
        if i in overridden_indices:
            continue

        predicted = acct.get("predicted", "")
        # Only refine head-only fallback codes
        if predicted not in HEAD_ONLY_CODES:
            continue

        name_lower = acct["name"].lower()
        acct_code_num = _parse_code_number(acct["code"])

        for anchor in anchors:
            config = anchor["anchor_config"]

            # Check if this account's fallback head matches the anchor's target
            if predicted not in config["nearby_fallback_heads"]:
                continue

            # Check proximity (NaN-safe)
            anchor_num = anchor["anchor_code_num"]
            if acct_code_num != acct_code_num or anchor_num != anchor_num:
                continue  # NaN check
            if abs(acct_code_num - anchor_num) > config["proximity"]:
                continue

            # Check if name matches any inference keywords
            if any(kw in name_lower for kw in config["nearby_keywords"]):
                results.append({
                    "index": i,
                    "code": acct["code"],
                    "name": acct["name"],
                    "inferred_code": config["inferred_code"],
                    "reason": f"CrossAccountContext:{anchor['anchor_name']}",
                    "anchor_code": anchor["anchor_code"],
                })
                break  # One inference per account

    return results


def infer_section(
    accounts: List[Dict],
    bal_lookup: Dict[str, float],
    overridden_indices: Set[int],
    window: int = 5,
    consensus_threshold: float = 0.6,
) -> List[Dict]:
    """Infer balance sheet section for head-only accounts from neighbours.

    Looks at nearby accounts (by index position) and if a supermajority share
    the same code prefix (e.g., ASS.NCA), refines the head-only account to
    match that section.

    Args:
        accounts: List of account dicts.
        bal_lookup: Trial balance lookup.
        overridden_indices: Indices to skip.
        window: Number of neighbours to examine in each direction.
        consensus_threshold: Fraction of neighbours that must agree.

    Returns:
        List of inference result dicts.
    """
    results = []

    for i, acct in enumerate(accounts):
        if i in overridden_indices:
            continue
        predicted = acct.get("predicted", "")
        if predicted not in HEAD_ONLY_CODES:
            continue

        # Skip clearing/generic accounts that should stay at head level
        name_lower = acct["name"].lower()
        if any(excl in name_lower for excl in SECTION_INFERENCE_EXCLUSIONS):
            continue

        # Gather neighbours' code prefixes (2-level: ASS.NCA, LIA.CUR, etc.)
        neighbour_prefixes = []
        for j in range(max(0, i - window), min(len(accounts), i + window + 1)):
            if j == i:
                continue
            nb_code = accounts[j].get("predicted", "")
            if not nb_code or nb_code in HEAD_ONLY_CODES:
                continue
            parts = nb_code.split(".")
            if len(parts) >= 2 and parts[0] == predicted:
                # Same head — record the 2-level prefix
                prefix = ".".join(parts[:2])
                # Weight by active balance
                nb_acct_code = accounts[j]["code"]
                balance = abs(bal_lookup.get(nb_acct_code, 0.0))
                weight = 1.0 if balance > 0 else 0.3
                neighbour_prefixes.append((prefix, weight))

        if not neighbour_prefixes:
            continue

        # Find consensus prefix
        weighted_counts: Dict[str, float] = {}
        for prefix, weight in neighbour_prefixes:
            weighted_counts[prefix] = weighted_counts.get(prefix, 0.0) + weight

        total_weight = sum(weighted_counts.values())
        if total_weight == 0:
            continue

        best_prefix, best_weight = max(weighted_counts.items(), key=lambda x: x[1])
        if best_weight / total_weight >= consensus_threshold:
            results.append({
                "index": i,
                "code": acct["code"],
                "name": acct["name"],
                "inferred_code": best_prefix,
                "reason": f"SectionInference:{best_prefix}",
            })

    return results
