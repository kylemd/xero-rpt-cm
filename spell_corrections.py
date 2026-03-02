"""Spell correction preprocessing for account names.

Provides abbreviation expansion and typo correction using pyspellchecker.
Domain-specific accounting terms and project dictionaries (bank names,
vehicle makes, lender names) are whitelisted to prevent false corrections.
"""
from typing import Dict, List, Optional

from spellchecker import SpellChecker


# Domain-specific abbreviation expansions.
# Applied before spell-checking. Keys are lowercase tokens.
ABBREVIATIONS: Dict[str, str] = {
    "scg": "sgc",
    "lsl": "long service leave",
    "wip": "work in progress",
    "fy": "financial year",
    "ytd": "year to date",
    "mtd": "month to date",
    "bal": "balance",
    "acct": "account",
    "dept": "department",
    "govt": "government",
    "insur": "insurance",
    "maint": "maintenance",
    "mgmt": "management",
    "prepd": "prepaid",
    "prov": "provision",
    "depr": "depreciation",
    "amort": "amortisation",
}

# Terms to whitelist in pyspellchecker — valid domain jargon, not typos.
ACCOUNTING_TERMS: List[str] = [
    # Tax & regulatory
    "payg", "ato", "gst", "asic", "bas", "fbt", "sgc", "sga", "atsgc",
    "rcti", "abn", "acn", "tfn", "smsf", "ndis", "whs",
    # Software & entity
    "xero", "myob", "quickbooks",
    "pty", "ltd",
    # Accounting concepts
    "superannuation", "annuation",
    "div7a", "payable", "receivable", "accrual", "accruals",
    "amortisation", "amortization", "depreciation",
    "franking", "imputation", "gearing",
    "revaluation", "withholdings",
    # Common business abbreviations
    "admin", "qleave",
    # Australian acronyms (insurance, tax, entity)
    "eftpos", "ctp", "sbe", "lct", "ica",
]


def build_spell_checker(extra_known: List[str]) -> SpellChecker:
    """Build a SpellChecker with domain terms and extra words whitelisted.

    Domain terms are loaded with a high frequency boost so that pyspellchecker
    prefers them over common English words when correcting typos (e.g.
    "revalution" -> "revaluation" rather than "revolution").

    Args:
        extra_known: Additional words to whitelist (bank names, vehicle makes,
                     lender names, business name tokens, etc.)
    """
    spell = SpellChecker()
    # Whitelist and boost accounting terms so they outrank common English words
    spell.word_frequency.load_words(ACCOUNTING_TERMS)
    _boost_frequencies(spell, ACCOUNTING_TERMS)
    # Whitelist and boost extra domain words (lowercased)
    if extra_known:
        lowered = [w.lower() for w in extra_known]
        spell.word_frequency.load_words(lowered)
        _boost_frequencies(spell, lowered)
    return spell


# Frequency value high enough to outrank any common English word in
# pyspellchecker's built-in dictionary (max is ~100k for "the").
_DOMAIN_BOOST = 200_000


def _boost_frequencies(spell: SpellChecker, words: List[str]) -> None:
    """Set domain words to a high frequency so they win correction ranking."""
    for word in words:
        w = word.lower()
        if spell.word_frequency[w] < _DOMAIN_BOOST:
            spell.word_frequency._dictionary[w] = _DOMAIN_BOOST


def _correct_tokens(
    text: str,
    spell: Optional[SpellChecker],
) -> Dict:
    """Correct tokens in *text* via abbreviation expansion then spell-check.

    This is the inner workhorse — operates on a single text segment.
    """
    tokens = text.split()
    corrections: list = []
    result_tokens: list = []

    for token in tokens:
        lower = token.lower()

        # Stage A: Abbreviation expansion
        if lower in ABBREVIATIONS:
            expanded = ABBREVIATIONS[lower]
            corrections.append({
                "original": token,
                "corrected": expanded,
                "source": "abbreviation",
            })
            result_tokens.append(expanded)
            continue

        # Stage B: Spell-check (if checker provided)
        if spell is not None:
            # Only check tokens that look like words (skip codes, numbers)
            if lower.isalpha() and len(lower) > 2:
                unknown = spell.unknown([lower])
                if unknown:
                    suggestion = spell.correction(lower)
                    if suggestion and suggestion != lower:
                        # Preserve original casing style
                        if token[0].isupper():
                            suggestion = suggestion.capitalize()
                        if token.isupper():
                            suggestion = suggestion.upper()
                        corrections.append({
                            "original": token,
                            "corrected": suggestion,
                            "source": "spellcheck",
                        })
                        result_tokens.append(suggestion)
                        continue

        result_tokens.append(token)

    corrected = " ".join(result_tokens)
    return {"corrected": corrected, "corrections": corrections}


def correct_account_name(
    name: str,
    spell: Optional[SpellChecker] = None,
) -> Dict:
    """Correct an account name via abbreviation expansion then spell-check.

    Splits on the first `` - `` (space-dash-space) separator.  Only the
    *prefix* (the accounting description) is spell-checked; the suffix
    (often a business name, personal name, or location) passes through
    untouched.  This prevents false corrections on proper nouns like
    "Hendra", "M Vieira", or "EasyCars".

    Args:
        name: Raw account name from the chart of accounts.
        spell: Pre-built SpellChecker instance. If None, only abbreviation
               expansion is applied (no typo correction).

    Returns:
        Dict with keys:
            corrected: The corrected name string.
            corrections: List of {original, corrected, source} dicts.
    """
    # Split on first " - " to protect business/personal name suffixes
    sep = " - "
    idx = name.find(sep)
    if idx >= 0:
        prefix = name[:idx]
        suffix = name[idx:]  # includes " - …"
        result = _correct_tokens(prefix, spell)
        result["corrected"] = result["corrected"] + suffix
        return result
    return _correct_tokens(name, spell)
