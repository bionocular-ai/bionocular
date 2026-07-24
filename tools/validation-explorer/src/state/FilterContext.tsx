import { createContext, useContext, useState, type ReactNode } from 'react'
import { emptyFilter, type FilterState } from '@/lib/filters'

interface FilterContextValue {
  filter: FilterState
  setFilter: (updater: (f: FilterState) => FilterState) => void
  reset: () => void
}

const FilterContext = createContext<FilterContextValue | null>(null)

export function FilterProvider({ children }: { children: ReactNode }) {
  const [filter, setState] = useState<FilterState>(emptyFilter())
  const setFilter = (updater: (f: FilterState) => FilterState) => setState(updater)
  const reset = () => setState(emptyFilter())
  return <FilterContext.Provider value={{ filter, setFilter, reset }}>{children}</FilterContext.Provider>
}

export function useFilter(): FilterContextValue {
  const ctx = useContext(FilterContext)
  if (!ctx) throw new Error('useFilter must be used within FilterProvider')
  return ctx
}
