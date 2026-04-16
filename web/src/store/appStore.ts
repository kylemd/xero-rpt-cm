/**
 * Global application state managed via Zustand.
 *
 * Stores the parsed Verification Report, pipeline outputs, rule data,
 * and admin state. Decisions are persisted per-client to localStorage
 * via decisionsStorage.
 */

import { create } from 'zustand';
import type {
  MappedAccount,
  RulesData,
  GroupRelationships,
  TemplateName,
  VerificationReportData,
  DecisionMap,
} from '../types';
import {
  deriveClientKey,
  loadDecisions,
  saveDecisions,
  clearDecisions,
} from '../services/decisionsStorage';

const GITHUB_TOKEN_KEY = 'github_token';

function loadGithubToken(): string | null {
  try {
    return localStorage.getItem(GITHUB_TOKEN_KEY);
  } catch {
    return null;
  }
}

function saveGithubToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(GITHUB_TOKEN_KEY, token);
    else localStorage.removeItem(GITHUB_TOKEN_KEY);
  } catch {
    // ignore
  }
}

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

interface AppState {
  // Inputs
  templateName: TemplateName;
  verificationReport: VerificationReportData | null;
  groupRelationships: GroupRelationships | null;
  industry: string;

  // Outputs
  mappedAccounts: MappedAccount[];
  isProcessing: boolean;
  codeTypeMap: Record<string, string>;

  // Rules
  rulesData: RulesData | null;
  rulesLoading: boolean;

  // Decisions (per-client, mirrored into localStorage)
  clientKey: string;
  decisions: DecisionMap;

  // Admin
  githubToken: string | null;

  // Actions
  setTemplateName: (name: TemplateName) => void;
  setVerificationReport: (data: VerificationReportData) => void;
  setGroupRelationships: (data: GroupRelationships) => void;
  setIndustry: (industry: string) => void;
  setMappedAccounts: (accounts: MappedAccount[]) => void;
  setIsProcessing: (processing: boolean) => void;
  setRulesData: (data: RulesData) => void;
  setRulesLoading: (loading: boolean) => void;
  setGithubToken: (token: string | null) => void;
  setCodeTypeMap: (map: Record<string, string>) => void;
  overrideAccount: (index: number, code: string, reason: string) => void;
  approveAccount: (index: number) => void;
  overrideAccountType: (index: number, newType: string) => void;
  clearAllDecisions: () => void;
  reset: () => void;
}

const initialState = {
  templateName: 'Company' as TemplateName,
  verificationReport: null as VerificationReportData | null,
  groupRelationships: null as GroupRelationships | null,
  industry: '',

  mappedAccounts: [] as MappedAccount[],
  isProcessing: false,
  codeTypeMap: {} as Record<string, string>,

  rulesData: null as RulesData | null,
  rulesLoading: false,

  clientKey: '',
  decisions: {} as DecisionMap,

  githubToken: loadGithubToken(),
};

// ---------------------------------------------------------------------------
// Hydration helpers
// ---------------------------------------------------------------------------

function applyDecisions(
  accounts: MappedAccount[],
  decisions: DecisionMap,
): MappedAccount[] {
  return accounts.map((a) => {
    const d = decisions[a.code];
    if (!d) return a;
    return {
      ...a,
      overrideCode: d.overrideCode ?? a.overrideCode,
      overrideReason: d.overrideReason ?? a.overrideReason,
      typeOverride: d.typeOverride ?? a.typeOverride,
      approved: d.approved ?? a.approved,
      auto: d.auto ?? a.auto,
    };
  });
}

function decisionForAccount(a: MappedAccount) {
  const d = {
    overrideCode: a.overrideCode,
    overrideReason: a.overrideReason,
    typeOverride: a.typeOverride,
    approved: a.approved,
    auto: a.auto,
  };
  const cleaned: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(d)) {
    if (v !== undefined) cleaned[k] = v;
  }
  return cleaned;
}

function extractDecisions(accounts: MappedAccount[]): DecisionMap {
  const out: DecisionMap = {};
  for (const a of accounts) {
    const d = decisionForAccount(a);
    if (Object.keys(d).length > 0) out[a.code] = d;
  }
  return out;
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useAppStore = create<AppState>()((set, get) => ({
  ...initialState,

  setTemplateName: (name) => set({ templateName: name }),

  setVerificationReport: (data) => {
    const codes = data.accounts.map((a) => a.code);
    const clientKey = deriveClientKey(data.clientParams.displayName, codes);
    const decisions = loadDecisions(clientKey);
    set({ verificationReport: data, clientKey, decisions });
  },

  setGroupRelationships: (data) => set({ groupRelationships: data }),

  setIndustry: (industry) => set({ industry }),

  setMappedAccounts: (accounts) => {
    const { decisions } = get();
    set({ mappedAccounts: applyDecisions(accounts, decisions) });
  },

  setIsProcessing: (processing) => set({ isProcessing: processing }),

  setRulesData: (data) => set({ rulesData: data }),

  setRulesLoading: (loading) => set({ rulesLoading: loading }),

  setCodeTypeMap: (map) => set({ codeTypeMap: map }),

  setGithubToken: (token) => {
    saveGithubToken(token);
    set({ githubToken: token });
  },

  overrideAccount: (index, code, reason) =>
    set((state) => {
      if (index < 0 || index >= state.mappedAccounts.length) return state;
      const updated = [...state.mappedAccounts];
      updated[index] = { ...updated[index], overrideCode: code, overrideReason: reason };
      const decisions = extractDecisions(updated);
      if (state.clientKey) saveDecisions(state.clientKey, decisions);
      return { mappedAccounts: updated, decisions };
    }),

  approveAccount: (index) =>
    set((state) => {
      if (index < 0 || index >= state.mappedAccounts.length) return state;
      const updated = [...state.mappedAccounts];
      updated[index] = { ...updated[index], approved: true };
      const decisions = extractDecisions(updated);
      if (state.clientKey) saveDecisions(state.clientKey, decisions);
      return { mappedAccounts: updated, decisions };
    }),

  overrideAccountType: (index, newType) =>
    set((state) => {
      if (index < 0 || index >= state.mappedAccounts.length) return state;
      const updated = [...state.mappedAccounts];
      updated[index] = { ...updated[index], typeOverride: newType };
      const decisions = extractDecisions(updated);
      if (state.clientKey) saveDecisions(state.clientKey, decisions);
      return { mappedAccounts: updated, decisions };
    }),

  clearAllDecisions: () =>
    set((state) => {
      if (state.clientKey) clearDecisions(state.clientKey);
      const cleared = state.mappedAccounts.map((a) => ({
        ...a,
        overrideCode: undefined,
        overrideReason: undefined,
        typeOverride: undefined,
        approved: undefined,
        auto: undefined,
      }));
      return { mappedAccounts: cleared, decisions: {} };
    }),

  reset: () =>
    set({
      ...initialState,
      githubToken: loadGithubToken(),
    }),
}));
