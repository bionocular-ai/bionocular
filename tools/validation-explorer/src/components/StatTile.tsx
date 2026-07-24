import { cn } from '@/lib/cn'

export function StatTile({
  label,
  value,
  accentClassName,
}: {
  label: string
  value: string | number
  /** Optional solid color class (e.g. 'bg-emerald-600') for a small identity dot next to the value. */
  accentClassName?: string
}) {
  return (
    <div className={cn('rounded-lg border border-slate-200 bg-white p-4')}>
      <div className={cn('flex items-center gap-2 text-2xl font-semibold text-slate-900')}>
        {accentClassName && (
          <span className={cn('h-2 w-2 shrink-0 rounded-full', accentClassName)} aria-hidden="true" />
        )}
        {value}
      </div>
      <div className={cn('mt-1 text-xs uppercase tracking-wide text-slate-500')}>{label}</div>
    </div>
  )
}
