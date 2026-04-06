import { useState, useMemo } from 'react'
import { DragDropContext, Droppable, Draggable, DropResult } from '@hello-pangea/dnd'
import { Plus, ExternalLink, Trash2, Search, X, SlidersHorizontal } from 'lucide-react'
import { useApplications } from '../../hooks/useApplications'
import AddApplicationModal from './AddApplicationModal'
import ApplicationDetailModal from './ApplicationDetailModal'
import ConfirmDialog from '../layout/ConfirmDialog'
import { STATUS_LABELS, STATUS_COLORS, STATUS_COLUMNS } from '../../lib/utils'
import type { AppStatus, Application } from '../../types'

const STATUS_BORDER: Record<AppStatus, string> = {
  applied:   'border-l-blue-400',
  screened:  'border-l-purple-400',
  interview: 'border-l-amber-400',
  offer:     'border-l-green-400',
  rejected:  'border-l-red-400',
  withdrawn: 'border-l-gray-300',
}

function SkeletonCard() {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg p-3 border border-gray-100 dark:border-gray-800 animate-pulse">
      <div className="h-3.5 bg-gray-100 dark:bg-gray-800 rounded w-3/4 mb-2" />
      <div className="h-3 bg-gray-100 dark:bg-gray-800 rounded w-1/2 mb-3" />
      <div className="flex gap-2">
        <div className="h-3 bg-gray-100 dark:bg-gray-800 rounded w-12" />
        <div className="h-3 bg-gray-100 dark:bg-gray-800 rounded w-16" />
      </div>
    </div>
  )
}

function EmptyColumn({ status, filtered }: { status: AppStatus; filtered: boolean }) {
  const messages: Record<AppStatus, string> = {
    applied: 'Add your first application', screened: 'No screenings yet',
    interview: 'No interviews yet', offer: 'Offers will appear here',
    rejected: 'No rejections yet', withdrawn: 'No withdrawals',
  }
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <p className="text-xs text-gray-300 dark:text-gray-600">{filtered ? 'No matches' : messages[status]}</p>
    </div>
  )
}

