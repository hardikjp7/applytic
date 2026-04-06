import { useState } from 'react'
import { X, ExternalLink, Trash2, Save, Clock } from 'lucide-react'
import type { Application, AppStatus } from '../../types'
import { STATUS_LABELS, STATUS_COLORS, SOURCE_LABELS } from '../../lib/utils'
import { formatDistanceToNow, format } from 'date-fns'
import ConfirmDialog from '../layout/ConfirmDialog'

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
    company: app.company, role: app.role, source: app.source,
    resumeVersion: app.resumeVersion, companySize: app.companySize,
    jobDescUrl: app.jobDescUrl, notes: app.notes, dateApplied: app.dateApplied,
  })

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))
  const handleSave = () => { onSave(app.appId, form); setEditing(false) }
  const handleDelete = () => setShowConfirmDelete(true)

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
                  <option value="linkedin">LinkedIn</option><option value="referral">Referral</option>
                  <option value="cold">Cold Apply</option><option value="job-board">Job Board</option><option value="unknown">Other</option>
                </select>
              ) : <p className="text-sm text-gray-800 dark:text-gray-200">{SOURCE_LABELS[app.source] ?? app.source}</p>}
            </Field>
            <Field label="Date applied" dark>
              {editing ? <input type="date" className={inp} value={form.dateApplied} onChange={e => set('dateApplied', e.target.value)} />
                : <p className="text-sm text-gray-800 dark:text-gray-200">{app.dateApplied}</p>}
            </Field>
            <Field label="Resume version" dark>
              {editing ? <input className={inp} value={form.resumeVersion} onChange={e => set('resumeVersion', e.target.value)} />
                : <p className="text-sm text-gray-800 dark:text-gray-200">{app.resumeVersion || '—'}</p>}
            </Field>
            <Field label="Company size" dark>
              {editing ? (
                <select className={inp} value={form.companySize} onChange={e => set('companySize', e.target.value)}>
                  <option value="">Unknown</option><option value="startup">Startup</option><option value="mid">Mid-size</option><option value="enterprise">Enterprise</option>
                </select>
              ) : <p className="text-sm text-gray-800 dark:text-gray-200">{app.companySize || '—'}</p>}
            </Field>
          </div>

          <Field label="Job description" dark>
            {editing ? <input className={inp} value={form.jobDescUrl} onChange={e => set('jobDescUrl', e.target.value)} placeholder="https://..." />
              : app.jobDescUrl
                ? <a href={app.jobDescUrl} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-sm text-brand-600 dark:text-brand-400 hover:underline"><ExternalLink size={12} /> View posting</a>
                : <p className="text-sm text-gray-400">—</p>}
          </Field>

          <Field label="Notes" dark>
            {editing ? <textarea className={`${inp} resize-none`} rows={3} value={form.notes} onChange={e => set('notes', e.target.value)} placeholder="Any notes..." />
              : <p className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap">{app.notes || '—'}</p>}
          </Field>

          {/* Timeline */}
          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <Clock size={11} /> Timeline
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
          message={`Remove ${app.company} — ${app.role}? This cannot be undone.`}
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
