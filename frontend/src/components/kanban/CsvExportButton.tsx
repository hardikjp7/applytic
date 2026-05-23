import { Download } from 'lucide-react'
import { exportToCsv } from '../../lib/csv'
import type { Application } from '../../types'

interface Props {
  applications: Application[]
}

export default function CsvExportButton({ applications }: Props) {
  return (
    <button
      onClick={() => exportToCsv(applications)}
      disabled={applications.length === 0}
      className="flex items-center gap-1.5 px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:border-gray-300 dark:hover:border-gray-600 hover:text-gray-700 dark:hover:text-gray-200 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      title="Export to CSV"
    >
      <Download size={14} />
      <span className="hidden sm:inline">Export</span>
    </button>
  )
}
