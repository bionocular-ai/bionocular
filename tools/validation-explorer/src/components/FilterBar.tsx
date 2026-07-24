import { useFilter } from '@/state/FilterContext'
import { cn } from '@/lib/cn'
import type { Decision, FieldStatus } from '@/lib/types'

const DECISIONS: Decision[] = ['kept', 'hitl', 'dropped', 'fixed', 'error']
const FIELDS = ['treatment_name', 'modality', 'biomarker', 'stage', 'line_of_therapy', 'previous_treatment_criteria']

// Semantic color per decision outcome, used only for the active state of the toggle chips.
const DECISION_ACTIVE_CLASS: Record<Decision, string> = {
  kept: 'border-emerald-600 bg-emerald-600 text-white',
  fixed: 'border-blue-600 bg-blue-600 text-white',
  hitl: 'border-amber-500 bg-amber-500 text-white',
  dropped: 'border-slate-500 bg-slate-500 text-white',
  error: 'border-rose-600 bg-rose-600 text-white',
}

const selectClass = cn(
  'rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-700 shadow-sm',
  'transition-colors hover:border-slate-400',
  'focus:outline-none focus:ring-2 focus:ring-teal-600/50 focus:ring-offset-1',
)

export function FilterBar({ cancerTypes }: { cancerTypes: string[] }) {
  const { filter, setFilter, reset } = useFilter()

  const toggleDecision = (d: Decision) =>
    setFilter((f) => {
      const next = new Set(f.decisions)
      next.has(d) ? next.delete(d) : next.add(d)
      return { ...f, decisions: next }
    })

  return (
    <div
      className={cn(
        'flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-slate-200 bg-white px-4 py-3',
      )}
    >
      <div className={cn('flex items-center gap-1.5')}>
        {DECISIONS.map((d) => (
          <button
            key={d}
            onClick={() => toggleDecision(d)}
            className={cn(
              'rounded-full border px-2.5 py-1 text-xs font-medium capitalize transition-colors',
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600/50 focus-visible:ring-offset-1',
              filter.decisions.has(d)
                ? DECISION_ACTIVE_CLASS[d]
                : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50',
            )}
          >
            {d}
          </button>
        ))}
      </div>

      <div className={cn('h-5 w-px bg-slate-200')} />

      <div className={cn('flex items-center gap-1.5 text-xs text-slate-500')}>
        <span className={cn('tabular-nums')}>score</span>
        <input
          type="number"
          min={0}
          max={1}
          step={0.05}
          value={filter.scoreMin}
          onChange={(e) => setFilter((f) => ({ ...f, scoreMin: Number(e.target.value) }))}
          className={cn(selectClass, 'w-16 tabular-nums')}
          aria-label="Minimum score"
        />
        <span>-</span>
        <input
          type="number"
          min={0}
          max={1}
          step={0.05}
          value={filter.scoreMax}
          onChange={(e) => setFilter((f) => ({ ...f, scoreMax: Number(e.target.value) }))}
          className={cn(selectClass, 'w-16 tabular-nums')}
          aria-label="Maximum score"
        />
      </div>

      <div className={cn('h-5 w-px bg-slate-200')} />

      <input
        placeholder="Search NCT / value"
        value={filter.search}
        onChange={(e) => setFilter((f) => ({ ...f, search: e.target.value }))}
        className={cn(selectClass, 'w-48 font-mono')}
      />

      <select
        value={filter.fieldName ?? ''}
        onChange={(e) => setFilter((f) => ({ ...f, fieldName: e.target.value || null }))}
        className={selectClass}
      >
        <option value="">any field</option>
        {FIELDS.map((x) => (
          <option key={x} value={x}>
            {x}
          </option>
        ))}
      </select>

      <select
        value={filter.status ?? ''}
        onChange={(e) => setFilter((f) => ({ ...f, status: (e.target.value || null) as FieldStatus | null }))}
        className={selectClass}
      >
        <option value="">any status</option>
        <option value="PASS">PASS</option>
        <option value="FAIL">FAIL</option>
      </select>

      <select
        value={filter.cancerType ?? ''}
        onChange={(e) => setFilter((f) => ({ ...f, cancerType: e.target.value || null }))}
        className={selectClass}
      >
        <option value="">any cancer type</option>
        {cancerTypes.map((x) => (
          <option key={x} value={x}>
            {x}
          </option>
        ))}
      </select>

      <div className={cn('h-5 w-px bg-slate-200')} />

      <label className={cn('flex items-center gap-1.5 text-xs text-slate-600')}>
        <input
          type="checkbox"
          checked={filter.hasFail}
          onChange={(e) => setFilter((f) => ({ ...f, hasFail: e.target.checked }))}
          className={cn('accent-teal-600')}
        />
        has FAIL
      </label>
      <label className={cn('flex items-center gap-1.5 text-xs text-slate-600')}>
        <input
          type="checkbox"
          checked={filter.hasMissed}
          onChange={(e) => setFilter((f) => ({ ...f, hasMissed: e.target.checked }))}
          className={cn('accent-teal-600')}
        />
        has missed
      </label>

      <button
        onClick={reset}
        className={cn(
          'ml-auto rounded-md px-2.5 py-1.5 text-xs font-medium text-slate-500 transition-colors',
          'hover:bg-slate-100 hover:text-slate-900',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600/50 focus-visible:ring-offset-1',
        )}
      >
        Reset
      </button>
    </div>
  )
}
