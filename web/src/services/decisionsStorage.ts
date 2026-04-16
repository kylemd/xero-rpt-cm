/**
 * Per-client decision persistence backed by localStorage.
 *
 * Storage key: `xrcm:decisions:v1:<clientKey>`
 * clientKey is derived from the entity display name, or from a hash of
 * account codes when no display name is available.
 */

import type { ClientDecisionsFile, DecisionMap } from '../types';

export const STORAGE_KEY_PREFIX = 'xrcm:decisions:v1:';

/**
 * FNV-1a 32-bit hash, base36-encoded. Stable across sessions.
 */
function hashCodes(codes: string[]): string {
  let h = 0x811c9dc5;
  for (const code of codes) {
    for (let i = 0; i < code.length; i++) {
      h ^= code.charCodeAt(i);
      h = Math.imul(h, 0x01000193);
    }
    h ^= 0x7c;
  }
  return (h >>> 0).toString(36);
}

export function deriveClientKey(displayName: string, codes: string[] = []): string {
  const normalized = displayName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
  if (normalized) return normalized;
  return `codes_${hashCodes(codes)}`;
}

export function loadDecisions(clientKey: string): DecisionMap {
  if (!clientKey) return {};
  try {
    const raw = localStorage.getItem(`${STORAGE_KEY_PREFIX}${clientKey}`);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as ClientDecisionsFile;
    if (parsed?.version !== 1 || !parsed.decisions) return {};
    return parsed.decisions;
  } catch {
    return {};
  }
}

export function saveDecisions(clientKey: string, decisions: DecisionMap): void {
  if (!clientKey) return;
  const payload: ClientDecisionsFile = {
    version: 1,
    clientKey,
    savedAt: new Date().toISOString(),
    decisions,
  };
  try {
    localStorage.setItem(
      `${STORAGE_KEY_PREFIX}${clientKey}`,
      JSON.stringify(payload),
    );
  } catch {
    // Quota exceeded or localStorage unavailable — silently drop.
  }
}

export function clearDecisions(clientKey: string): void {
  if (!clientKey) return;
  try {
    localStorage.removeItem(`${STORAGE_KEY_PREFIX}${clientKey}`);
  } catch {
    // noop
  }
}
