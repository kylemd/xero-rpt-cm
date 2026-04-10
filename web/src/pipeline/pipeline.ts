/**
 * Pipeline orchestrator — runs the full mapping waterfall + post-processing.
 *
 * This is the main entry point for mapping a set of accounts to reporting codes.
 * It mirrors the logic in mapping_logic_v15.py.
 */

import type {
  Account,
  MappedAccount,
  RulesData,
  Rule,
  MatchContext,
  TemplateEntry,
  SystemMapping,
  GLEntry,
} from '../types';

import { normalise, canonicalType, headFromType, headGroup, similarity, stripNoiseSuffixes } from './normalise';
import { evaluateRules } from './ruleEngine';
import { fuzzyMatchInHead } from './fuzzyMatch';
import { extractAccumBaseKey } from './accumDep';
import { inferFromContext, inferSection } from './contextRules';
import { serviceOnlyReclass, autoIndustryReclass, typeRangeCorrection } from './postProcess';
import { correctAccountName } from './spellCorrections';

// ---------------------------------------------------------------------------
// Public interface
// ---------------------------------------------------------------------------

export interface PipelineInput {
  accounts: Account[];
  rulesData: RulesData;
  templateEntries: TemplateEntry[];
  systemMappings: SystemMapping[];
  glSummary: GLEntry[];
  industry: string;
  templateName: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Template code match minimum similarity threshold. */
const TEMPLATE_SIMILARITY_THRESHOLD = 0.60;

/** Sources that are trusted for cross-head guard bypass. */
const CROSS_HEAD_SKIP_SOURCES = new Set([
  'DefaultChart',
  'AlreadyCorrect',
  'ExistingCodeValid',
  'ExistingCodeValidByName',
]);

// ---------------------------------------------------------------------------
// Dictionary expansion
// ---------------------------------------------------------------------------

/**
 * Expand dictionary references in rule keyword arrays.
 * Keywords like "$AUSTRALIAN_BANKS" are replaced with the actual dictionary
 * values from rulesData.dictionaries.
 */
function expandDictionaries(rules: Rule[], dictionaries: Record<string, string[]>): Rule[] {
  return rules.map((rule) => {
    const expand = (kws: string[]): string[] => {
      const result: string[] = [];
      for (const kw of kws) {
        if (kw.startsWith('$') && dictionaries[kw.slice(1)]) {
          result.push(...dictionaries[kw.slice(1)]);
        } else {
          result.push(kw);
        }
      }
      return result;
    };

    return {
      ...rule,
      keywords: expand(rule.keywords),
      keywordsAll: expand(rule.keywordsAll),
      keywordsExclude: expand(rule.keywordsExclude),
    };
  });
}

// ---------------------------------------------------------------------------
// Lookup builders
// ---------------------------------------------------------------------------

interface Lookups {
  templateByCode: Map<string, TemplateEntry>;
  templateByNameType: Map<string, TemplateEntry>;
  nameToLeaf: Map<string, SystemMapping>;
  leafSet: Set<string>;
  activityLookup: Map<string, boolean>;
  balanceLookup: Map<string, number>;
}

function buildLookups(
  templateEntries: TemplateEntry[],
  systemMappings: SystemMapping[],
  glSummary: GLEntry[],
): Lookups {
  // Template by code
  const templateByCode = new Map<string, TemplateEntry>();
  for (const entry of templateEntries) {
    templateByCode.set(entry.code, entry);
  }

  // Template by normalised name + canonType
  const templateByNameType = new Map<string, TemplateEntry>();
  for (const entry of templateEntries) {
    const key = `${normalise(entry.name)}|${canonicalType(entry.type)}`;
    templateByNameType.set(key, entry);
  }

  // System mappings: name -> leaf, leaf set
  const nameToLeaf = new Map<string, SystemMapping>();
  const leafSet = new Set<string>();
  for (const sm of systemMappings) {
    if (sm.isLeaf) {
      leafSet.add(sm.reportingCode);
      const normName = normalise(sm.name);
      if (normName) {
        nameToLeaf.set(normName, sm);
      }
    }
  }

  // GL summary lookups
  const activityLookup = new Map<string, boolean>();
  const balanceLookup = new Map<string, number>();
  for (const gl of glSummary) {
    const hasActivity = gl.debit !== 0 || gl.credit !== 0 || gl.netMovement !== 0;
    activityLookup.set(gl.accountCode, hasActivity);
    balanceLookup.set(gl.accountCode, gl.closingBalance);
  }

  return { templateByCode, templateByNameType, nameToLeaf, leafSet, activityLookup, balanceLookup };
}

// ---------------------------------------------------------------------------
// MatchContext builder
// ---------------------------------------------------------------------------

function buildMatchContext(
  acct: Account,
  correctedName: string,
  templateName: string,
  ownerKeywords: string[],
  industry: string,
): MatchContext {
  const stripped = stripNoiseSuffixes(correctedName);
  const normName = normalise(stripped);
  const normText = `${normName} ${canonicalType(acct.type)}`;

  return {
    normalisedText: normText,
    normalisedName: normName,
    rawType: acct.type,
    canonType: canonicalType(acct.type),
    templateName,
    ownerKeywords,
    industry,
  };
}

// ---------------------------------------------------------------------------
// Waterfall steps
// ---------------------------------------------------------------------------

interface WaterfallResult {
  code: string;
  source: string;
  mappingName: string;
}

function tryTemplateCodeMatch(
  acct: Account,
  normName: string,
  lookups: Lookups,
): WaterfallResult | null {
  if (!acct.reportCode) return null;

  const entry = lookups.templateByCode.get(acct.reportCode);
  if (!entry) return null;

  // Same root head guard
  const entryRoot = entry.reportingCode.split('.')[0];
  const expectedHead = headFromType(acct.type);
  const expectedRoot = expectedHead.split('.')[0];
  if (entryRoot !== expectedRoot) return null;

  // Name similarity check
  const templateNorm = normalise(entry.name);
  const sim = similarity(normName, templateNorm);
  if (sim < TEMPLATE_SIMILARITY_THRESHOLD) return null;

  return {
    code: entry.reportingCode,
    source: 'TemplateCodeMatch',
    mappingName: entry.reportingName || entry.name,
  };
}

function tryTemplateNameTypeMatch(
  normName: string,
  canonType: string,
  lookups: Lookups,
): WaterfallResult | null {
  const key = `${normName}|${canonType}`;
  const entry = lookups.templateByNameType.get(key);
  if (!entry) return null;

  // Head guard
  const entryRoot = entry.reportingCode.split('.')[0];
  const expectedHead = headFromType(canonType);
  const expectedRoot = expectedHead.split('.')[0];
  if (entryRoot !== expectedRoot) return null;

  return {
    code: entry.reportingCode,
    source: 'TemplateNameMatch',
    mappingName: entry.reportingName || entry.name,
  };
}

function tryRuleEngine(
  rules: Rule[],
  ctx: MatchContext,
): WaterfallResult | null {
  const result = evaluateRules(rules, ctx);
  if (!result) return null;

  return {
    code: result.code,
    source: `Rule: ${result.name}`,
    mappingName: result.name,
  };
}

function tryDirectNameMatch(
  normName: string,
  acct: Account,
  lookups: Lookups,
): WaterfallResult | null {
  const mapping = lookups.nameToLeaf.get(normName);
  if (!mapping) return null;

  // Root head guard
  const mappingRoot = mapping.reportingCode.split('.')[0];
  const expectedHead = headFromType(acct.type);
  const expectedRoot = expectedHead.split('.')[0];
  if (mappingRoot !== expectedRoot) return null;

  return {
    code: mapping.reportingCode,
    source: 'DirectNameMatch',
    mappingName: mapping.name,
  };
}

function tryAlreadyCorrect(
  acct: Account,
  lookups: Lookups,
): WaterfallResult | null {
  if (!acct.reportCode) return null;
  if (!lookups.leafSet.has(acct.reportCode)) return null;

  return {
    code: acct.reportCode,
    source: 'AlreadyCorrect',
    mappingName: acct.reportCode,
  };
}

function tryFuzzyMatch(
  normName: string,
  acct: Account,
  systemMappings: SystemMapping[],
): WaterfallResult | null {
  const expectedHead = headFromType(acct.type);
  const match = fuzzyMatchInHead(normName, expectedHead, systemMappings);
  if (!match) return null;

  return {
    code: match.reportingCode,
    source: 'FuzzyMatch',
    mappingName: match.name,
  };
}

function fallbackParent(acct: Account): WaterfallResult {
  const head = headFromType(acct.type);
  return {
    code: head,
    source: 'FallbackParent',
    mappingName: head,
  };
}

// ---------------------------------------------------------------------------
// runPipeline
// ---------------------------------------------------------------------------

export function runPipeline(input: PipelineInput): MappedAccount[] {
  const {
    accounts,
    rulesData,
    templateEntries,
    systemMappings,
    glSummary,
    industry,
    templateName,
  } = input;

  // 1. Expand dictionary references in rules
  const expandedRules = expandDictionaries(rulesData.rules, rulesData.dictionaries);

  // 2. Build lookups
  const lookups = buildLookups(templateEntries, systemMappings, glSummary);

  // Owner keywords for rule engine context
  const ownerKeywords = rulesData.dictionaries['OWNER_KEYWORDS'] ?? [];

  // 3. Per-account waterfall
  const mapped: MappedAccount[] = [];

  // First pass: build nameToPredicted map for accum dep pairing
  // We need a preliminary waterfall run to populate base asset codes
  const prelimResults: WaterfallResult[] = [];

  for (const acct of accounts) {
    const { corrected } = correctAccountName(acct.name);
    const stripped = stripNoiseSuffixes(corrected);
    const normName = normalise(stripped);
    const ct = canonicalType(acct.type);
    const ctx = buildMatchContext(acct, corrected, templateName, ownerKeywords, industry);

    // Waterfall (first match wins)
    let result: WaterfallResult | null = null;

    result = tryTemplateCodeMatch(acct, normName, lookups);
    if (!result) result = tryTemplateNameTypeMatch(normName, ct, lookups);
    if (!result) result = tryRuleEngine(expandedRules, ctx);
    // Skip accum dep here — done in second pass
    if (!result) result = tryDirectNameMatch(normName, acct, lookups);
    if (!result) result = tryAlreadyCorrect(acct, lookups);
    if (!result) result = tryFuzzyMatch(normName, acct, systemMappings);
    if (!result) result = fallbackParent(acct);

    prelimResults.push(result);
  }

  // Build nameToPredicted for accum dep pairing
  const nameToPredicted = new Map<string, string>();
  for (let i = 0; i < accounts.length; i++) {
    const normName = normalise(stripNoiseSuffixes(correctAccountName(accounts[i].name).corrected));
    if (prelimResults[i].source !== 'FallbackParent') {
      nameToPredicted.set(normName, prelimResults[i].code);
    }
  }

  // Final pass: apply accum dep pairing for fallback accounts
  for (let i = 0; i < accounts.length; i++) {
    const acct = accounts[i];
    const { corrected } = correctAccountName(acct.name);
    const stripped = stripNoiseSuffixes(corrected);
    const normName = normalise(stripped);
    const ct = canonicalType(acct.type);
    const ctx = buildMatchContext(acct, corrected, templateName, ownerKeywords, industry);

    let result: WaterfallResult | null = null;

    // Waterfall with accum dep pairing inserted at correct position
    result = tryTemplateCodeMatch(acct, normName, lookups);
    if (!result) result = tryTemplateNameTypeMatch(normName, ct, lookups);
    if (!result) result = tryRuleEngine(expandedRules, ctx);

    // Accumulated depreciation pairing
    if (!result) {
      const baseKey = extractAccumBaseKey(acct.name);
      if (baseKey) {
        const baseCode = nameToPredicted.get(baseKey);
        if (baseCode) {
          result = {
            code: `${baseCode}.ACC`,
            source: 'AccumDepPairing',
            mappingName: `${baseCode}.ACC`,
          };
        }
      }
    }

    if (!result) result = tryDirectNameMatch(normName, acct, lookups);
    if (!result) result = tryAlreadyCorrect(acct, lookups);
    if (!result) result = tryFuzzyMatch(normName, acct, systemMappings);
    if (!result) result = fallbackParent(acct);

    // 4. Cross-head guard
    if (!CROSS_HEAD_SKIP_SOURCES.has(result.source)) {
      const codeGroup = headGroup(result.code);
      const typeGroup = headGroup(headFromType(acct.type));
      if (codeGroup && typeGroup && codeGroup !== typeGroup) {
        result = fallbackParent(acct);
      }
    }

    const hasActivity = lookups.activityLookup.get(acct.code) ?? false;
    const closingBalance = lookups.balanceLookup.get(acct.code) ?? 0;

    mapped.push({
      ...acct,
      predictedCode: result.code,
      mappingName: result.mappingName,
      source: result.source,
      needsReview: result.source === 'FallbackParent' || result.source === 'FuzzyMatch',
      hasActivity,
      closingBalance,
      correctedName: corrected !== acct.name ? corrected : undefined,
    });
  }

  // 5. Post-processing passes

  // 5a. Context inference
  const contextAccounts = mapped.map((a) => ({
    code: a.code,
    name: a.name,
    predicted: a.predictedCode,
    source: a.source,
  }));
  const balRecord: Record<string, number> = {};
  for (const [key, val] of lookups.balanceLookup) {
    balRecord[key] = val;
  }
  const overriddenIndices = new Set<number>();

  const contextChanges = inferFromContext(contextAccounts, balRecord, overriddenIndices);
  for (const change of contextChanges) {
    mapped[change.index].predictedCode = change.inferred_code;
    mapped[change.index].source = change.reason;
  }

  // 5b. Section inference (only for FallbackParent sources)
  const sectionAccounts = mapped.map((a) => ({
    code: a.code,
    name: a.name,
    predicted: a.predictedCode,
    source: a.source,
  }));
  const sectionChanges = inferSection(sectionAccounts, balRecord, overriddenIndices);
  for (const change of sectionChanges) {
    // Only apply if source is FallbackParent
    if (mapped[change.index].source === 'FallbackParent') {
      mapped[change.index].predictedCode = change.inferred_code;
      mapped[change.index].source = change.reason;
    }
  }

  // 5c. Service-only reclassification
  serviceOnlyReclass(mapped, industry);

  // 5d. Auto industry reclassification
  autoIndustryReclass(mapped, industry);

  // 5e. Type range correction
  typeRangeCorrection(mapped);

  return mapped;
}
