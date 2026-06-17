import { X } from 'lucide-react'

interface Props {
  onClose: () => void
}

const SHORTCUTS: { keys: string[]; description: string }[] = [
  { keys: ['N'], description: 'Add a new application' },
  { keys: ['Esc'], description: 'Close the open dialog' },
  { keys: ['?'], description: 'Toggle this shortcuts overlay' },
]

export default function ShortcutsHelpModal({ onClose }: Props) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-2xl w-full max-w-sm shadow-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">Keyboard shortcuts</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
            <X size={18} />
          </button>
        </div>

        <div className="space-y-3">
          {SHORTCUTS.map(({ keys, description }) => (
            <div key={description} className="flex items-center justify-between gap-4">
              <p className="text-sm text-gray-600 dark:text-gray-300">{description}</p>
              <div className="flex gap-1">
                {keys.map(k => (
                  <kbd
                    key={k}
                    className="px-2 py-1 text-xs font-mono font-medium text-gray-600 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md min-w-[1.75rem] text-center"
                  >
                    {k}
                  </kbd>
                ))}
              </div>
            </div>
          ))}
        </div>

        <p className="text-xs text-gray-400 mt-4">Shortcuts are disabled while typing in a text field, except Esc.</p>
      </div>
    </div>
  )
}
