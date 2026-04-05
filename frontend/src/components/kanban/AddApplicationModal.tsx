import { useState } from 'react'
import { X } from 'lucide-react'
import type { Application } from '../../types'

interface Props {
  onClose: () => void
  onSave: (data: Omit<Application, 'appId' | 'userId' | 'createdAt' | 'updatedAt'>) => void
}

const defaultForm = {
  company: '', role: '', status: 'applied' as const,
  dateApplied: new Date().toISOString().split('T')[0],
  source: 'linkedin' as const, resumeVersion: 'v1',
  companySize: '' as const, jobDescUrl: '', notes: '',
}

const inp = 'w-full border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400 placeholder:text-gray-400 dark:placeholder:text-gray-500'

export default function AddApplicationModal({ onClose, onSave }: Props) {
  const [form, setForm] = useState(defaultForm)
  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.company || !form.role) return
    onSave(form)
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-900 rounded-2xl w-full max-w-lg shadow-xl border border-gray-100 dark:border-gray-800 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-gray-800 sticky top-0 bg-white dark:bg-gray-900">
          <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">Add application</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Company *</label>
              <input className={inp} value={form.company} onChange={e => set('company', e.target.value)} placeholder="Anthropic" required />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Role *</label>
              <input className={inp} value={form.role} onChange={e => set('role', e.target.value)} placeholder="ML Engineer" required />
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Source</label>
              <select className={inp} value={form.source} onChange={e => set('source', e.target.value)}>
                <option value="linkedin">LinkedIn</option>
                <option value="referral">Referral</option>
                <option value="cold">Cold Apply</option>
                <option value="job-board">Job Board</option>
                <option value="unknown">Other</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Date applied</label>
              <input type="date" className={inp} value={form.dateApplied} onChange={e => set('dateApplied', e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Company size</label>
              <select className={inp} value={form.companySize} onChange={e => set('companySize', e.target.value)}>
                <option value="">Unknown</option>
                <option value="startup">Startup</option>
                <option value="mid">Mid-size</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Resume version</label>
              <input className={inp} value={form.resumeVersion} onChange={e => set('resumeVersion', e.target.value)} placeholder="v1-ml-focused" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Job description URL</label>
            <input className={inp} value={form.jobDescUrl} onChange={e => set('jobDescUrl', e.target.value)} placeholder="https://..." />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Notes</label>
            <textarea className={`${inp} resize-none`} rows={2} value={form.notes} onChange={e => set('notes', e.target.value)} placeholder="Referral from Priya..." />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">Cancel</button>
            <button type="submit" className="px-4 py-2 text-sm font-medium bg-brand-600 text-white rounded-lg hover:bg-brand-800 transition-colors">Add application</button>
          </div>
        </form>
      </div>
    </div>
  )
}
