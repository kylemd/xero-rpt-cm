/**
 * Main mapping results table using TanStack Table.
 *
 * Displays mapped accounts with colour-coded confidence, filtering, and export.
 * Includes original code comparison, type mismatch detection, and quick-approve.
 */

import { useMemo, useState, useCallback } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table';
import { useAppStore } from '../store/appStore';
import {
  predictTypeFromCode,
  SYSTEM_TYPES,
  ALLOWED_TYPES_BY_HEAD,
  hasTypeMismatch,
} from '../pipeline/typePredict';
import systemMappings from '../data/systemMappings.json';
import type { MappedAccount, SystemMapping } from '../types';

// ---------------------------------------------------------------------------
// Filter types
// ---------------------------------------------------------------------------

type FilterMode = 'all' | 'review' | 'fallback' | 'active' | 'typeMismatch';

// ---------------------------------------------------------------------------
// System mappings code-to-name lookup
// ---------------------------------------------------------------------------

const allMappings = systemMappings as SystemMapping[];
const codeToName: Record<string, string> = {};
for (const m of allMappings) {
  codeToName[m.reportingCode] = m.name;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function codeBadgeClass(source: string): string {
  if (source === 'FallbackParent') {
    return 'text-red-600 bg-red-50 border border-red-200';
  }
  if (source === 'FuzzyMatch') {
    return 'text-amber-600 bg-amber-50 border border-amber-200';
  }
  return 'text-green-600 bg-green-50 border border-green-200';
}

function generateExportCSV(
  accounts: MappedAccount[],
  codeTypeMap: Record<string, string>,
): string {
  const header = '*Code,*Name,*Type,*Tax Code,Report Code';
  const rows = accounts.map((a) => {
    const reportCode = a.overrideCode ?? a.predictedCode;
    const finalType =
      a.typeOverride || predictTypeFromCode(reportCode, a.type, codeTypeMap);
    const escape = (s: string) =>
      s.includes(',') || s.includes('"') ? `"${s.replace(/"/g, '""')}"` : s;
    return [
      escape(a.code),
      escape(a.name),
      escape(finalType),
      escape(a.taxCode ?? ''),
      escape(reportCode),
    ].join(',');
  });
  return [header, ...rows].join('\n');
}

function generateDecisionsJSON(
  accounts: MappedAccount[],
  codeTypeMap: Record<string, string>,
): string {
  const decisions = accounts
    .filter((a) => a.overrideCode || a.typeOverride)
    .map((a) => {
      const finalCode = a.overrideCode ?? a.predictedCode;
      const predictedType = predictTypeFromCode(finalCode, a.type, codeTypeMap);
      const hasTypeChange =
        a.typeOverride || (predictedType !== a.type && !SYSTEM_TYPES.has(a.type));
      return {
        accountCode: a.code,
        accountName: a.name,
        originalCode: a.predictedCode,
        newCode: a.overrideCode ?? a.predictedCode,
        reason: a.overrideReason ?? '',
        ...(hasTypeChange
          ? { typeChange: { from: a.type, to: a.typeOverride || predictedType } }
          : {}),
      };
    });
  return JSON.stringify({ decisions }, null, 2);
}

function downloadFile(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** Check if a given account has a type mismatch. */
function hasTypeMismatchForAccount(acct: MappedAccount): boolean {
  return hasTypeMismatch(acct.type, acct.overrideCode || acct.predictedCode);
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface MappingTableProps {
  onSelectAccount: (index: number | null) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function MappingTable({ onSelectAccount }: MappingTableProps) {
  const mappedAccounts = useAppStore((s) => s.mappedAccounts);
  const codeTypeMap = useAppStore((s) => s.codeTypeMap);
  const approveAccount = useAppStore((s) => s.approveAccount);
  const overrideAccountType = useAppStore((s) => s.overrideAccountType);

  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState('');
  const [filterMode, setFilterMode] = useState<FilterMode>('all');
  const [selectedRowIndex, setSelectedRowIndex] = useState<number | null>(null);

  // Apply filter mode
  const filteredData = useMemo(() => {
    let data = mappedAccounts;
    switch (filterMode) {
      case 'review':
        data = data.filter((a) => a.needsReview);
        break;
      case 'fallback':
        data = data.filter((a) => a.source === 'FallbackParent');
        break;
      case 'active':
        data = data.filter((a) => a.hasActivity);
        break;
      case 'typeMismatch':
        data = data.filter((a) => hasTypeMismatchForAccount(a));
        break;
    }
    return data;
  }, [mappedAccounts, filterMode]);

  const columns = useMemo<ColumnDef<MappedAccount>[]>(
    () => [
      {
        accessorKey: 'code',
        header: 'Code',
        size: 80,
        enableSorting: true,
      },
      {
        accessorKey: 'name',
        header: 'Account Name',
        size: 220,
        enableSorting: true,
        cell: ({ row }) => (
          <span className="truncate block" title={row.original.name}>
            {row.original.correctedName ? (
              <span>
                <span>{row.original.correctedName}</span>
                <span className="text-xs text-gray-400 ml-1">(corrected)</span>
              </span>
            ) : (
              row.original.name
            )}
          </span>
        ),
      },
      {
        id: 'type',
        header: 'Type',
        size: 140,
        accessorFn: (row) => row.typeOverride ?? row.type,
        cell: ({ row }) => {
          const acct = row.original;
          const finalCode = acct.overrideCode || acct.predictedCode;
          const predictedType = predictTypeFromCode(
            finalCode,
            acct.type,
            codeTypeMap,
          );
          const hasMismatch = hasTypeMismatchForAccount(acct);
          const originalIndex = mappedAccounts.indexOf(acct);

          if (acct.typeOverride) {
            return (
              <div>
                <span className="line-through text-gray-400 text-xs">
                  {acct.type}
                </span>{' '}
                <span className="text-blue-600 font-bold text-xs">
                  {acct.typeOverride}
                </span>
              </div>
            );
          }

          if (hasMismatch) {
            const codeHead = finalCode.split('.')[0];
            const allowedTypes =
              ALLOWED_TYPES_BY_HEAD[codeHead] ?? [];
            return (
              <div className="space-y-1">
                <div>
                  <span className="line-through text-gray-400 text-xs">
                    {acct.type}
                  </span>{' '}
                  <span className="text-red-600 font-bold text-xs">
                    {predictedType}
                  </span>
                </div>
                {allowedTypes.length > 0 && (
                  <select
                    className="text-xs border border-red-300 rounded px-1 py-0.5 bg-white w-full"
                    value=""
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => {
                      if (e.target.value && originalIndex >= 0) {
                        overrideAccountType(originalIndex, e.target.value);
                      }
                    }}
                  >
                    <option value="">Override type...</option>
                    {allowedTypes.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            );
          }

          return <span className="text-xs">{acct.type}</span>;
        },
      },
      {
        id: 'originalCode',
        header: 'Original Code',
        size: 140,
        accessorFn: (row) => row.reportCode ?? '',
        cell: ({ row }) => {
          const acct = row.original;
          const rc = acct.reportCode;
          if (!rc) {
            return (
              <span className="text-gray-300 font-mono text-xs">{'\u2014'}</span>
            );
          }
          const name = codeToName[rc];
          return (
            <div>
              <span
                className="inline-block font-mono text-xs"
                style={{ color: '#6b7280' }}
              >
                {rc}
              </span>
              {name && (
                <div className="text-xs text-gray-400 truncate" title={name}>
                  {name}
                </div>
              )}
            </div>
          );
        },
      },
      {
        id: 'mappedCode',
        header: 'Mapped Code',
        size: 150,
        accessorFn: (row) => row.overrideCode ?? row.predictedCode,
        cell: ({ row }) => {
          const acct = row.original;
          const displayCode = acct.overrideCode ?? acct.predictedCode;
          const badgeCls = acct.overrideCode
            ? 'text-blue-600 bg-blue-50 border border-blue-200'
            : codeBadgeClass(acct.source);
          const name = codeToName[displayCode];
          return (
            <div>
              <span
                className={`inline-block px-1.5 py-0.5 rounded text-xs font-mono ${badgeCls}`}
              >
                {displayCode}
              </span>
              {name && (
                <div className="text-xs text-gray-400 truncate" title={name}>
                  {name}
                </div>
              )}
            </div>
          );
        },
      },
      {
        accessorKey: 'source',
        header: 'Source',
        size: 130,
        cell: ({ getValue }) => (
          <span className="text-gray-500 text-xs">{getValue() as string}</span>
        ),
      },
      {
        id: 'active',
        header: 'Active',
        size: 55,
        accessorFn: (row) => row.hasActivity,
        cell: ({ row }) => (
          <span
            className={`text-lg ${row.original.hasActivity ? 'text-green-500' : 'text-gray-300'}`}
          >
            {'\u25CF'}
          </span>
        ),
      },
      {
        id: 'decision',
        header: 'Decision',
        size: 100,
        cell: ({ row }) => {
          const acct = row.original;
          const originalIndex = mappedAccounts.indexOf(acct);

          // Already overridden
          if (acct.overrideCode) {
            return (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium text-blue-600 bg-blue-50 border border-blue-200">
                {'\u2713'} Overridden
              </span>
            );
          }

          // Already approved
          if (acct.approved) {
            return (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium text-green-600 bg-green-50 border border-green-200">
                {'\u2713'} Approved
              </span>
            );
          }

          // Auto-confirmed: predicted matches original (or no original)
          if (
            !acct.reportCode ||
            acct.predictedCode === acct.reportCode
          ) {
            return (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium text-green-600 bg-green-50 border border-green-200">
                {'\u2713'} Auto
              </span>
            );
          }

          // Needs approval: predicted differs from original
          return (
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (originalIndex >= 0) {
                  approveAccount(originalIndex);
                }
              }}
              className="px-2 py-0.5 text-xs font-medium rounded bg-blue-600 text-white hover:bg-blue-700 transition-colors"
            >
              Accept
            </button>
          );
        },
      },
    ],
    [mappedAccounts, codeTypeMap, approveAccount, overrideAccountType],
  );

  const table = useReactTable({
    data: filteredData,
    columns,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    globalFilterFn: (row, _columnId, filterValue: string) => {
      const search = filterValue.toLowerCase();
      const acct = row.original;
      return (
        acct.name.toLowerCase().includes(search) ||
        acct.code.toLowerCase().includes(search) ||
        acct.predictedCode.toLowerCase().includes(search)
      );
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  const handleRowClick = useCallback(
    (rowIndex: number) => {
      // rowIndex here is the index into filteredData, but we need the
      // original index in mappedAccounts
      const acct = filteredData[rowIndex];
      const originalIndex = mappedAccounts.indexOf(acct);
      setSelectedRowIndex(rowIndex);
      onSelectAccount(originalIndex >= 0 ? originalIndex : null);
    },
    [filteredData, mappedAccounts, onSelectAccount],
  );

  const handleExportCSV = useCallback(() => {
    const csv = generateExportCSV(mappedAccounts, codeTypeMap);
    downloadFile(csv, 'MappedChartOfAccounts.csv', 'text/csv');
  }, [mappedAccounts, codeTypeMap]);

  const handleExportDecisions = useCallback(() => {
    const json = generateDecisionsJSON(mappedAccounts, codeTypeMap);
    downloadFile(json, 'decisions.json', 'application/json');
  }, [mappedAccounts, codeTypeMap]);

  const filterChips: { mode: FilterMode; label: string }[] = [
    { mode: 'all', label: 'All' },
    { mode: 'review', label: 'Needs Review' },
    { mode: 'fallback', label: 'Fallback Only' },
    { mode: 'active', label: 'Active' },
    { mode: 'typeMismatch', label: 'Type Mismatch' },
  ];

  const reviewCount = mappedAccounts.filter((a) => a.needsReview).length;
  const fallbackCount = mappedAccounts.filter(
    (a) => a.source === 'FallbackParent',
  ).length;
  const typeMismatchCount = mappedAccounts.filter((a) =>
    hasTypeMismatchForAccount(a),
  ).length;

  if (mappedAccounts.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
        <div className="text-center">
          <p className="text-lg font-medium text-gray-300 mb-1">
            No mapping results yet
          </p>
          <p>Load files and run the pipeline to see results here.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="shrink-0 px-4 py-2 border-b border-gray-200 bg-white flex items-center gap-3 flex-wrap">
        {/* Search */}
        <input
          type="text"
          placeholder="Search by name or code..."
          value={globalFilter}
          onChange={(e) => setGlobalFilter(e.target.value)}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-md w-64 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />

        {/* Filter chips */}
        <div className="flex gap-1.5">
          {filterChips.map(({ mode, label }) => (
            <button
              key={mode}
              onClick={() => setFilterMode(mode)}
              className={`px-2.5 py-1 text-xs rounded-full font-medium transition-colors ${
                filterMode === mode
                  ? 'bg-blue-100 text-blue-700 border border-blue-300'
                  : 'bg-gray-100 text-gray-600 border border-gray-200 hover:bg-gray-200'
              }`}
            >
              {label}
              {mode === 'review' && reviewCount > 0 && (
                <span className="ml-1 text-amber-600">({reviewCount})</span>
              )}
              {mode === 'fallback' && fallbackCount > 0 && (
                <span className="ml-1 text-red-600">({fallbackCount})</span>
              )}
              {mode === 'typeMismatch' && typeMismatchCount > 0 && (
                <span className="ml-1 text-red-600">({typeMismatchCount})</span>
              )}
            </button>
          ))}
        </div>

        <div className="flex-1" />

        {/* Export buttons */}
        <button
          onClick={handleExportCSV}
          className="px-3 py-1.5 text-xs font-medium bg-white border border-gray-300 rounded-md hover:bg-gray-50 text-gray-700"
        >
          Export CSV
        </button>
        <button
          onClick={handleExportDecisions}
          className="px-3 py-1.5 text-xs font-medium bg-white border border-gray-300 rounded-md hover:bg-gray-50 text-gray-700"
        >
          Export Decisions
        </button>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-gray-50 border-b border-gray-200">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer select-none hover:bg-gray-100"
                    style={{ width: header.getSize() }}
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <div className="flex items-center gap-1">
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                      {{
                        asc: ' \u25B2',
                        desc: ' \u25BC',
                      }[header.column.getIsSorted() as string] ?? ''}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-gray-100">
            {table.getRowModel().rows.map((row) => {
              const acct = row.original;
              const hasMismatch = hasTypeMismatchForAccount(acct);

              return (
                <tr
                  key={row.id}
                  onClick={() => handleRowClick(row.index)}
                  className={`cursor-pointer transition-colors ${
                    selectedRowIndex === row.index
                      ? 'bg-blue-50'
                      : hasMismatch
                        ? 'hover:bg-red-50'
                        : 'hover:bg-gray-50'
                  }`}
                >
                  {row.getVisibleCells().map((cell) => {
                    const isTypeCell = cell.column.id === 'type';
                    return (
                      <td
                        key={cell.id}
                        className={`px-3 py-2 ${isTypeCell && hasMismatch && !acct.typeOverride ? 'bg-red-100' : ''}`}
                      >
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext(),
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer count */}
      <div className="shrink-0 px-4 py-1.5 border-t border-gray-200 bg-gray-50 text-xs text-gray-500">
        Showing {table.getRowModel().rows.length} of {mappedAccounts.length}{' '}
        accounts
      </div>
    </div>
  );
}
