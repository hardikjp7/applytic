import { useApplications } from '../../hooks/useApplications'
import { STATUS_LABELS, STATUS_COLORS } from '../../lib/utils'
import type { AppStatus } from '../../types'
import { formatDistanceToNow } from 'date-fns'
import { TrendingUp, Target, Zap, Award } from 'lucide-react'

export default function Dashboard() {
  const { applications, loading } = useApplications()

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-gray-400 text-sm">Loading...</div>
  )

  const total = applications.length
  const interviews = applications.filter(a => a.status === 'interview').length
  const offers = applications.filter(a => a.status === 'offer').length
  const responded = applications.filter(a =>
    ['screened', 'interview', 'offer'].includes(a.status)
  ).length
  const responseRate = total > 0 ? Math.round((responded / total) * 100) : 0

  const recent = [...applications]
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
    .slice(0, 8)

  const statusCounts = applications.reduce((acc, a) => {
    acc[a.status] = (acc[a.status] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-400 mt-0.5">Your job search at a glance</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total applied', value: total, icon: Target, color: 'text-brand-600' },
          { label: 'Response rate', value: `${responseRate}%`, icon: TrendingUp, color: 'text-green-600' },
          { label: 'Interviews', value: interviews, icon: Zap, color: 'text-amber-500' },
          { label: 'Offers', value: offers, icon: Award, color: 'text-green-500' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-white border border-gray-100 rounded-xl p-4">
            <div className={`${color} mb-2`}><Icon size={16} /></div>
            <p className="text-2xl font-semibold text-gray-900">{value}</p>
            <p className="text-xs text-gray-400 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Recent activity */}
        <div className="col-span-2 bg-white border border-gray-100 rounded-xl p-5">
          <p className="text-sm font-medium text-gray-700 mb-4">Recent activity</p>
          {recent.length === 0 ? (
            <p className="text-sm text-gray-400 py-8 text-center">
              No applications yet — add your first one on the Board page.
            </p>
          ) : (
            <div className="space-y-3">
              {recent.map(app => (
                <div key={app.appId} className="flex items-center justify-between">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate">{app.company}</p>
                    <p className="text-xs text-gray-400 truncate">{app.role}</p>
                  </div>
                  <div className="flex items-center gap-3 shrink-0 ml-4">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[app.status as AppStatus]}`}>
                      {STATUS_LABELS[app.status as AppStatus]}
                    </span>
                    <span className="text-xs text-gray-300 w-20 text-right">
                      {formatDistanceToNow(new Date(app.updatedAt), { addSuffix: true })}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Status breakdown */}
        <div className="bg-white border border-gray-100 rounded-xl p-5">
          <p className="text-sm font-medium text-gray-700 mb-4">By status</p>
          <div className="space-y-3">
            {Object.entries(statusCounts).map(([status, count]) => (
              <div key={status} className="flex items-center justify-between">
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[status as AppStatus]}`}>
                  {STATUS_LABELS[status as AppStatus]}
                </span>
                <div className="flex items-center gap-2">
                  <div className="w-20 bg-gray-100 rounded-full h-1.5">
                    <div
                      className="bg-brand-400 h-1.5 rounded-full"
                      style={{ width: `${total > 0 ? (count / total) * 100 : 0}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-500 w-4 text-right">{count}</span>
                </div>
              </div>
            ))}
            {Object.keys(statusCounts).length === 0 && (
              <p className="text-xs text-gray-400 text-center py-4">No data yet</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
