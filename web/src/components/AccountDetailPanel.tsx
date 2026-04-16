/**
 * Slide-out detail panel for a selected account.
 *
 * Shows account info, GL activity, depreciation links, group context,
 * and an override section for manually assigning a different reporting code.
 */

import { useState, useMemo, useCallback } from 'react';
import { useAppStore } from '../store/appStore';
import systemMappings from '../data/systemMappings.json';
import type { SystemMapping } from '../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const allMappings = systemMappings as SystemMapping[];
const leafMappings = allMappings.filter((m) => m.isLeaf);

/** Head groups in display order. */
const HEAD_ORDER = ['ASS', 'LIA', 'EQU', 'REV', 'EXP'];
const HEAD_LABELS: Record<string, string> = {
  ASS: 'Assets (ASS)',
  LIA: 'Liabilities (LIA)',
  EQU: 'Equity (EQU)',
  REV: 'Revenue (REV)',
  EXP: 'Expenses (EXP)',
};

/**
 * Extract the head group (first segment) from a reporting code.
 */
function headFromCode(code: string): string {
  return code.split('.')[0];
}

/** Group leaf mappings by head. */
const leafByHead: Record<string, SystemMapping[]> = {};
for (const m of leafMappings) {
  const head = headFromCode(m.reportingCode);
  if (!leafByHead[head]) leafByHead[head] = [];
  leafByHead[head].push(m);
}

