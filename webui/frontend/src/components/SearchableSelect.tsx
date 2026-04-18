import { useState, useRef, useEffect, useCallback } from 'react';
import '../styles/SearchableSelect.css';

interface Option {
  value: string;
  label: string;
}

interface SearchableSelectProps {
  options: Option[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  searchable?: boolean;
  disabled?: boolean;
}

function SearchableSelect({ options, value, onChange, placeholder = 'Select...', searchable = false, disabled = false }: SearchableSelectProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [highlightIndex, setHighlightIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const filtered = searchable && query
    ? options.filter(o => o.label.toLowerCase().includes(query.toLowerCase()) || o.value.toLowerCase().includes(query.toLowerCase()))
    : options;

  const selectedLabel = options.find(o => o.value === value)?.label;

  const close = useCallback(() => {
    setOpen(false);
    setQuery('');
    setHighlightIndex(-1);
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) close();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [close]);

  useEffect(() => {
    if (open && searchable && inputRef.current) inputRef.current.focus();
  }, [open, searchable]);

  useEffect(() => {
    if (highlightIndex >= 0 && listRef.current) {
      const el = listRef.current.children[highlightIndex] as HTMLElement | undefined;
      el?.scrollIntoView({ block: 'nearest' });
    }
  }, [highlightIndex]);

  const handleSelect = (val: string) => {
    onChange(val);
    close();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
        e.preventDefault();
        setOpen(true);
      }
      return;
    }
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setHighlightIndex(i => (i + 1) % filtered.length);
        break;
      case 'ArrowUp':
        e.preventDefault();
        setHighlightIndex(i => (i <= 0 ? filtered.length - 1 : i - 1));
        break;
      case 'Enter':
        e.preventDefault();
        if (highlightIndex >= 0 && highlightIndex < filtered.length) handleSelect(filtered[highlightIndex].value);
        break;
      case 'Escape':
        e.preventDefault();
        close();
        break;
    }
  };

  return (
    <div
      className={`ss-container${open ? ' ss-open' : ''}${disabled ? ' ss-disabled' : ''}`}
      ref={containerRef}
      onKeyDown={handleKeyDown}
    >
      <button
        type="button"
        className="ss-trigger"
        onClick={() => !disabled && setOpen(prev => !prev)}
        tabIndex={0}
        aria-haspopup="listbox"
        aria-expanded={open}
        disabled={disabled}
      >
        <span className={`ss-trigger-text${!value ? ' ss-placeholder' : ''}`}>
          {selectedLabel || placeholder}
        </span>
        <svg className="ss-chevron" width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <div className="ss-dropdown">
          {searchable && (
            <div className="ss-search-wrap">
              <input
                ref={inputRef}
                className="ss-search"
                type="text"
                value={query}
                onChange={e => { setQuery(e.target.value); setHighlightIndex(0); }}
                placeholder="Search..."
                autoComplete="off"
              />
            </div>
          )}
          <div className="ss-list" ref={listRef} role="listbox">
            {filtered.length === 0 ? (
              <div className="ss-empty">No results</div>
            ) : (
              filtered.map((opt, idx) => (
                <div
                  key={opt.value}
                  className={`ss-option${opt.value === value ? ' ss-selected' : ''}${idx === highlightIndex ? ' ss-highlighted' : ''}`}
                  role="option"
                  aria-selected={opt.value === value}
                  onMouseEnter={() => setHighlightIndex(idx)}
                  onClick={() => handleSelect(opt.value)}
                >
                  {opt.label}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default SearchableSelect;
