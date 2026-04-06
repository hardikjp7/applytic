import { useState, useRef, useEffect } from 'react'
import { Upload, FileText, CheckCircle, Trash2, RefreshCw } from 'lucide-react'
import { getUploadUrl, uploadResumeToS3, listResumes } from '../../lib/api'
import toast from 'react-hot-toast'

interface Resume { versionName: string; filename: string; uploadedAt: string }

const inp = 'w-full border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400 placeholder:text-gray-400 dark:placeholder:text-gray-500'

export default function ResumeUpload() {
  const [versionName, setVersionName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [resumes, setResumes] = useState<Resume[]>([])
  const [loadingResumes, setLoadingResumes] = useState(true)
  const inputRef = useRef<HTMLInputElement>(null)

  const fetchResumes = async () => {
    setLoadingResumes(true)
    try {
      const data = await listResumes()
      setResumes(data)
    } catch {
      // silently fail — not critical
    } finally {
      setLoadingResumes(false)
    }
  }

  useEffect(() => { fetchResumes() }, [])

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f && f.type === 'application/pdf') setFile(f)
    else toast.error('Please select a PDF file')
  }

  const handleUpload = async () => {
    if (!file || !versionName.trim()) { toast.error('Add a version name and select a PDF'); return }
    setUploading(true)
    try {
      const { uploadUrl } = await getUploadUrl(file.name, versionName)
      await uploadResumeToS3(uploadUrl, file)
      toast.success(`Resume "${versionName}" uploaded`)
      setFile(null)
      setVersionName('')
      if (inputRef.current) inputRef.current.value = ''
      await fetchResumes()
    } catch { toast.error('Upload failed') } finally { setUploading(false) }
  }

  return (
    <div className="p-4 lg:p-6 max-w-2xl">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Resumes</h1>
        <p className="text-sm text-gray-400 mt-0.5">Upload different versions and track which converts best in Analytics.</p>
      </div>

      {/* Upload card */}
      <div className="bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-xl p-6 space-y-4 mb-6">
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Version name</label>
          <input className={inp} placeholder="e.g. v3-ml-focused, senior-backend-v2" value={versionName} onChange={e => setVersionName(e.target.value)} />
          <p className="text-xs text-gray-400 mt-1">Use the same name when logging an application so analytics can track it.</p>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">PDF file</label>
          <div
            onClick={() => inputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
              file ? 'border-brand-400 bg-brand-50 dark:bg-brand-900/20' : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
            }`}
          >
            {file ? (
              <div className="flex items-center justify-center gap-2 text-brand-600 dark:text-brand-400">
                <FileText size={18} /><span className="text-sm font-medium">{file.name}</span>
              </div>
            ) : (
              <div className="text-gray-400">
                <Upload size={24} className="mx-auto mb-2" />
                <p className="text-sm">Click to select PDF</p>
              </div>
            )}
          </div>
          <input ref={inputRef} type="file" accept="application/pdf" onChange={handleFile} className="hidden" />
        </div>
        <button
          onClick={handleUpload}
          disabled={uploading || !file || !versionName.trim()}
          className="w-full py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-800 disabled:opacity-40 transition-colors"
        >
          {uploading ? 'Uploading...' : 'Upload resume'}
        </button>
      </div>

      {/* Existing resumes from S3 */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
            All uploaded resumes
          </p>
          <button
            onClick={fetchResumes}
            className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
          >
            <RefreshCw size={13} />
          </button>
        </div>

        {loadingResumes ? (
          <div className="space-y-2">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-14 bg-gray-100 dark:bg-gray-800 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : resumes.length === 0 ? (
          <div className="text-center py-8 text-sm text-gray-400">
            No resumes uploaded yet
          </div>
        ) : (
          <div className="space-y-2">
            {resumes.map((r, i) => (
              <div key={i} className="flex items-center gap-3 bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-lg px-4 py-3">
                <CheckCircle size={15} className="text-green-500 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{r.versionName}</p>
                  <p className="text-xs text-gray-400">{r.filename} · {r.uploadedAt}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
