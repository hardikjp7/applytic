export type AppStatus =
  | 'applied'
  | 'screened'
  | 'interview'
  | 'offer'
  | 'rejected'
  | 'withdrawn'

export interface Application {
  appId: string
  userId: string
  company: string
  role: string
  status: AppStatus
  dateApplied: string
  resumeVersion: string
  source: 'linkedin' | 'referral' | 'cold' | 'job-board' | 'unknown'
  companySize: 'startup' | 'mid' | 'enterprise' | ''
  jobDescUrl: string
  notes: string
  followUpDate: string | null  // v2.0: YYYY-MM-DD, null if not set
  createdAt: string
  updatedAt: string
}

export interface StatusEvent {
  fromStatus: AppStatus | null
  toStatus: AppStatus
  notes: string
  createdAt: string
}

export interface InsightBreakdown {
  total: number
  responseRate: number
}

// v2.1: funnel stage returned by the insights Lambda
export interface FunnelStage {
  stage: string
  count: number
  conversionFromPrev: number
  conversionFromStart: number
}

// v2.1: one data point in the response-rate time series
export interface ResponseRatePoint {
  week: string        // "M/DD" label, e.g. "5/12"
  responseRate: number
  total: number
}

// v2.1: one week of status history (how many apps per status applied that week)
export interface StatusHistoryPoint {
  week: string
  applied: number
  screened: number
  interview: number
  offer: number
  rejected: number
}

export interface Patterns {
  summary: {
    total: number
    byStatus: Record<AppStatus, number>
    responseRate: number
    offerRate: number
  }
  breakdowns: {
    bySource: Record<string, InsightBreakdown>
    byCompanySize: Record<string, InsightBreakdown>
    byResumeVersion: Record<string, InsightBreakdown>
    byRoleLevel: Record<string, InsightBreakdown>
  }
  highlights: {
    bestSource: { name: string; responseRate: number } | null
    bestResumeVersion: { name: string; responseRate: number } | null
    bestCompanySize: { name: string; responseRate: number } | null
  }
  velocity: Record<string, number>
  // v2.1 additions
  funnel: { stages: FunnelStage[] }
  responseRateTimeSeries: ResponseRatePoint[]
  statusHistory: StatusHistoryPoint[]
}

// v2.0: user settings - weekly goal and streak
export interface UserSettings {
  weeklyGoal: number
  streakCount: number
  streakLastUpdated: string | null
}

// v2.0: timestamped note on an application
export interface Note {
  noteId: string
  appId: string
  content: string
  createdAt: string
}
