import { BrowserRouter, Routes, Route, Navigate, useLocation, Outlet } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { useState, useEffect } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { fetchAuthSession } from 'aws-amplify/auth'
import { Hub } from 'aws-amplify/utils'
import './lib/amplify'
import { getInitialTheme, applyTheme } from './lib/theme'
import { queryClient } from './lib/queryClient'

import Sidebar from './components/layout/Sidebar'
import ErrorBoundary from './components/layout/ErrorBoundary'
import Dashboard from './pages/Dashboard'
import KanbanBoard from './components/kanban/KanbanBoard'
import AnalyticsDashboard from './components/analytics/AnalyticsDashboard'
import CoachChat from './components/chat/CoachChat'
import ResumeUpload from './components/resume/ResumeUpload'
import Landing from './pages/Landing'
import AuthModal from './components/landing/AuthModal'
import PrivacyPolicy from './pages/PrivacyPolicy'   // v2.3 Session 5
import Terms from './pages/Terms'                   // v2.3 Session 5

export interface Message {
  role: 'user' | 'assistant'
  content: string
}

const INITIAL_MESSAGES: Message[] = [
  {
    role: 'assistant',
    content: "Hi! I'm your AI job search coach. I have access to your full application history and pattern data. Ask me anything - I'll give you specific advice based on your actual numbers.",
  },
]

type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated'

// ── RequireAuth ────────────────────────────────────────────────────────────────
function RequireAuth() {
  const location = useLocation()
  const [status, setStatus] = useState<AuthStatus>('loading')

  const checkSession = async () => {
    try {
      const session = await fetchAuthSession()
      setStatus(session.tokens?.idToken ? 'authenticated' : 'unauthenticated')
    } catch {
      setStatus('unauthenticated')
    }
  }

  useEffect(() => {
    checkSession()
    const unsubscribe = Hub.listen('auth', ({ payload }) => {
      switch (payload.event) {
        case 'signedIn':
        case 'tokenRefresh':
          setStatus('authenticated')
          break
        case 'signedOut':
        case 'tokenRefresh_failure':
          setStatus('unauthenticated')
          break
      }
    })
    return unsubscribe
  }, [])

  if (status === 'loading') {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50 dark:bg-gray-950">
        <div className="w-8 h-8 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  return <Outlet />
}

// ── AuthCallback ───────────────────────────────────────────────────────────────
function AuthCallback() {
  const [error, setError] = useState(false)

  useEffect(() => {
    const timer = setTimeout(async () => {
      try {
        const session = await fetchAuthSession()
        if (session.tokens?.idToken) {
          window.location.replace(
            import.meta.env.BASE_URL.replace(/\/$/, '') + '/dashboard'
          )
        } else {
          setError(true)
        }
      } catch {
        setError(true)
      }
    }, 2000)

    const unsubscribe = Hub.listen('auth', ({ payload }) => {
      if (payload.event === 'signedIn') {
        clearTimeout(timer)
        window.location.replace(
          import.meta.env.BASE_URL.replace(/\/$/, '') + '/dashboard'
        )
      }
      if (payload.event === 'signInWithRedirect_failure') {
        clearTimeout(timer)
        setError(true)
      }
    })

    return () => { clearTimeout(timer); unsubscribe() }
  }, [])

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-screen gap-4"
           style={{ background: '#0a0a0f' }}>
        <p className="text-sm text-gray-400">Sign-in failed. Please try again.</p>
        <a
          href={import.meta.env.BASE_URL + 'login'}
          className="px-4 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-800 transition-colors"
        >
          Back to login
        </a>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center justify-center h-screen gap-3"
         style={{ background: '#0a0a0f' }}>
      <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      <p className="text-sm text-gray-500">Completing sign-in...</p>
    </div>
  )
}

// ── AppShell ───────────────────────────────────────────────────────────────────
function AppShell({
  theme,
  toggleTheme,
  chatHistory,
  setChatHistory,
}: {
  theme: 'dark' | 'light'
  toggleTheme: () => void
  chatHistory: Message[]
  setChatHistory: React.Dispatch<React.SetStateAction<Message[]>>
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50 dark:bg-gray-950">
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-20 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <Sidebar
        theme={theme}
        toggleTheme={toggleTheme}
        sidebarOpen={sidebarOpen}
        setSidebarOpen={setSidebarOpen}
      />

      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="lg:hidden flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="6" x2="21" y2="6"/>
              <line x1="3" y1="12" x2="21" y2="12"/>
              <line x1="3" y1="18" x2="21" y2="18"/>
            </svg>
          </button>
          <span className="text-sm font-semibold text-brand-800 dark:text-brand-400">applytic</span>
          <div className="w-8" />
        </div>

        <main className="flex-1 overflow-y-auto">
          <ErrorBoundary>
            <Routes>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/board"     element={<KanbanBoard />} />
              <Route path="/analytics" element={<AnalyticsDashboard />} />
              <Route path="/coach"     element={
                <CoachChat messages={chatHistory} setMessages={setChatHistory} />
              } />
              <Route path="/resumes"   element={<ResumeUpload />} />
              <Route path="*"          element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}

// ── Root ───────────────────────────────────────────────────────────────────────
function Root() {
  const location = useLocation()
  const backgroundLocation = (location.state as any)?.backgroundLocation

  const [chatHistory, setChatHistory] = useState<Message[]>(INITIAL_MESSAGES)
  const [theme, setTheme] = useState<'dark' | 'light'>(getInitialTheme)

  useEffect(() => { applyTheme(theme) }, [theme])
  const toggleTheme = () => setTheme(t => t === 'dark' ? 'light' : 'dark')

  return (
    <>
      <Routes location={backgroundLocation ?? location}>
        {/* Public routes - no auth required */}
        <Route path="/"              element={<Landing />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="/login"         element={<AuthModal initialView="login"  isModal={false} />} />
        <Route path="/signup"        element={<AuthModal initialView="signup" isModal={false} />} />
        <Route path="/privacy"       element={<PrivacyPolicy />} />   {/* v2.3 Session 5 */}
        <Route path="/terms"         element={<Terms />} />           {/* v2.3 Session 5 */}

        {/* Protected routes */}
        <Route element={<RequireAuth />}>
          <Route
            path="/*"
            element={
              <AppShell
                theme={theme}
                toggleTheme={toggleTheme}
                chatHistory={chatHistory}
                setChatHistory={setChatHistory}
              />
            }
          />
        </Route>
      </Routes>

      {/* Modal overlay - only when backgroundLocation is set */}
      {backgroundLocation && (
        <Routes>
          <Route path="/login"  element={<AuthModal initialView="login"  isModal={true} />} />
          <Route path="/signup" element={<AuthModal initialView="signup" isModal={true} />} />
        </Routes>
      )}
    </>
  )
}

// ── App ────────────────────────────────────────────────────────────────────────
export default function App() {
  const basename = import.meta.env.BASE_URL.replace(/\/$/, '') || '/'

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename={basename}>
        <Root />
      </BrowserRouter>
      <Toaster
        position="top-center"
        toastOptions={{ style: { fontSize: '13px' }, duration: 3000 }}
      />
    </QueryClientProvider>
  )
}
