/**
 * Left sidebar panel for pipeline inputs.
 *
 * Single Verification Report drop zone (replaces the legacy two-file
 * intake) plus an optional Group Relationships file and the template
 * selector.
 */

import { useCallback, useState } from 'react';
import FileDropZone from './FileDropZone';
import { useAppStore } from '../store/appStore';
import { parseVerificationReport } from '../parsers/verificationReportParser';
import { parseGroupRelationshipsFile } from '../parsers/groupParser';
import { runPipeline } from '../pipeline/pipeline';
import { buildCodeTypeMap } from '../pipeline/typePredict';
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
  const verificationReport = useAppStore((s) => s.verificationReport);
  const setVerificationReport = useAppStore((s) => s.setVerificationReport);
  const setGroupRelationships = useAppStore((s) => s.setGroupRelationships);
  const rulesData = useAppStore((s) => s.rulesData);
  const isProcessing = useAppStore((s) => s.isProcessing);
  const setIsProcessing = useAppStore((s) => s.setIsProcessing);
  const setMappedAccounts = useAppStore((s) => s.setMappedAccounts);
  const setCodeTypeMap = useAppStore((s) => s.setCodeTypeMap);
  const industry = useAppStore((s) => s.industry);

  const [reportFileName, setReportFileName] = useState<string>();
  const [groupFileName, setGroupFileName] = useState<string>();
  const [reportStatus, setReportStatus] = useState<string>();
  const [error, setError] = useState<string>();

  const canRun =
    verificationReport !== null && rulesData !== null && !isProcessing;

  const handleReportFile = useCallback(
    async (file: File) => {
      setError(undefined);
      setReportFileName(file.name);
      setReportStatus('Parsing...');
      try {
        const data = await parseVerificationReport(file);
        setVerificationReport(data);
        const mandatory = data.accounts.filter((a) => a.activity === 'mandatory').length;
        const optional = data.accounts.filter((a) => a.activity === 'optional').length;
        setReportStatus(
          `${data.accounts.length} accounts \u00B7 ${mandatory} mandatory \u00B7 ${optional} optional`,
        );
      } catch (e) {
        setReportStatus(undefined);
        setReportFileName(undefined);
        setError(
          e instanceof Error
            ? e.message
            : 'Failed to parse Verification Report',
        );
      }
    },
    [setVerificationReport],
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
    if (!canRun || !rulesData || !verificationReport) return;
    setError(undefined);
    setIsProcessing(true);
    try {
      const templateModule = await import(
        `../data/templates/${templateName}.json`
      );
      const templateEntries = templateModule.default;
      setCodeTypeMap(buildCodeTypeMap(templateEntries));

      const result = runPipeline({
        accounts: verificationReport.accounts,
        rulesData,
        templateEntries,
        systemMappings: systemMappings as SystemMapping[],
        glSummary: verificationReport.glSummary,
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
    verificationReport,
    templateName,
    industry,
    setIsProcessing,
    setMappedAccounts,
    setCodeTypeMap,
  ]);

  const clientParams = verificationReport?.clientParams;

  return (
    <aside className="w-72 shrink-0 border-r border-gray-200 bg-gray-50 p-4 overflow-y-auto">
      <h2 className="text-sm font-semibold text-gray-700 mb-3">
        Pipeline Inputs
      </h2>

      {/* Safety banner */}
      <div className="mb-3 p-2 bg-yellow-50 border border-yellow-200 rounded text-xs text-yellow-800">
        Before using this report, make sure you've exported a fresh
        Verification Report from Xero \u2014 stale data produces stale mappings.
      </div>

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

      {/* Verification Report */}
      <FileDropZone
        label="Verification Report"
        required
        accept=".xlsx"
        onFile={handleReportFile}
        fileName={reportFileName}
        status={reportStatus}
      />

      {/* Group Relationships (optional) */}
      <FileDropZone
        label="Group Relationships"
        accept=".csv"
        onFile={handleGroupFile}
        fileName={groupFileName}
      />

      {/* Error */}
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
        {isProcessing ? 'Processing...' : 'Run Mapping'}
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
            <div>
              <dt className="text-gray-400">Name</dt>
              <dd className="text-gray-700 font-medium">
                {clientParams.displayName}
              </dd>
            </div>
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
          </dl>
        </div>
      )}
    </aside>
  );
}
