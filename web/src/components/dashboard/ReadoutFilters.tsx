'use client';

import * as React from 'react';
import { ChevronDown, PanelLeftClose, PanelLeftOpen, Search } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  FILTER_GROUPS,
  facetCounts,
  type FilterGroup,
  type Readout,
  type ReadoutFilters as Filters,
} from '@/lib/readouts';

const TITLES: Record<FilterGroup, string> = {
  phase: 'Phase',
  setting: 'Setting',
  endpoint: 'Endpoint reported',
  target: 'Target',
  modality: 'Modality',
  sponsor: 'Sponsor',
  source: 'Source',
};

const OPTION_LABELS: Record<string, string> = { 'R/R': 'R/R (relapsed/refractory)' };

const SHOWN = 5;

const WIDE = '(min-width: 1024px)';

/**
 * Desktop shows every group open; a phone starts them closed so the cards
 * aren't pushed below the rail. Read on first render: the rail mounts only
 * after the readouts load in the browser, so there is no server render to match.
 */
function useWide() {
  const [wide, setWide] = React.useState(() => window.matchMedia(WIDE).matches);
  React.useEffect(() => {
    const mq = window.matchMedia(WIDE);
    const onChange = (e: MediaQueryListEvent) => setWide(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  return wide;
}

function Group({
  group,
  readouts,
  filters,
  onChange,
  open,
}: {
  group: FilterGroup;
  readouts: Readout[];
  filters: Filters;
  onChange: (f: Filters) => void;
  open: boolean;
}) {
  const [expanded, setExpanded] = React.useState(false);
  const picked = filters.selected[group] ?? [];
  const counts = facetCounts(readouts, filters, group);
  // A ticked option stays listed even when other filters leave it at 0.
  for (const v of picked) if (!counts.has(v)) counts.set(v, 0);
  const options = [...counts];
  if (!options.length) return null;
  const max = Math.max(1, ...counts.values());
  const shown = expanded ? options : options.slice(0, SHOWN);

  const toggle = (value: string) => {
    const next = picked.includes(value) ? picked.filter((v) => v !== value) : [...picked, value];
    onChange({ ...filters, selected: { ...filters.selected, [group]: next } });
  };

  return (
    <details open={open} className="group border-t border-(--brand-border) pt-3.5 pb-2.5">
      {/* Inert on desktop, where every group stays open: no toggle by mouse or keyboard, no tab stop. */}
      <summary
        onClick={open ? (e) => e.preventDefault() : undefined}
        tabIndex={open ? -1 : undefined}
        className="mb-1.5 flex cursor-pointer list-none items-center justify-between text-[13px] font-semibold lg:cursor-default"
      >
        {TITLES[group]}
        <span className="flex items-center gap-2 lg:hidden">
          {picked.length > 0 && <span className="text-xs font-medium text-(--brand-primary)">{picked.length} selected</span>}
          <ChevronDown className="h-4 w-4 text-(--brand-text-muted) transition-transform group-open:rotate-180" aria-hidden="true" />
        </span>
      </summary>
      {shown.map(([value, count]) => (
        <label
          key={value}
          className="grid cursor-pointer grid-cols-[15px_minmax(0,1fr)_auto] items-center gap-x-[9px] py-[3px] text-[13px]"
        >
          <input
            type="checkbox"
            checked={picked.includes(value)}
            onChange={() => toggle(value)}
            className="h-[15px] w-[15px] cursor-pointer accent-(--brand-primary)"
          />
          <span className="min-w-0">{OPTION_LABELS[value] ?? value}</span>
          <span className="text-xs tabular-nums text-[#7F9BA5]">{count}</span>
          <span className="col-start-2 col-end-4 mt-[3px] mb-0.5 h-0.5 bg-[#E3EEEA]">
            <i className="block h-full bg-(--brand-accent)" style={{ width: `${(count / max) * 100}%` }} />
          </span>
        </label>
      ))}
      {options.length > SHOWN && (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="pt-1.5 text-[12.5px] font-medium text-(--brand-primary) hover:underline"
        >
          {expanded ? 'Show fewer' : `Show ${options.length - SHOWN} more`}
        </button>
      )}
    </details>
  );
}

export function ReadoutFilters({
  readouts,
  filters,
  onChange,
  collapsed,
  onCollapsedChange,
}: {
  readouts: Readout[];
  filters: Filters;
  onChange: (f: Filters) => void;
  /** Desktop only: the rail shrinks to its toggle. A phone always shows the filters. */
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
}) {
  const wide = useWide();

  // Cmd/Ctrl+B, as on the agent page's history rail.
  React.useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === 'b' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        onCollapsedChange(!collapsed);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [collapsed, onCollapsedChange]);

  const ToggleIcon = collapsed ? PanelLeftOpen : PanelLeftClose;

  return (
    // Same geometry as the global sidebar it docks against: sticky under the
    // 56px top nav, full remaining height, scrolling on its own.
    <aside
      aria-label="Filters"
      className={cn(
        'flex flex-col lg:sticky lg:top-14 lg:h-[calc(100vh-3.5rem)] lg:overflow-y-auto lg:overscroll-contain lg:pb-8 lg:[scrollbar-width:thin]',
        // Collapsed the rail is a single icon on the page background, as on the
        // agent page: a panel and border would frame an empty column.
        collapsed ? 'lg:px-2' : 'lg:border-r lg:border-(--brand-border) lg:bg-(--brand-surface) lg:px-4',
      )}
    >
      <div className={cn('hidden h-12 shrink-0 items-center lg:flex', collapsed ? 'justify-center' : 'justify-between')}>
        {!collapsed && (
          <span className="font-mono text-[10px] tracking-[0.12em] text-(--brand-text-muted) uppercase">Filters</span>
        )}
        <button
          type="button"
          onClick={() => onCollapsedChange(!collapsed)}
          title={`${collapsed ? 'Show' : 'Hide'} filters (⌘B)`}
          aria-label={`${collapsed ? 'Show' : 'Hide'} filters`}
          aria-expanded={!collapsed}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-(--brand-text-muted) transition hover:bg-(--brand-accent-light) hover:text-(--brand-primary) focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:outline-none"
        >
          <ToggleIcon className="h-4 w-4" aria-hidden />
        </button>
      </div>
      <div className={cn('flex flex-col', collapsed && 'lg:hidden')}>
        <label className="flex items-center gap-2 rounded-lg border border-(--brand-border) bg-(--brand-surface) px-2.5 py-2 text-[13px] focus-within:border-(--brand-primary)">
          <Search className="h-[15px] w-[15px] shrink-0 text-[#7F9BA5]" aria-hidden="true" />
          <input
            type="search"
            value={filters.search}
            onChange={(e) => onChange({ ...filters, search: e.target.value })}
            placeholder="Drug, trial or NCT number"
            aria-label="Search readouts"
            className="w-full min-w-0 bg-transparent outline-none placeholder:text-[#7F9BA5]"
          />
        </label>
        <label className="flex cursor-pointer items-center gap-2.5 pt-3.5 pb-1.5 text-[13px]">
          <button
            type="button"
            role="switch"
            aria-checked={filters.onlyResults}
            onClick={() => onChange({ ...filters, onlyResults: !filters.onlyResults })}
            className={cn(
              'relative h-[17px] w-[30px] shrink-0 rounded-full transition-colors',
              filters.onlyResults ? 'bg-(--brand-primary)' : 'bg-[#B4C9C1]',
            )}
          >
            <span
              className={cn(
                'absolute top-0.5 h-[13px] w-[13px] rounded-full bg-white transition-[left]',
                filters.onlyResults ? 'left-[15px]' : 'left-0.5',
              )}
            />
          </button>
          Only readouts with results
        </label>
        {FILTER_GROUPS.map((g) => (
          <Group key={g} group={g} readouts={readouts} filters={filters} onChange={onChange} open={wide} />
        ))}
      </div>
    </aside>
  );
}
