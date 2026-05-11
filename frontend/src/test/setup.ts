import '@testing-library/jest-dom'

// Mock AWS Amplify auth - used by most components indirectly via api.ts
vi.mock('aws-amplify/auth', () => ({
  fetchAuthSession: vi.fn().mockResolvedValue({
    tokens: { idToken: { toString: () => 'mock-jwt-token' } },
  }),
  getCurrentUser: vi.fn().mockResolvedValue({
    signInDetails: { loginId: 'test@example.com' },
  }),
  signOut: vi.fn().mockResolvedValue(undefined),
}))

// Mock aws-amplify configure - no-op in tests
vi.mock('aws-amplify', () => ({
  Amplify: { configure: vi.fn() },
}))

// Mock react-hot-toast - avoid rendering toast container in tests
vi.mock('react-hot-toast', () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
  Toaster: () => null,
}))

// Suppress specific console errors from Amplify/React in test output
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
