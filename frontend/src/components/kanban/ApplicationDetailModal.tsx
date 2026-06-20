import { useState } from 'react'
import { X, ExternalLink, Trash2, Save, Clock, Send, MessageSquare } from 'lucide-react'
import type { Application, AppStatus } from '../../types'
import { STATUS_LABELS, STATUS_COLORS, SOURCE_LABELS } from '../../lib/utils'
import { formatDistanceToNow, format } from 'date-fns'
import ConfirmDialog from '../layout/ConfirmDialog'
import { useNotes } from '../../hooks/useNotes'
import ResumeVersionSelect from './ResumeVersionSelect'

interface Props {
  app: Application
  onClose: () => void
  onSave: (appId: string, data: Partial<Application>) => void
  onDelete: (appId: string) => void
  onStatusChange: (appId: string, status: AppStatus) => void
}

const STATUS_OPTIONS: AppStatus[] = ['applied', 'screened', 'interview', 'offer', 'rejected', 'withdrawn']
const inp = 'w-full border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400'

export default function ApplicationDetailModal({ app, onClose, onSave, onDelete, onStatusChange }: Props) {
  const [editing, setEditing] = useState(false)
  const [showConfirmDelete, setShowConfirmDelete] = useState(false)
  const [form, setForm] = useState({
    company: app.company,
    role: app.role,
    source: app.source,
    resumeVersion: app.resumeVersion,
    companySize: app.companySize,
    jobDescUrl: app.jobDescUrl,
    notes: app.notes,
    dateApplied: app.dateApplied,
    followUpDate: app.followUpDate ?? '',   // Bug 1 fix: add followUpDate to form
  })
  const [noteInput, setNoteInput] = useState('')

  // Bug 2 fix: use notes timeline hook (v2.1: React Query backed)
  const { notes, loading: notesLoading, submitting, addNote, removeNote } = useNotes(app.appId)

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  const handleSave = () => {
    onSave(app.appId, {
      ...form,
      // Send null when field is cleared so the backend clears it
      followUpDate: form.followUpDate.trim() === '' ? null : form.followUpDate,
    })
    setEditing(false)
  }

  const handleDelete = () => setShowConfirmDelete(true)

  const handleAddNote = async () => {
    if (!noteInput.trim()) return
    try {
      await addNote(noteInput)
      setNoteInput('')
    } catch {
      // error toast already shown by useNotes - keep the draft so the user can retry
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-2xl w-full max-w-xl shadow-xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-start justify-between px-6 py-4 border-b border-gray-100 dark:border-gray-800 shrink-0">
          <div className="min-w-0 flex-1">
            {editing ? (
              <div className="space-y-2">
                <input className="w-full text-base font-semibold border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-400" value={form.company} onChange={e => set('company', e.target.value)} />
                <input className="w-full text-sm border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-400" value={form.role} onChange={e => set('role', e.target.value)} />
              </div>
            ) : (
              <>
                <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100 truncate">{app.company}</h2>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{app.role}</p>
              </>
            )}
          </div>
          <div className="flex items-center gap-2 ml-4 shrink-0">
            {editing ? (
              <button onClick={handleSave} className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 text-white text-xs font-medium rounded-lg hover:bg-brand-800 transition-colors">
                <Save size={13} /> Save
              </button>
            ) : (
              <button onClick={() => setEditing(true)} className="px-3 py-1.5 text-xs font-medium text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">Edit</button>
            )}
            <button onClick={handleDelete} className="p-1.5 text-gray-300 hover:text-red-400 transition-colors"><Trash2 size={15} /></button>
            <button onClick={onClose} className="p-1.5 text-gray-300 dark:text-gray-600 hover:text-gray-600 dark:hover:text-gray-300"><X size={16} /></button>
          </div>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-6 py-5 space-y-5">
          {/* Status */}
          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">Status</p>
            <div className="flex flex-wrap gap-2">
              {STATUS_OPTIONS.map(s => (
                <button key={s} onClick={() => onStatusChange(app.appId, s)}
                  className={`text-xs px-3 py-1 rounded-full font-medium border transition-all ${
                    app.status === s ? STATUS_COLORS[s] + ' border-transparent ring-2 ring-offset-1 ring-brand-400' : 'text-gray-400 dark:text-gray-500 border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                  }`}>
                  {STATUS_LABELS[s]}
                </button>
              ))}
            </div>
          </div>

          {/* Fields */}
          <div className="grid grid-cols-2 gap-4">
            <Field label="Source" dark>
              {editing ? (
                <select className={inp} value={form.source} onChange={e => set('source', e.target.value)}>
                  <option value="linkedin">LinkedIn</option>
                  <option value="referral">Referral</option>
                  <option value="cold">Cold Apply</option>
                  <option value="job-board">Job Board</option>
                  <option value="unknown">Other</option>
                </select>
              ) : <p className="text-sm text-gray-800 dark:text-gray-200">{SOURCE_LABELS[app.source] ?? app.source}</p>}
            </Field>
            <Field label="Date applied" dark>
              {editing ? <input type="date" className={inp} value={form.dateApplied} onChange={e => set('dateApplied', e.target.value)} />
                : <p className="text-sm text-gray-800 dark:text-gray-200">{app.dateApplied}</p>}
            </Field>
            <Field label="Resume version" dark>
              {editing ? <ResumeVersionSelect className={inp} value={form.resumeVersion} onChange={v => set('resumeVersion', v)} />
                : <p className="text-sm text-gray-800 dark:text-gray-200">{app.resumeVersion || '-'}</p>}
            </Field>
            <Field label="Company size" dark>
              {editing ? (
                <select className={inp} value={form.companySize} onChange={e => set('companySize', e.target.value)}>
                  <option value="">Unknown</option>
                  <option value="startup">Startup</option>
                  <option value="mid">Mid-size</option>
                  <option value="enterprise">Enterprise</option>
                </select>
              ) : <p className="text-sm text-gray-800 dark:text-gray-200">{app.companySize || '-'}</p>}
            </Field>
          </div>

          <Field label="Job description" dark>
            {editing ? <input className={inp} value={form.jobDescUrl} onChange={e => set('jobDescUrl', e.target.value)} placeholder="https://..." />
              : app.jobDescUrl
                ? <a href={app.jobDescUrl} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-sm text-brand-600 dark:text-brand-400 hover:underline"><ExternalLink size={12} /> View posting</a>
                : <p className="text-sm text-gray-400">-</p>}
          </Field>

          {/* Bug 1 fix: Follow-up date field */}
          <Field label="Follow-up date" dark>
            {editing ? (
              <div className="space-y-1">
                <input
                  type="date"
                  className={inp}
                  value={form.followUpDate ?? ''}
                  onChange={e => set('followUpDate', e.target.value)}
                />
                <p className="text-xs text-gray-400">Leave empty to clear the follow-up reminder.</p>
              </div>
            ) : app.followUpDate ? (
              <div className="flex items-center gap-2">
                <p className="text-sm text-gray-800 dark:text-gray-200">{app.followUpDate}</p>
                {new Date(app.followUpDate) <= new Date() && ['applied', 'screened'].includes(app.status) && (
                  <span className="text-xs bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 px-1.5 py-0.5 rounded">Overdue</span>
                )}
              </div>
            ) : (
              <p className="text-sm text-gray-400">-</p>
            )}
          </Field>

          {/* Application-level notes (quick field) */}
          <Field label="Quick notes" dark>
            {editing
              ? <textarea className={`${inp} resize-none`} rows={2} value={form.notes} onChange={e => set('notes', e.target.value)} placeholder="Any quick notes..." />
              : <p className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap">{app.notes || '-'}</p>}
          </Field>

          {/* Bug 2 fix: Notes timeline */}
          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <MessageSquare size={11} /> Notes timeline
            </p>

            {/* Existing notes list */}
            <div className="space-y-2 mb-3">
              {notesLoading ? (
                <div className="space-y-2">
                  {[...Array(2)].map((_, i) => (
                    <div key={i} className="h-12 bg-gray-100 dark:bg-gray-800 rounded-lg animate-pulse" />
                  ))}
                </div>
              ) : notes.length === 0 ? (
                <p className="text-xs text-gray-300 dark:text-gray-600 py-2">No notes yet. Add one below.</p>
              ) : (
                notes.map(note => (
                  <div key={note.noteId} className="group flex items-start gap-2 bg-gray-50 dark:bg-gray-800 rounded-lg px-3 py-2.5">
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">
                        {format(new Date(note.createdAt), 'MMM d, yyyy · h:mm a')}
                      </p>
                      <p className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap">{note.content}</p>
                    </div>
                    <button
                      onClick={() => removeNote(note.noteId)}
                      className="shrink-0 opacity-0 group-hover:opacity-100 text-gray-300 hover:text-red-400 transition-all p-0.5"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))
              )}
            </div>

            {/* Add note input */}
            <div className="flex gap-2">
              <input
                className="flex-1 border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400 placeholder:text-gray-400 dark:placeholder:text-gray-500"
                placeholder="Add a note..."
                value={noteInput}
                onChange={e => setNoteInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleAddNote()}
                disabled={submitting}
              />
              <button
                onClick={handleAddNote}
                disabled={submitting || !noteInput.trim()}
                className="px-3 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-800 disabled:opacity-40 transition-colors"
              >
                <Send size={14} />
              </button>
            </div>
          </div>

          {/* Timeline */}
          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <Clock size={11} /> Status timeline
            </p>
            <div className="space-y-2">
              <TimelineEvent label="Added to tracker" date={app.createdAt} color="bg-gray-200 dark:bg-gray-700" />
              {app.status !== 'applied' && <TimelineEvent label={`Moved to ${STATUS_LABELS[app.status]}`} date={app.updatedAt} color={getDot(app.status)} />}
            </div>
            <p className="text-xs text-gray-300 dark:text-gray-600 mt-2">
              Last updated {formatDistanceToNow(new Date(app.updatedAt), { addSuffix: true })}
            </p>
          </div>
        </div>
      </div>

      {showConfirmDelete && (
        <ConfirmDialog
          title="Delete application"
          message={`Remove ${app.company} - ${app.role}? This cannot be undone.`}
          confirmLabel="Delete"
          danger
          onConfirm={() => { onDelete(app.appId); onClose() }}
          onCancel={() => setShowConfirmDelete(false)}
        />
      )}
    </div>
  )
}

function Field({ label, children, dark }: { label: string; children: React.ReactNode; dark?: boolean }) {
  return (
    <div>
      <p className={`text-xs font-medium mb-1 ${dark ? 'text-gray-400 dark:text-gray-500' : 'text-gray-400'}`}>{label}</p>
      {children}
    </div>
  )
}

function TimelineEvent({ label, date, color }: { label: string; date: string; color: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className={`w-2 h-2 rounded-full shrink-0 ${color}`} />
      <p className="text-xs text-gray-600 dark:text-gray-400">{label}</p>
      <p className="text-xs text-gray-300 dark:text-gray-600 ml-auto">{format(new Date(date), 'MMM d, yyyy')}</p>
    </div>
  )
}

function getDot(status: AppStatus): string {
  const map: Record<AppStatus, string> = {
    applied: 'bg-blue-300', screened: 'bg-purple-300', interview: 'bg-amber-300',
    offer: 'bg-green-400', rejected: 'bg-red-300', withdrawn: 'bg-gray-300',
  }
  return map[status] ?? 'bg-gray-200'
}
