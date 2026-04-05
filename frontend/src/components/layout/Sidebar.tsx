import { NavLink, useLocation } from 'react-router-dom'
import { LayoutDashboard, Kanban, BarChart2, MessageSquare, Upload, LogOut, Sun, Moon, X } from 'lucide-react'
import { signOut, getCurrentUser } from 'aws-amplify/auth'
import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'

const nav = [
  { to: '/',          icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/board',     icon: Kanban,          label: 'Board' },
  { to: '/analytics', icon: BarChart2,        label: 'Analytics' },
  { to: '/coach',     icon: MessageSquare,    label: 'AI Coach' },
  { to: '/resumes',   icon: Upload,           label: 'Resumes' },
]

interface Props {
  theme: 'dark' | 'light'
  toggleTheme: () => void
  sidebarOpen: boolean
  setSidebarOpen: (open: boolean) => void
}

export default function Sidebar({ theme, toggleTheme, sidebarOpen, setSidebarOpen }: Props) {
  const [userEmail, setUserEmail] = useState('')
  const location = useLocation()

  useEffect(() => {
    getCurrentUser().then(u => setUserEmail(u.signInDetails?.loginId ?? '')).catch(() => {})
  }, [])

  const handleSignOut = async () => {
    try { await signOut() } catch { toast.error('Sign out failed') }
  }

  const initials = userEmail ? userEmail[0].toUpperCase() : '?'

  return (
    <aside className={`
      fixed lg:static inset-y-0 left-0 z-30
      w-56 shrink-0 h-screen flex flex-col
      bg-white dark:bg-gray-900
      border-r border-gray-100 dark:border-gray-800
      transition-transform duration-200
      ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
    `}>
      {/* Header */}
      <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
        <span className="text-lg font-semibold text-brand-800 dark:text-brand-400 tracking-tight">applytic</span>
        <button
          onClick={() => setSidebarOpen(false)}
          className="lg:hidden p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
        >
          <X size={16} />
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {nav.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-brand-50 dark:bg-brand-800/20 text-brand-800 dark:text-brand-400 font-medium'
                  : 'text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-800 dark:hover:text-gray-100'
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-3 py-3 border-t border-gray-100 dark:border-gray-800 space-y-1">
        {/* Dark mode toggle */}
        <button
          onClick={toggleTheme}
          className="flex items-center gap-3 px-3 py-2 w-full rounded-lg text-sm text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-800 dark:hover:text-gray-100 transition-colors"
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          {theme === 'dark' ? 'Light mode' : 'Dark mode'}
        </button>

        {/* User info */}
        {userEmail && (
          <div className="flex items-center gap-2.5 px-3 py-2">
            <div className="w-6 h-6 rounded-full bg-brand-100 dark:bg-brand-800 flex items-center justify-center text-xs font-medium text-brand-700 dark:text-brand-300 shrink-0">
              {initials}
            </div>
            <span className="text-xs text-gray-400 dark:text-gray-500 truncate">{userEmail}</span>
          </div>
        )}

        {/* Sign out */}
        <button
          onClick={handleSignOut}
          className="flex items-center gap-3 px-3 py-2 w-full rounded-lg text-sm text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-red-500 dark:hover:text-red-400 transition-colors"
        >
          <LogOut size={16} />
          Sign out
        </button>
      </div>
    </aside>
  )
}
