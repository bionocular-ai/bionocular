import { useQuery } from '@tanstack/react-query'
import { fetchRun } from '@/lib/api'

export function useRun(id: string | null) {
  return useQuery({
    queryKey: ['run', id],
    queryFn: () => fetchRun(id!),
    enabled: id !== null,
  })
}
