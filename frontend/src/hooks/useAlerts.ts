import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getAlerts, dismissAlert } from '../lib/api'
import type { PatternAlert } from '../types'

export const ALERTS_KEY = ['alerts'] as const

export function useAlerts() {
  const qc = useQueryClient()

  const { data: alerts = [], isLoading: loading } = useQuery({
    queryKey: ALERTS_KEY,
    queryFn: getAlerts,
    // Alerts don't change during a session unless the digest runs (weekly),
    // so a longer stale time avoids unnecessary refetches on tab focus.
    staleTime: 1000 * 60 * 5,
  })

  const dismissMutation = useMutation({
    mutationFn: dismissAlert,
    // Optimistic update - remove the alert from the list instantly
    onMutate: async (alertId: string) => {
      await qc.cancelQueries({ queryKey: ALERTS_KEY })
      const previous = qc.getQueryData<PatternAlert[]>(ALERTS_KEY)
      qc.setQueryData<PatternAlert[]>(ALERTS_KEY, prev =>
        prev?.filter(a => a.alertId !== alertId) ?? []
      )
      return { previous }
    },
    onError: (_err, _alertId, context) => {
      if (context?.previous) {
        qc.setQueryData(ALERTS_KEY, context.previous)
      }
    },
  })

  return {
    alerts,
    loading,
    dismiss: (alertId: string) => dismissMutation.mutate(alertId),
    reload: () => qc.invalidateQueries({ queryKey: ALERTS_KEY }),
  }
}