export default function KanbanBoard() {
  const { applications, loading, create, update, remove, changeStatus } = useApplications()
  const [showModal, setShowModal] = useState(false)
  const [selectedApp, setSelectedApp] = useState<Application | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<Application | null>(null)
  const [search, setSearch] = useState('')
  const [filterSource, setFilterSource] = useState('')
  const [showFilters, setShowFilters] = useState(false)

  const onDragEnd = (result: DropResult) => {
    if (!result.destination) return
    const newStatus = result.destination.droppableId as AppStatus
    const app = applications.find(a => a.appId === result.draggableId)
    if (app && app.status !== newStatus) changeStatus(result.draggableId, newStatus)
  }

  const filtered = useMemo(() => {
    let list = applications
    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter(a => a.company.toLowerCase().includes(q) || a.role.toLowerCase().includes(q))
    }
    if (filterSource) list = list.filter(a => a.source === filterSource)
    return list
  }, [applications, search, filterSource])

  const isFiltering = search.trim() !== '' || filterSource !== ''
  const byStatus = (status: AppStatus) => filtered.filter(a => a.status === status)
  const clearFilters = () => { setSearch(''); setFilterSource('') }

  if (loading) return (
    <div className="p-4 lg:p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="h-5 bg-gray-100 dark:bg-gray-800 rounded w-16 animate-pulse mb-1.5" />
          <div className="h-3.5 bg-gray-100 dark:bg-gray-800 rounded w-28 animate-pulse" />
        </div>
        <div className="h-9 bg-gray-100 dark:bg-gray-800 rounded-lg w-36 animate-pulse" />
      </div>
      <div className="flex gap-4 overflow-x-auto pb-4">
        {STATUS_COLUMNS.map(s => (
          <div key={s} className="flex-shrink-0 w-60 lg:w-64">
            <div className="h-5 bg-gray-100 dark:bg-gray-800 rounded w-20 animate-pulse mb-3" />
            <div className="bg-gray-50 dark:bg-gray-900 rounded-xl p-2 space-y-2">
              {[...Array(s === 'applied' ? 3 : 1)].map((_, i) => <SkeletonCard key={i} />)}
            </div>
          </div>
        ))}
      </div>
    </div>
  )

  if (applications.length === 0) return (
    <div className="p-4 lg:p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Board</h1>
          <p className="text-sm text-gray-400 mt-0.5">0 applications</p>
        </div>
        <button onClick={() => setShowModal(true)} className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-800 transition-colors">
          <Plus size={15} /> Add application
        </button>
      </div>
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <div className="w-12 h-12 rounded-full bg-brand-50 dark:bg-brand-800/20 flex items-center justify-center mb-4">
          <Plus size={20} className="text-brand-600 dark:text-brand-400" />
        </div>
        <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">No applications yet</p>
        <p className="text-sm text-gray-400 mb-5">Start tracking your job search — add your first application.</p>
        <button onClick={() => setShowModal(true)} className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-800 transition-colors">
          Add first application
        </button>
      </div>
      {showModal && <AddApplicationModal onClose={() => setShowModal(false)} onSave={(data) => create(data as Omit<Application, 'appId' | 'userId' | 'createdAt' | 'updatedAt'>)} />}
    </div>
  )

  return (
    <div className="p-4 lg:p-6 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 shrink-0">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Board</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            {isFiltering ? `${filtered.length} of ${applications.length} applications` : `${applications.length} applications`}
          </p>
        </div>
        <button onClick={() => setShowModal(true)} className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-800 transition-colors">
          <Plus size={15} />
          <span className="hidden sm:inline">Add application</span>
          <span className="sm:hidden">Add</span>
        </button>
      </div>

      {/* Search + filter */}
      <div className="flex items-center gap-2 mb-4 shrink-0">
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-300 dark:text-gray-600" />
          <input
            className="w-full pl-8 pr-8 py-2 text-sm border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-400 placeholder:text-gray-400 dark:placeholder:text-gray-600"
            placeholder="Search..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {search && (
            <button onClick={() => setSearch('')} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-300 hover:text-gray-500">
              <X size={13} />
            </button>
          )}
        </div>
        <button
          onClick={() => setShowFilters(f => !f)}
          className={`flex items-center gap-1.5 px-3 py-2 text-sm border rounded-lg transition-colors ${
            showFilters || filterSource ? 'border-brand-400 text-brand-600 bg-brand-50 dark:bg-brand-800/20 dark:text-brand-400' : 'border-gray-200 dark:border-gray-700 text-gray-400 hover:border-gray-300'
          }`}
        >
          <SlidersHorizontal size={14} />
          <span className="hidden sm:inline">Filter</span>
          {filterSource && <span className="w-1.5 h-1.5 rounded-full bg-brand-600" />}
        </button>
        {isFiltering && (
          <button onClick={clearFilters} className="text-xs text-gray-400 hover:text-gray-600 underline">Clear</button>
        )}
      </div>

      {showFilters && (
        <div className="flex items-center gap-3 mb-4 p-3 bg-gray-50 dark:bg-gray-800 rounded-xl shrink-0 flex-wrap">
          <span className="text-xs font-medium text-gray-400">Source</span>
          <div className="flex gap-2 flex-wrap">
            {['', 'linkedin', 'referral', 'cold', 'job-board', 'unknown'].map(src => (
              <button
                key={src}
                onClick={() => setFilterSource(src)}
                className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                  filterSource === src ? 'bg-brand-600 text-white border-brand-600' : 'border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:border-gray-300 bg-white dark:bg-gray-900'
                }`}
              >
                {src === '' ? 'All' : src === 'job-board' ? 'Job board' : src.charAt(0).toUpperCase() + src.slice(1)}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Columns */}
      <DragDropContext onDragEnd={onDragEnd}>
        <div className="flex gap-3 lg:gap-4 overflow-x-auto pb-4 flex-1">
          {STATUS_COLUMNS.map(status => (
            <div key={status} className="flex-shrink-0 w-60 lg:w-64">
              <div className="flex items-center gap-2 mb-3">
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_COLORS[status]}`}>
                  {STATUS_LABELS[status]}
                </span>
                <span className="text-xs text-gray-400">{byStatus(status).length}</span>
              </div>
              <Droppable droppableId={status}>
                {(provided, snapshot) => (
                  <div
                    ref={provided.innerRef}
                    {...provided.droppableProps}
                    className={`min-h-32 rounded-xl p-2 space-y-2 transition-colors ${
                      snapshot.isDraggingOver ? 'bg-brand-50 dark:bg-brand-900/20' : 'bg-gray-50 dark:bg-gray-900/50'
                    }`}
                  >
                    {byStatus(status).length === 0 && <EmptyColumn status={status} filtered={isFiltering} />}
                    {byStatus(status).map((app, index) => (
                      <Draggable key={app.appId} draggableId={app.appId} index={index}>
                        {(provided, snapshot) => (
                          <div
                            ref={provided.innerRef}
                            {...provided.draggableProps}
                            {...provided.dragHandleProps}
                            onClick={() => !snapshot.isDragging && setSelectedApp(app)}
                            className={`bg-white dark:bg-gray-800 rounded-lg p-3 border-l-4 border border-gray-100 dark:border-gray-700 text-sm transition-shadow cursor-pointer ${STATUS_BORDER[status]} ${
                              snapshot.isDragging ? 'shadow-lg' : 'hover:shadow-sm hover:border-gray-200 dark:hover:border-gray-600'
                            }`}
                          >
                            <div className="flex items-start justify-between gap-1">
                              <div className="min-w-0">
                                <p className="font-medium text-gray-900 dark:text-gray-100 truncate">{app.company}</p>
                                <p className="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">{app.role}</p>
                              </div>
                              <div className="flex gap-1 shrink-0">
                                {app.jobDescUrl && (
                                  <a href={app.jobDescUrl} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()} className="text-gray-300 hover:text-brand-600 dark:hover:text-brand-400">
                                    <ExternalLink size={13} />
                                  </a>
                                )}
                                <button onClick={e => { e.stopPropagation(); setConfirmDelete(app) }} className="text-gray-300 hover:text-red-400">
                                  <Trash2 size={13} />
                                </button>
                              </div>
                            </div>
                            <div className="flex items-center gap-2 mt-2">
                              <span className="text-xs text-gray-400 dark:text-gray-500">{app.source}</span>
                              {app.resumeVersion && (
                                <span className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 px-1.5 py-0.5 rounded">{app.resumeVersion}</span>
                              )}
                            </div>
                            <p className="text-xs text-gray-300 dark:text-gray-600 mt-1">{app.dateApplied}</p>
                          </div>
                        )}
                      </Draggable>
                    ))}
                    {provided.placeholder}
                  </div>
                )}
              </Droppable>
            </div>
          ))}
        </div>
      </DragDropContext>

      {showModal && <AddApplicationModal onClose={() => setShowModal(false)} onSave={(data) => create(data as Omit<Application, 'appId' | 'userId' | 'createdAt' | 'updatedAt'>)} />}
      {selectedApp && (
        <ApplicationDetailModal
          app={applications.find(a => a.appId === selectedApp.appId) ?? selectedApp}
          onClose={() => setSelectedApp(null)}
          onSave={(appId, data) => update(appId, data)}
          onDelete={(appId) => { remove(appId); setSelectedApp(null) }}
          onStatusChange={(appId, status) => changeStatus(appId, status)}
        />
      )}
      {confirmDelete && (
        <ConfirmDialog
          title="Delete application"
          message={`Remove ${confirmDelete.company} — ${confirmDelete.role}? This cannot be undone.`}
          confirmLabel="Delete"
          danger
          onConfirm={() => { remove(confirmDelete.appId); setConfirmDelete(null) }}
          onCancel={() => setConfirmDelete(null)}
        />
      )}
    </div>
  )
}
