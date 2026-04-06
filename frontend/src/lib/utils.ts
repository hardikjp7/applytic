import type { AppStatus } from '../types'

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
