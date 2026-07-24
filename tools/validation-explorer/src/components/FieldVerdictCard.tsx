import type { FieldEvalRow } from '@/lib/types'
import { cn } from '@/lib/cn'

// Status accent mirrors the app's existing semantics: FAIL takes the same
// "critical" red used for the fail-rate chart series; PASS takes the same
// emerald used for a "kept" decision. Keeps red/green meaning consistent
// across the whole tool instead of inventing a third color pairing here.
const STATUS_BADGE_CLASS: Record<FieldEvalRow['status'], string> = {
  FAIL: 'bg-rose-100 text-rose-700',
  PASS: 'bg-emerald-100 text-emerald-700',
}

export function FieldVerdictCard({ field }: { field: FieldEvalRow }) {
  const hasCorrection = field.corrected !== null && field.corrected !== field.extracted

  return (
    <div className={cn('rounded-lg border border-slate-200 bg-white p-3 text-sm')}>
      <div className={cn('flex items-center justify-between gap-2')}>
        <span className={cn('font-medium text-slate-900')}>{field.fieldName}</span>
        <span
          className={cn(
            'rounded px-1.5 py-0.5 text-xs font-semibold tracking-wide',
            STATUS_BADGE_CLASS[field.status],
          )}
        >
          {field.status}
        </span>
      </div>

      {/* Redline: extracted -> corrected as a single tracked-change line, since
          this tool exists to audit LLM output against the corrected ground
          truth - showing both values inline makes the diff legible at a glance. */}
      <div className={cn('mt-2 flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5')}>
        <span className={cn(hasCorrection ? 'text-slate-400 line-through' : 'text-slate-700')}>
          {field.extracted || <em className={cn('text-slate-400 not-italic')}>empty</em>}
        </span>
        {hasCorrection && (
          <>
            <span className={cn('text-slate-400')} aria-hidden="true">
              &rarr;
            </span>
            <span className={cn('font-medium text-slate-900')}>{field.corrected}</span>
          </>
        )}
      </div>

      {field.issue && <div className={cn('mt-1.5 text-rose-700')}>{field.issue}</div>}
      {field.justification && <div className={cn('mt-1 text-slate-500')}>{field.justification}</div>}
      {field.evidence && (
        <blockquote className={cn('mt-1.5 border-l-2 border-slate-300 pl-2 italic text-slate-500')}>
          {field.evidence}
        </blockquote>
      )}
    </div>
  )
}
