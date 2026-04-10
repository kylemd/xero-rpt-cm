/**
 * Rules administration panel.
 *
 * Full-screen overlay gated by GitHub PAT authentication.
 * Allows viewing, editing, adding, and deleting rules.
 */

import { useState, useMemo, useCallback } from 'react';
import { useAppStore } from '../store/appStore';
import { saveRules } from '../services/rulesService';
import type { Rule, RulesData } from '../types';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const EMPTY_RULE: Rule = {
  name: '',
  code: '',
  priority: 70,
  keywords: [],
  keywordsAll: [],
  keywordsExclude: [],
  rawTypes: [],
  canonTypes: [],
  typeExclude: [],
  template: undefined,
  ownerContext: false,
  nameOnly: false,
  industries: [],
  notes: '',
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface RulesAdminProps {
  onClose: () => void;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function TokenGate({
  onAuthenticate,
}: {
  onAuthenticate: (token: string) => void;
}) {
  const [input, setInput] = useState('');

  return (
    <div className="flex items-center justify-center h-full">
      <div className="w-96 p-6 bg-white rounded-lg shadow-lg border border-gray-200">
        <h3 className="text-lg font-semibold text-gray-800 mb-2">
          GitHub Authentication
        </h3>
        <p className="text-sm text-gray-500 mb-4">
          Enter a GitHub Personal Access Token with repo write access to manage
          rules.
        </p>
        <input
          type="password"
          placeholder="ghp_..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
        <button
          onClick={() => {
            if (input.trim()) onAuthenticate(input.trim());
          }}
          disabled={!input.trim()}
          className={`w-full py-2 rounded-md text-sm font-medium transition-colors ${
            input.trim()
              ? 'bg-blue-600 text-white hover:bg-blue-700'
              : 'bg-gray-200 text-gray-400 cursor-not-allowed'
          }`}
        >
          Authenticate
        </button>
      </div>
    </div>
  );
}

function arrayToString(arr: string[]): string {
  return arr.join(', ');
}

function stringToArray(s: string): string[] {
  return s
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function RulesAdmin({ onClose }: RulesAdminProps) {
  const githubToken = useAppStore((s) => s.githubToken);
  const setGithubToken = useAppStore((s) => s.setGithubToken);
  const rulesData = useAppStore((s) => s.rulesData);
  const setRulesData = useAppStore((s) => s.setRulesData);

  const [search, setSearch] = useState('');
  const [editingRule, setEditingRule] = useState<Rule | null>(null);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string>();
  const [deleteConfirmIdx, setDeleteConfirmIdx] = useState<number | null>(null);

  const rules = rulesData?.rules ?? [];

  const filteredRules = useMemo(() => {
    if (!search) return rules.map((r, i) => ({ rule: r, originalIndex: i }));
    const s = search.toLowerCase();
    return rules
      .map((r, i) => ({ rule: r, originalIndex: i }))
      .filter(
        ({ rule: r }) =>
          r.name.toLowerCase().includes(s) ||
          r.code.toLowerCase().includes(s) ||
          r.keywords.some((k) => k.toLowerCase().includes(s)),
      );
  }, [rules, search]);

  const handleAuthenticate = useCallback(
    (token: string) => {
      setGithubToken(token);
    },
    [setGithubToken],
  );

  const handleEditRule = useCallback(
    (index: number) => {
      setEditingRule({ ...rules[index] });
      setEditingIndex(index);
      setSaveMessage(undefined);
    },
    [rules],
  );

  const handleAddRule = useCallback(() => {
    setEditingRule({ ...EMPTY_RULE });
    setEditingIndex(null);
    setSaveMessage(undefined);
  }, []);

  const handleDeleteRule = useCallback(
    (index: number) => {
      if (!rulesData) return;
      const updated: RulesData = {
        ...rulesData,
        rules: rules.filter((_, i) => i !== index),
        updatedAt: new Date().toISOString(),
      };
      setRulesData(updated);
      setDeleteConfirmIdx(null);
      if (editingIndex === index) {
        setEditingRule(null);
        setEditingIndex(null);
      }
    },
    [rulesData, rules, setRulesData, editingIndex],
  );

  const handleSaveEdit = useCallback(() => {
    if (!editingRule || !rulesData) return;
    const updatedRules = [...rules];
    if (editingIndex !== null) {
      updatedRules[editingIndex] = editingRule;
    } else {
      updatedRules.push(editingRule);
    }
    const updated: RulesData = {
      ...rulesData,
      rules: updatedRules,
      updatedAt: new Date().toISOString(),
    };
    setRulesData(updated);
    setEditingRule(null);
    setEditingIndex(null);
  }, [editingRule, rulesData, rules, editingIndex, setRulesData]);

  const handleSaveToGitHub = useCallback(async () => {
    if (!githubToken || !rulesData) return;
    setIsSaving(true);
    setSaveMessage(undefined);
    try {
      await saveRules(githubToken, rulesData);
      setSaveMessage('Saved successfully');
    } catch (e) {
      setSaveMessage(
        `Save failed: ${e instanceof Error ? e.message : 'Unknown error'}`,
      );
    } finally {
      setIsSaving(false);
    }
  }, [githubToken, rulesData]);

  const updateField = useCallback(
    <K extends keyof Rule>(field: K, value: Rule[K]) => {
      if (!editingRule) return;
      setEditingRule({ ...editingRule, [field]: value });
    },
    [editingRule],
  );

  return (
    <div className="fixed inset-0 z-50 bg-black/20 flex items-stretch">
      <div className="flex-1 bg-white flex flex-col m-4 rounded-lg shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
          <h2 className="text-lg font-semibold text-gray-800">Rules Admin</h2>
          <div className="flex items-center gap-2">
            {githubToken && (
              <>
                <button
                  onClick={handleSaveToGitHub}
                  disabled={isSaving}
                  className="px-3 py-1.5 text-xs font-medium bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
                >
                  {isSaving ? 'Saving...' : 'Save to GitHub'}
                </button>
                {saveMessage && (
                  <span
                    className={`text-xs ${saveMessage.includes('failed') ? 'text-red-600' : 'text-green-600'}`}
                  >
                    {saveMessage}
                  </span>
                )}
              </>
            )}
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-xs font-medium border border-gray-300 rounded-md hover:bg-gray-100 text-gray-600"
            >
              Close
            </button>
          </div>
        </div>

        {/* Body */}
        {!githubToken ? (
          <TokenGate onAuthenticate={handleAuthenticate} />
        ) : (
          <div className="flex flex-1 overflow-hidden">
            {/* Rules list */}
            <div className="w-1/2 flex flex-col border-r border-gray-200">
              {/* Search + add */}
              <div className="p-3 border-b border-gray-100 flex gap-2">
                <input
                  type="text"
                  placeholder="Search rules..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="flex-1 px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <button
                  onClick={handleAddRule}
                  className="px-3 py-1.5 text-xs font-medium bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  + Add Rule
                </button>
              </div>

              {/* List */}
              <div className="flex-1 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">
                        Name
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">
                        Code
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">
                        Pri
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">
                        Keywords
                      </th>
                      <th className="px-3 py-2 w-16"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {filteredRules.map(({ rule: r, originalIndex }) => (
                      <tr
                        key={originalIndex}
                        onClick={() => handleEditRule(originalIndex)}
                        className={`cursor-pointer transition-colors ${
                          editingIndex === originalIndex
                            ? 'bg-blue-50'
                            : 'hover:bg-gray-50'
                        }`}
                      >
                        <td className="px-3 py-2 truncate max-w-[160px]">
                          {r.name}
                        </td>
                        <td className="px-3 py-2 font-mono text-xs text-gray-600">
                          {r.code}
                        </td>
                        <td className="px-3 py-2 text-center">{r.priority}</td>
                        <td className="px-3 py-2 text-xs text-gray-500 truncate max-w-[180px]">
                          {r.keywords.slice(0, 3).join(', ')}
                          {r.keywords.length > 3 && '...'}
                        </td>
                        <td className="px-3 py-2">
                          {deleteConfirmIdx === originalIndex ? (
                            <div className="flex gap-1">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDeleteRule(originalIndex);
                                }}
                                className="text-xs text-red-600 font-medium"
                              >
                                Yes
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setDeleteConfirmIdx(null);
                                }}
                                className="text-xs text-gray-500"
                              >
                                No
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setDeleteConfirmIdx(originalIndex);
                              }}
                              className="text-xs text-red-400 hover:text-red-600"
                            >
                              Del
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {filteredRules.length === 0 && (
                  <div className="p-4 text-center text-sm text-gray-400">
                    No rules found
                  </div>
                )}
              </div>

              <div className="px-3 py-2 border-t border-gray-200 text-xs text-gray-500">
                {rules.length} rules total
                {rulesData?.version && ` | v${rulesData.version}`}
              </div>
            </div>

            {/* Edit form */}
            <div className="w-1/2 overflow-y-auto p-4">
              {editingRule ? (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-gray-700">
                    {editingIndex !== null ? 'Edit Rule' : 'New Rule'}
                  </h3>

                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Name
                    </label>
                    <input
                      type="text"
                      value={editingRule.name}
                      onChange={(e) => updateField('name', e.target.value)}
                      className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">
                        Code
                      </label>
                      <input
                        type="text"
                        value={editingRule.code}
                        onChange={(e) => updateField('code', e.target.value)}
                        className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">
                        Priority
                      </label>
                      <input
                        type="number"
                        value={editingRule.priority}
                        onChange={(e) =>
                          updateField('priority', parseInt(e.target.value) || 0)
                        }
                        className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Keywords (comma-separated)
                    </label>
                    <input
                      type="text"
                      value={arrayToString(editingRule.keywords)}
                      onChange={(e) =>
                        updateField('keywords', stringToArray(e.target.value))
                      }
                      className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Keywords All (comma-separated)
                    </label>
                    <input
                      type="text"
                      value={arrayToString(editingRule.keywordsAll)}
                      onChange={(e) =>
                        updateField(
                          'keywordsAll',
                          stringToArray(e.target.value),
                        )
                      }
                      className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Keywords Exclude (comma-separated)
                    </label>
                    <input
                      type="text"
                      value={arrayToString(editingRule.keywordsExclude)}
                      onChange={(e) =>
                        updateField(
                          'keywordsExclude',
                          stringToArray(e.target.value),
                        )
                      }
                      className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">
                        Raw Types (comma-separated)
                      </label>
                      <input
                        type="text"
                        value={arrayToString(editingRule.rawTypes)}
                        onChange={(e) =>
                          updateField(
                            'rawTypes',
                            stringToArray(e.target.value),
                          )
                        }
                        className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">
                        Canon Types (comma-separated)
                      </label>
                      <input
                        type="text"
                        value={arrayToString(editingRule.canonTypes)}
                        onChange={(e) =>
                          updateField(
                            'canonTypes',
                            stringToArray(e.target.value),
                          )
                        }
                        className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Type Exclude (comma-separated)
                    </label>
                    <input
                      type="text"
                      value={arrayToString(editingRule.typeExclude)}
                      onChange={(e) =>
                        updateField(
                          'typeExclude',
                          stringToArray(e.target.value),
                        )
                      }
                      className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">
                        Template
                      </label>
                      <select
                        value={editingRule.template ?? ''}
                        onChange={(e) =>
                          updateField(
                            'template',
                            e.target.value || undefined,
                          )
                        }
                        className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="">Any</option>
                        <option value="Company">Company</option>
                        <option value="Trust">Trust</option>
                        <option value="Partnership">Partnership</option>
                        <option value="SoleTrader">SoleTrader</option>
                        <option value="XeroHandi">XeroHandi</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">
                        Industries (comma-separated)
                      </label>
                      <input
                        type="text"
                        value={arrayToString(editingRule.industries ?? [])}
                        onChange={(e) =>
                          updateField(
                            'industries',
                            stringToArray(e.target.value),
                          )
                        }
                        className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                  </div>

                  <div className="flex gap-4">
                    <label className="flex items-center gap-1.5 text-sm text-gray-600">
                      <input
                        type="checkbox"
                        checked={editingRule.ownerContext ?? false}
                        onChange={(e) =>
                          updateField('ownerContext', e.target.checked)
                        }
                        className="rounded border-gray-300"
                      />
                      Owner Context
                    </label>
                    <label className="flex items-center gap-1.5 text-sm text-gray-600">
                      <input
                        type="checkbox"
                        checked={editingRule.nameOnly ?? false}
                        onChange={(e) =>
                          updateField('nameOnly', e.target.checked)
                        }
                        className="rounded border-gray-300"
                      />
                      Name Only
                    </label>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Notes
                    </label>
                    <textarea
                      value={editingRule.notes ?? ''}
                      onChange={(e) => updateField('notes', e.target.value)}
                      className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                      rows={3}
                    />
                  </div>

                  <div className="flex gap-2 pt-2">
                    <button
                      onClick={handleSaveEdit}
                      className="px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-md hover:bg-blue-700"
                    >
                      {editingIndex !== null ? 'Update Rule' : 'Add Rule'}
                    </button>
                    <button
                      onClick={() => {
                        setEditingRule(null);
                        setEditingIndex(null);
                      }}
                      className="px-4 py-2 text-sm font-medium border border-gray-300 rounded-md hover:bg-gray-50 text-gray-600"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-center h-full text-sm text-gray-400">
                  Select a rule to edit, or click "+ Add Rule"
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
