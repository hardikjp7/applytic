import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Authenticator } from '@aws-amplify/ui-react'
import '@aws-amplify/ui-react/styles.css'
import { Toaster } from 'react-hot-toast'
import './lib/amplify'

import Sidebar from './components/layout/Sidebar'
import Dashboard from './pages/Dashboard'
import KanbanBoard from './components/kanban/KanbanBoard'
import AnalyticsDashboard from './components/analytics/AnalyticsDashboard'
import CoachChat from './components/chat/CoachChat'
import ResumeUpload from './components/resume/ResumeUpload'

export default function App() {
  return (
    <Authenticator>
      {() => (
        <BrowserRouter>
          <div className="flex h-screen overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-y-auto">
              <Routes>
                <Route path="/"          element={<Dashboard />} />
                <Route path="/board"     element={<KanbanBoard />} />
                <Route path="/analytics" element={<AnalyticsDashboard />} />
                <Route path="/coach"     element={<CoachChat />} />
                <Route path="/resumes"   element={<ResumeUpload />} />
              </Routes>
            </main>
          </div>
          <Toaster position="bottom-right" toastOptions={{ style: { fontSize: '13px' } }} />
        </BrowserRouter>
      )}
    </Authenticator>
  )
}
