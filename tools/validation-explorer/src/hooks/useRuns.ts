import { useQuery } from '@tanstack/react-query'
import { fetchRuns } from '@/lib/api'

export function useRuns() {
  return useQuery({ queryKey: ['runs'], queryFn: fetchRuns })
}
