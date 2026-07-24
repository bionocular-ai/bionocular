import { useRef } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import type { FieldEvalRow } from '@/lib/types'
import { STATUS_BADGE_CLASS } from '@/lib/status-style'
import { cn } from '@/lib/cn'

// Shared grid template so the header row and every body row line up. Widths
// are fixed for the short/structured columns; the two value columns split
// remaining space evenly and truncate independently.
const COLS = 'grid grid-cols-[110px_150px_70px_1fr_1fr] gap-3'
const ROW_HEIGHT = 40

export function FieldEvalsTable({ rows }: { rows: FieldEvalRow[] }) {
  const parentRef = useRef<HTMLDivElement>(null)
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 12,
  })

  if (rows.length === 0) {
    return <div className={cn('p-6 text-slate-400')}>No field evaluations match the current filters.</div>
  }

  return (
    <div className={cn('overflow-hidden rounded-lg border border-slate-200')}>
      <div
        className={cn(
          COLS,
          'border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium uppercase tracking-wide text-slate-500',
        )}
      >
        <div>NCT</div>
        <div>Field</div>
        <div>Status</div>
        <div>Extracted</div>
        <div>Corrected</div>
      </div>
      {/* The scroll container owns its own overflow so a ~10k-row table never
          pushes the page body wider or taller than the viewport - the
          bottom border above doubles as a subtle "more content" affordance
          against the header's shadow-free top edge. */}
      <div ref={parentRef} className={cn('h-[70vh] overflow-auto bg-white')}>
        <div style={{ height: virtualizer.getTotalSize(), position: 'relative', width: '100%' }}>
          {virtualizer.getVirtualItems().map((v) => {
            const r = rows[v.index]
            return (
              <div
                key={v.key}
                data-index={v.index}
                className={cn(
                  COLS,
                  'items-center border-b border-slate-100 px-3 text-sm transition-colors hover:bg-slate-50',
                )}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: v.size,
                  transform: `translateY(${v.start}px)`,
                }}
              >
                <div className={cn('truncate font-mono text-xs text-slate-900')} title={r.nct}>
                  {r.nct}
                </div>
                <div className={cn('truncate text-slate-700')} title={r.fieldName}>
                  {r.fieldName}
                </div>
                <div>
                  <span
                    className={cn(
                      'rounded px-1.5 py-0.5 text-xs font-semibold tracking-wide',
                      STATUS_BADGE_CLASS[r.status],
                    )}
                  >
                    {r.status}
                  </span>
                </div>
                <div className={cn('truncate')} title={r.extracted ?? undefined}>
                  {r.extracted || <em className={cn('text-slate-400 not-italic')}>empty</em>}
                </div>
                <div className={cn('truncate')} title={r.corrected ?? undefined}>
                  {r.corrected || <span className={cn('text-slate-300')}>-</span>}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
