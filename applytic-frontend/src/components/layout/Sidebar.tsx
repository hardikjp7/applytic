import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Kanban, BarChart2, MessageSquare, Upload, LogOut } from 'lucide-react'
import { signOut } from 'aws-amplify/auth'
import toast from 'react-hot-toast'

const nav = [
  { to: '/',          icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/board',     icon: Kanban,          label: 'Board' },
  { to: '/analytics', icon: BarChart2,        label: 'Analytics' },
  { to: '/coach',     icon: MessageSquare,    label: 'AI Coach' },
  { to: '/resumes',   icon: Upload,           label: 'Resumes' },
]

export default function Sidebar() {
  const handleSignOut = async () => {
    try {
      await signOut()
    } catch {
      toast.error('Sign out failed')
    }
  }

  return (
    <aside className="w-56 shrink-0 h-screen sticky top-0 border-r border-gray-100 flex flex-col bg-white">
      <div className="px-5 py-5 border-b border-gray-100">
        <span className="text-lg font-semibold text-brand-800 tracking-tight">applytic</span>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {nav.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-brand-50 text-brand-800 font-medium'
                  : 'text-gray-500 hover:bg-gray-50 hover:text-gray-800'
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-3 py-4 border-t border-gray-100">
        <button
          onClick={handleSignOut}
          className="flex items-center gap-3 px-3 py-2 w-full rounded-lg text-sm text-gray-500 hover:bg-gray-50 hover:text-gray-800 transition-colors"
        >
          <LogOut size={16} />
          Sign out
        </button>
      </div>
    </aside>
  )
}
