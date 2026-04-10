/**
 * Rule engine — 1:1 port of rule_engine.py from the Python codebase.
 *
 * Evaluates a list of Rules against a MatchContext and returns the
 * highest-priority match.
 */

import type { Rule, MatchContext } from '../types';

// ---------------------------------------------------------------------------
// ruleMatches
// ---------------------------------------------------------------------------

/**
 * Test whether a single rule matches the given context.
 *
 * Ported from Python `_rule_matches()` in rule_engine.py.
 * All keyword matching uses substring `includes()`, NOT word boundaries.
 */
export function ruleMatches(rule: Rule, ctx: MatchContext): boolean {
  const text = rule.nameOnly ? ctx.normalisedName : ctx.normalisedText;

  // Keywords: any-of match (substring)
  if (rule.keywords.length > 0 && !rule.keywords.some((kw) => text.includes(kw))) {
    return false;
  }
  if (rule.keywordsAll.length > 0 && !rule.keywordsAll.every((kw) => text.includes(kw))) {
    return false;
  }
  if (rule.keywordsExclude.length > 0 && rule.keywordsExclude.some((kw) => text.includes(kw))) {
    return false;
  }

  // Type constraints
  if (
    rule.rawTypes.length > 0 &&
    !rule.rawTypes.some((t) => t.toLowerCase() === ctx.rawType.toLowerCase())
  ) {
    return false;
  }
  if (rule.canonTypes.length > 0 && !rule.canonTypes.includes(ctx.canonType)) {
    return false;
  }
  if (rule.typeExclude.length > 0 && rule.typeExclude.includes(ctx.canonType)) {
    return false;
  }

  // Template restriction
  if (rule.template !== undefined && rule.template.toLowerCase() !== ctx.templateName.toLowerCase()) {
    return false;
  }

  // Owner context — at least one ownerKeyword must appear in normalisedText
  if (rule.ownerContext) {
    if (!ctx.ownerKeywords.some((kw) => ctx.normalisedText.includes(kw))) {
      return false;
    }
  }

  // Industry restriction
  if (rule.industries !== undefined && rule.industries.length > 0) {
    if (!rule.industries.includes(ctx.industry)) {
      return false;
    }
  }

  return true;
}

// ---------------------------------------------------------------------------
// evaluateRules
// ---------------------------------------------------------------------------

/**
 * Evaluate all rules against the context and return the highest-priority
 * match, or null if no rule matches.
 *
 * Ported from Python `evaluate_rules()` in rule_engine.py.
 */
export function evaluateRules(
  rules: Rule[],
  ctx: MatchContext,
): { code: string; name: string } | null {
  let best: Rule | null = null;

  for (const rule of rules) {
    if (ruleMatches(rule, ctx)) {
      if (best === null || rule.priority > best.priority) {
        best = rule;
      }
    }
  }

  if (best !== null) {
    return { code: best.code, name: best.name };
  }
  return null;
}
