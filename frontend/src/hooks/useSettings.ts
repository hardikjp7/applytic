import { useState, useEffect, useCallback } from 'react'
import { getSettings, updateSettings } from '../lib/api'
import type { UserSettings } from '../types'
import toast from 'react-hot-toast'

const DEFAULT_SETTINGS: UserSettings = {
  weeklyGoal: 10,
  streakCount: 0,
  streakLastUpdated: null,
}

export function useSettings() {
  const [settings, setSettings] = useState<UserSettings>(DEFAULT_SETTINGS)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      setLoading(true)
      const data = await getSettings()
      setSettings(data)
    } catch {
      // silently fall back to defaults - settings are non-critical
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const saveGoal = async (weeklyGoal: number) => {
    try {
      const updated = await updateSettings({ weeklyGoal })
      setSettings(updated)
      toast.success('Weekly goal updated')
      return updated
    } catch {
      toast.error('Failed to update goal')
    }
  }

  return { settings, loading, saveGoal, reload: load }
}
