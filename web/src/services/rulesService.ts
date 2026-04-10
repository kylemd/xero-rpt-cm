/**
 * Rules service — fetch and save rules data via GitHub API.
 *
 * fetchRules() caches in localStorage with a 5-minute TTL.
 * saveRules() uses Octokit to commit updated rules to the repository.
 */

import { Octokit } from '@octokit/rest';
import type { RulesData } from '../types';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CACHE_KEY = 'rules_cache';
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

const RAW_URL =
  'https://raw.githubusercontent.com/kylemd/xero-report-code-mapper/main/web/data/rules.json';

const REPO_OWNER = 'kylemd';
const REPO_NAME = 'xero-report-code-mapper';
const FILE_PATH = 'web/data/rules.json';

// ---------------------------------------------------------------------------
// Cache helpers
// ---------------------------------------------------------------------------

interface CacheEntry {
  timestamp: number;
  data: RulesData;
}

function readCache(): CacheEntry | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as CacheEntry;
  } catch {
    return null;
  }
}

function writeCache(data: RulesData): void {
  try {
    const entry: CacheEntry = { timestamp: Date.now(), data };
    localStorage.setItem(CACHE_KEY, JSON.stringify(entry));
  } catch {
    // localStorage unavailable
  }
}

// ---------------------------------------------------------------------------
// Bundled baseline (inline fallback)
// ---------------------------------------------------------------------------

/**
 * Lazily import the bundled baseline rules.json from the data directory.
 * This serves as the last-resort fallback when both network and cache fail.
 */
async function loadBundledBaseline(): Promise<RulesData> {
  const mod = await import('../../data/rules.json');
  return mod.default as unknown as RulesData;
}

// ---------------------------------------------------------------------------
// fetchRules
// ---------------------------------------------------------------------------

/**
 * Fetch rules data with a caching strategy:
 * 1. Return localStorage cache if fresh (< 5 min old)
 * 2. Fetch from GitHub raw URL
 * 3. On fetch error: return stale cache if available
 * 4. Final fallback: return bundled baseline
 */
export async function fetchRules(): Promise<RulesData> {
  // 1. Check fresh cache
  const cached = readCache();
  if (cached && Date.now() - cached.timestamp < CACHE_TTL_MS) {
    return cached.data;
  }

  // 2. Fetch from GitHub
  try {
    const response = await fetch(RAW_URL);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data: RulesData = await response.json();
    writeCache(data);
    return data;
  } catch {
    // 3. Fall back to stale cache
    if (cached) {
      return cached.data;
    }

    // 4. Fall back to bundled baseline
    return loadBundledBaseline();
  }
}

// ---------------------------------------------------------------------------
// saveRules
// ---------------------------------------------------------------------------

/**
 * Save updated rules data to the GitHub repository.
 *
 * Uses Octokit to:
 * 1. GET the current file SHA
 * 2. PUT updated content (base64-encoded)
 * 3. Update localStorage cache
 */
export async function saveRules(token: string, rulesData: RulesData): Promise<void> {
  const octokit = new Octokit({ auth: token });

  // 1. Get current file SHA
  const { data: fileData } = await octokit.repos.getContent({
    owner: REPO_OWNER,
    repo: REPO_NAME,
    path: FILE_PATH,
  });

  if (Array.isArray(fileData) || fileData.type !== 'file') {
    throw new Error('Expected a file but got a directory');
  }

  const sha = fileData.sha;

  // 2. Encode content as base64
  const jsonContent = JSON.stringify(rulesData, null, 2);
  const content = btoa(unescape(encodeURIComponent(jsonContent)));

  // 3. PUT updated file
  await octokit.repos.createOrUpdateFileContents({
    owner: REPO_OWNER,
    repo: REPO_NAME,
    path: FILE_PATH,
    message: `chore: update rules.json via web UI`,
    content,
    sha,
  });

  // 4. Update local cache
  writeCache(rulesData);
}
