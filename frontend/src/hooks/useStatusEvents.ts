import { useQuery } from '@tanstack/react-query'
import { getStatusEvents } from '../lib/api'

export const statusEventsKey = (appId: string) => ['status-events', appId] as const

export function useStatusEvents(appId: string) {
  const { data: events = [], isLoading: loading, isError } = useQuery({
    queryKey: statusEventsKey(appId),
    queryFn: () => getStatusEvents(appId),
    enabled: !!appId,
  })

  return { events, loading, isError }
}
