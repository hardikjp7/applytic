import { useState } from 'react'
import { DragDropContext, Droppable, Draggable, DropResult } from '@hello-pangea/dnd'
import { Plus, ExternalLink, Trash2 } from 'lucide-react'
import { useApplications } from '../../hooks/useApplications'
import AddApplicationModal from './AddApplicationModal'
import { STATUS_LABELS, STATUS_COLORS, STATUS_COLUMNS } from '../../lib/utils'
import type { AppStatus, Application } from '../../types'

export default function KanbanBoard() {
  const { applications, loading, create, remove, changeStatus } = useApplications()
  const [showModal, setShowModal] = useState(false)

  const onDragEnd = (result: DropResult) => {
    if (!result.destination) return
    const newStatus = result.destination.droppableId as AppStatus
    const appId = result.draggableId
    const app = applications.find(a => a.appId === appId)
    if (app && app.status !== newStatus) changeStatus(appId, newStatus)
  }

  const byStatus = (status: AppStatus) =>
    applications.filter(a => a.status === status)

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-gray-400 text-sm">Loading...</div>
  )

  return (
    <div className="p-6 h-full">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Board</h1>
          <p className="text-sm text-gray-400 mt-0.5">{applications.length} applications</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-800 transition-colors"
        >
          <Plus size={15} />
          Add application
        </button>
      </div>

      <DragDropContext onDragEnd={onDragEnd}>
        <div className="flex gap-4 overflow-x-auto pb-4">
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
                    {byStatus(status).map((app, index) => (
                      <Draggable key={app.appId} draggableId={app.appId} index={index}>
                        {(provided, snapshot) => (
                          <div
                            ref={provided.innerRef}
                            {...provided.draggableProps}
                            {...provided.dragHandleProps}
                            className={`bg-white rounded-lg p-3 border text-sm transition-shadow ${
                              snapshot.isDragging
                                ? 'shadow-lg border-brand-200'
                                : 'border-gray-100 hover:border-gray-200 hover:shadow-sm'
                            }`}
                          >
                            <div className="flex items-start justify-between gap-1">
                              <div className="min-w-0">
                                <p className="font-medium text-gray-900 truncate">{app.company}</p>
                                <p className="text-xs text-gray-500 truncate mt-0.5">{app.role}</p>
                              </div>
                              <div className="flex gap-1 shrink-0">
                                {app.jobDescUrl && (
                                  <a
                                    href={app.jobDescUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    onClick={e => e.stopPropagation()}
                                    className="text-gray-300 hover:text-brand-600"
                                  >
                                    <ExternalLink size={13} />
                                  </a>
                                )}
                                <button
                                  onClick={() => remove(app.appId)}
                                  className="text-gray-300 hover:text-red-400"
                                >
                                  <Trash2 size={13} />
                                </button>
                              </div>
                            </div>
                            <div className="flex items-center gap-2 mt-2">
                              <span className="text-xs text-gray-400">{app.source}</span>
                              {app.resumeVersion && (
                                <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                                  {app.resumeVersion}
                                </span>
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
    </div>
  )
}
