/**
 * Root application component.
 *
 * Wires together StatusBar, InputPanel, MappingTable, AccountDetailPanel,
 * and RulesAdmin into the main layout.
 */

import { useEffect, useState } from 'react';
import StatusBar from './components/StatusBar';
import InputPanel from './components/InputPanel';
import MappingTable from './components/MappingTable';
import AccountDetailPanel from './components/AccountDetailPanel';
import RulesAdmin from './components/RulesAdmin';
import { useAppStore } from './store/appStore';
import { fetchRules } from './services/rulesService';

export default function App() {
  const setRulesData = useAppStore((s) => s.setRulesData);
  const setRulesLoading = useAppStore((s) => s.setRulesLoading);

  const [showRulesAdmin, setShowRulesAdmin] = useState(false);
  const [selectedAccountIndex, setSelectedAccountIndex] = useState<
    number | null
  >(null);

  // Fetch rules on mount
  useEffect(() => {
    let cancelled = false;
    setRulesLoading(true);
    fetchRules()
      .then((data) => {
        if (!cancelled) {
          setRulesData(data);
        }
      })
      .catch(() => {
        // fetchRules already falls back to bundled baseline
      })
      .finally(() => {
        if (!cancelled) {
          setRulesLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [setRulesData, setRulesLoading]);

  return (
    <div className="flex flex-col h-screen bg-white text-gray-800">
      <StatusBar
        onToggleRulesAdmin={() => setShowRulesAdmin(!showRulesAdmin)}
      />
      <div className="flex flex-1 overflow-hidden">
        <InputPanel />
        <main className="flex-1 flex overflow-hidden">
          <MappingTable onSelectAccount={setSelectedAccountIndex} />
          {selectedAccountIndex !== null && (
            <AccountDetailPanel
              selectedIndex={selectedAccountIndex}
              onClose={() => setSelectedAccountIndex(null)}
            />
          )}
        </main>
      </div>
      {showRulesAdmin && (
        <RulesAdmin onClose={() => setShowRulesAdmin(false)} />
      )}
    </div>
  );
}
