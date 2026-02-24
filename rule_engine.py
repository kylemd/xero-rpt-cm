"""Declarative rule engine for Xero reporting code assignment.

Rules are defined as dataclass instances with explicit conditions and priorities.
The engine evaluates all matching rules against an account row and returns the
highest-priority match.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Rule:
    """A single keyword-based mapping rule.

    Attributes:
        name:             Unique identifier for this rule.
        code:             Reporting code to assign when this rule matches.
        priority:         Explicit priority (higher wins). Tiers:
                          100+ = type-specific overrides
                          90-99 = high-confidence keywords
                          80-89 = industry-specific
                          70-79 = general categories
                          60-69 = broad patterns
                          50-59 = catch-all
        keywords:         ANY of these must appear in normalised text.
        keywords_all:     ALL of these must appear in normalised text.
        keywords_exclude: NONE of these may appear in normalised text.
        raw_types:        Raw *Type field must be one of these (case-insensitive).
        canon_types:      Canonical type must be one of these.
        type_exclude:     Canonical type must NOT be one of these.
        template:         Only matches when using this template name (e.g. "company").
        owner_context:    If True, requires OWNER_KEYWORDS match in text.
        name_only:        If True, match only against account name (not name+description).
        notes:            Human-readable audit notes.
    """
    name: str
    code: str
    priority: int
    keywords: list[str] = field(default_factory=list)
    keywords_all: list[str] = field(default_factory=list)
    keywords_exclude: list[str] = field(default_factory=list)
    raw_types: set[str] = field(default_factory=set)
    canon_types: set[str] = field(default_factory=set)
    type_exclude: set[str] = field(default_factory=set)
    template: str | None = None
    owner_context: bool = False
    name_only: bool = False
    notes: str = ""


@dataclass
class MatchContext:
    """Context passed to rule evaluation.

    Attributes:
        normalised_text:   Normalised account name + description.
        normalised_name:   Normalised account name only (for name_only rules).
        raw_type:          Raw *Type field value.
        canon_type:        Canonical type after TYPE_EQ mapping.
        template_name:     Template chart name (e.g. "company", "trust").
        owner_keywords:    List of owner keyword strings for owner_context check.
    """
    normalised_text: str
    raw_type: str
    canon_type: str
    template_name: str
    normalised_name: str = ""
    owner_keywords: list[str] = field(default_factory=list)


def _rule_matches(rule: Rule, ctx: MatchContext) -> bool:
    """Check whether a single rule's conditions are met."""
    text = ctx.normalised_name if rule.name_only else ctx.normalised_text

    # Keyword conditions
    if rule.keywords and not any(kw in text for kw in rule.keywords):
        return False
    if rule.keywords_all and not all(kw in text for kw in rule.keywords_all):
        return False
    if rule.keywords_exclude and any(kw in text for kw in rule.keywords_exclude):
        return False

    # Type constraints
    raw_lower = ctx.raw_type.strip().lower()
    if rule.raw_types and raw_lower not in rule.raw_types:
        return False
    if rule.canon_types and ctx.canon_type not in rule.canon_types:
        return False
    if rule.type_exclude and ctx.canon_type in rule.type_exclude:
        return False

    # Template constraint
    if rule.template is not None and ctx.template_name.strip().lower() != rule.template:
        return False

    # Owner context
    if rule.owner_context:
        if not any(kw in ctx.normalised_text for kw in ctx.owner_keywords):
            return False

    return True


def evaluate_rules(
    rules: list[Rule], ctx: MatchContext
) -> tuple[Optional[str], Optional[str]]:
    """Evaluate all rules against a row context, return (code, rule_name) of winner.

    Returns (None, None) if no rule matches.
    """
    candidates = [r for r in rules if _rule_matches(r, ctx)]
    if not candidates:
        return None, None
    winner = max(candidates, key=lambda r: r.priority)
    return winner.code, winner.name
