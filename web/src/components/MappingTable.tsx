/**
 * Main mapping results table using TanStack Table.
 *
 * Displays mapped accounts with colour-coded confidence, filtering, and export.
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
import type { MappedAccount } from '../types';

// ---------------------------------------------------------------------------
// Filter types
// ---------------------------------------------------------------------------

type FilterMode = 'all' | 'review' | 'fallback' | 'active';

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

function statusLabel(acct: MappedAccount): { text: string; cls: string } {
  if (acct.overrideCode) {
    return { text: 'Overridden', cls: 'text-blue-600' };
  }
  if (acct.needsReview) {
    return { text: 'Review', cls: 'text-amber-600' };
  }
  return { text: 'OK', cls: 'text-green-600' };
}

function generateExportCSV(accounts: MappedAccount[]): string {
  const header = '*Code,*Name,*Type,*Tax Code,Report Code';
  const rows = accounts.map((a) => {
    const reportCode = a.overrideCode ?? a.predictedCode;
    const escape = (s: string) =>
      s.includes(',') || s.includes('"') ? `"${s.replace(/"/g, '""')}"` : s;
    return [
      escape(a.code),
      escape(a.name),
      escape(a.type),
      escape(a.taxCode ?? ''),
      escape(reportCode),
    ].join(',');
  });
  return [header, ...rows].join('\n');
}

function generateDecisionsJSON(accounts: MappedAccount[]): string {
  const decisions = accounts
    .filter((a) => a.overrideCode)
    .map((a) => ({
      accountCode: a.code,
      accountName: a.name,
      originalCode: a.predictedCode,
      newCode: a.overrideCode!,
      reason: a.overrideReason ?? '',
    }));
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
        size: 240,
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
        accessorKey: 'type',
        header: 'Type',
        size: 120,
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
          return (
            <span
              className={`inline-block px-1.5 py-0.5 rounded text-xs font-mono ${badgeCls}`}
            >
              {displayCode}
            </span>
          );
        },
      },
      {
        accessorKey: 'source',
        header: 'Source',
        size: 140,
        cell: ({ getValue }) => (
          <span className="text-gray-500 text-xs">{getValue() as string}</span>
        ),
      },
      {
        id: 'active',
        header: 'Active',
        size: 60,
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
        id: 'status',
        header: 'Status',
        size: 90,
        cell: ({ row }) => {
          const { text, cls } = statusLabel(row.original);
          return <span className={`text-xs font-medium ${cls}`}>{text}</span>;
        },
      },
    ],
    [],
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
    const csv = generateExportCSV(mappedAccounts);
    downloadFile(csv, 'MappedChartOfAccounts.csv', 'text/csv');
  }, [mappedAccounts]);

  const handleExportDecisions = useCallback(() => {
    const json = generateDecisionsJSON(mappedAccounts);
    downloadFile(json, 'decisions.json', 'application/json');
  }, [mappedAccounts]);

  const filterChips: { mode: FilterMode; label: string }[] = [
    { mode: 'all', label: 'All' },
    { mode: 'review', label: 'Needs Review' },
    { mode: 'fallback', label: 'Fallback Only' },
    { mode: 'active', label: 'Active' },
  ];

  const reviewCount = mappedAccounts.filter((a) => a.needsReview).length;
  const fallbackCount = mappedAccounts.filter(
    (a) => a.source === 'FallbackParent',
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
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                onClick={() => handleRowClick(row.index)}
                className={`cursor-pointer transition-colors ${
                  selectedRowIndex === row.index
                    ? 'bg-blue-50'
                    : 'hover:bg-gray-50'
                }`}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-3 py-2">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
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
