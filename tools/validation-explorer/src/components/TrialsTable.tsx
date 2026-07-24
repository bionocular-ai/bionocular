import { Fragment, useState } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from '@tanstack/react-table'
import type { TrialRow } from '@/lib/types'
import { FieldVerdictCard } from './FieldVerdictCard'
import { cn } from '@/lib/cn'
import { DECISION_ACTIVE_CLASS } from '@/lib/decision-style'

const col = createColumnHelper<TrialRow>()
const columns = [
  col.accessor('nct', {
    header: 'NCT',
    cell: (c) => <span className={cn('font-mono text-slate-900')}>{c.getValue()}</span>,
  }),
  col.accessor('decision', {
    header: 'Decision',
    cell: (c) => {
      const decision = c.getValue()
      return (
        <span
          className={cn(
            'inline-block rounded-full border px-2 py-0.5 text-xs font-medium capitalize',
            DECISION_ACTIVE_CLASS[decision],
          )}
        >
          {decision}
        </span>
      )
    },
  }),
  col.accessor('score', {
    header: 'Score',
    cell: (c) => <span className={cn('tabular-nums')}>{c.getValue()?.toFixed(2) ?? '-'}</span>,
  }),
  col.accessor('isValid', {
    header: 'is_valid',
    cell: (c) => (
      <span
        className={cn(
          'inline-block rounded px-1.5 py-0.5 text-xs font-semibold tracking-wide',
          c.getValue() ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700',
        )}
      >
        {c.getValue() ? 'yes' : 'no'}
      </span>
    ),
  }),
  col.accessor('failCount', { header: '# FAIL' }),
  col.accessor('missedCount', { header: '# missed' }),
  col.accessor((r) => r.cancerType.join(', '), { id: 'cancerType', header: 'Cancer type' }),
]

// Chevron rotates to point down when its row is expanded - the same
// affordance used for disclosure widgets everywhere, kept as inline SVG
// since the app has no icon dependency.
function ExpandChevron({ expanded }: { expanded: boolean }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden="true"
      className={cn('h-3.5 w-3.5 shrink-0 text-slate-400 transition-transform', expanded && 'rotate-90')}
    >
      <path
        fillRule="evenodd"
        d="M7.21 14.77a.75.75 0 0 1 .02-1.06L11.168 10 7.23 6.29a.75.75 0 1 1 1.04-1.08l4.5 4.25a.75.75 0 0 1 0 1.08l-4.5 4.25a.75.75 0 0 1-1.06-.02Z"
        clipRule="evenodd"
      />
    </svg>
  )
}

export function TrialsTable({ rows }: { rows: TrialRow[] }) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  if (rows.length === 0) {
    return <div className={cn('p-6 text-slate-400')}>No trials match the current filters.</div>
  }

  return (
    <table className={cn('w-full text-sm')}>
      <thead>
        {table.getHeaderGroups().map((hg) => (
          <tr key={hg.id} className={cn('border-b border-slate-200 text-left')}>
            {hg.headers.map((h) => (
              <th
                key={h.id}
                onClick={h.column.getToggleSortingHandler()}
                className={cn(
                  'cursor-pointer select-none px-3 py-2 text-xs font-medium uppercase tracking-wide text-slate-500',
                  'hover:text-slate-800',
                )}
              >
                {flexRender(h.column.columnDef.header, h.getContext())}
                {{ asc: ' ↑', desc: ' ↓' }[h.column.getIsSorted() as string] ?? ''}
              </th>
            ))}
          </tr>
        ))}
      </thead>
      <tbody>
        {table.getRowModel().rows.map((r) => {
          const isExpanded = expanded === r.original.nct
          return (
            <Fragment key={r.id}>
              <tr
                onClick={() => setExpanded(isExpanded ? null : r.original.nct)}
                className={cn(
                  'cursor-pointer border-b border-slate-100 transition-colors hover:bg-slate-50',
                  isExpanded && 'bg-teal-50/60',
                )}
              >
                {r.getVisibleCells().map((c, i) => (
                  <td key={c.id} className={cn('px-3 py-2')}>
                    <div className={cn('flex items-center gap-1.5')}>
                      {i === 0 && (
                        <button
                          type="button"
                          aria-expanded={isExpanded}
                          aria-label={`Toggle details for ${r.original.nct}`}
                          onClick={(e) => {
                            e.stopPropagation()
                            setExpanded(isExpanded ? null : r.original.nct)
                          }}
                          className={cn(
                            'rounded p-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600/50 focus-visible:ring-offset-1',
                          )}
                        >
                          <ExpandChevron expanded={isExpanded} />
                        </button>
                      )}
                      {flexRender(c.column.columnDef.cell, c.getContext())}
                    </div>
                  </td>
                ))}
              </tr>
              {isExpanded && (
                <tr>
                  <td colSpan={columns.length} className={cn('border-b border-slate-100 bg-slate-50 p-3')}>
                    <div className={cn('grid gap-2 sm:grid-cols-2')}>
                      {r.original.fields.map((f) => (
                        <FieldVerdictCard key={f.fieldName} field={f} />
                      ))}
                      {r.original.fields.length === 0 && (
                        <div className={cn('text-slate-400')}>No field evaluations (deterministic drop).</div>
                      )}
                    </div>
                  </td>
                </tr>
              )}
            </Fragment>
          )
        })}
      </tbody>
    </table>
  )
}
