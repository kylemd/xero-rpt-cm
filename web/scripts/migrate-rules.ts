/**
 * migrate-rules.ts — Extracts Rule instances and keyword dictionaries
 * from rules.py into a JSON file for the web client.
 *
 * Strategy:
 *   1. Read rules.py as text
 *   2. Extract dictionary constants (lists of strings)
 *   3. Extract INDUSTRY_ALIASES dict
 *   4. Extract Rule() instances with all fields
 *   5. Write to web/data/rules.json
 *
 * Run: npx tsx scripts/migrate-rules.ts
 */

import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..', '..');
const SRC = path.join(ROOT, 'rules.py');
const OUT = path.join(import.meta.dirname, '..', 'data', 'rules.json');

const src = fs.readFileSync(SRC, 'utf-8');

// ---------------------------------------------------------------------------
// 1. Extract dictionary constants (flat lists of strings)
// ---------------------------------------------------------------------------

const DICT_NAMES = [
  'OWNER_KEYWORDS',
  'CREDIT_CARD_NAMES',
  'AUSTRALIAN_BANKS',
  'VEHICLE_MAKES',
  'AUSTRALIAN_LENDERS',
  'VEHICLE_TOKENS',
  'VEHICLE_EXPENSE_TOKENS',
  'COMMON_FIRST_NAMES',
  'PAYROLL_KW',
];

/**
 * Extract all quoted strings from the bracket-delimited list following a
 * variable assignment like `FOO = [...]`.
 */
function extractList(varName: string): string[] {
  // Match the assignment and capture everything within the brackets.
  // The list may span many lines.
  const re = new RegExp(`^${varName}\\s*=\\s*\\[`, 'm');
  const match = re.exec(src);
  if (!match) {
    console.warn(`  WARNING: could not find ${varName}`);
    return [];
  }
  // Find the matching closing bracket
  let depth = 1;
  let i = match.index + match[0].length;
  const start = i;
  while (i < src.length && depth > 0) {
    if (src[i] === '[') depth++;
    else if (src[i] === ']') depth--;
    i++;
  }
  const body = src.slice(start, i - 1);
  // Pull out all quoted strings (single or double)
  const strings: string[] = [];
  const strRe = /(?:"([^"]*?)"|'([^']*?)')/g;
  let m: RegExpExecArray | null;
  while ((m = strRe.exec(body)) !== null) {
    strings.push(m[1] ?? m[2]);
  }
  return strings;
}

const dictionaries: Record<string, string[]> = {};
for (const name of DICT_NAMES) {
  dictionaries[name] = extractList(name);
  console.log(`  ${name}: ${dictionaries[name].length} entries`);
}

// Also add BANK_NAMES as an alias
dictionaries['BANK_NAMES'] = dictionaries['AUSTRALIAN_BANKS'];
console.log(`  BANK_NAMES: alias of AUSTRALIAN_BANKS (${dictionaries['BANK_NAMES'].length} entries)`);

// ---------------------------------------------------------------------------
// 2. Extract INDUSTRY_ALIASES dict
// ---------------------------------------------------------------------------

function extractIndustryAliases(): Record<string, string> {
  const re = /INDUSTRY_ALIASES\s*(?::\s*dict\[str,\s*str\])?\s*=\s*\{/m;
  const match = re.exec(src);
  if (!match) {
    console.warn('  WARNING: could not find INDUSTRY_ALIASES');
    return {};
  }
  let depth = 1;
  let i = match.index + match[0].length;
  const start = i;
  while (i < src.length && depth > 0) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') depth--;
    i++;
  }
  const body = src.slice(start, i - 1);
  const result: Record<string, string> = {};
  const pairRe = /(?:"([^"]*?)"|'([^']*?)')\s*:\s*(?:"([^"]*?)"|'([^']*?)')/g;
  let m: RegExpExecArray | null;
  while ((m = pairRe.exec(body)) !== null) {
    const key = m[1] ?? m[2];
    const val = m[3] ?? m[4];
    result[key] = val;
  }
  return result;
}

const industryAliases = extractIndustryAliases();
console.log(`  INDUSTRY_ALIASES: ${Object.keys(industryAliases).length} entries`);

// ---------------------------------------------------------------------------
// 3. Extract Rule() instances
// ---------------------------------------------------------------------------

