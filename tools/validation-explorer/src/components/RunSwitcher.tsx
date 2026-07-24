import type { ManifestEntry } from '@/lib/api'
import { cn } from '@/lib/cn'

export function RunSwitcher({
  runs,
  selected,
  onSelect,
}: {
  runs: ManifestEntry[]
  selected: string | null
  onSelect: (id: string) => void
}) {
  return (
    <select
      className={cn(
        'rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700',
        'shadow-sm transition-colors hover:border-slate-400',
        'focus:outline-none focus:ring-2 focus:ring-teal-600/50 focus:ring-offset-1',
      )}
      value={selected ?? ''}
      onChange={(e) => onSelect(e.target.value)}
    >
      {runs.map((r) => (
        <option key={r.id} value={r.id}>
          {r.label} ({r.counts.total})
        </option>
      ))}
    </select>
  )
}
