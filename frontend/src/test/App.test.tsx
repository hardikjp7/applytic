/**
 * Critical path frontend tests - v2.1
 * Updated to wrap renders in QueryClientProvider for React Query compatibility.
 * Part 2: added tests for keyboard shortcuts (N / Escape / ?) and
 * per-column "Show more" pagination.
 * v2.2 Session 0: AddApplicationModal now uses ResumeVersionSelect (S3-backed,
 * React Query), so its tests need QueryClientProvider + a resolved listResumes mock.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AddApplicationModal from '../components/kanban/AddApplicationModal'
import Dashboard from '../pages/Dashboard'
import KanbanBoard from '../components/kanban/KanbanBoard'
import type { Application } from '../types'

vi.mock('../lib/api', () => ({
  getApplications: vi.fn(),
  createApplication: vi.fn(),
  updateApplication: vi.fn(),
  deleteApplication: vi.fn(),
  updateStatus: vi.fn(),
  getInsights: vi.fn(),
  chatWithCoach: vi.fn(),
  getUploadUrl: vi.fn(),
  uploadResumeToS3: vi.fn(),
  listResumes: vi.fn(),
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  getNotes: vi.fn(),
  createNote: vi.fn(),
  deleteNote: vi.fn(),
}))

vi.mock('../lib/amplify', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
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

const renderWithProviders = (ui: React.ReactElement) => {
  const client = createTestQueryClient()
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  )
}

// v2.2 Session 0: AddApplicationModal isn't wrapped in MemoryRouter (it doesn't
// use routing), but it now needs QueryClientProvider for ResumeVersionSelect.
const renderModalWithQueryClient = (ui: React.ReactElement) => {
  const client = createTestQueryClient()
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

// Helper to build a minimal valid Application for mock data
function makeApp(overrides: Partial<Application>): Application {
  return {
    appId: 'app-x',
    userId: 'u',
    company: 'Company',
    role: 'Engineer',
    status: 'applied',
    source: 'linkedin',
    resumeVersion: 'v1',
    companySize: '',
    jobDescUrl: '',
    notes: '',
    followUpDate: null,
    dateApplied: '2024-01-01',
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
    ...overrides,
  }
}

const SAMPLE_RESUMES = [
  { versionName: 'v1-generic', filename: 'resume-v1.pdf', uploadedAt: '2026-01-01' },
  { versionName: 'v3-ml-focused', filename: 'resume-v3.pdf', uploadedAt: '2026-02-01' },
]

// ── AddApplicationModal ───────────────────────────────────────────────────────

describe('AddApplicationModal', () => {
  const mockOnClose = vi.fn()
  const mockOnSave = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    // v2.2 Session 0: ResumeVersionSelect fetches resumes on mount via useResumes
    vi.mocked(api.listResumes).mockResolvedValue(SAMPLE_RESUMES)
  })

  it('renders company and role inputs', () => {
    renderModalWithQueryClient(<AddApplicationModal onClose={mockOnClose} onSave={mockOnSave} />)
    expect(screen.getByPlaceholderText('Anthropic')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('ML Engineer')).toBeInTheDocument()
  })

  it('renders submit button', () => {
    renderModalWithQueryClient(<AddApplicationModal onClose={mockOnClose} onSave={mockOnSave} />)
    expect(screen.getByRole('button', { name: /add application/i })).toBeInTheDocument()
  })

  it('calls onClose when Cancel is clicked', async () => {
    renderModalWithQueryClient(<AddApplicationModal onClose={mockOnClose} onSave={mockOnSave} />)
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(mockOnClose).toHaveBeenCalledOnce()
  })

  it('does not call onSave when company is empty', async () => {
    renderModalWithQueryClient(<AddApplicationModal onClose={mockOnClose} onSave={mockOnSave} />)
    await userEvent.type(screen.getByPlaceholderText('ML Engineer'), 'Software Engineer')
    await userEvent.click(screen.getByRole('button', { name: /add application/i }))
    expect(mockOnSave).not.toHaveBeenCalled()
  })

  it('does not call onSave when role is empty', async () => {
    renderModalWithQueryClient(<AddApplicationModal onClose={mockOnClose} onSave={mockOnSave} />)
    await userEvent.type(screen.getByPlaceholderText('Anthropic'), 'Stripe')
    await userEvent.click(screen.getByRole('button', { name: /add application/i }))
    expect(mockOnSave).not.toHaveBeenCalled()
  })

  it('calls onSave and onClose with correct data when form is valid', async () => {
    renderModalWithQueryClient(<AddApplicationModal onClose={mockOnClose} onSave={mockOnSave} />)
    await userEvent.type(screen.getByPlaceholderText('Anthropic'), 'Stripe')
    await userEvent.type(screen.getByPlaceholderText('ML Engineer'), 'Backend Engineer')
    await userEvent.click(screen.getByRole('button', { name: /add application/i }))
    expect(mockOnSave).toHaveBeenCalledOnce()
    const savedData = mockOnSave.mock.calls[0][0]
    expect(savedData.company).toBe('Stripe')
    expect(savedData.role).toBe('Backend Engineer')
    expect(savedData.status).toBe('applied')
    expect(mockOnClose).toHaveBeenCalledOnce()
  })

  it('defaults source to linkedin', async () => {
    renderModalWithQueryClient(<AddApplicationModal onClose={mockOnClose} onSave={mockOnSave} />)
    await userEvent.type(screen.getByPlaceholderText('Anthropic'), 'Stripe')
    await userEvent.type(screen.getByPlaceholderText('ML Engineer'), 'Eng')
    await userEvent.click(screen.getByRole('button', { name: /add application/i }))
    expect(mockOnSave.mock.calls[0][0].source).toBe('linkedin')
  })

  it('renders follow-up date field', () => {
    renderModalWithQueryClient(<AddApplicationModal onClose={mockOnClose} onSave={mockOnSave} />)
    expect(screen.getByText(/follow-up date/i)).toBeInTheDocument()
  })

  // v2.2 Session 0: resume version dropdown tests
  it('defaults resume version to empty (no free-text default)', async () => {
    renderModalWithQueryClient(<AddApplicationModal onClose={mockOnClose} onSave={mockOnSave} />)
    await userEvent.type(screen.getByPlaceholderText('Anthropic'), 'Stripe')
    await userEvent.type(screen.getByPlaceholderText('ML Engineer'), 'Eng')
    await userEvent.click(screen.getByRole('button', { name: /add application/i }))
    expect(mockOnSave.mock.calls[0][0].resumeVersion).toBe('')
  })

  it('populates resume version options from listResumes', async () => {
    renderModalWithQueryClient(<AddApplicationModal onClose={mockOnClose} onSave={mockOnSave} />)
    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'v1-generic' })).toBeInTheDocument()
      expect(screen.getByRole('option', { name: 'v3-ml-focused' })).toBeInTheDocument()
    })
  })

  it('selecting a resume version includes it in saved data', async () => {
    renderModalWithQueryClient(<AddApplicationModal onClose={mockOnClose} onSave={mockOnSave} />)
    await userEvent.type(screen.getByPlaceholderText('Anthropic'), 'Stripe')
    await userEvent.type(screen.getByPlaceholderText('ML Engineer'), 'Eng')
    await waitFor(() => screen.getByRole('option', { name: 'v3-ml-focused' }))
    const resumeSelect = screen.getByRole('option', { name: 'v3-ml-focused' }).closest('select')!
    await userEvent.selectOptions(resumeSelect, 'v3-ml-focused')
    await userEvent.click(screen.getByRole('button', { name: /add application/i }))
    expect(mockOnSave.mock.calls[0][0].resumeVersion).toBe('v3-ml-focused')
  })
})

// ── Dashboard ─────────────────────────────────────────────────────────────────

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.getSettings).mockResolvedValue({ weeklyGoal: 10, streakCount: 0, streakLastUpdated: null })
  })

  it('shows empty state when no applications', async () => {
    vi.mocked(api.getApplications).mockResolvedValue([])
    renderWithProviders(<Dashboard />)
    await waitFor(() => {
      expect(screen.getByText(/nothing tracked yet/i)).toBeInTheDocument()
    })
  })

  it('shows correct total applied count', async () => {
    vi.mocked(api.getApplications).mockResolvedValue([
      makeApp({ appId: '1', company: 'Stripe', role: 'Eng', status: 'applied', dateApplied: '2024-01-01', createdAt: '2024-01-01T00:00:00Z', updatedAt: '2024-01-01T00:00:00Z' }),
      makeApp({ appId: '2', company: 'Google', role: 'SWE', status: 'interview', dateApplied: '2024-01-02', createdAt: '2024-01-02T00:00:00Z', updatedAt: '2024-01-02T00:00:00Z' }),
    ])
    renderWithProviders(<Dashboard />)
    await waitFor(() => {
      expect(screen.getByText('2')).toBeInTheDocument()
    })
  })

  it('shows link to board from empty state', async () => {
    vi.mocked(api.getApplications).mockResolvedValue([])
    renderWithProviders(<Dashboard />)
    await waitFor(() => {
      expect(screen.getByRole('link', { name: /go to board/i })).toBeInTheDocument()
    })
  })
})

// ── KanbanBoard ───────────────────────────────────────────────────────────────

describe('KanbanBoard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.listResumes).mockResolvedValue(SAMPLE_RESUMES)
  })

  it('shows empty state when no applications', async () => {
    vi.mocked(api.getApplications).mockResolvedValue([])
    renderWithProviders(<KanbanBoard />)
    await waitFor(() => {
      expect(screen.getByText(/no applications yet/i)).toBeInTheDocument()
    })
  })

  it('shows Add application button', async () => {
    vi.mocked(api.getApplications).mockResolvedValue([])
    renderWithProviders(<KanbanBoard />)
    await waitFor(() => {
      const buttons = screen.getAllByRole('button', { name: /add.*application/i })
      expect(buttons.length).toBeGreaterThanOrEqual(1)
    })
  })

  it('shows add application modal when button is clicked', async () => {
    vi.mocked(api.getApplications).mockResolvedValue([])
    renderWithProviders(<KanbanBoard />)
    await waitFor(() => screen.getByRole('button', { name: /add first application/i }))
    await userEvent.click(screen.getByRole('button', { name: /add first application/i }))
    expect(screen.getByPlaceholderText('Anthropic')).toBeInTheDocument()
  })

  it('shows application cards when applications exist', async () => {
    vi.mocked(api.getApplications).mockResolvedValue([
      makeApp({ appId: '1', company: 'Stripe', role: 'ML Engineer', status: 'applied' }),
    ])
    renderWithProviders(<KanbanBoard />)
    await waitFor(() => {
      expect(screen.getByText('Stripe')).toBeInTheDocument()
      expect(screen.getByText('ML Engineer')).toBeInTheDocument()
    })
  })
})

// ── KanbanBoard - keyboard shortcuts (v2.1 Part 2) ──────────────────────────────

describe('KanbanBoard keyboard shortcuts', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.listResumes).mockResolvedValue(SAMPLE_RESUMES)
  })

  it('pressing "n" opens the Add application modal', async () => {
    vi.mocked(api.getApplications).mockResolvedValue([])
    renderWithProviders(<KanbanBoard />)
    await waitFor(() => screen.getByRole('button', { name: /add first application/i }))

    await userEvent.keyboard('n')
    expect(screen.getByPlaceholderText('Anthropic')).toBeInTheDocument()
  })

  it('pressing Escape closes the open Add application modal', async () => {
    vi.mocked(api.getApplications).mockResolvedValue([])
    renderWithProviders(<KanbanBoard />)
    await waitFor(() => screen.getByRole('button', { name: /add first application/i }))

    await userEvent.click(screen.getByRole('button', { name: /add first application/i }))
    expect(screen.getByPlaceholderText('Anthropic')).toBeInTheDocument()

    await userEvent.keyboard('{Escape}')
    expect(screen.queryByPlaceholderText('Anthropic')).not.toBeInTheDocument()
  })

  it('pressing "?" toggles the shortcuts help overlay', async () => {
    vi.mocked(api.getApplications).mockResolvedValue([])
    renderWithProviders(<KanbanBoard />)
    await waitFor(() => screen.getByRole('button', { name: /add first application/i }))

    await userEvent.keyboard('?')
    expect(screen.getByText(/keyboard shortcuts/i)).toBeInTheDocument()

    await userEvent.keyboard('{Escape}')
    expect(screen.queryByText(/keyboard shortcuts/i)).not.toBeInTheDocument()
  })

  it('the shortcuts button in the header also opens the overlay', async () => {
    vi.mocked(api.getApplications).mockResolvedValue([
      makeApp({ appId: '1', company: 'Stripe', role: 'ML Engineer', status: 'applied' }),
    ])
    renderWithProviders(<KanbanBoard />)
    await waitFor(() => screen.getByText('Stripe'))

    await userEvent.click(screen.getByTitle(/keyboard shortcuts/i))
    expect(screen.getByText(/keyboard shortcuts/i)).toBeInTheDocument()
  })

  it('typing "n" in the search box does not open the Add application modal', async () => {
    vi.mocked(api.getApplications).mockResolvedValue([
      makeApp({ appId: '1', company: 'Stripe', role: 'ML Engineer', status: 'applied' }),
    ])
    renderWithProviders(<KanbanBoard />)
    await waitFor(() => screen.getByText('Stripe'))

    const search = screen.getByPlaceholderText('Search...')
    await userEvent.type(search, 'n')

    expect(screen.queryByPlaceholderText('Anthropic')).not.toBeInTheDocument()
    expect(search).toHaveValue('n')
  })
})

// ── KanbanBoard - column pagination (v2.1 Part 2) ───────────────────────────────

describe('KanbanBoard column pagination', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.listResumes).mockResolvedValue(SAMPLE_RESUMES)
  })

  it('shows a "Show more" button when a column has more than 20 cards, and reveals the rest on click', async () => {
    const apps = Array.from({ length: 25 }, (_, i) =>
      makeApp({ appId: `app-${i}`, company: `Company ${i}`, role: 'Engineer', status: 'applied' })
    )
    vi.mocked(api.getApplications).mockResolvedValue(apps)
    renderWithProviders(<KanbanBoard />)

    await waitFor(() => screen.getByText('Company 0'))

    // 25 applied apps, 20 shown by default -> 5 hidden
    expect(screen.getByRole('button', { name: /show 5 more/i })).toBeInTheDocument()
    expect(screen.queryByText('Company 24')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /show 5 more/i }))

    expect(screen.getByText('Company 24')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /show.*more/i })).not.toBeInTheDocument()
  })

  it('does not show a "Show more" button when a column has 20 or fewer cards', async () => {
    const apps = Array.from({ length: 20 }, (_, i) =>
      makeApp({ appId: `app-${i}`, company: `Company ${i}`, role: 'Engineer', status: 'applied' })
    )
    vi.mocked(api.getApplications).mockResolvedValue(apps)
    renderWithProviders(<KanbanBoard />)

    await waitFor(() => screen.getByText('Company 0'))

    expect(screen.getByText('Company 19')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /show.*more/i })).not.toBeInTheDocument()
  })
})