interface RuleData {
  name: string;
  code: string;
  priority: number;
  keywords: string[];
  keywordsAll: string[];
  keywordsExclude: string[];
  rawTypes: string[];
  canonTypes: string[];
  typeExclude: string[];
  template?: string;
  ownerContext?: boolean;
  nameOnly?: boolean;
  industries?: string[];
  notes?: string;
}

/**
 * Extract all quoted strings from a Python list literal like ["a", "b"].
 * If the value is a bare variable name (e.g. AUSTRALIAN_BANKS), return "$AUSTRALIAN_BANKS".
 * If it contains spread operators (e.g. [*AUSTRALIAN_BANKS, "extra"]), expand them.
 */
function parseListField(value: string): string[] {
  const trimmed = value.trim();

  // Bare variable reference (no brackets)
  if (!trimmed.startsWith('[') && !trimmed.startsWith('{')) {
    // Check if it's a known dictionary name
    const varName = trimmed.replace(/,$/, '').trim();
    if (dictionaries[varName]) {
      return [`$${varName}`];
    }
    return [`$${varName}`];
  }

  // Set literal: {"a", "b"}
  const body = trimmed.startsWith('{')
    ? trimmed.slice(1, -1)
    : trimmed.slice(1, -1);

  const result: string[] = [];

  // Handle spread operators like *AUSTRALIAN_BANKS
  const spreadRe = /\*([A-Z_]+)/g;
  let sm: RegExpExecArray | null;
  while ((sm = spreadRe.exec(body)) !== null) {
    const varName = sm[1];
    if (dictionaries[varName]) {
      result.push(`$${varName}`);
    } else {
      result.push(`$${varName}`);
    }
  }

  // Handle quoted strings
  const strRe = /(?:"([^"]*?)"|'([^']*?)')/g;
  let m: RegExpExecArray | null;
  while ((m = strRe.exec(body)) !== null) {
    result.push(m[1] ?? m[2]);
  }

  return result;
}

/**
 * Parse a Python set literal like {"a", "b"} into a string array.
 */
function parseSetField(value: string): string[] {
  const trimmed = value.trim();
  if (!trimmed.startsWith('{')) return [];
  const body = trimmed.slice(1, -1);
  const result: string[] = [];
  const strRe = /(?:"([^"]*?)"|'([^']*?)')/g;
  let m: RegExpExecArray | null;
  while ((m = strRe.exec(body)) !== null) {
    result.push(m[1] ?? m[2]);
  }
  return result;
}

/**
 * Find all Rule(...) calls in the source and extract their fields.
 */
