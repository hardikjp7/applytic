import { useState, useEffect, useCallback } from 'react'
import { getNotes, createNote, deleteNote } from '../lib/api'
import type { Note } from '../types'
import toast from 'react-hot-toast'

export function useNotes(appId: string) {
  const [notes, setNotes] = useState<Note[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(async () => {
    if (!appId) return
    try {
      setLoading(true)
      const data = await getNotes(appId)
      setNotes(data)
    } catch {
      // silently fail - notes are non-critical
    } finally {
      setLoading(false)
    }
  }, [appId])

  useEffect(() => { load() }, [load])

  const addNote = async (content: string) => {
    if (!content.trim()) return
    try {
      setSubmitting(true)
      const note = await createNote(appId, content.trim())
      setNotes(prev => [...prev, note])
      toast.success('Note added')
      return note
    } catch {
      toast.error('Failed to add note')
    } finally {
      setSubmitting(false)
    }
  }

  const removeNote = async (noteId: string) => {
    try {
      await deleteNote(appId, noteId)
      setNotes(prev => prev.filter(n => n.noteId !== noteId))
      toast.success('Note deleted')
    } catch {
      toast.error('Failed to delete note')
    }
  }

  return { notes, loading, submitting, addNote, removeNote, reload: load }
}
