/**
 * v3.2.1 - CSV export/import round trip.
 * Covers: quoted newlines, quotes and commas, formula-injection guard,
 * CRLF files, BOM, header validation and error row numbering.
 */
import { describe, it, expect } from 'vitest'
import { buildCsv, parseImportCsv } from '../lib/csv'
import type { Application } from '../types'

const makeApp = (overrides: Partial<Application> = {}): Application => ({
  appId: 'a1',
  userId: 'u',
  company: 'Stripe',
  role: 'Backend Engineer',
  status: 'applied',
  dateApplied: '2024-01-15',
  resumeVersion: 'v1',
  source: 'linkedin',
  companySize: 'mid',
  jobDescUrl: 'https://stripe.com/jobs',
  notes: '',
  followUpDate: null,
  expectedSalary: null,
  offeredSalary: null,
  salaryNotes: '',
  salaryCurrency: 'USD',
  createdAt: '2024-01-15T00:00:00Z',
  updatedAt: '2024-01-15T00:00:00Z',
  ...overrides,
})

describe('CSV export', () => {
  it('neutralises cells that start with a formula character', () => {
    const csv = buildCsv([makeApp({ notes: '=1+1' })])
    expect(csv).toContain("'=1+1")
    expect(csv).not.toMatch(/(^|,)"?=1\+1/m)
  })

  it('guards + - and @ prefixes too', () => {
    for (const lead of ['+', '-', '@']) {
      const csv = buildCsv([makeApp({ notes: `${lead}cmd` })])
      expect(csv).toContain(`'${lead}cmd`)
    }
  })

  it('leaves ordinary cells alone', () => {
    const csv = buildCsv([makeApp({ notes: 'Great team' })])
    expect(csv).toContain(',Great team,')
    expect(csv).not.toContain("'Great")
  })
})

describe('CSV round trip', () => {
  it('survives newlines, quotes and commas in notes', () => {
    const notes = 'Recruiter said "call back",\nthen ask about team size'
    const result = parseImportCsv(buildCsv([makeApp({ notes })]))
    expect(result.errors).toEqual([])
    expect(result.valid).toHaveLength(1)
    expect(result.valid[0].notes).toBe(notes)
  })

  it('keeps a multi-line note in one row, not several', () => {
    const csv = buildCsv([
      makeApp({ company: 'A', notes: 'line1\nline2\nline3' }),
      makeApp({ company: 'B' }),
    ])
    const result = parseImportCsv(csv)
    expect(result.errors).toEqual([])
    expect(result.valid.map(r => r.company)).toEqual(['A', 'B'])
  })

  it('restores values that were formula-guarded on export', () => {
    const notes = '=HYPERLINK("http://example.com","click"),+1'
    const result = parseImportCsv(buildCsv([makeApp({ notes })]))
    expect(result.valid[0].notes).toBe(notes)
  })

  it('round trips the other exported fields', () => {
    const app = makeApp({
      status: 'interview',
      source: 'referral',
      companySize: 'startup',
      resumeVersion: 'v3-ml-focused',
      followUpDate: '2024-02-01',
    })
    const [row] = parseImportCsv(buildCsv([app])).valid
    expect(row).toMatchObject({
      company: 'Stripe',
      role: 'Backend Engineer',
      status: 'interview',
      dateApplied: '2024-01-15',
      source: 'referral',
      resumeVersion: 'v3-ml-focused',
      companySize: 'startup',
      jobDescUrl: 'https://stripe.com/jobs',
      followUpDate: '2024-02-01',
    })
  })
})

describe('CSV import parsing', () => {
  const header = 'company,role,status'

  it('accepts CRLF line endings', () => {
    const result = parseImportCsv(`${header}\r\nStripe,SWE,applied\r\nGoogle,SRE,offer\r\n`)
    expect(result.errors).toEqual([])
    expect(result.valid).toHaveLength(2)
  })

  it('ignores a leading BOM', () => {
    const result = parseImportCsv(`\uFEFF${header}\nStripe,SWE,applied`)
    expect(result.errors).toEqual([])
    expect(result.valid[0].company).toBe('Stripe')
  })

  it('handles a final row with no trailing newline', () => {
    const result = parseImportCsv(`${header}\nStripe,SWE,applied`)
    expect(result.valid).toHaveLength(1)
  })

  it('skips blank lines', () => {
    const result = parseImportCsv(`${header}\n\nStripe,SWE,applied\n\n`)
    expect(result.valid).toHaveLength(1)
    expect(result.errors).toEqual([])
  })

  it('reports a missing required column', () => {
    const result = parseImportCsv('company,status\nStripe,applied')
    expect(result.valid).toEqual([])
    expect(result.errors[0].reason).toMatch(/Missing required column: "role"/)
  })

  it('reports an empty file', () => {
    expect(parseImportCsv('').errors[0].reason).toMatch(/empty/i)
    expect(parseImportCsv(header).errors[0].reason).toMatch(/no data rows/i)
  })

  it('numbers errors by record, header is row 1', () => {
    const result = parseImportCsv(`${header}\nStripe,SWE,applied\nGoogle,SRE,bogus`)
    expect(result.valid).toHaveLength(1)
    expect(result.errors).toHaveLength(1)
    expect(result.errors[0].row).toBe(3)
    expect(result.errors[0].reason).toMatch(/Invalid status/)
  })
})
