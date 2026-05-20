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
