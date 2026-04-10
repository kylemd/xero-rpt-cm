/**
 * Global application state managed via Zustand.
 *
 * Stores pipeline inputs, outputs, rule data, and admin state.
 * githubToken is persisted to/from localStorage.
 */

import { create } from 'zustand';
import type {
  Account,
  MappedAccount,
  RulesData,
  ChartCheckData,
  GroupRelationships,
  TemplateName,
} from '../types';

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

interface AppState {
  // Inputs
  templateName: TemplateName;
  accounts: Account[];
  chartCheckData: ChartCheckData | null;
  groupRelationships: GroupRelationships | null;
  industry: string;

  // Outputs
  mappedAccounts: MappedAccount[];
  isProcessing: boolean;

  // Rules
  rulesData: RulesData | null;
  rulesLoading: boolean;

  // Admin
  githubToken: string | null;

  // Actions
  setTemplateName: (name: TemplateName) => void;
  setAccounts: (accounts: Account[]) => void;
  setChartCheckData: (data: ChartCheckData) => void;
  setGroupRelationships: (data: GroupRelationships) => void;
  setIndustry: (industry: string) => void;
  setMappedAccounts: (accounts: MappedAccount[]) => void;
  setIsProcessing: (processing: boolean) => void;
  setRulesData: (data: RulesData) => void;
  setRulesLoading: (loading: boolean) => void;
  setGithubToken: (token: string | null) => void;
  overrideAccount: (index: number, code: string, reason: string) => void;
  reset: () => void;
}

// ---------------------------------------------------------------------------
// localStorage helpers
// ---------------------------------------------------------------------------

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
    if (token) {
      localStorage.setItem(GITHUB_TOKEN_KEY, token);
    } else {
      localStorage.removeItem(GITHUB_TOKEN_KEY);
    }
  } catch {
    // localStorage unavailable (SSR, private browsing, etc.)
  }
}

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------

const initialState = {
  templateName: 'Company' as TemplateName,
  accounts: [] as Account[],
  chartCheckData: null as ChartCheckData | null,
  groupRelationships: null as GroupRelationships | null,
  industry: '',

  mappedAccounts: [] as MappedAccount[],
  isProcessing: false,

  rulesData: null as RulesData | null,
  rulesLoading: false,

  githubToken: loadGithubToken(),
};

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useAppStore = create<AppState>()((set) => ({
  ...initialState,

  setTemplateName: (name) => set({ templateName: name }),

  setAccounts: (accounts) => set({ accounts }),

  setChartCheckData: (data) => set({ chartCheckData: data }),

  setGroupRelationships: (data) => set({ groupRelationships: data }),

  setIndustry: (industry) => set({ industry }),

  setMappedAccounts: (accounts) => set({ mappedAccounts: accounts }),

  setIsProcessing: (processing) => set({ isProcessing: processing }),

  setRulesData: (data) => set({ rulesData: data }),

  setRulesLoading: (loading) => set({ rulesLoading: loading }),

  setGithubToken: (token) => {
    saveGithubToken(token);
    set({ githubToken: token });
  },

  overrideAccount: (index, code, reason) =>
    set((state) => {
      const updated = [...state.mappedAccounts];
      if (index >= 0 && index < updated.length) {
        updated[index] = {
          ...updated[index],
          overrideCode: code,
          overrideReason: reason,
        };
      }
      return { mappedAccounts: updated };
    }),

  reset: () =>
    set({
      ...initialState,
      // Preserve the github token across resets
      githubToken: loadGithubToken(),
    }),
}));
