import { api } from './amplify'
import type { Application, AppStatus, Patterns, UserSettings, Note } from '../types'

// ── Applications ──────────────────────────────────────────────────────────────

export const getApplications = async (): Promise<Application[]> => {
  const res = await api.get('/applications')
  return res.data.applications
}

export const createApplication = async (
  data: Omit<Application, 'appId' | 'userId' | 'createdAt' | 'updatedAt'>
): Promise<Application> => {
  const res = await api.post('/applications', data)
  return res.data.application
}

export const updateApplication = async (
  appId: string,
  data: Partial<Application>
): Promise<void> => {
  await api.put(`/applications/${appId}`, data)
}

export const deleteApplication = async (appId: string): Promise<void> => {
  await api.delete(`/applications/${appId}`)
}

export const updateStatus = async (
  appId: string,
  status: AppStatus,
  notes?: string
): Promise<void> => {
  await api.post(`/applications/${appId}/status`, { status, notes })
}

// ── Resume upload ─────────────────────────────────────────────────────────────

export const getUploadUrl = async (
  filename: string,
  versionName: string
): Promise<{ uploadUrl: string; s3Key: string }> => {
  const res = await api.post('/resumes/upload-url', {
    filename,
    versionName,
    contentType: 'application/pdf',
  })
  return res.data
}

export const uploadResumeToS3 = async (
  uploadUrl: string,
  file: File
): Promise<void> => {
  await fetch(uploadUrl, {
    method: 'PUT',
    body: file,
    headers: { 'Content-Type': 'application/pdf' },
  })
}

export const listResumes = async (): Promise<{ versionName: string; filename: string; uploadedAt: string }[]> => {
  const res = await api.get('/resumes/list')
  return res.data.resumes
}

// ── Insights ──────────────────────────────────────────────────────────────────

export const getInsights = async (): Promise<Patterns> => {
  const res = await api.get('/insights')
  return res.data.patterns
}

export const chatWithCoach = async (
  message: string
): Promise<{ reply: string; dataInsufficient?: boolean }> => {
  const res = await api.post('/insights/chat', { message })
  return res.data
}

// ── v2.0: User settings ───────────────────────────────────────────────────────

export const getSettings = async (): Promise<UserSettings> => {
  const res = await api.get('/users/settings')
  return res.data.settings
}

export const updateSettings = async (
  data: Pick<UserSettings, 'weeklyGoal'>
): Promise<UserSettings> => {
  const res = await api.put('/users/settings', data)
  return res.data.settings
}

// ── v2.0: Notes ───────────────────────────────────────────────────────────────

export const getNotes = async (appId: string): Promise<Note[]> => {
  const res = await api.get(`/applications/${appId}/notes`)
  return res.data.notes
}

export const createNote = async (
  appId: string,
  content: string
): Promise<Note> => {
  const res = await api.post(`/applications/${appId}/notes`, { content })
  return res.data.note
}

export const deleteNote = async (
  appId: string,
  noteId: string
): Promise<void> => {
  await api.delete(`/applications/${appId}/notes/${noteId}`)
}
