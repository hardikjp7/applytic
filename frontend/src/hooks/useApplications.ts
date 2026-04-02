import { useState, useEffect, useCallback } from 'react'
import { getApplications, createApplication, updateApplication, deleteApplication, updateStatus } from '../lib/api'
import type { Application, AppStatus } from '../types'
import toast from 'react-hot-toast'

export function useApplications() {
  const [applications, setApplications] = useState<Application[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      setLoading(true)
      const data = await getApplications()
      setApplications(data)
    } catch {
      toast.error('Failed to load applications')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const create = async (data: Omit<Application, 'appId' | 'userId' | 'createdAt' | 'updatedAt'>) => {
    try {
      const app = await createApplication(data)
      setApplications(prev => [app, ...prev])
      toast.success('Application added')
      return app
    } catch {
      toast.error('Failed to add application')
    }
  }

  const update = async (appId: string, data: Partial<Application>) => {
    try {
      await updateApplication(appId, data)
      setApplications(prev =>
        prev.map(a => a.appId === appId ? { ...a, ...data } : a)
      )
      toast.success('Updated')
    } catch {
      toast.error('Failed to update')
    }
  }

  const remove = async (appId: string) => {
    try {
      await deleteApplication(appId)
      setApplications(prev => prev.filter(a => a.appId !== appId))
      toast.success('Deleted')
    } catch {
      toast.error('Failed to delete')
    }
  }

  const changeStatus = async (appId: string, status: AppStatus) => {
    try {
      await updateStatus(appId, status)
      setApplications(prev =>
        prev.map(a => a.appId === appId ? { ...a, status } : a)
      )
    } catch {
      toast.error('Failed to update status')
    }
  }

  return { applications, loading, create, update, remove, changeStatus, reload: load }
}
