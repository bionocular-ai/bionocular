import { cn } from '@/lib/cn'

export type TabKey = 'dashboard' | 'trials' | 'fields'

export function Tabs({ active, onChange }: { active: TabKey; onChange: (t: TabKey) => void }) {
  const tabs: { key: TabKey; label: string }[] = [
    { key: 'dashboard', label: 'Dashboard' },
    { key: 'trials', label: 'Trials' },
    { key: 'fields', label: 'Field evals' },
  ]
  return (
    <div className={cn('flex gap-1 border-b border-slate-200 px-4')} role="tablist">
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={active === t.key}
          onClick={() => onChange(t.key)}
          className={cn(
            'border-b-2 px-3 py-2.5 text-sm transition-colors',
            'focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600/50 focus-visible:ring-offset-1',
            active === t.key
              ? 'border-teal-600 font-medium text-slate-900'
              : 'border-transparent text-slate-500 hover:text-slate-800',
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}
