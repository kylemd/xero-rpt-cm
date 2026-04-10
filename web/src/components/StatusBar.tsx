/**
 * Top status bar with app title, entity info, and stat badges.
 */

import { useAppStore } from '../store/appStore';

interface StatusBarProps {
  onToggleRulesAdmin: () => void;
}

export default function StatusBar({ onToggleRulesAdmin }: StatusBarProps) {
  const chartCheckData = useAppStore((s) => s.chartCheckData);
  const mappedAccounts = useAppStore((s) => s.mappedAccounts);

  const entityName = chartCheckData?.clientParams?.displayName;

  const totalCount = mappedAccounts.length;
  const reviewCount = mappedAccounts.filter((a) => a.needsReview).length;
  const fallbackCount = mappedAccounts.filter(
    (a) => a.source === 'FallbackParent',
  ).length;

  return (
    <header className="flex items-center h-12 px-4 border-b border-gray-200 bg-white shrink-0">
      {/* Left section */}
      <div className="flex items-center gap-3">
        <span className="text-blue-600 font-semibold text-lg tracking-tight">
          Xero Code Mapper
        </span>
        {entityName && (
          <span className="text-sm text-gray-500 border-l border-gray-200 pl-3">
            {entityName}
          </span>
        )}
      </div>

      <div className="flex-1" />

      {/* Right section */}
      <div className="flex items-center gap-2">
        {totalCount > 0 && (
          <>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
              {totalCount} accounts
            </span>
            {reviewCount > 0 && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
                {reviewCount} review
              </span>
            )}
            {fallbackCount > 0 && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
                {fallbackCount} fallback
              </span>
            )}
          </>
        )}
        <button
          onClick={onToggleRulesAdmin}
          className="ml-2 px-3 py-1 text-xs font-medium border border-gray-300 rounded-md hover:bg-gray-50 text-gray-600 transition-colors"
        >
          Rules Admin
        </button>
      </div>
    </header>
  );
}
