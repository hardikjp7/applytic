import { useState, useMemo } from 'react'
import { DragDropContext, Droppable, Draggable, DropResult } from '@hello-pangea/dnd'
import { Plus, ExternalLink, Trash2, Search, X, SlidersHorizontal } from 'lucide-react'
import { useApplications } from '../../hooks/useApplications'
import AddApplicationModal from './AddApplicationModal'
import ApplicationDetailModal from './ApplicationDetailModal'
import { STATUS_LABELS, STATUS_COLORS, STATUS_COLUMNS } from '../../lib/utils'
import type { AppStatus, Application } from '../../types'

function SkeletonCard() {
  return (
    <div className="bg-white rounded-lg p-3 border border-gray-100 animate-pulse">
      <div className="h-3.5 bg-gray-100 rounded w-3/4 mb-2" />
      <div className="h-3 bg-gray-100 rounded w-1/2 mb-3" />
      <div className="flex gap-2">
        <div className="h-3 bg-gray-100 rounded w-12" />
        <div className="h-3 bg-gray-100 rounded w-16" />
      </div>
    </div>
  )
}

function EmptyColumn({ status, filtered }: { status: AppStatus; filtered: boolean }) {
  const messages: Record<AppStatus, string> = {
    applied:   'Add your first application',
    screened:  'No screenings yet',
    interview: 'No interviews yet',
    offer:     'Offers will appear here',
    rejected:  'No rejections yet',
    withdrawn: 'No withdrawals',
  }
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <p className="text-xs text-gray-300">{filtered ? 'No matches' : messages[status]}</p>
    </div>
  )
}

