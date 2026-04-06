import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Authenticator } from '@aws-amplify/ui-react'
import '@aws-amplify/ui-react/styles.css'
import { Toaster } from 'react-hot-toast'
import { useState, useEffect } from 'react'
import './lib/amplify'
import { getInitialTheme, applyTheme } from './lib/theme'

import Sidebar from './components/layout/Sidebar'
import ErrorBoundary from './components/layout/ErrorBoundary'
import Dashboard from './pages/Dashboard'
import KanbanBoard from './components/kanban/KanbanBoard'
import AnalyticsDashboard from './components/analytics/AnalyticsDashboard'
import CoachChat from './components/chat/CoachChat'
import ResumeUpload from './components/resume/ResumeUpload'

export interface Message {
  role: 'user' | 'assistant'
  content: string
}

const INITIAL_MESSAGES: Message[] = [
  {
    role: 'assistant',
    content: "Hi! I'm your AI job search coach. I have access to your full application history and pattern data. Ask me anything — I'll give you specific advice based on your actual numbers.",
  },
]

export default function App() {
  const [chatHistory, setChatHistory] = useState<Message[]>(INITIAL_MESSAGES)
  const [theme, setTheme] = useState<'dark' | 'light'>(getInitialTheme)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  const toggleTheme = () => setTheme(t => t === 'dark' ? 'light' : 'dark')

  return (
    <Authenticator>
      {() => (
        <BrowserRouter>
          <div className="flex h-screen overflow-hidden bg-gray-50 dark:bg-gray-950">
            {/* Mobile overlay */}
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
              {/* Mobile top bar */}
              <div className="lg:hidden flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
                <button
                  onClick={() => setSidebarOpen(true)}
                  className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
                  </svg>
                </button>
                <span className="text-sm font-semibold text-brand-800 dark:text-brand-400">applytic</span>
                <div className="w-8" />
              </div>

              <main className="flex-1 overflow-y-auto">
                <ErrorBoundary>
                  <Routes>
                    <Route path="/"          element={<Dashboard />} />
                    <Route path="/board"     element={<KanbanBoard />} />
                    <Route path="/analytics" element={<AnalyticsDashboard />} />
                    <Route path="/coach"     element={
                      <CoachChat messages={chatHistory} setMessages={setChatHistory} />
                    } />
                    <Route path="/resumes"   element={<ResumeUpload />} />
                  </Routes>
                </ErrorBoundary>
              </main>
            </div>
          </div>
          <Toaster
            position="top-center"
            toastOptions={{
              style: { fontSize: '13px' },
              duration: 3000,
            }}
          />
        </BrowserRouter>
      )}
    </Authenticator>
  )
}
