import { useApplications } from '../hooks/useApplications'
import { STATUS_LABELS, STATUS_COLORS } from '../lib/utils'
import type { AppStatus } from '../types'
import { formatDistanceToNow } from 'date-fns'
import { TrendingUp, Target, Zap, Award, ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'

function SkeletonStatCard() {
  return (
    <div className="bg-white border border-gray-100 rounded-xl p-4 animate-pulse">
      <div className="h-4 w-4 bg-gray-100 rounded mb-2" />
      <div className="h-7 bg-gray-100 rounded w-12 mb-1.5" />
      <div className="h-3 bg-gray-100 rounded w-20" />
    </div>
  )
}

function SkeletonRow() {
  return (
    <div className="flex items-center justify-between animate-pulse">
      <div>
        <div className="h-3.5 bg-gray-100 rounded w-28 mb-1.5" />
        <div className="h-3 bg-gray-100 rounded w-20" />
      </div>
      <div className="h-5 bg-gray-100 rounded-full w-16" />
    </div>
  )
}

export default function Dashboard() {
  const { applications, loading } = useApplications()

  // Loading skeleton
  if (loading) return (
    <div className="p-6 space-y-6">
      <div>
        <div className="h-5 bg-gray-100 rounded w-24 animate-pulse mb-1.5" />
        <div className="h-3.5 bg-gray-100 rounded w-40 animate-pulse" />
      </div>
      <div className="grid grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => <SkeletonStatCard key={i} />)}
      </div>
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 bg-white border border-gray-100 rounded-xl p-5 space-y-4">
          <div className="h-4 bg-gray-100 rounded w-28 animate-pulse" />
          {[...Array(5)].map((_, i) => <SkeletonRow key={i} />)}
        </div>
        <div className="bg-white border border-gray-100 rounded-xl p-5 space-y-3">
          <div className="h-4 bg-gray-100 rounded w-16 animate-pulse" />
          {[...Array(4)].map((_, i) => <div key={i} className="h-5 bg-gray-100 rounded animate-pulse" />)}
        </div>
      </div>
    </div>
  )

  const total = applications.length
  const interviews = applications.filter(a => a.status === 'interview').length
  const offers = applications.filter(a => a.status === 'offer').length
  const responded = applications.filter(a => ['screened', 'interview', 'offer'].includes(a.status)).length
  const responseRate = total > 0 ? Math.round((responded / total) * 100) : 0

  const recent = [...applications]
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
    .slice(0, 8)

  const statusCounts = applications.reduce((acc, a) => {
    acc[a.status] = (acc[a.status] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  // Zero state
  if (total === 0) return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-400 mt-0.5">Your job search at a glance</p>
      </div>
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total applied', value: '0', icon: Target, color: 'text-brand-600' },
          { label: 'Response rate', value: '0%', icon: TrendingUp, color: 'text-green-600' },
          { label: 'Interviews', value: '0', icon: Zap, color: 'text-amber-500' },
          { label: 'Offers', value: '0', icon: Award, color: 'text-green-500' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-white border border-gray-100 rounded-xl p-4">
            <div className={`${color} mb-2`}><Icon size={16} /></div>
            <p className="text-2xl font-semibold text-gray-900">{value}</p>
            <p className="text-xs text-gray-400 mt-0.5">{label}</p>
          </div>
        ))}
      </div>
      <div className="bg-white border border-gray-100 rounded-xl p-10 text-center">
        <div className="w-12 h-12 rounded-full bg-brand-50 flex items-center justify-center mx-auto mb-4">
          <Target size={20} className="text-brand-600" />
        </div>
        <p className="text-sm font-medium text-gray-700 mb-1">Nothing tracked yet</p>
        <p className="text-sm text-gray-400 mb-5">
          Head to the Board and add your first application — your stats will show up here.
        </p>
        <Link
          to="/board"
          className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-800 transition-colors"
        >
          Go to board <ArrowRight size={14} />
        </Link>
      </div>
    </div>
  )

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
          </div>
        </div>
      </div>
    </div>
  )
}
