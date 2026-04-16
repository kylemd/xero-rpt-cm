// @vitest-environment jsdom

import { describe, it, expect, beforeEach } from 'vitest';
import {
  deriveClientKey,
  loadDecisions,
  saveDecisions,
  clearDecisions,
  STORAGE_KEY_PREFIX,
} from '../decisionsStorage';
import type { DecisionMap } from '../../types';

// jsdom provides localStorage; clear it between tests
beforeEach(() => {
  localStorage.clear();
});

describe('deriveClientKey', () => {
  it('normalises display name to lowercase alphanumeric with underscores', () => {
    expect(deriveClientKey('Demo Company (AU)')).toBe('demo_company_au');
    expect(deriveClientKey('Smith & Co. Pty Ltd')).toBe('smith_co_pty_ltd');
  });

  it('returns a code-hash fallback when name is empty', () => {
    const key = deriveClientKey('', ['100', '200', '300']);
    expect(key).toMatch(/^codes_[a-z0-9]+$/);
    // Deterministic: same codes give the same key
    expect(deriveClientKey('', ['100', '200', '300'])).toBe(key);
  });

  it('returns different keys for different code sets', () => {
    const a = deriveClientKey('', ['100']);
    const b = deriveClientKey('', ['200']);
    expect(a).not.toBe(b);
  });

  it('produces the same key regardless of code ordering', () => {
    const a = deriveClientKey('', ['300', '100', '200']);
    const b = deriveClientKey('', ['100', '200', '300']);
    expect(a).toBe(b);
  });

  it('preserves Unicode letters in display names', () => {
    const key = deriveClientKey('株式会社');
    expect(key).toBe('株式会社');
  });

  it('produces distinct keys for distinct non-ASCII names', () => {
    // Names that previously all collapsed to empty → identical fallback
    expect(deriveClientKey('###', ['1'])).not.toBe(deriveClientKey('株式会社', ['1']));
    expect(deriveClientKey('🎉🎉🎉', ['1'])).not.toBe(deriveClientKey('###', ['1']));
  });
});

describe('saveDecisions / loadDecisions / clearDecisions', () => {
  it('round-trips a decision map for a given client', () => {
    const decisions: DecisionMap = {
      '404': { approved: true, auto: true },
      '200': { overrideCode: 'REV.TRA.GOO', overrideReason: 'user correction' },
    };
    saveDecisions('demo_company', decisions);
    expect(loadDecisions('demo_company')).toEqual(decisions);
  });

  it('returns an empty map when no data stored for the client', () => {
    expect(loadDecisions('unknown_client')).toEqual({});
  });

  it('scopes storage per client', () => {
    saveDecisions('client_a', { '100': { approved: true } });
    saveDecisions('client_b', { '100': { overrideCode: 'EXP' } });
    expect(loadDecisions('client_a')).toEqual({ '100': { approved: true } });
    expect(loadDecisions('client_b')).toEqual({ '100': { overrideCode: 'EXP' } });
  });

  it('clearDecisions removes only the target client', () => {
    saveDecisions('client_a', { '100': { approved: true } });
    saveDecisions('client_b', { '100': { overrideCode: 'EXP' } });
    clearDecisions('client_a');
    expect(loadDecisions('client_a')).toEqual({});
    expect(loadDecisions('client_b')).toEqual({ '100': { overrideCode: 'EXP' } });
  });

  it('writes under the versioned namespace', () => {
    saveDecisions('demo', { '100': { approved: true } });
    const raw = localStorage.getItem(`${STORAGE_KEY_PREFIX}demo`);
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw!);
    expect(parsed.version).toBe(1);
    expect(parsed.clientKey).toBe('demo');
    expect(parsed.decisions['100'].approved).toBe(true);
  });

  it('ignores malformed stored data', () => {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}broken`, '{not json');
    expect(loadDecisions('broken')).toEqual({});
  });
});
