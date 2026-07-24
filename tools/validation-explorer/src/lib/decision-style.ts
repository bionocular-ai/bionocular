import type { Decision } from './types'

// Semantic color per decision outcome. Shared so every view (filter chips,
// dashboard tiles, ...) colors a given decision the same way.

// Full "solid" chip classes - used for an active/selected toggle state.
export const DECISION_ACTIVE_CLASS: Record<Decision, string> = {
  kept: 'border-emerald-600 bg-emerald-600 text-white',
  fixed: 'border-blue-600 bg-blue-600 text-white',
  hitl: 'border-amber-500 bg-amber-500 text-white',
  dropped: 'border-slate-500 bg-slate-500 text-white',
  error: 'border-rose-600 bg-rose-600 text-white',
}

// Solid dot/swatch classes - used as a small color accent next to a decision
// label (e.g. a stat tile) where a full chip fill would be too heavy.
export const DECISION_DOT_CLASS: Record<Decision, string> = {
  kept: 'bg-emerald-600',
  fixed: 'bg-blue-600',
  hitl: 'bg-amber-500',
  dropped: 'bg-slate-500',
  error: 'bg-rose-600',
}
