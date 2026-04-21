/**
 * Chips-plus-search combobox for multi-value string fields.
 *
 * Selected values appear as removable chips. The text input filters a dropdown
 * of suggested options. Press Enter or click a suggestion to add; click × to
 * remove. Free-text values outside the suggestion list are accepted — the
 * suggestions are a hint, not a whitelist.
 */

import { useMemo, useRef, useState } from 'react';

interface TypeMultiSelectProps {
  value: string[];
  options: readonly string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
}

export function TypeMultiSelect({
  value,
  options,
  onChange,
  placeholder,
}: TypeMultiSelectProps) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedSet = useMemo(
    () => new Set(value.map((v) => v.toLowerCase())),
    [value],
  );

  const suggestions = useMemo(() => {
    const q = query.trim().toLowerCase();
    return options.filter(
      (opt) =>
        !selectedSet.has(opt.toLowerCase()) &&
        (q === '' || opt.toLowerCase().includes(q)),
    );
  }, [options, query, selectedSet]);

  const addValue = (raw: string) => {
    const trimmed = raw.trim();
    if (!trimmed) return;
    if (selectedSet.has(trimmed.toLowerCase())) {
      setQuery('');
      return;
    }
    onChange([...value, trimmed]);
    setQuery('');
    setActiveIndex(0);
  };

  const removeAt = (idx: number) => {
    const next = value.slice();
    next.splice(idx, 1);
    onChange(next);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (open && suggestions[activeIndex]) {
        addValue(suggestions[activeIndex]);
      } else if (query.trim()) {
        addValue(query);
      }
    } else if (e.key === 'Backspace' && query === '' && value.length > 0) {
      removeAt(value.length - 1);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setOpen(true);
      setActiveIndex((i) => Math.min(i + 1, Math.max(suggestions.length - 1, 0)));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  const handleBlur = (e: React.FocusEvent<HTMLDivElement>) => {
    if (!containerRef.current?.contains(e.relatedTarget as Node)) {
      setOpen(false);
    }
  };

  return (
    <div className="relative" ref={containerRef} onBlur={handleBlur}>
      <div
        className="w-full min-h-[34px] px-1.5 py-1 flex flex-wrap gap-1 items-center border border-gray-300 rounded-md bg-white focus-within:ring-2 focus-within:ring-blue-500"
        onClick={() => {
          const input = containerRef.current?.querySelector('input');
          input?.focus();
        }}
      >
        {value.map((v, idx) => (
          <span
            key={`${v}-${idx}`}
            className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-blue-50 text-blue-700 border border-blue-200 rounded"
          >
            {v}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                removeAt(idx);
              }}
              className="text-blue-500 hover:text-blue-800 leading-none"
              aria-label={`Remove ${v}`}
            >
              ×
            </button>
          </span>
        ))}
        <input
          type="text"
          value={query}
          placeholder={value.length === 0 ? placeholder : ''}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
            setActiveIndex(0);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          className="flex-1 min-w-[80px] px-1 py-0.5 text-sm outline-none bg-transparent"
        />
      </div>
      {open && suggestions.length > 0 && (
        <ul className="absolute z-10 left-0 right-0 mt-1 max-h-48 overflow-y-auto bg-white border border-gray-200 rounded-md shadow-lg text-sm">
          {suggestions.map((opt, idx) => (
            <li
              key={opt}
              onMouseDown={(e) => {
                e.preventDefault();
                addValue(opt);
              }}
              onMouseEnter={() => setActiveIndex(idx)}
              className={`px-2 py-1 cursor-pointer ${
                idx === activeIndex
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-gray-700'
              }`}
            >
              {opt}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
