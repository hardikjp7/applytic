import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import { getInsights } from '../../lib/api'
import type { Patterns } from '../../types'
import { TrendingUp, Target, Zap } from 'lucide-react'

const COLORS = ['#7f77dd', '#1d9e75', '#ef9f27', '#e24b4a', '#378add', '#d85a30']

export default function AnalyticsDashboard() {
  const [patterns, setPatterns] = useState<Patterns | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getInsights()
      .then(setPatterns)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="p-6 space-y-6">
      <div>
        <div className="h-5 bg-gray-100 rounded w-24 animate-pulse mb-1.5" />
        <div className="h-3.5 bg-gray-100 rounded w-48 animate-pulse" />
      </div>
      <div className="grid grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-white border border-gray-100 rounded-xl p-4 animate-pulse">
            <div className="h-4 w-4 bg-gray-100 rounded mb-2" />
            <div className="h-7 bg-gray-100 rounded w-12 mb-1.5" />
            <div className="h-3 bg-gray-100 rounded w-20" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-6">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-white border border-gray-100 rounded-xl p-5 animate-pulse">
            <div className="h-4 bg-gray-100 rounded w-36 mb-4" />
            <div className="h-48 bg-gray-50 rounded-lg" />
          </div>
        ))}
      </div>
    </div>
  )

  if (!patterns || patterns.summary.total === 0) return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Analytics</h1>
        <p className="text-sm text-gray-400 mt-0.5">Pattern analysis across your applications</p>
      </div>
      <div className="bg-white border border-gray-100 rounded-xl p-12 text-center">
        <div className="w-12 h-12 rounded-full bg-brand-50 flex items-center justify-center mx-auto mb-4">
          <TrendingUp size={20} className="text-brand-600" />
        </div>
        <p className="text-sm font-medium text-gray-700 mb-1">No data to analyse yet</p>
        <p className="text-sm text-gray-400">
          Add at least 5 applications on the Board and your patterns will appear here.
        </p>
      </div>
    </div>
  )

  const sourceData = Object.entries(patterns.breakdowns.bySource).map(([name, d]) => ({
    name, responseRate: d.responseRate, total: d.total,
  }))

  const resumeData = Object.entries(patterns.breakdowns.byResumeVersion).map(([name, d]) => ({
    name, responseRate: d.responseRate, total: d.total,
  }))

  const statusData = Object.entries(patterns.summary.byStatus).map(([name, value]) => ({
    name, value,
  }))

  const velocityData = Object.entries(patterns.velocity).map(([key, count]) => ({
    name: key.replace('week_', 'W-').replace('_ago', ''),
    count,
  })).reverse()

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Analytics</h1>
        <p className="text-sm text-gray-400 mt-0.5">Pattern analysis across your applications</p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total applied', value: patterns.summary.total, icon: Target, color: 'text-brand-600' },
          { label: 'Response rate', value: `${patterns.summary.responseRate}%`, icon: TrendingUp, color: 'text-green-600' },
          { label: 'Interviews', value: patterns.summary.byStatus.interview ?? 0, icon: Zap, color: 'text-amber-600' },
          { label: 'Offers', value: patterns.summary.byStatus.offer ?? 0, icon: Zap, color: 'text-green-600' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-white border border-gray-100 rounded-xl p-4">
            <div className={`${color} mb-2`}><Icon size={16} /></div>
            <p className="text-2xl font-semibold text-gray-900">{value}</p>
            <p className="text-xs text-gray-400 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* Highlights */}
      {(patterns.highlights.bestSource || patterns.highlights.bestResumeVersion) && (
        <div className="bg-brand-50 border border-brand-100 rounded-xl p-4">
          <p className="text-xs font-medium text-brand-600 uppercase tracking-wide mb-2">Top insights</p>
          <div className="grid grid-cols-3 gap-4 text-sm">
            {patterns.highlights.bestSource && (
              <div>
                <p className="text-gray-400 text-xs">Best source</p>
                <p className="font-medium text-brand-800">{patterns.highlights.bestSource.name}</p>
                <p className="text-xs text-brand-600">{patterns.highlights.bestSource.responseRate}% response rate</p>
              </div>
            )}
            {patterns.highlights.bestResumeVersion && (
              <div>
                <p className="text-gray-400 text-xs">Best resume version</p>
                <p className="font-medium text-brand-800">{patterns.highlights.bestResumeVersion.name}</p>
                <p className="text-xs text-brand-600">{patterns.highlights.bestResumeVersion.responseRate}% response rate</p>
              </div>
            )}
            {patterns.highlights.bestCompanySize && (
              <div>
                <p className="text-gray-400 text-xs">Best company size</p>
                <p className="font-medium text-brand-800">{patterns.highlights.bestCompanySize.name}</p>
                <p className="text-xs text-brand-600">{patterns.highlights.bestCompanySize.responseRate}% response rate</p>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-6">
        {/* Response rate by source */}
        <div className="bg-white border border-gray-100 rounded-xl p-5">
          <p className="text-sm font-medium text-gray-700 mb-4">Response rate by source</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={sourceData} barSize={28}>
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} unit="%" />
              <Tooltip formatter={(v) => `${v}%`} />
              <Bar dataKey="responseRate" fill="#7f77dd" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Status breakdown pie */}
        <div className="bg-white border border-gray-100 rounded-xl p-5">
          <p className="text-sm font-medium text-gray-700 mb-4">Status breakdown</p>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={statusData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label>
                {statusData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Legend iconSize={10} wrapperStyle={{ fontSize: 11 }} />
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Resume version performance */}
        <div className="bg-white border border-gray-100 rounded-xl p-5">
          <p className="text-sm font-medium text-gray-700 mb-4">Response rate by resume version</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={resumeData} barSize={28}>
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} unit="%" />
              <Tooltip formatter={(v) => `${v}%`} />
              <Bar dataKey="responseRate" fill="#1d9e75" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Weekly velocity */}
        <div className="bg-white border border-gray-100 rounded-xl p-5">
          <p className="text-sm font-medium text-gray-700 mb-4">Weekly application velocity</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={velocityData} barSize={28}>
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="count" fill="#ef9f27" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
