import { useQuery } from '@tanstack/react-query'
import { listResumes } from '../lib/api'

export const RESUMES_KEY = ['resumes'] as const

export interface ResumeOption {
  versionName: string
  filename: string
  uploadedAt: string
}

export function useResumes() {
  const { data: resumes = [], isLoading: loading } = useQuery({
    queryKey: RESUMES_KEY,
    queryFn: listResumes,
    staleTime: 1000 * 60, // 1 minute - resume list changes rarely within a session
  })

  return { resumes, loading }
}
