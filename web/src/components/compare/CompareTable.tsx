'use client';

import { useMemo } from 'react';
import { Check, ChevronDown, Activity, ShieldAlert } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  CompareCell,
  CompareMode,
  CompareRow,
  CompareSelection,
  CompareSortMode,
  CompareTableData,
  TreatmentMeta,
} from '@/types/compare';
import { CompareTableLegend } from './CompareTableLegend';

interface CompareTableProps {
  data: CompareTableData;
  mode: CompareMode;
  title: string;
  sort: CompareSortMode;
  onSortChange: (s: CompareSortMode) => void;
  hideEmpty: boolean;
  onHideEmptyChange: (b: boolean) => void;
  selections: CompareSelection[];
  onToggleSelection: (s: CompareSelection) => void;
  activeMetricKeys: string[];
}

const SORT_LABELS: Record<CompareSortMode, string> = {
  'most-complete': 'Most complete',
  alphabetical: 'Alphabetical',
};

const EFFICACY_SUB_GROUP_ORDER = ['Study', 'PFS', 'OS', 'Response', 'EFS', 'RFS', 'MFS', 'Time-to'];
const SAFETY_SUB_GROUP_ORDER = ['Study', 'AE', 'TEAE', 'TRAE', 'Specific AE', 'Grade 3+ AE', 'Grade 3+ TRAE', 'Grade 3+ TEAE'];

function sortRows(rows: CompareRow[], _mode: CompareSortMode, subGroupOrder: string[]): CompareRow[] {
  const definitionIndex = new Map(rows.map((r, i) => [r.metricKey, i]));
  const copy = [...rows];
  copy.sort((a, b) => {
    const ia = subGroupOrder.indexOf(a.subGroup ?? '');
    const ib = subGroupOrder.indexOf(b.subGroup ?? '');
    const groupDiff = (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
    if (groupDiff !== 0) return groupDiff;
    return definitionIndex.get(a.metricKey)! - definitionIndex.get(b.metricKey)!;
  });
  return copy;
}

function CompareCellView({
  cell,
  selected,
  onClick,
  hasData,
  active,
  columnActive,
}: {
  cell: CompareCell;
  selected: boolean;
  onClick: () => void;
  hasData: boolean;
  active: boolean;
  columnActive: boolean;
}) {
  const isEmpty = cell.status !== 'value';

  if (isEmpty) {
    return (
      <div
        className={cn(
          'w-full h-[44px] flex items-center justify-center',
          columnActive ? 'bg-[var(--brand-accent-light)]' : '',
        )}
        style={columnActive ? undefined : {
          backgroundImage: 'repeating-linear-gradient(135deg, #f8fafc 0 4px, #ffffff 4px 8px)',
        }}
      >
        <span className="text-[11px] text-slate-300 select-none tabular-nums">—</span>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!hasData || !active}
      className={cn(
        'relative group w-full h-[44px] px-3 text-left transition-colors duration-100',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-primary)] focus-visible:ring-inset',
        active && !selected && (columnActive ? 'hover:bg-[var(--brand-primary)]/15' : 'hover:bg-[var(--brand-accent-light)]'),
        active && !selected ? 'cursor-pointer' : !active ? 'cursor-default' : '',
        active && selected && columnActive && 'bg-[var(--brand-primary)] cursor-pointer',
        active && selected && !columnActive && 'bg-[var(--brand-accent-light)] ring-2 ring-[var(--brand-primary)] ring-inset cursor-pointer',
      )}
    >
      <span className={cn(
        'font-mono font-bold text-[13px] tabular-nums',
        active && selected && columnActive ? 'text-white' :
        active && selected ? 'text-[var(--brand-primary)]' :
        columnActive ? 'text-[var(--brand-primary)]' : 'text-slate-800',
      )}>
        {cell.displayValue}
      </span>
      {active && !selected && (
        <span
          className={cn(
            'absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full transition-all duration-100',
            columnActive
              ? 'bg-[var(--brand-primary)]/30 group-hover:bg-[var(--brand-primary)]/70'
              : 'bg-slate-300 group-hover:bg-[var(--brand-primary)]/50',
          )}
        />
      )}
    </button>
  );
}

/* Each section (efficacy / safety) gets its own overflow-x-auto so the table
   sizes to its own content rather than stretching to match the widest sibling.
   This also means sticky-right Cov anchors correctly to each section's viewport. */
