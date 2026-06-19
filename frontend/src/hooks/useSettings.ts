import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getSettings, updateSettings } from '../lib/api'
import type { UserSettings } from '../types'
import toast from 'react-hot-toast'

export const SETTINGS_KEY = ['settings'] as const

const DEFAULT_SETTINGS: UserSettings = {
  weeklyGoal: 10,
  streakCount: 0,
  streakLastUpdated: null,
}

export function useSettings() {
  const qc = useQueryClient()

  const { data: settings = DEFAULT_SETTINGS, isLoading: loading } = useQuery({
    queryKey: SETTINGS_KEY,
    queryFn: getSettings,
  })

  const updateMutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: (updated) => {
      qc.setQueryData(SETTINGS_KEY, updated)
      toast.success('Weekly goal updated')
    },
    onError: () => toast.error('Failed to update goal'),
  })

  return {
    settings,
    loading,
    saveGoal: (weeklyGoal: number) => updateMutation.mutateAsync({ weeklyGoal }),
    reload: () => qc.invalidateQueries({ queryKey: SETTINGS_KEY }),
  }
}
