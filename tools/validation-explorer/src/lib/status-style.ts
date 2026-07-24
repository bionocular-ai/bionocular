import type { FieldStatus } from './types'

// Status accent mirrors the app's existing semantics: FAIL takes the same
// "critical" red used for the fail-rate chart series; PASS takes the same
// emerald used for a "kept" decision. Keeps red/green meaning consistent
// across the whole tool instead of inventing a third color pairing.

export const STATUS_BADGE_CLASS: Record<FieldStatus, string> = {
  FAIL: 'bg-rose-100 text-rose-700',
  PASS: 'bg-emerald-100 text-emerald-700',
}