function CompareSectionTable({
  rows,
  treatments,
  selectionSet,
  onToggleSelection,
  activeMetricKeys,
  treatmentMeta,
}: {
  rows: CompareRow[];
  treatments: string[];
  selectionSet: Set<string>;
  onToggleSelection: (s: CompareSelection) => void;
  activeMetricKeys: string[];
  treatmentMeta: Record<string, TreatmentMeta>;
}) {
  const orderedRows = useMemo(() => {
    if (activeMetricKeys.length === 0) return rows;
    const active = rows.filter(r => activeMetricKeys.includes(r.metricKey));
    const inactive = rows.filter(r => !activeMetricKeys.includes(r.metricKey));
    return [...active, ...inactive];
  }, [rows, activeMetricKeys]);

  const firstInGroup = new Set<string>();
  let lastGroup = '';
  for (const row of orderedRows) {
    const g = row.subGroup ?? '';
    if (g !== lastGroup) {
      firstInGroup.add(row.metricKey);
      lastGroup = g;
    }
  }

  return (
    <div className="overflow-x-auto">
      <table className="caption-bottom text-sm border-collapse min-w-max">
        <thead>
          <tr className="border-b-2 border-slate-200">
            <th
              className="sticky left-0 z-20 bg-white text-left text-[10px] font-bold text-slate-500 uppercase tracking-[0.12em] px-4 pb-2 pt-2 border-r border-slate-200 align-bottom"
              style={{ width: 180, minWidth: 180 }}
            >
              <span className="invisible block text-[8px] mb-1.5">{'\u00A0'}</span>
              <span className="block leading-tight">Treatment</span>
              <span className="invisible block text-[9px] mt-0.5">{'\u00A0'}</span>
            </th>
            <th
              className="text-left text-[10px] font-bold text-slate-500 uppercase tracking-[0.12em] px-3 pb-2 pt-2 border-l border-slate-200 align-bottom"
              style={{ width: 110, minWidth: 110 }}
            >
              <span className="invisible block text-[8px] mb-1.5">{'\u00A0'}</span>
              <span className="block leading-tight">NCT</span>
              <span className="invisible block text-[9px] mt-0.5">{'\u00A0'}</span>
            </th>
            <th
              className="text-left text-[10px] font-bold text-slate-500 uppercase tracking-[0.12em] px-3 pb-2 pt-2 border-l border-slate-200 align-bottom"
              style={{ width: 120, minWidth: 120 }}
            >
              <span className="invisible block text-[8px] mb-1.5">{'\u00A0'}</span>
              <span className="block leading-tight">Modality</span>
              <span className="invisible block text-[9px] mt-0.5">{'\u00A0'}</span>
            </th>
            <th
              className="text-left text-[10px] font-bold text-slate-500 uppercase tracking-[0.12em] px-3 pb-2 pt-2 border-l border-slate-200 align-bottom"
              style={{ width: 100, minWidth: 100 }}
            >
              <span className="invisible block text-[8px] mb-1.5">{'\u00A0'}</span>
              <span className="block leading-tight">Line</span>
              <span className="invisible block text-[9px] mt-0.5">{'\u00A0'}</span>
            </th>
            {orderedRows.map(row => {
              const isActive = activeMetricKeys.length === 0 || activeMetricKeys.includes(row.metricKey);
              const isFirst = firstInGroup.has(row.metricKey);
              const subGroup = row.subGroup ?? '';
              return (
                <th
                  key={row.metricKey}
                  className={cn(
                    'text-left text-[10px] font-bold uppercase tracking-[0.08em] px-3 pb-2 pt-2 min-w-[110px] align-bottom transition-colors',
                    isFirst ? 'border-l-2 border-l-slate-300' : 'border-l border-slate-100',
                    isActive
                      ? 'text-[var(--brand-primary)] bg-[var(--brand-accent-light)]'
                      : 'text-slate-500 bg-white',
                  )}
                  title={row.label}
                >
                  <span className={cn(
                    'block text-[8px] font-extrabold uppercase tracking-[0.15em] mb-1.5',
                    isFirst && subGroup ? 'text-slate-400' : 'invisible',
                  )}>
                    {subGroup || '\u00A0'}
                  </span>
                  <span className="block truncate leading-tight">{row.label}</span>
                  <span className={cn(
                    'block text-[9px] font-normal normal-case tracking-normal opacity-60 mt-0.5',
                    row.unit ? '' : 'invisible',
                  )}>
                    ({row.unit || '\u00A0'})
                  </span>
                </th>
              );
            })}
            <th
              className="sticky right-0 bg-white text-left text-[10px] font-bold text-slate-700 uppercase tracking-[0.12em] px-3 pb-2 pt-2 border-l border-slate-200 align-bottom"
              style={{ width: 52, minWidth: 52 }}
            >
              <span className="invisible block text-[8px] mb-1.5">{'\u00A0'}</span>
              <span className="block leading-tight">Cov</span>
              <span className="invisible block text-[9px] mt-0.5">{'\u00A0'}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {treatments.map(treatment => {
            const cov = rows.filter(r => r.cells[treatment]?.status === 'value').length;
            return (
              <tr
                key={treatment}
                className="border-b border-slate-100 hover:bg-slate-50/70 transition-colors duration-75"
              >
                <td
                  className="sticky left-0 z-10 bg-white px-4 py-0 border-r border-slate-200 align-top"
                  style={{ width: 180, minWidth: 180 }}
                >
                  <span className="text-[13px] font-semibold text-slate-800 leading-snug block py-3 pr-2 break-words">
                    {treatment}
                  </span>
                </td>
                <td className="px-3 py-0 border-l border-slate-100 align-middle" style={{ width: 110, minWidth: 110 }}>
                  {treatmentMeta[treatment]?.nctId ? (
                    <a
                      href={`https://clinicaltrials.gov/study/${treatmentMeta[treatment].nctId}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[12px] font-mono text-[var(--brand-primary)] hover:underline leading-tight block py-3"
                    >
                      {treatmentMeta[treatment].nctId}
                    </a>
                  ) : (
                    <span className="text-[13px] text-slate-400 leading-tight block py-3">—</span>
                  )}
                </td>
                <td className="px-3 py-0 border-l border-slate-100 align-middle" style={{ width: 120, minWidth: 120 }}>
                  <span className="text-[13px] font-semibold text-slate-800 leading-tight block py-3">
                    {treatmentMeta[treatment]?.modality ?? '—'}
                  </span>
                </td>
                <td className="px-3 py-0 border-l border-slate-100 align-middle" style={{ width: 100, minWidth: 100 }}>
                  <span className="text-[13px] font-semibold text-slate-800 leading-tight block py-3">
                    {treatmentMeta[treatment]?.lineOfTreatment ?? '—'}
                  </span>
                </td>
                {orderedRows.map(row => {
                  const cell = row.cells[treatment];
                  const key = `${treatment}::${row.metricKey}`;
                  const isActive =
                    activeMetricKeys.length === 0 || activeMetricKeys.includes(row.metricKey);
                  const colActive = activeMetricKeys.length > 0 && isActive;
                  const isFirst = firstInGroup.has(row.metricKey);
                  return (
                    <td
                      key={row.metricKey}
                      className={cn(
                        'p-0 align-middle',
                        isFirst ? 'border-l-2 border-l-slate-300' : 'border-l border-slate-100',
                        colActive && 'bg-[var(--brand-accent-light)]',
                      )}
                    >
                      <CompareCellView
                        cell={cell}
                        selected={selectionSet.has(key)}
                        onClick={() =>
                          onToggleSelection({ treatmentName: treatment, metricKey: row.metricKey })
                        }
                        hasData={rows.length > 0}
                        active={isActive}
                        columnActive={colActive}
                      />
                    </td>
                  );
                })}
                <td
                  className="sticky right-0 bg-white px-3 py-0 border-l border-slate-200 align-middle"
                  style={{ width: 52, minWidth: 52 }}
                >
                  <span
                    className={cn(
                      'text-[11px] font-mono tabular-nums block text-center',
                      cov > 0 ? 'text-[var(--brand-primary)] font-bold' : 'text-slate-300',
                    )}
                  >
                    {cov}/{rows.length}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function CompareTable({
  data,
  mode,
  title,
  sort,
  onSortChange,
  hideEmpty,
  onHideEmptyChange,
  selections,
  onToggleSelection,
  activeMetricKeys,
}: CompareTableProps) {
  const { treatments } = data;
  const total = treatments.length;

  const visibleEfficacy = useMemo(() => {
    const sorted = sortRows(data.efficacyRows, sort, EFFICACY_SUB_GROUP_ORDER);
    return hideEmpty ? sorted.filter(r => r.coverage > 0) : sorted;
  }, [data.efficacyRows, sort, hideEmpty]);

  const visibleSafety = useMemo(() => {
    const sorted = sortRows(data.safetyRows, sort, SAFETY_SUB_GROUP_ORDER);
    return hideEmpty ? sorted.filter(r => r.coverage > 0) : sorted;
  }, [data.safetyRows, sort, hideEmpty]);

  const showEfficacy = mode === 'efficacy' || mode === 'all';
  const showSafety = mode === 'safety' || mode === 'all';

  const selectionSet = useMemo(
    () => new Set(selections.map(s => `${s.treatmentName}::${s.metricKey}`)),
    [selections],
  );

  return (
    <div className="flex flex-col h-full w-full bg-white rounded-lg border border-slate-200 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 gap-3 flex-shrink-0">
        <h3 className="text-[15px] font-bold text-slate-900 tracking-tight truncate">{title}</h3>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-[11px] text-slate-400 font-medium">Sort:</span>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:border-slate-300 hover:bg-slate-50 transition-colors">
                {SORT_LABELS[sort]}
                <ChevronDown className="h-3 w-3 opacity-50" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-44">
              {(Object.keys(SORT_LABELS) as CompareSortMode[]).map(key => (
                <DropdownMenuItem
                  key={key}
                  className="text-sm cursor-pointer"
                  onClick={() => onSortChange(key)}
                >
                  <div className="flex items-center justify-between w-full">
                    <span>{SORT_LABELS[key]}</span>
                    {sort === key && <Check className="h-3.5 w-3.5 text-[var(--brand-primary)]" />}
                  </div>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <button
            type="button"
            onClick={() => onHideEmptyChange(!hideEmpty)}
            className={cn(
              'inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-semibold transition-colors',
              hideEmpty
                ? 'border-[var(--brand-primary)] bg-[var(--brand-accent-light)] text-[var(--brand-primary)]'
                : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50',
            )}
          >
            Hide empty: {hideEmpty ? 'On' : 'Off'}
          </button>
        </div>
      </div>

      {/* Sections */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {total === 0 ? (
          <div className="flex items-center justify-center h-full py-16 text-sm text-slate-400 text-center px-6">
            No treatments available.
          </div>
        ) : (
          <div>
            {showEfficacy && visibleEfficacy.length > 0 && (
              <div>
                <div className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-emerald-50/80 to-transparent border-b border-slate-200 sticky top-0 z-30">
                  <Activity className="h-3.5 w-3.5 text-emerald-600 flex-shrink-0" />
                  <span className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-emerald-700">
                    Efficacy Endpoints
                  </span>
                  <span className="text-[10px] text-slate-400">
                    · {visibleEfficacy.length} metric{visibleEfficacy.length !== 1 ? 's' : ''}
                  </span>
                </div>
                <CompareSectionTable
                  rows={visibleEfficacy}
                  treatments={treatments}
                  selectionSet={selectionSet}
                  onToggleSelection={onToggleSelection}
                  activeMetricKeys={activeMetricKeys}
                  treatmentMeta={data.treatmentMeta}
                />
              </div>
            )}
            {showSafety && visibleSafety.length > 0 && (
              <div>
                <div className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-orange-50/80 to-transparent border-b border-slate-200 border-t border-slate-200 sticky top-0 z-30">
                  <ShieldAlert className="h-3.5 w-3.5 text-orange-500 flex-shrink-0" />
                  <span className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-orange-700">
                    Safety
                  </span>
                  <span className="text-[10px] text-slate-400">
                    · {visibleSafety.length} metric{visibleSafety.length !== 1 ? 's' : ''}
                  </span>
                </div>
                <CompareSectionTable
                  rows={visibleSafety}
                  treatments={treatments}
                  selectionSet={selectionSet}
                  onToggleSelection={onToggleSelection}
                  activeMetricKeys={activeMetricKeys}
                  treatmentMeta={data.treatmentMeta}
                />
              </div>
            )}
          </div>
        )}
      </div>

      <CompareTableLegend />
    </div>
  );
}
