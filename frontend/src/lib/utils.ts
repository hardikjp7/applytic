import type { AppStatus, Application } from '../types'

export const STATUS_LABELS: Record<AppStatus, string> = {
  applied:   'Applied',
  screened:  'Screened',
  interview: 'Interview',
  offer:     'Offer',
  rejected:  'Rejected',
  withdrawn: 'Withdrawn',
}

export const STATUS_COLORS: Record<AppStatus, string> = {
  applied:   'bg-blue-100 text-blue-800',
  screened:  'bg-purple-100 text-purple-800',
  interview: 'bg-amber-100 text-amber-800',
  offer:     'bg-green-100 text-green-800',
  rejected:  'bg-red-100 text-red-800',
  withdrawn: 'bg-gray-100 text-gray-600',
}

export const STATUS_COLUMNS: AppStatus[] = [
  'applied',
  'screened',
  'interview',
  'offer',
  'rejected',
  'withdrawn',
]

export const SOURCE_LABELS: Record<string, string> = {
  linkedin:    'LinkedIn',
  referral:    'Referral',
  cold:        'Cold Apply',
  'job-board': 'Job Board',
  unknown:     'Other',
}

// v3.3.0: "responded" means the application ever reached screened or beyond,
// even if it was rejected afterwards. Items written before maxStage existed
// fall back to their current status, matching the backend.
const STAGES = ['applied', 'screened', 'interview', 'offer']

export function effectiveMaxStage(app: Pick<Application, 'status' | 'maxStage'>): string {
  if (app.maxStage && STAGES.includes(app.maxStage)) return app.maxStage
  return STAGES.includes(app.status) ? app.status : 'applied'
}

export function hasResponded(app: Pick<Application, 'status' | 'maxStage'>): boolean {
  return STAGES.indexOf(effectiveMaxStage(app)) >= 1
}