function extractRules(): RuleData[] {
  const rules: RuleData[] = [];

  // Find each "Rule(" and then find the matching closing paren
  const ruleRe = /Rule\s*\(/g;
  let ruleMatch: RegExpExecArray | null;

  while ((ruleMatch = ruleRe.exec(src)) !== null) {
    // Find matching closing paren
    let depth = 1;
    let i = ruleMatch.index + ruleMatch[0].length;
    const start = i;
    while (i < src.length && depth > 0) {
      if (src[i] === '(') depth++;
      else if (src[i] === ')') depth--;
      else if (src[i] === '"' || src[i] === "'") {
        // Skip strings (including multi-line string concatenation)
        const quote = src[i];
        i++;
        while (i < src.length && src[i] !== quote) {
          if (src[i] === '\\') i++; // skip escape
          i++;
        }
      } else if (src[i] === '[') {
        // Skip list literals
        let listDepth = 1;
        i++;
        while (i < src.length && listDepth > 0) {
          if (src[i] === '[') listDepth++;
          else if (src[i] === ']') listDepth--;
          else if (src[i] === '"' || src[i] === "'") {
            const q = src[i];
            i++;
            while (i < src.length && src[i] !== q) {
              if (src[i] === '\\') i++;
              i++;
            }
          }
          i++;
        }
        continue;
      } else if (src[i] === '{') {
        // Skip set/dict literals
        let setDepth = 1;
        i++;
        while (i < src.length && setDepth > 0) {
          if (src[i] === '{') setDepth++;
          else if (src[i] === '}') setDepth--;
          else if (src[i] === '"' || src[i] === "'") {
            const q = src[i];
            i++;
            while (i < src.length && src[i] !== q) {
              if (src[i] === '\\') i++;
              i++;
            }
          }
          i++;
        }
        continue;
      }
      i++;
    }
    const body = src.slice(start, i - 1);

    // Parse individual fields from the Rule body
    const rule: RuleData = {
      name: '',
      code: '',
      priority: 0,
      keywords: [],
      keywordsAll: [],
      keywordsExclude: [],
      rawTypes: [],
      canonTypes: [],
      typeExclude: [],
    };

    // Extract simple string fields: name=, code=, template=, notes=
    const nameMatch = body.match(/\bname\s*=\s*"([^"]*)"/);
    if (nameMatch) rule.name = nameMatch[1];

    const codeMatch = body.match(/\bcode\s*=\s*"([^"]*)"/);
    if (codeMatch) rule.code = codeMatch[1];

    const priorityMatch = body.match(/\bpriority\s*=\s*(\d+)/);
    if (priorityMatch) rule.priority = parseInt(priorityMatch[1], 10);

    const templateMatch = body.match(/\btemplate\s*=\s*"([^"]*)"/);
    if (templateMatch) rule.template = templateMatch[1];

    // Extract boolean fields
    if (/\bowner_context\s*=\s*True/.test(body)) rule.ownerContext = true;
    if (/\bname_only\s*=\s*True/.test(body)) rule.nameOnly = true;

    // Extract notes (may be multi-line with string concatenation)
    const notesMatch = body.match(/\bnotes\s*=\s*"((?:[^"\\]|\\.)*)"/);
    if (notesMatch) rule.notes = notesMatch[1].replace(/\\"/g, '"');

    // Extract list/set fields
    rule.keywords = extractFieldValue(body, 'keywords');
    rule.keywordsAll = extractFieldValue(body, 'keywords_all');
    rule.keywordsExclude = extractFieldValue(body, 'keywords_exclude');
    rule.rawTypes = extractFieldValue(body, 'raw_types');
    rule.canonTypes = extractFieldValue(body, 'canon_types');
    rule.typeExclude = extractFieldValue(body, 'type_exclude');

    const industries = extractFieldValue(body, 'industries');
    if (industries.length > 0) rule.industries = industries;

    if (rule.name) {
      rules.push(rule);
    }
  }

  return rules;
}

/**
 * Extract the value of a field like `keywords=[...]` or `raw_types={...}`
 * from a Rule body string.
 */
function extractFieldValue(body: string, fieldName: string): string[] {
  // Match field=VALUE where VALUE can be a list [...], set {...}, or bare identifier
  const re = new RegExp(`\\b${fieldName}\\s*=\\s*`);
  const m = re.exec(body);
  if (!m) return [];

  let i = m.index + m[0].length;

  // Determine value type
  if (body[i] === '[') {
    // List literal - find matching bracket
    let depth = 1;
    let j = i + 1;
    while (j < body.length && depth > 0) {
      if (body[j] === '[') depth++;
      else if (body[j] === ']') depth--;
      else if (body[j] === '"' || body[j] === "'") {
        const q = body[j];
        j++;
        while (j < body.length && body[j] !== q) {
          if (body[j] === '\\') j++;
          j++;
        }
      }
      j++;
    }
    return parseListField(body.slice(i, j));
  } else if (body[i] === '{') {
    // Set literal - find matching brace
    let depth = 1;
    let j = i + 1;
    while (j < body.length && depth > 0) {
      if (body[j] === '{') depth++;
      else if (body[j] === '}') depth--;
      else if (body[j] === '"' || body[j] === "'") {
        const q = body[j];
        j++;
        while (j < body.length && body[j] !== q) {
          if (body[j] === '\\') j++;
          j++;
        }
      }
      j++;
    }
    return parseSetField(body.slice(i, j));
  } else {
    // Bare variable name
    const varMatch = body.slice(i).match(/^([A-Z_][A-Z_0-9]*)/);
    if (varMatch) {
      const varName = varMatch[1];
      return [`$${varName}`];
    }
    return [];
  }
}

// ---------------------------------------------------------------------------
// Run
// ---------------------------------------------------------------------------

console.log('\nMigrate rules: extracting from rules.py...');
const rules = extractRules();
console.log(`  Extracted ${rules.length} rules`);

const output = {
  version: 1,
  updatedAt: new Date().toISOString(),
  dictionaries,
  industryAliases,
  rules,
};

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify(output, null, 2));
console.log(`  Written to ${path.relative(ROOT, OUT)}`);
console.log('Rules migration complete.');
