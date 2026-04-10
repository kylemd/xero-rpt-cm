/**
 * Prebuild script — converts CSV reference data to JSON at build time.
 *
 * Reads from the project root:
 *   SystemFiles/SystemMappings.csv      -> web/src/data/systemMappings.json
 *   SystemFiles/Account_Types_Head.csv  -> web/src/data/accountTypesHead.json
 *   ChartOfAccounts/*.csv               -> web/src/data/templates/{name}.json
 *
 * Run: npm run prebuild
 */

import fs from 'node:fs';
import path from 'node:path';

// ---------------------------------------------------------------------------
// CSV parser (handles quoted fields with embedded commas & newlines)
// ---------------------------------------------------------------------------

function parseCSV(text: string): string[][] {
  const rows: string[][] = [];
  let i = 0;
  const len = text.length;

  while (i < len) {
    const row: string[] = [];
    while (i < len) {
      if (text[i] === '"') {
        // Quoted field
        i++; // skip opening quote
        let field = '';
        while (i < len) {
          if (text[i] === '"') {
            if (i + 1 < len && text[i + 1] === '"') {
              // Escaped quote
              field += '"';
              i += 2;
            } else {
              // End of quoted field
              i++; // skip closing quote
              break;
            }
          } else {
            field += text[i];
            i++;
          }
        }
        row.push(field);
        // Skip comma or end-of-line
        if (i < len && text[i] === ',') {
          i++;
        } else if (i < len && (text[i] === '\r' || text[i] === '\n')) {
          if (text[i] === '\r' && i + 1 < len && text[i + 1] === '\n') i += 2;
          else i++;
          break;
        }
      } else if (text[i] === '\r' || text[i] === '\n') {
        // End of row (could be empty trailing field)
        if (text[i] === '\r' && i + 1 < len && text[i + 1] === '\n') i += 2;
        else i++;
        break;
      } else {
        // Unquoted field
        let field = '';
        while (i < len && text[i] !== ',' && text[i] !== '\r' && text[i] !== '\n') {
          field += text[i];
          i++;
        }
        row.push(field);
        if (i < len && text[i] === ',') {
          i++;
        } else if (i < len && (text[i] === '\r' || text[i] === '\n')) {
          if (text[i] === '\r' && i + 1 < len && text[i + 1] === '\n') i += 2;
          else i++;
          break;
        }
      }
    }
    if (row.length > 0) {
      rows.push(row);
    }
  }
  return rows;
}

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

const ROOT = path.resolve(import.meta.dirname, '..', '..');
const OUT = path.resolve(import.meta.dirname, '..', 'src', 'data');

// ---------------------------------------------------------------------------
// 1. SystemMappings.csv
// ---------------------------------------------------------------------------

function buildSystemMappings(): void {
  const csvPath = path.join(ROOT, 'SystemFiles', 'SystemMappings.csv');
  const text = fs.readFileSync(csvPath, 'utf-8');
  const rows = parseCSV(text);
  const header = rows[0];

  const colIdx = (name: string) => header.findIndex((h) => h.trim() === name);
  const iCode = colIdx('Reporting Code');
  const iName = colIdx('Name');
  const iLeaf = colIdx('IsLeaf');

  const data = rows.slice(1)
    .filter((r) => r.length > Math.max(iCode, iName, iLeaf))
    .map((r) => ({
      reportingCode: r[iCode].trim(),
      name: r[iName].trim(),
      isLeaf: r[iLeaf].trim().toUpperCase() === 'TRUE',
    }));

  const outPath = path.join(OUT, 'systemMappings.json');
  fs.writeFileSync(outPath, JSON.stringify(data, null, 2));
  console.log(`  systemMappings.json: ${data.length} entries`);
}

// ---------------------------------------------------------------------------
// 2. Account_Types_Head.csv
// ---------------------------------------------------------------------------

function buildAccountTypesHead(): void {
  const csvPath = path.join(ROOT, 'SystemFiles', 'Account_Types_Head.csv');
  const text = fs.readFileSync(csvPath, 'utf-8');
  const rows = parseCSV(text);
  const header = rows[0];

  const colIdx = (name: string) => header.findIndex((h) => h.trim() === name);
  const iType = colIdx('Account Type');
  const iHead = colIdx('Expected Head Reporting Code');

  const map: Record<string, string> = {};
  for (const row of rows.slice(1)) {
    if (row.length > Math.max(iType, iHead)) {
      const type = row[iType].trim();
      const head = row[iHead].trim();
      if (type && head) map[type] = head;
    }
  }

  const outPath = path.join(OUT, 'accountTypesHead.json');
  fs.writeFileSync(outPath, JSON.stringify(map, null, 2));
  console.log(`  accountTypesHead.json: ${Object.keys(map).length} types`);
}

// ---------------------------------------------------------------------------
// 3. ChartOfAccounts/*.csv
// ---------------------------------------------------------------------------

const TEMPLATE_NAMES = ['Company', 'Trust', 'Partnership', 'SoleTrader', 'XeroHandi'];

function buildTemplates(): void {
  const templatesDir = path.join(OUT, 'templates');
  fs.mkdirSync(templatesDir, { recursive: true });

  for (const name of TEMPLATE_NAMES) {
    const csvPath = path.join(ROOT, 'ChartOfAccounts', `${name}.csv`);
    const text = fs.readFileSync(csvPath, 'utf-8');
    const rows = parseCSV(text);
    const header = rows[0];

    const colIdx = (h: string) => header.findIndex((c) => c.trim() === h);
    const iCode = colIdx('Code');
    const iReportCode = colIdx('Reporting Code');
    const iName = colIdx('Name');
    const iType = colIdx('Type');
    const iReportName = colIdx('Reporting Name');

    const data = rows.slice(1)
      .filter((r) => r.length > Math.max(iCode, iReportCode, iName, iType))
      .map((r) => ({
        code: r[iCode].trim(),
        reportingCode: r[iReportCode].trim(),
        name: r[iName].trim(),
        type: r[iType].trim(),
        reportingName: iReportName >= 0 && r.length > iReportName ? r[iReportName].trim() : '',
      }));

    const outPath = path.join(templatesDir, `${name}.json`);
    fs.writeFileSync(outPath, JSON.stringify(data, null, 2));
    console.log(`  templates/${name}.json: ${data.length} entries`);
  }
}

// ---------------------------------------------------------------------------
// Run
// ---------------------------------------------------------------------------

console.log('Prebuild: converting CSV reference data to JSON...');
fs.mkdirSync(OUT, { recursive: true });
buildSystemMappings();
buildAccountTypesHead();
buildTemplates();
console.log('Prebuild complete.');