const codeToDescription: Record<string, string> = {};
for (const m of allMappings) {
  codeToDescription[m.reportingCode] = m.name;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface AccountDetailPanelProps {
  selectedIndex: number;
  onClose: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AccountDetailPanel({
  selectedIndex,
  onClose,
}: AccountDetailPanelProps) {
  const mappedAccounts = useAppStore((s) => s.mappedAccounts);
  const verificationReport = useAppStore((s) => s.verificationReport);
  const groupRelationships = useAppStore((s) => s.groupRelationships);
  const overrideAccount = useAppStore((s) => s.overrideAccount);

  const [overrideCode, setOverrideCode] = useState('');
  const [overrideReason, setOverrideReason] = useState('');
  const [codeSearch, setCodeSearch] = useState('');

  const account = mappedAccounts[selectedIndex];
  if (!account) return null;

  // GL entry for this account
  const glEntry = verificationReport?.glSummary.find(
    (gl) => gl.accountCode === account.code,
  );

  // Depreciation links
  const depAssets = verificationReport?.depSchedule.filter(
    (d) => d.costAccount === account.code,
  );

  // Group relationships matching this entity
  const entityRelationships = useMemo(() => {
    if (!groupRelationships || !verificationReport) return [];
    const entityName = verificationReport.clientParams.displayName;
    if (!entityName) return [];
    return groupRelationships.relationships.filter(
      (r) =>
        r.entityName.toLowerCase().includes(entityName.toLowerCase()) ||
        r.relatedClient.toLowerCase().includes(entityName.toLowerCase()),
    );
  }, [groupRelationships, verificationReport]);

  // All leaf codes grouped by head, filtered by search
  const groupedCodes = useMemo(() => {
    const search = codeSearch.toLowerCase();
    const groups: { head: string; label: string; codes: SystemMapping[] }[] = [];
    for (const head of HEAD_ORDER) {
      const mappings = leafByHead[head] ?? [];
      const filtered = search
        ? mappings.filter(
            (m) =>
              m.reportingCode.toLowerCase().includes(search) ||
              m.name.toLowerCase().includes(search),
          )
        : mappings;
      if (filtered.length > 0) {
        groups.push({
          head,
          label: HEAD_LABELS[head] ?? head,
          codes: filtered,
        });
      }
    }
    return groups;
  }, [codeSearch]);

  const handleApplyOverride = useCallback(() => {
    if (!overrideCode) return;
    overrideAccount(selectedIndex, overrideCode, overrideReason);
    setOverrideCode('');
    setOverrideReason('');
    setCodeSearch('');
  }, [overrideCode, overrideReason, selectedIndex, overrideAccount]);

  const displayCode = account.overrideCode ?? account.predictedCode;

  return (
    <div className="w-96 shrink-0 border-l border-gray-200 bg-white overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <h3 className="text-sm font-semibold text-gray-700">Account Detail</h3>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 text-lg leading-none"
        >
          {'\u2715'}
        </button>
      </div>

      <div className="p-4 space-y-4">
        {/* Account info */}
        <section>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Account
          </h4>
          <dl className="space-y-1 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Code</dt>
              <dd className="text-gray-800 font-mono">{account.code}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Name</dt>
              <dd className="text-gray-800 font-medium">{account.name}</dd>
            </div>
            {account.correctedName && (
              <div>
                <dt className="text-gray-500">Corrected Name</dt>
                <dd className="text-gray-800">{account.correctedName}</dd>
              </div>
            )}
            <div className="flex justify-between">
              <dt className="text-gray-500">Type</dt>
              <dd className="text-gray-800">{account.type}</dd>
            </div>
          </dl>
        </section>

        {/* Mapping result */}
        <section>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Mapping
          </h4>
          <dl className="space-y-1 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Predicted Code</dt>
              <dd className="text-gray-800 font-mono">
                {account.predictedCode}
              </dd>
            </div>
            {account.overrideCode && (
              <div className="flex justify-between">
                <dt className="text-gray-500">Override Code</dt>
                <dd className="text-blue-600 font-mono font-medium">
                  {account.overrideCode}
                </dd>
              </div>
            )}
            <div className="flex justify-between">
              <dt className="text-gray-500">Final Code</dt>
              <dd className="font-mono font-medium text-gray-900">
                {displayCode}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Source</dt>
              <dd className="text-gray-600">{account.source}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Mapping Name</dt>
              <dd className="text-gray-600">{account.mappingName}</dd>
            </div>
          </dl>
        </section>

        {/* GL Activity */}
        {glEntry && (
          <section>
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              GL Activity
            </h4>
            <dl className="space-y-1 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Opening Balance</dt>
                <dd className="text-gray-800 font-mono">
                  {glEntry.openingBalance.toLocaleString('en-AU', {
                    minimumFractionDigits: 2,
                  })}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Debits</dt>
                <dd className="text-gray-800 font-mono">
                  {glEntry.debit.toLocaleString('en-AU', {
                    minimumFractionDigits: 2,
                  })}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Credits</dt>
                <dd className="text-gray-800 font-mono">
                  {glEntry.credit.toLocaleString('en-AU', {
                    minimumFractionDigits: 2,
                  })}
                </dd>
              </div>
              <div className="flex justify-between border-t border-gray-100 pt-1">
                <dt className="text-gray-500 font-medium">Closing Balance</dt>
                <dd className="text-gray-900 font-mono font-medium">
                  {glEntry.closingBalance.toLocaleString('en-AU', {
                    minimumFractionDigits: 2,
                  })}
                </dd>
              </div>
            </dl>
          </section>
        )}

        {/* Depreciation links */}
        {depAssets && depAssets.length > 0 && (
          <section>
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Depreciation Schedule
            </h4>
            <div className="space-y-2">
              {depAssets.map((asset, i) => (
                <div
                  key={i}
                  className="p-2 bg-gray-50 rounded text-xs space-y-0.5"
                >
                  <div className="font-medium text-gray-700">{asset.name}</div>
                  <div className="text-gray-500">
                    Type: {asset.assetType} | Cost:{' '}
                    {asset.cost.toLocaleString('en-AU', {
                      minimumFractionDigits: 2,
                    })}
                  </div>
                  <div className="text-gray-500">
                    Closing Value:{' '}
                    {asset.closingValue.toLocaleString('en-AU', {
                      minimumFractionDigits: 2,
                    })}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Group relationships */}
        {entityRelationships.length > 0 && (
          <section>
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Group Relationships
            </h4>
            <div className="space-y-1">
              {entityRelationships.map((rel, i) => (
                <div key={i} className="p-2 bg-gray-50 rounded text-xs">
                  <span className="text-gray-600">{rel.type}:</span>{' '}
                  <span className="text-gray-800 font-medium">
                    {rel.relatedClient}
                  </span>
                  {rel.percentage !== undefined && (
                    <span className="text-gray-500 ml-1">
                      ({rel.percentage}%)
                    </span>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Override section */}
        <section className="border-t border-gray-200 pt-4">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Override Code
          </h4>

          {/* Code search */}
          <input
            type="text"
            placeholder="Search codes..."
            value={codeSearch}
            onChange={(e) => setCodeSearch(e.target.value)}
            className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md mb-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />

          {/* Code dropdown — all leaf codes grouped by head */}
          <select
            value={overrideCode}
            onChange={(e) => setOverrideCode(e.target.value)}
            className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md mb-2 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            size={6}
          >
            <option value="">-- Select code --</option>
            {groupedCodes.map((group) => (
              <optgroup key={group.head} label={group.label}>
                {group.codes.map((m) => (
                  <option key={m.reportingCode} value={m.reportingCode}>
                    {m.reportingCode} - {m.name}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>

          {overrideCode && (
            <div className="mb-2 text-xs">
              <div className="text-blue-600 font-mono">Selected: {overrideCode}</div>
              {codeToDescription[overrideCode] && (
                <div className="text-gray-500 mt-0.5">
                  {codeToDescription[overrideCode]}
                </div>
              )}
            </div>
          )}

          {/* Reason */}
          <textarea
            placeholder="Reason for override..."
            value={overrideReason}
            onChange={(e) => setOverrideReason(e.target.value)}
            className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md mb-2 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            rows={2}
          />

          <button
            onClick={handleApplyOverride}
            disabled={!overrideCode}
            className={`w-full py-1.5 px-3 text-sm font-medium rounded-md transition-colors ${
              overrideCode
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-gray-200 text-gray-400 cursor-not-allowed'
            }`}
          >
            Apply Override
          </button>
        </section>
      </div>
    </div>
  );
}