export default function KanbanBoard() {
  const { applications, loading, create, update, remove, changeStatus } = useApplications()
  const [showModal, setShowModal] = useState(false)
  const [selectedApp, setSelectedApp] = useState<Application | null>(null)
  const [search, setSearch] = useState('')
  const [filterSource, setFilterSource] = useState('')
  const [showFilters, setShowFilters] = useState(false)

  const onDragEnd = (result: DropResult) => {
    if (!result.destination) return
    const newStatus = result.destination.droppableId as AppStatus
    const appId = result.draggableId
    const app = applications.find(a => a.appId === appId)
    if (app && app.status !== newStatus) changeStatus(appId, newStatus)
  }

  const filtered = useMemo(() => {
    let list = applications
    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter(a =>
        a.company.toLowerCase().includes(q) || a.role.toLowerCase().includes(q)
      )
    }
    if (filterSource) list = list.filter(a => a.source === filterSource)
    return list
  }, [applications, search, filterSource])

  const isFiltering = search.trim() !== '' || filterSource !== ''
  const byStatus = (status: AppStatus) => filtered.filter(a => a.status === status)
  const clearFilters = () => { setSearch(''); setFilterSource('') }

  // Loading skeleton
  if (loading) return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="h-5 bg-gray-100 rounded w-16 animate-pulse mb-1.5" />
          <div className="h-3.5 bg-gray-100 rounded w-28 animate-pulse" />
        </div>
        <div className="h-9 bg-gray-100 rounded-lg w-36 animate-pulse" />
      </div>
      <div className="flex gap-4">
        {STATUS_COLUMNS.map(s => (
          <div key={s} className="flex-shrink-0 w-64">
            <div className="h-5 bg-gray-100 rounded w-20 animate-pulse mb-3" />
            <div className="bg-gray-50 rounded-xl p-2 space-y-2">
              {[...Array(s === 'applied' ? 3 : s === 'rejected' ? 2 : 1)].map((_, i) => (
                <SkeletonCard key={i} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )

  // Zero state
  if (applications.length === 0) return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Board</h1>
          <p className="text-sm text-gray-400 mt-0.5">0 applications</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-800 transition-colors"
        >
          <Plus size={15} /> Add application
        </button>
      </div>
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <div className="w-12 h-12 rounded-full bg-brand-50 flex items-center justify-center mb-4">
          <Plus size={20} className="text-brand-600" />
        </div>
        <p className="text-sm font-medium text-gray-700 mb-1">No applications yet</p>
        <p className="text-sm text-gray-400 mb-5">Start tracking your job search — add your first application.</p>
        <button
          onClick={() => setShowModal(true)}
          className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-800 transition-colors"
        >
          Add first application
        </button>
      </div>
      {showModal && (
        <AddApplicationModal
          onClose={() => setShowModal(false)}
          onSave={(data) => create(data as Omit<Application, 'appId' | 'userId' | 'createdAt' | 'updatedAt'>)}
        />
      )}
    </div>
  )

  return (
    <div className="p-6 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Board</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            {isFiltering ? `${filtered.length} of ${applications.length} applications` : `${applications.length} applications`}
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-800 transition-colors"
        >
          <Plus size={15} /> Add application
        </button>
      </div>

      {/* Search + filter bar */}
      <div className="flex items-center gap-2 mb-4">
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-300" />
          <input
            className="w-full pl-8 pr-8 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-400 bg-white"
            placeholder="Search company or role..."
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
            showFilters || filterSource ? 'border-brand-400 text-brand-600 bg-brand-50' : 'border-gray-200 text-gray-400 hover:border-gray-300'
          }`}
        >
          <SlidersHorizontal size={14} />
          Filter
          {filterSource && <span className="w-1.5 h-1.5 rounded-full bg-brand-600" />}
        </button>
        {isFiltering && (
          <button onClick={clearFilters} className="text-xs text-gray-400 hover:text-gray-600 underline">
            Clear all
          </button>
        )}
      </div>

      {/* Filter panel */}
      {showFilters && (
        <div className="flex items-center gap-3 mb-4 p-3 bg-gray-50 rounded-xl">
          <span className="text-xs font-medium text-gray-400">Source</span>
          <div className="flex gap-2 flex-wrap">
            {['', 'linkedin', 'referral', 'cold', 'job-board', 'unknown'].map(src => (
              <button
                key={src}
                onClick={() => setFilterSource(src)}
                className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                  filterSource === src ? 'bg-brand-600 text-white border-brand-600' : 'border-gray-200 text-gray-500 hover:border-gray-300 bg-white'
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
        <div className="flex gap-4 overflow-x-auto pb-4 flex-1">
          {STATUS_COLUMNS.map(status => (
            <div key={status} className="flex-shrink-0 w-64">
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
                      snapshot.isDraggingOver ? 'bg-brand-50' : 'bg-gray-50'
                    }`}
                  >
                    {byStatus(status).length === 0 && (
                      <EmptyColumn status={status} filtered={isFiltering} />
                    )}
                    {byStatus(status).map((app, index) => (
                      <Draggable key={app.appId} draggableId={app.appId} index={index}>
                        {(provided, snapshot) => (
                          <div
                            ref={provided.innerRef}
                            {...provided.draggableProps}
                            {...provided.dragHandleProps}
                            onClick={() => !snapshot.isDragging && setSelectedApp(app)}
                            className={`bg-white rounded-lg p-3 border text-sm transition-shadow cursor-pointer ${
                              snapshot.isDragging ? 'shadow-lg border-brand-200' : 'border-gray-100 hover:border-brand-200 hover:shadow-sm'
                            }`}
                          >
                            <div className="flex items-start justify-between gap-1">
                              <div className="min-w-0">
                                <p className="font-medium text-gray-900 truncate">{app.company}</p>
                                <p className="text-xs text-gray-500 truncate mt-0.5">{app.role}</p>
                              </div>
                              <div className="flex gap-1 shrink-0">
                                {app.jobDescUrl && (
                                  <a href={app.jobDescUrl} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()} className="text-gray-300 hover:text-brand-600">
                                    <ExternalLink size={13} />
                                  </a>
                                )}
                                <button onClick={e => { e.stopPropagation(); remove(app.appId) }} className="text-gray-300 hover:text-red-400">
                                  <Trash2 size={13} />
                                </button>
                              </div>
                            </div>
                            <div className="flex items-center gap-2 mt-2">
                              <span className="text-xs text-gray-400">{app.source}</span>
                              {app.resumeVersion && (
                                <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">{app.resumeVersion}</span>
                              )}
                            </div>
                            <p className="text-xs text-gray-300 mt-1">{app.dateApplied}</p>
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

      {showModal && (
        <AddApplicationModal
          onClose={() => setShowModal(false)}
          onSave={(data) => create(data as Omit<Application, 'appId' | 'userId' | 'createdAt' | 'updatedAt'>)}
        />
      )}
      {selectedApp && (
        <ApplicationDetailModal
          app={applications.find(a => a.appId === selectedApp.appId) ?? selectedApp}
          onClose={() => setSelectedApp(null)}
          onSave={(appId, data) => update(appId, data)}
          onDelete={(appId) => { remove(appId); setSelectedApp(null) }}
          onStatusChange={(appId, status) => changeStatus(appId, status)}
        />
      )}
    </div>
  )
}
