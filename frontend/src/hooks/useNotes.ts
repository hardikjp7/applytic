import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getNotes, createNote, deleteNote } from '../lib/api'
import type { Note } from '../types'
import toast from 'react-hot-toast'

export const notesKey = (appId: string) => ['notes', appId] as const

export function useNotes(appId: string) {
  const qc = useQueryClient()

  const { data: notes = [], isLoading: loading } = useQuery({
    queryKey: notesKey(appId),
    queryFn: () => getNotes(appId),
    enabled: !!appId,
  })

  const addMutation = useMutation({
    mutationFn: (content: string) => createNote(appId, content),
    onSuccess: (note) => {
      qc.setQueryData<Note[]>(notesKey(appId), prev => [...(prev ?? []), note])
      toast.success('Note added')
    },
    onError: () => toast.error('Failed to add note'),
  })

  const removeMutation = useMutation({
    mutationFn: (noteId: string) => deleteNote(appId, noteId),
    onSuccess: (_, noteId) => {
      qc.setQueryData<Note[]>(notesKey(appId), prev =>
        prev?.filter(n => n.noteId !== noteId) ?? []
      )
      toast.success('Note deleted')
    },
    onError: () => toast.error('Failed to delete note'),
  })

  return {
    notes,
    loading,
    submitting: addMutation.isPending,
    addNote: (content: string) => addMutation.mutateAsync(content),
    removeNote: (noteId: string) => removeMutation.mutate(noteId),
    reload: () => qc.invalidateQueries({ queryKey: notesKey(appId) }),
  }
}
