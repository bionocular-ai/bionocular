import { useEffect, useMemo, useState } from 'react'
import { useRuns } from '@/hooks/useRuns'
import { useRun } from '@/hooks/useRun'
import { FilterProvider, useFilter } from '@/state/FilterContext'
import { RunSwitcher } from '@/components/RunSwitcher'
import { FilterBar } from '@/components/FilterBar'
import { Tabs, type TabKey } from '@/components/Tabs'
import { Dashboard } from '@/components/Dashboard'
import { TrialsTable } from '@/components/TrialsTable'
import { FieldEvalsTable } from '@/components/FieldEvalsTable'
import { EmptyState } from '@/components/EmptyState'
import { filterTrials, filterFieldEvals, scopeToTrials } from '@/lib/filters'
import { cn } from '@/lib/cn'

function Explorer({ runId }: { runId: string }) {
  const { data: run, isLoading, isError } = useRun(runId)
  const { filter, reset } = useFilter()
  const [tab, setTab] = useState<TabKey>('dashboard')

  // Switching runs can leave stale facets (e.g. a cancerType absent from the
  // new run) active, silently zeroing out every panel - reset on run change.
  // Deliberately keyed on runId only: `reset` is redefined (new function
  // identity) on every FilterProvider render since it isn't memoized, so
  // including it here would re-run this effect - and re-reset the filter -
  // on every keystroke in the filter bar, not just on a run switch.
  useEffect(() => {
    reset()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- see comment above
  }, [runId])

  const trials = useMemo(() => (run ? filterTrials(run.trials, filter) : []), [run, filter])
  // Field-evals are scoped to the trials that pass the trial-level filter so
  // trial-grain facets (cancerType/score/hasFail/hasMissed) also narrow the
  // field-evals table, not just fieldName/status/search.
  const fieldEvals = useMemo(
    () => (run ? scopeToTrials(filterFieldEvals(run.fieldEvals, filter), trials) : []),
    [run, filter, trials],
  )
  const cancerTypes = useMemo(
    () => (run ? [...new Set(run.trials.flatMap((t) => t.cancerType))].sort() : []),
    [run],
  )

  if (isLoading) {
    return <div className={cn('p-16 text-center text-sm text-slate-400')}>Loading run…</div>
  }
  if (isError || !run) {
    return <EmptyState kind="run-error" />
  }

  return (
    <>
      <FilterBar cancerTypes={cancerTypes} />
      <Tabs active={tab} onChange={setTab} />
      <div className={cn('p-6')}>
        {tab === 'dashboard' && <Dashboard trials={trials} metadata={run.metadata} />}
        {tab === 'trials' && <TrialsTable rows={trials} />}
        {tab === 'fields' && <FieldEvalsTable rows={fieldEvals} />}
      </div>
    </>
  )
}

export default function App() {
  const { data: runs, isLoading, isError } = useRuns()
  const [selected, setSelected] = useState<string | null>(null)
  const runId = selected ?? runs?.[0]?.id ?? null

  return (
    <FilterProvider>
      <div className={cn('min-h-screen bg-white text-slate-900')}>
        <header
          className={cn(
            'sticky top-0 z-20 flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-3',
          )}
        >
          <span className={cn('h-2 w-2 rounded-full bg-teal-600')} aria-hidden="true" />
          <h1 className={cn('text-base font-semibold tracking-tight text-slate-900')}>Validation Explorer</h1>
          <span className={cn('text-xs uppercase tracking-wide text-slate-400')}>LLM extraction QA</span>
          {runs && runs.length > 0 && (
            <div className={cn('ml-auto')}>
              <RunSwitcher runs={runs} selected={runId} onSelect={setSelected} />
            </div>
          )}
        </header>

        {isLoading && <div className={cn('p-16 text-center text-sm text-slate-400')}>Loading runs…</div>}
        {(isError || (runs && runs.length === 0)) && <EmptyState kind="no-manifest" />}
        {runId && <Explorer runId={runId} />}
      </div>
    </FilterProvider>
  )
}
