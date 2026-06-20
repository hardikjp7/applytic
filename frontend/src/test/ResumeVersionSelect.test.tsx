/**
 * v2.2 Session 0 - tests for the S3-backed resume version dropdown.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ResumeVersionSelect from '../components/kanban/ResumeVersionSelect'

vi.mock('../lib/api', () => ({
  listResumes: vi.fn(),
}))

import * as api from '../lib/api'

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

const renderWithClient = (ui: React.ReactElement) => {
  const client = createTestQueryClient()
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

const RESUMES = [
  { versionName: 'v1-generic', filename: 'resume-v1.pdf', uploadedAt: '2026-01-01' },
  { versionName: 'v3-ml-focused', filename: 'resume-v3.pdf', uploadedAt: '2026-02-01' },
]

describe('ResumeVersionSelect', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows loading placeholder while resumes are fetching', async () => {
    vi.mocked(api.listResumes).mockImplementation(() => new Promise(() => {})) // never resolves
    renderWithClient(<ResumeVersionSelect value="" onChange={vi.fn()} />)
    expect(screen.getByRole('combobox')).toBeDisabled()
    expect(screen.getByText(/loading resumes/i)).toBeInTheDocument()
  })

  it('shows empty-state hint when no resumes are uploaded', async () => {
    vi.mocked(api.listResumes).mockResolvedValue([])
    renderWithClient(<ResumeVersionSelect value="" onChange={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByText(/head to the resumes page/i)).toBeInTheDocument()
    })
    expect(screen.getByRole('combobox')).toBeDisabled()
  })

  it('renders all uploaded resumes as selectable options', async () => {
    vi.mocked(api.listResumes).mockResolvedValue(RESUMES)
    renderWithClient(<ResumeVersionSelect value="" onChange={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'v1-generic' })).toBeInTheDocument()
      expect(screen.getByRole('option', { name: 'v3-ml-focused' })).toBeInTheDocument()
    })
    expect(screen.getByRole('combobox')).not.toBeDisabled()
  })

  it('flags a stale resumeVersion not present in the current S3 list as a disabled option', async () => {
    vi.mocked(api.listResumes).mockResolvedValue(RESUMES)
    renderWithClient(<ResumeVersionSelect value="v0-deleted-version" onChange={vi.fn()} />)
    await waitFor(() => {
      const staleOption = screen.getByRole('option', { name: /v0-deleted-version/i })
      expect(staleOption).toBeInTheDocument()
      expect(staleOption).toBeDisabled()
      expect(staleOption.textContent).toMatch(/no longer in s3/i)
    })
  })

  it('does not flag a value that matches a current resume', async () => {
    vi.mocked(api.listResumes).mockResolvedValue(RESUMES)
    renderWithClient(<ResumeVersionSelect value="v1-generic" onChange={vi.fn()} />)
    await waitFor(() => {
      expect(screen.queryByText(/no longer in s3/i)).not.toBeInTheDocument()
    })
  })

  it('does not show stale flag when value is empty', async () => {
    vi.mocked(api.listResumes).mockResolvedValue(RESUMES)
    renderWithClient(<ResumeVersionSelect value="" onChange={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'v1-generic' })).toBeInTheDocument()
    })
    expect(screen.queryByText(/no longer in s3/i)).not.toBeInTheDocument()
  })
})
