import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getApplications, createApplication, updateApplication, deleteApplication, updateStatus } from '../lib/api'
import type { Application, AppStatus } from '../types'
import toast from 'react-hot-toast'

export const APPLICATIONS_KEY = ['applications'] as const

export function useApplications() {
  const qc = useQueryClient()

  const { data: applications = [], isLoading: loading } = useQuery({
    queryKey: APPLICATIONS_KEY,
    queryFn: getApplications,
  })

  const createMutation = useMutation({
    mutationFn: createApplication,
    onSuccess: (app) => {
      qc.setQueryData<Application[]>(APPLICATIONS_KEY, prev => [app, ...(prev ?? [])])
      toast.success('Application added')
    },
    onError: () => toast.error('Failed to add application'),
  })

  const updateMutation = useMutation({
    mutationFn: ({ appId, data }: { appId: string; data: Partial<Application> }) =>
      updateApplication(appId, data),
    onSuccess: (_, { appId, data }) => {
      qc.setQueryData<Application[]>(APPLICATIONS_KEY, prev =>
        prev?.map(a => a.appId === appId ? { ...a, ...data } : a) ?? []
      )
      toast.success('Updated')
    },
    onError: () => toast.error('Failed to update'),
  })

  const removeMutation = useMutation({
    mutationFn: deleteApplication,
    onSuccess: (_, appId) => {
      qc.setQueryData<Application[]>(APPLICATIONS_KEY, prev =>
        prev?.filter(a => a.appId !== appId) ?? []
      )
      toast.success('Deleted')
    },
    onError: () => toast.error('Failed to delete'),
  })

  const changeStatusMutation = useMutation({
    mutationFn: ({ appId, status }: { appId: string; status: AppStatus }) =>
      updateStatus(appId, status),
    // Optimistic update: move card instantly, revert on failure
    onMutate: async ({ appId, status }) => {
      await qc.cancelQueries({ queryKey: APPLICATIONS_KEY })
      const previous = qc.getQueryData<Application[]>(APPLICATIONS_KEY)
      qc.setQueryData<Application[]>(APPLICATIONS_KEY, prev =>
        prev?.map(a => a.appId === appId ? { ...a, status } : a) ?? []
      )
      return { previous }
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        qc.setQueryData(APPLICATIONS_KEY, context.previous)
      }
      toast.error('Failed to update status')
    },
  })

  return {
    applications,
    loading,
    create: (data: Omit<Application, 'appId' | 'userId' | 'createdAt' | 'updatedAt'>) =>
      createMutation.mutateAsync(data),
    update: (appId: string, data: Partial<Application>) =>
      updateMutation.mutate({ appId, data }),
    remove: (appId: string) =>
      removeMutation.mutate(appId),
    changeStatus: (appId: string, status: AppStatus) =>
      changeStatusMutation.mutate({ appId, status }),
    reload: () => qc.invalidateQueries({ queryKey: APPLICATIONS_KEY }),
  }
}
