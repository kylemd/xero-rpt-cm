/**
 * Left sidebar panel for pipeline inputs.
 *
 * Contains template selector, file drop zones, run button, and entity context.
 */

import { useCallback, useState } from 'react';
import FileDropZone from './FileDropZone';
import { useAppStore } from '../store/appStore';
import { parseChartFile } from '../parsers/chartParser';
import { parseChartCheckReport } from '../parsers/chartCheckParser';
import { parseGroupRelationshipsFile } from '../parsers/groupParser';
import { runPipeline } from '../pipeline/pipeline';
import systemMappings from '../data/systemMappings.json';
import type { TemplateName, SystemMapping } from '../types';

const TEMPLATE_OPTIONS: TemplateName[] = [
  'Company',
  'Trust',
  'Partnership',
  'SoleTrader',
  'XeroHandi',
];

export default function InputPanel() {
  const templateName = useAppStore((s) => s.templateName);
  const setTemplateName = useAppStore((s) => s.setTemplateName);
  const accounts = useAppStore((s) => s.accounts);
  const setAccounts = useAppStore((s) => s.setAccounts);
  const chartCheckData = useAppStore((s) => s.chartCheckData);
  const setChartCheckData = useAppStore((s) => s.setChartCheckData);
  const setGroupRelationships = useAppStore((s) => s.setGroupRelationships);
  const rulesData = useAppStore((s) => s.rulesData);
  const isProcessing = useAppStore((s) => s.isProcessing);
  const setIsProcessing = useAppStore((s) => s.setIsProcessing);
  const setMappedAccounts = useAppStore((s) => s.setMappedAccounts);
  const industry = useAppStore((s) => s.industry);

  const [chartFileName, setChartFileName] = useState<string>();
  const [chartCheckFileName, setChartCheckFileName] = useState<string>();
  const [groupFileName, setGroupFileName] = useState<string>();
  const [chartStatus, setChartStatus] = useState<string>();
  const [chartCheckStatus, setChartCheckStatus] = useState<string>();
  const [error, setError] = useState<string>();

  const canRun =
    accounts.length > 0 && chartCheckData !== null && rulesData !== null && !isProcessing;

  const handleChartFile = useCallback(
    async (file: File) => {
      setError(undefined);
      setChartFileName(file.name);
      setChartStatus('Parsing...');
      try {
        const parsed = await parseChartFile(file);
        setAccounts(parsed);
        setChartStatus(`${parsed.length} accounts`);
      } catch (e) {
        setChartStatus(undefined);
        setChartFileName(undefined);
        setError(e instanceof Error ? e.message : 'Failed to parse chart file');
      }
    },
    [setAccounts],
  );

  const handleChartCheckFile = useCallback(
    async (file: File) => {
      setError(undefined);
      setChartCheckFileName(file.name);
      setChartCheckStatus('Parsing...');
      try {
        const data = await parseChartCheckReport(file);
        setChartCheckData(data);
        setChartCheckStatus(`${data.glSummary.length} GL entries`);
      } catch (e) {
        setChartCheckStatus(undefined);
        setChartCheckFileName(undefined);
        setError(
          e instanceof Error ? e.message : 'Failed to parse chart check report',
        );
      }
    },
    [setChartCheckData],
  );

  const handleGroupFile = useCallback(
    async (file: File) => {
      setError(undefined);
      setGroupFileName(file.name);
      try {
        const data = await parseGroupRelationshipsFile(file);
        setGroupRelationships(data);
      } catch (e) {
        setGroupFileName(undefined);
        setError(
          e instanceof Error ? e.message : 'Failed to parse group relationships',
        );
      }
    },
    [setGroupRelationships],
  );

  const handleRunMapping = useCallback(async () => {
    if (!canRun || !rulesData || !chartCheckData) return;
    setError(undefined);
    setIsProcessing(true);
    try {
      const templateModule = await import(
        `../data/templates/${templateName}.json`
      );
      const templateEntries = templateModule.default;

      const result = runPipeline({
        accounts,
        rulesData,
        templateEntries,
        systemMappings: systemMappings as SystemMapping[],
        glSummary: chartCheckData.glSummary,
        industry,
        templateName,
      });
      setMappedAccounts(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Pipeline failed');
    } finally {
      setIsProcessing(false);
    }
  }, [
    canRun,
    rulesData,
    chartCheckData,
    templateName,
    accounts,
    industry,
    setIsProcessing,
    setMappedAccounts,
  ]);

  const clientParams = chartCheckData?.clientParams;

  return (
    <aside className="w-72 shrink-0 border-r border-gray-200 bg-gray-50 p-4 overflow-y-auto">
      <h2 className="text-sm font-semibold text-gray-700 mb-3">
        Pipeline Inputs
      </h2>

      {/* Template selector */}
      <div className="mb-3">
        <label className="block text-xs font-medium text-gray-600 mb-1">
          Template
        </label>
        <select
          value={templateName}
          onChange={(e) => setTemplateName(e.target.value as TemplateName)}
          className="w-full text-sm border border-gray-300 rounded-md px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          {TEMPLATE_OPTIONS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      {/* File inputs */}
      <FileDropZone
        label="Chart of Accounts"
        required
        accept=".csv,.xlsx,.xls"
        onFile={handleChartFile}
        fileName={chartFileName}
        status={chartStatus}
      />

      <FileDropZone
        label="Chart Check Report"
        required
        accept=".xlsx,.xls"
        onFile={handleChartCheckFile}
        fileName={chartCheckFileName}
        status={chartCheckStatus}
      />

      <FileDropZone
        label="Group Relationships"
        accept=".csv"
        onFile={handleGroupFile}
        fileName={groupFileName}
      />

      {/* Error display */}
      {error && (
        <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
          {error}
        </div>
      )}

      {/* Run button */}
      <button
        onClick={handleRunMapping}
        disabled={!canRun}
        className={`w-full py-2 px-4 rounded-md text-sm font-medium transition-colors ${
          canRun
            ? 'bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800'
            : 'bg-gray-200 text-gray-400 cursor-not-allowed'
        }`}
      >
        {isProcessing ? (
          <span className="flex items-center justify-center gap-2">
            <svg
              className="animate-spin h-4 w-4"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            Processing...
          </span>
        ) : (
          'Run Mapping'
        )}
      </button>

      {/* Rules status */}
      <div className="mt-3 text-xs text-gray-500">
        {rulesData
          ? `Rules loaded: v${rulesData.version} (${rulesData.rules.length} rules)`
          : 'Loading rules...'}
      </div>

      {/* Entity context */}
      {clientParams && clientParams.displayName && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <h3 className="text-xs font-semibold text-gray-600 mb-2 uppercase tracking-wide">
            Entity Context
          </h3>
          <dl className="space-y-1.5 text-xs">
            {clientParams.displayName && (
              <div>
                <dt className="text-gray-400">Name</dt>
                <dd className="text-gray-700 font-medium">
                  {clientParams.displayName}
                </dd>
              </div>
            )}
            {clientParams.abn && (
              <div>
                <dt className="text-gray-400">ABN</dt>
                <dd className="text-gray-700">{clientParams.abn}</dd>
              </div>
            )}
            {clientParams.directors.length > 0 && (
              <div>
                <dt className="text-gray-400">Directors</dt>
                <dd className="text-gray-700">
                  {clientParams.directors.join(', ')}
                </dd>
              </div>
            )}
            {chartCheckData.glSummary.length > 0 && (
              <div>
                <dt className="text-gray-400">GL Entries</dt>
                <dd className="text-gray-700">
                  {chartCheckData.glSummary.length}
                </dd>
              </div>
            )}
          </dl>
        </div>
      )}
    </aside>
  );
}
