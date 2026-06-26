import { useState, useEffect } from 'react'
import { fetchAuthSession } from 'aws-amplify/auth'

// Returns true if a valid Cognito session exists, false if not, null while loading.
// Used by landing page CTAs to redirect authenticated users directly to /dashboard
// instead of showing the auth modal.
export function useAuthStatus(): boolean | null {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null)

  useEffect(() => {
    fetchAuthSession()
      .then(session => setIsAuthenticated(!!session.tokens?.idToken))
      .catch(() => setIsAuthenticated(false))
  }, [])

  return isAuthenticated
}
