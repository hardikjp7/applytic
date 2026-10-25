import type { Application } from '../types'

// ── CSV Export ────────────────────────────────────────────────────────────────

const EXPORT_HEADERS = [
  'company',
  'role',
  'status',
  'dateApplied',
  'source',
  'resumeVersion',
  'companySize',
  'jobDescUrl',
  'notes',
  'followUpDate',
]

// v3.2.1: spreadsheet apps (Excel, Sheets) run a cell as a formula when it
// starts with = + - @ (or tab/CR). Exported cells that start with one of
// those get a leading apostrophe so they open as plain text; import strips
// the apostrophe again so a round trip returns the original value.
const FORMULA_TRIGGER = /^[=+\-@\t\r]/
const GUARDED_CELL = /^'[=+\-@\t\r]/

function guardFormula(value: string): string {
  return FORMULA_TRIGGER.test(value) ? `'${value}` : value
}

function unguardFormula(value: string): string {
  return GUARDED_CELL.test(value) ? value.slice(1) : value
}

function escapeCell(value: string | null | undefined): string {
  const str = guardFormula(String(value ?? ''))
  // Wrap in quotes if contains comma, quote, or newline
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`
  }
  return str
}

// Pure string builder, split out of exportToCsv so it can be unit tested
// without a DOM (Blob / URL.createObjectURL).
export function buildCsv(applications: Application[]): string {
  const rows = [
    EXPORT_HEADERS.join(','),
    ...applications.map(app =>
      EXPORT_HEADERS.map(h => escapeCell(app[h as keyof Application] as string)).join(',')
    ),
  ]
  return rows.join('\n')
}

export function exportToCsv(applications: Application[]): void {
  const blob = new Blob([buildCsv(applications)], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `applytic-export-${new Date().toISOString().split('T')[0]}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

// ── CSV Import ────────────────────────────────────────────────────────────────

export const IMPORT_TEMPLATE_HEADERS = EXPORT_HEADERS

export const REQUIRED_IMPORT_HEADERS = ['company', 'role']

export const VALID_STATUSES = ['applied', 'screened', 'interview', 'offer', 'rejected', 'withdrawn']
export const VALID_SOURCES = ['linkedin', 'referral', 'cold', 'job-board', 'unknown']
export const VALID_COMPANY_SIZES = ['startup', 'mid', 'enterprise', '']

export interface ImportRow {
  company: string
  role: string
  status: string
  dateApplied: string
  source: string
  resumeVersion: string
  companySize: string
  jobDescUrl: string
  notes: string
  followUpDate: string | null
}

export interface ImportResult {
  valid: ImportRow[]
  errors: { row: number; reason: string }[]
}

// v3.2.1: parses the whole file as records instead of splitting on '\n'
// first, so a quoted cell containing a line break (e.g. a multi-line note)
// stays inside its row. Handles \n, \r\n and \r row endings, "" escapes and
// a leading BOM. Cells are trimmed, same as before.
function parseCsvRows(text: string): string[][] {
  const src = text.replace(/^\uFEFF/, '')
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let inQuotes = false

  const endCell = () => { row.push(cell.trim()); cell = '' }
  const endRow = () => { endCell(); rows.push(row); row = [] }

  for (let i = 0; i < src.length; i++) {
    const ch = src[i]
    if (inQuotes) {
      if (ch === '"') {
        if (src[i + 1] === '"') {
          cell += '"'
          i++ // skip escaped quote
        } else {
          inQuotes = false
        }
      } else {
        cell += ch
      }
    } else if (ch === '"') {
      inQuotes = true
    } else if (ch === ',') {
      endCell()
    } else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && src[i + 1] === '\n') i++
      endRow()
    } else {
      cell += ch
    }
  }
  // Last record when the file has no trailing newline
  if (cell !== '' || row.length > 0) endRow()

  // Drop fully blank records (same as the old "filter empty lines")
  return rows.filter(r => r.some(c => c !== ''))
}

export function parseImportCsv(text: string): ImportResult {
  const rows = parseCsvRows(text)

  if (rows.length < 2) {
    return { valid: [], errors: [{ row: 0, reason: 'File is empty or has no data rows' }] }
  }

  const headers = rows[0].map(h => h.toLowerCase().trim())

  // Validate required headers exist
  for (const req of REQUIRED_IMPORT_HEADERS) {
    if (!headers.includes(req)) {
      return {
        valid: [],
        errors: [{ row: 0, reason: `Missing required column: "${req}"` }],
      }
    }
  }

  const valid: ImportRow[] = []
  const errors: { row: number; reason: string }[] = []

  for (let i = 1; i < rows.length; i++) {
    const rowNum = i + 1 // record number, header = 1 (not a physical line number)
    const cells = rows[i]
    const row: Record<string, string> = {}
    headers.forEach((h, idx) => { row[h] = unguardFormula(cells[idx] ?? '') })

    // Validate required fields
    if (!row.company?.trim()) {
      errors.push({ row: rowNum, reason: 'company is required' })
      continue
    }
    if (!row.role?.trim()) {
      errors.push({ row: rowNum, reason: 'role is required' })
      continue
    }

    // Normalise status
    const status = row.status?.trim().toLowerCase() || 'applied'
    if (!VALID_STATUSES.includes(status)) {
      errors.push({ row: rowNum, reason: `Invalid status "${row.status}". Must be one of: ${VALID_STATUSES.join(', ')}` })
      continue
    }

    // Normalise source
    const source = row.source?.trim().toLowerCase() || 'unknown'
    if (!VALID_SOURCES.includes(source)) {
      errors.push({ row: rowNum, reason: `Invalid source "${row.source}". Must be one of: ${VALID_SOURCES.join(', ')}` })
      continue
    }

    // Normalise companySize
    const companySize = row.companysize?.trim().toLowerCase() || ''
    if (!VALID_COMPANY_SIZES.includes(companySize)) {
      errors.push({ row: rowNum, reason: `Invalid companySize "${row.companysize}". Must be one of: startup, mid, enterprise` })
      continue
    }

    // Validate dateApplied format if provided
    const dateApplied = row.dateapplied?.trim() || new Date().toISOString().split('T')[0]
    if (dateApplied && !/^\d{4}-\d{2}-\d{2}$/.test(dateApplied)) {
      errors.push({ row: rowNum, reason: `Invalid dateApplied "${dateApplied}". Must be YYYY-MM-DD` })
      continue
    }

    // Validate followUpDate format if provided
    const followUpDate = row.followupdate?.trim() || null
    if (followUpDate && !/^\d{4}-\d{2}-\d{2}$/.test(followUpDate)) {
      errors.push({ row: rowNum, reason: `Invalid followUpDate "${followUpDate}". Must be YYYY-MM-DD` })
      continue
    }

    valid.push({
      company: row.company.trim(),
      role: row.role.trim(),
      status,
      dateApplied,
      source,
      resumeVersion: row.resumeversion?.trim() || 'v1',
      companySize,
      jobDescUrl: row.jobdescurl?.trim() || '',
      notes: row.notes?.trim() || '',
      followUpDate,
    })
  }

  return { valid, errors }
}

export function downloadImportTemplate(): void {
  const rows = [
    IMPORT_TEMPLATE_HEADERS.join(','),
    'Anthropic,ML Engineer,applied,2024-01-15,linkedin,v1,startup,https://anthropic.com/careers,Great company,',
    'Stripe,Backend Engineer,interview,2024-01-10,referral,v2-focused,mid,,Referred by friend,2024-02-01',
  ]
  const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'applytic-import-template.csv'
  link.click()
  URL.revokeObjectURL(url)
}
