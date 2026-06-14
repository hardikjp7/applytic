import '@testing-library/jest-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'

// Provide a helper for tests to wrap components with QueryClientProvider
export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

export function withQueryClient(ui: React.ReactElement) {
  const client = createTestQueryClient()
  return createElement(QueryClientProvider, { client }, ui)
}

// Mock AWS Amplify auth
vi.mock('aws-amplify/auth', () => ({
  fetchAuthSession: vi.fn().mockResolvedValue({
    tokens: { idToken: { toString: () => 'mock-jwt-token' } },
  }),
  getCurrentUser: vi.fn().mockResolvedValue({
    signInDetails: { loginId: 'test@example.com' },
  }),
  signOut: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('aws-amplify', () => ({
  Amplify: { configure: vi.fn() },
}))

vi.mock('react-hot-toast', () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
  Toaster: () => null,
}))

// Mock queryClient module so tests use their own isolated client
vi.mock('../lib/queryClient', () => ({
  queryClient: new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  }),
}))

const originalError = console.error
beforeAll(() => {
  console.error = (...args: unknown[]) => {
    const msg = args[0]?.toString() ?? ''
    if (
      msg.includes('Warning: ReactDOM.render') ||
      msg.includes('Not implemented: navigation') ||
      msg.includes('Could not parse CSS stylesheet')
    ) return
    originalError(...args)
  }
})

afterAll(() => {
  console.error = originalError
})
