/**
 * Critical path frontend tests - v1.3
 * Covers: AddApplicationModal form, KanbanBoard empty state, Dashboard stats
 * Run: npm run test (from frontend/)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import AddApplicationModal from '../components/kanban/AddApplicationModal'
import Dashboard from '../pages/Dashboard'
import KanbanBoard from '../components/kanban/KanbanBoard'

// ── Mock api module ───────────────────────────────────────────────────────────

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

// ── Helpers ───────────────────────────────────────────────────────────────────

const renderWithRouter = (ui: React.ReactElement) =>
  render(<MemoryRouter>{ui}</MemoryRouter>)


// ── AddApplicationModal ───────────────────────────────────────────────────────

describe('AddApplicationModal', () => {
  const mockOnClose = vi.fn()
  const mockOnSave = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

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
    const roleInput = screen.getByPlaceholderText('ML Engineer')
    await userEvent.type(roleInput, 'Software Engineer')
    await userEvent.click(screen.getByRole('button', { name: /add application/i }))
    expect(mockOnSave).not.toHaveBeenCalled()
  })

  it('does not call onSave when role is empty', async () => {
    render(<AddApplicationModal onClose={mockOnClose} onSave={mockOnSave} />)
    const companyInput = screen.getByPlaceholderText('Anthropic')
    await userEvent.type(companyInput, 'Stripe')
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
    const savedData = mockOnSave.mock.calls[0][0]
    expect(savedData.source).toBe('linkedin')
  })
})


// ── Dashboard ─────────────────────────────────────────────────────────────────

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows empty state when no applications', async () => {
    vi.mocked(api.getApplications).mockResolvedValue([])
    renderWithRouter(<Dashboard />)
    await waitFor(() => {
      expect(screen.getByText(/nothing tracked yet/i)).toBeInTheDocument()
    })
  })

  it('shows correct total applied count', async () => {
    vi.mocked(api.getApplications).mockResolvedValue([
      { appId: '1', userId: 'u', company: 'Stripe', role: 'Eng', status: 'applied', source: 'linkedin', resumeVersion: 'v1', companySize: '', jobDescUrl: '', notes: '', dateApplied: '2024-01-01', createdAt: '2024-01-01T00:00:00Z', updatedAt: '2024-01-01T00:00:00Z' },
      { appId: '2', userId: 'u', company: 'Google', role: 'SWE', status: 'interview', source: 'linkedin', resumeVersion: 'v1', companySize: '', jobDescUrl: '', notes: '', dateApplied: '2024-01-02', createdAt: '2024-01-02T00:00:00Z', updatedAt: '2024-01-02T00:00:00Z' },
    ])
    renderWithRouter(<Dashboard />)
    await waitFor(() => {
      expect(screen.getByText('2')).toBeInTheDocument()
    })
  })

  it('shows link to board from empty state', async () => {
    vi.mocked(api.getApplications).mockResolvedValue([])
    renderWithRouter(<Dashboard />)
    await waitFor(() => {
      expect(screen.getByRole('link', { name: /go to board/i })).toBeInTheDocument()
    })
  })
})


// ── KanbanBoard ───────────────────────────────────────────────────────────────

describe('KanbanBoard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows empty state when no applications', async () => {
    vi.mocked(api.getApplications).mockResolvedValue([])
    renderWithRouter(<KanbanBoard />)
    await waitFor(() => {
      expect(screen.getByText(/no applications yet/i)).toBeInTheDocument()
    })
  })

  it('shows Add application button', async () => {
    vi.mocked(api.getApplications).mockResolvedValue([])
    renderWithRouter(<KanbanBoard />)
    await waitFor(() => {
      // Empty state renders two buttons matching this pattern:
      // "Add application" (header) and "Add first application" (body)
      const buttons = screen.getAllByRole('button', { name: /add.*application/i })
      expect(buttons.length).toBeGreaterThanOrEqual(1)
    })
  })

  it('shows add application modal when button is clicked', async () => {
    vi.mocked(api.getApplications).mockResolvedValue([])
    renderWithRouter(<KanbanBoard />)
    await waitFor(() => screen.getByRole('button', { name: /add first application/i }))
    await userEvent.click(screen.getByRole('button', { name: /add first application/i }))
    expect(screen.getByPlaceholderText('Anthropic')).toBeInTheDocument()
  })

  it('shows application cards when applications exist', async () => {
    vi.mocked(api.getApplications).mockResolvedValue([
      { appId: '1', userId: 'u', company: 'Stripe', role: 'ML Engineer', status: 'applied', source: 'linkedin', resumeVersion: 'v1', companySize: '', jobDescUrl: '', notes: '', dateApplied: '2024-01-01', createdAt: '2024-01-01T00:00:00Z', updatedAt: '2024-01-01T00:00:00Z' },
    ])
    renderWithRouter(<KanbanBoard />)
    await waitFor(() => {
      expect(screen.getByText('Stripe')).toBeInTheDocument()
      expect(screen.getByText('ML Engineer')).toBeInTheDocument()
    })
  })
})
