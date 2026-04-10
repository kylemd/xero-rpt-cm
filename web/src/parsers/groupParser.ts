/**
 * Group Relationships CSV parser.
 *
 * Parses the CSV export that describes entity group structures and
 * inter-entity relationships.
 *
 * Columns may have `[Client]` or `[Client Relationship]` prefixes which
 * are stripped before matching.
 */

import type { GroupRelationships, GroupEntity, Relationship } from '../types';

// ---------------------------------------------------------------------------
// CSV helpers
// ---------------------------------------------------------------------------

function splitCSVRow(line: string): string[] {
  const fields: string[] = [];
  let i = 0;
  const len = line.length;

  while (i <= len) {
    if (i === len) {
      fields.push('');
      break;
    }
    if (line[i] === '"') {
      i++;
      let field = '';
      while (i < len) {
        if (line[i] === '"') {
          if (i + 1 < len && line[i + 1] === '"') {
            field += '"';
            i += 2;
          } else {
            i++;
            break;
          }
        } else {
          field += line[i];
          i++;
        }
      }
      fields.push(field);
      if (i < len && line[i] === ',') i++;
    } else {
      let field = '';
      while (i < len && line[i] !== ',') {
        field += line[i];
        i++;
      }
      fields.push(field);
      if (i < len && line[i] === ',') {
        i++;
        if (i === len) fields.push('');
      } else {
        break;
      }
    }
  }
  return fields;
}

/**
 * Strip `[Client]` or `[Client Relationship]` prefixes from column names.
 */
function cleanHeader(header: string): string {
  return header
    .replace(/^\[Client(?:\s+Relationship)?\]\s*/i, '')
    .trim()
    .toLowerCase();
}

function findCol(headers: string[], ...names: string[]): number {
  for (const name of names) {
    const idx = headers.indexOf(name.toLowerCase());
    if (idx >= 0) return idx;
  }
  return -1;
}

// ---------------------------------------------------------------------------
// parseGroupRelationshipsCSV
// ---------------------------------------------------------------------------

export function parseGroupRelationshipsCSV(text: string): GroupRelationships {
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length < 2) {
    return { groupName: '', entities: [], relationships: [] };
  }

  const rawHeaders = splitCSVRow(lines[0]);
  const headers = rawHeaders.map(cleanHeader);

  // Entity columns
  const iUuid = findCol(headers, 'uuid', 'client uuid', 'id');
  const iName = findCol(headers, 'name', 'client name', 'display name');
  const iStructure = findCol(headers, 'business structure', 'structure', 'type');

  // Relationship columns
  const iRelType = findCol(headers, 'relationship type', 'type');
  const iRelatedClient = findCol(headers, 'related client', 'related client name', 'related');
  const iCurrent = findCol(headers, 'current', 'is current');
  const iShares = findCol(headers, 'shares', 'number of shares');
  const iPercentage = findCol(headers, 'percentage', 'ownership percentage', '%');

  // Group name column (if present)
  const iGroupName = findCol(headers, 'group name', 'group');

  const entitiesMap = new Map<string, GroupEntity>();
  const relationships: Relationship[] = [];
  let groupName = '';

  for (let row = 1; row < lines.length; row++) {
    const fields = splitCSVRow(lines[row]);

    // Extract group name from first row if available
    if (!groupName && iGroupName >= 0) {
      groupName = (fields[iGroupName] ?? '').trim();
    }

    const uuid = iUuid >= 0 ? (fields[iUuid] ?? '').trim() : '';
    const name = iName >= 0 ? (fields[iName] ?? '').trim() : '';
    const structure = iStructure >= 0 ? (fields[iStructure] ?? '').trim() : '';

    // Build entity
    if (uuid && !entitiesMap.has(uuid)) {
      entitiesMap.set(uuid, {
        uuid,
        name,
        businessStructure: structure,
      });
    }

    // Build relationship
    const relType = iRelType >= 0 ? (fields[iRelType] ?? '').trim() : '';
    const relatedClient = iRelatedClient >= 0 ? (fields[iRelatedClient] ?? '').trim() : '';

    if (uuid && relType) {
      const currentRaw = iCurrent >= 0 ? (fields[iCurrent] ?? '').trim().toLowerCase() : '';
      const shares = iShares >= 0 ? parseFloat(fields[iShares] ?? '') : undefined;
      const percentage = iPercentage >= 0 ? parseFloat(fields[iPercentage] ?? '') : undefined;

      relationships.push({
        entityUuid: uuid,
        entityName: name,
        type: relType,
        relatedClient,
        current: currentRaw !== 'false' && currentRaw !== 'no' && currentRaw !== '0',
        shares: shares !== undefined && !isNaN(shares) ? shares : undefined,
        percentage: percentage !== undefined && !isNaN(percentage) ? percentage : undefined,
      });
    }
  }

  return {
    groupName,
    entities: Array.from(entitiesMap.values()),
    relationships,
  };
}

// ---------------------------------------------------------------------------
// parseGroupRelationshipsFile
// ---------------------------------------------------------------------------

export async function parseGroupRelationshipsFile(file: File): Promise<GroupRelationships> {
  const text = await file.text();
  return parseGroupRelationshipsCSV(text);
}
