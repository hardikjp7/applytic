import { useState, useRef } from 'react'
import { X, Upload, FileText, AlertCircle, CheckCircle, Download } from 'lucide-react'
import { parseImportCsv, downloadImportTemplate } from '../../lib/csv'
import type { ImportRow, ImportResult } from '../../lib/csv'

interface Props {
  onClose: () => void
  onImport: (rows: ImportRow[]) => Promise<{ imported: number; failed: number }>
}

type Step = 'upload' | 'preview' | 'importing' | 'done'

export default function CsvImportModal({ onClose, onImport }: Props) {
  const [step, setStep] = useState<Step>('upload')
  const [parseResult, setParseResult] = useState<ImportResult | null>(null)
  const [fileName, setFileName] = useState('')
  const [importSummary, setImportSummary] = useState<{ imported: number; failed: number } | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.name.endsWith('.csv')) {
      alert('Please select a .csv file')
      return
    }
    setFileName(file.name)
    const reader = new FileReader()
    reader.onload = (ev) => {
      const text = ev.target?.result as string
      const result = parseImportCsv(text)
      setParseResult(result)
      setStep('preview')
    }
    reader.readAsText(file)
  }

  const handleImport = async () => {
    if (!parseResult || parseResult.valid.length === 0) return
    setStep('importing')
    const summary = await onImport(parseResult.valid)
    setImportSummary(summary)
    setStep('done')
  }

  const reset = () => {
    setStep('upload')
    setParseResult(null)
    setFileName('')
    setImportSummary(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-2xl w-full max-w-lg shadow-xl max-h-[90vh] flex flex-col">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-gray-800 shrink-0">
          <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">Import from CSV</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
            <X size={18} />
          </button>
        </div>

        <div className="overflow-y-auto flex-1 px-6 py-5">

          {/* Step: upload */}
          {step === 'upload' && (
            <div className="space-y-4">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Upload a CSV file to bulk-import applications. Download the template to see the expected format.
              </p>

              <button
                onClick={downloadImportTemplate}
                className="flex items-center gap-2 text-sm text-brand-600 dark:text-brand-400 hover:underline"
              >
                <Download size={14} />
                Download template CSV
              </button>

              <div
                onClick={() => inputRef.current?.click()}
                className="border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-xl p-8 text-center cursor-pointer hover:border-brand-400 transition-colors"
              >
                <Upload size={24} className="mx-auto mb-2 text-gray-400" />
                <p className="text-sm text-gray-500 dark:text-gray-400">Click to select a CSV file</p>
                <p className="text-xs text-gray-300 dark:text-gray-600 mt-1">Required columns: company, role</p>
              </div>
              <input ref={inputRef} type="file" accept=".csv" onChange={handleFile} className="hidden" />
            </div>
          )}

          {/* Step: preview */}
          {step === 'preview' && parseResult && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                <FileText size={14} />
                <span className="truncate">{fileName}</span>
              </div>

              {/* Summary pills */}
              <div className="flex gap-3">
                <div className="flex items-center gap-1.5 px-3 py-1.5 bg-green-50 dark:bg-green-900/20 rounded-lg">
                  <CheckCircle size={13} className="text-green-600 dark:text-green-400" />
                  <span className="text-xs font-medium text-green-700 dark:text-green-300">
                    {parseResult.valid.length} ready to import
                  </span>
                </div>
                {parseResult.errors.length > 0 && (
                  <div className="flex items-center gap-1.5 px-3 py-1.5 bg-red-50 dark:bg-red-900/20 rounded-lg">
                    <AlertCircle size={13} className="text-red-500" />
                    <span className="text-xs font-medium text-red-600 dark:text-red-400">
                      {parseResult.errors.length} row{parseResult.errors.length > 1 ? 's' : ''} skipped
                    </span>
                  </div>
                )}
              </div>

              {/* Valid rows preview */}
              {parseResult.valid.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">Preview</p>
                  <div className="space-y-1.5 max-h-40 overflow-y-auto">
                    {parseResult.valid.slice(0, 5).map((row, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs bg-gray-50 dark:bg-gray-800 rounded-lg px-3 py-2">
                        <span className="font-medium text-gray-800 dark:text-gray-200 truncate">{row.company}</span>
                        <span className="text-gray-400">-</span>
                        <span className="text-gray-500 dark:text-gray-400 truncate">{row.role}</span>
                        <span className="ml-auto shrink-0 text-gray-400">{row.status}</span>
                      </div>
                    ))}
                    {parseResult.valid.length > 5 && (
                      <p className="text-xs text-gray-400 text-center py-1">
                        +{parseResult.valid.length - 5} more
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* Errors */}
              {parseResult.errors.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">Skipped rows</p>
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {parseResult.errors.map((err, i) => (
                      <div key={i} className="text-xs text-red-500 dark:text-red-400 bg-red-50 dark:bg-red-900/10 rounded px-3 py-1.5">
                        Row {err.row}: {err.reason}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {parseResult.valid.length === 0 && (
                <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
                  No valid rows found. Fix the errors and try again.
                </p>
              )}
            </div>
          )}

          {/* Step: importing */}
          {step === 'importing' && (
            <div className="flex flex-col items-center justify-center py-10 gap-3">
              <div className="w-8 h-8 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
              <p className="text-sm text-gray-500 dark:text-gray-400">Importing applications...</p>
            </div>
          )}

          {/* Step: done */}
          {step === 'done' && importSummary && (
            <div className="space-y-4">
              <div className="flex flex-col items-center py-6 gap-3">
                <CheckCircle size={40} className="text-green-500" />
                <p className="text-base font-semibold text-gray-900 dark:text-gray-100">Import complete</p>
              </div>
              <div className="flex gap-3 justify-center">
                <div className="text-center px-6 py-3 bg-green-50 dark:bg-green-900/20 rounded-xl">
                  <p className="text-2xl font-semibold text-green-700 dark:text-green-300">{importSummary.imported}</p>
                  <p className="text-xs text-green-600 dark:text-green-400 mt-0.5">imported</p>
                </div>
                {importSummary.failed > 0 && (
                  <div className="text-center px-6 py-3 bg-red-50 dark:bg-red-900/20 rounded-xl">
                    <p className="text-2xl font-semibold text-red-600 dark:text-red-400">{importSummary.failed}</p>
                    <p className="text-xs text-red-500 dark:text-red-400 mt-0.5">failed</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-100 dark:border-gray-800 flex justify-end gap-2 shrink-0">
          {step === 'upload' && (
            <button onClick={onClose} className="px-4 py-2 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">
              Cancel
            </button>
          )}
          {step === 'preview' && (
            <>
              <button onClick={reset} className="px-4 py-2 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">
                Back
              </button>
              <button
                onClick={handleImport}
                disabled={!parseResult || parseResult.valid.length === 0}
                className="px-4 py-2 text-sm font-medium bg-brand-600 text-white rounded-lg hover:bg-brand-800 disabled:opacity-40 transition-colors"
              >
                Import {parseResult?.valid.length} application{parseResult?.valid.length !== 1 ? 's' : ''}
              </button>
            </>
          )}
          {step === 'done' && (
            <button onClick={onClose} className="px-4 py-2 text-sm font-medium bg-brand-600 text-white rounded-lg hover:bg-brand-800 transition-colors">
              Done
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
