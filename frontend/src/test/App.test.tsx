/**
 * Critical path frontend tests - v2.1
 * Updated to wrap renders in QueryClientProvider for React Query compatibility
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AddApplicationModal from '../components/kanban/AddApplicationModal'
import Dashboard from '../pages/Dashboard'
import KanbanBoard from '../components/kanban/KanbanBoard'

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

// ── AddApplicationModal ───────────────────────────────────────────────────────

describe('AddApplicationModal', () => {
  const mockOnClose = vi.fn()
  const mockOnSave = vi.fn()

  beforeEach(() => vi.clearAllMocks())

  it('renders company and role inputs', () => {
    render(<AddApplicationModal onClose={mockOnClose} onSave={mockOnSave} />)
    expect(screen.getByPlaceholderText('Anthropic')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('ML Engineer')).toBeInTheDocument()
  })

  it('renders submit button', () => {
    render(<AddApplicationModal onClose={mockOnClose} onSave={mockOnSave} />)
    expect(screen.getByRole('button', { name: /add application/i })).toBeInTheDocument()
  })

  it('calls onClose when Cancel is clicked', async () => {
    render(<AddApplicationModal onClose={mockOnClose} onSave={mockOnSave} />)
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(mockOnClose).toHaveBeenCalledOnce()
  })

  it('does not call onSave when company is empty', async () => {
    render(<AddApplicationModal onClose={mockOnClose} onSave={mockOnSave} />)
    await userEvent.type(screen.getByPlaceholderText('ML Engineer'), 'Software Engineer')
    await userEvent.click(screen.getByRole('button', { name: /add application/i }))
    expect(mockOnSave).not.toHaveBeenCalled()
  })

  it('does not call onSave when role is empty', async () => {
    render(<AddApplicationModal onClose={mockOnClose} onSave={mockOnSave} />)
    await userEvent.type(screen.getByPlaceholderText('Anthropic'), 'Stripe')
    await userEvent.click(screen.getByRole('button', { name: /add application/i }))
    expect(mockOnSave).not.toHaveBeenCalled()
  })

  it('calls onSave and onClose with correct data when form is valid', async () => {
    render(<AddApplicationModal onClose={mockOnClose} onSave={mockOnSave} />)
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
    render(<AddApplicationModal onClose={mockOnClose} onSave={mockOnSave} />)
    await userEvent.type(screen.getByPlaceholderText('Anthropic'), 'Stripe')
    await userEvent.type(screen.getByPlaceholderText('ML Engineer'), 'Eng')
    await userEvent.click(screen.getByRole('button', { name: /add application/i }))
    expect(mockOnSave.mock.calls[0][0].source).toBe('linkedin')
  })

  it('renders follow-up date field', () => {
    render(<AddApplicationModal onClose={mockOnClose} onSave={mockOnSave} />)
    expect(screen.getByText(/follow-up date/i)).toBeInTheDocument()
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
      { appId: '1', userId: 'u', company: 'Stripe', role: 'Eng', status: 'applied', source: 'linkedin', resumeVersion: 'v1', companySize: '', jobDescUrl: '', notes: '', followUpDate: null, dateApplied: '2024-01-01', createdAt: '2024-01-01T00:00:00Z', updatedAt: '2024-01-01T00:00:00Z' },
      { appId: '2', userId: 'u', company: 'Google', role: 'SWE', status: 'interview', source: 'linkedin', resumeVersion: 'v1', companySize: '', jobDescUrl: '', notes: '', followUpDate: null, dateApplied: '2024-01-02', createdAt: '2024-01-02T00:00:00Z', updatedAt: '2024-01-02T00:00:00Z' },
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
  beforeEach(() => vi.clearAllMocks())

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
      { appId: '1', userId: 'u', company: 'Stripe', role: 'ML Engineer', status: 'applied', source: 'linkedin', resumeVersion: 'v1', companySize: '', jobDescUrl: '', notes: '', followUpDate: null, dateApplied: '2024-01-01', createdAt: '2024-01-01T00:00:00Z', updatedAt: '2024-01-01T00:00:00Z' },
    ])
    renderWithProviders(<KanbanBoard />)
    await waitFor(() => {
      expect(screen.getByText('Stripe')).toBeInTheDocument()
      expect(screen.getByText('ML Engineer')).toBeInTheDocument()
    })
  })
})
