import { useMemo, useState } from 'react'
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
import { filterTrials, filterFieldEvals } from '@/lib/filters'
import { cn } from '@/lib/cn'

function Explorer({ runId }: { runId: string }) {
  const { data: run, isLoading, isError } = useRun(runId)
  const { filter } = useFilter()
  const [tab, setTab] = useState<TabKey>('dashboard')

  const trials = useMemo(() => (run ? filterTrials(run.trials, filter) : []), [run, filter])
  const fieldEvals = useMemo(() => (run ? filterFieldEvals(run.fieldEvals, filter) : []), [run, filter])
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
        {tab === 'dashboard' && <Dashboard trials={trials} fieldEvals={fieldEvals} metadata={run.metadata} />}
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
