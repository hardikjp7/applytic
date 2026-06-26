import { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStatus } from './useAuthStatus'

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [hidden, setHidden] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const lastY = useRef(0)
  const navigate = useNavigate()
  const location = useLocation()
  const isAuthenticated = useAuthStatus()

  useEffect(() => {
    const onScroll = () => {
      const y = window.scrollY
      setScrolled(y > 20)
      setHidden(y > lastY.current && y > 80)
      lastY.current = y
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const scrollTo = (id: string) => {
    setMobileOpen(false)
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
  }

  // If already authenticated, go straight to dashboard.
  // Otherwise open the modal over the landing page.
  const openAuth = (path: '/login' | '/signup') => {
    setMobileOpen(false)
    if (isAuthenticated) {
      navigate('/dashboard', { replace: true })
      return
    }
    navigate(path, { state: { backgroundLocation: location } })
  }

  const navLinks = [
    { label: 'Features',     id: 'features' },
    { label: 'How it works', id: 'how-it-works' },
    { label: 'About',        id: 'about' },
    { label: 'FAQ',          id: 'faq' },
  ]

  return (
    <header
      className={`land-nav fixed top-0 left-0 right-0 z-50 ${
        scrolled ? 'land-nav-scrolled' : ''
      } ${hidden ? 'land-nav-hidden' : ''}`}
    >
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <button
          onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
          className="flex items-center gap-2.5"
        >
          <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
               style={{ background: '#534ab7' }}>
            <span className="text-white font-bold text-base leading-none">A</span>
          </div>
          <span className="text-white font-semibold text-lg tracking-tight"
                style={{ fontFamily: 'Syne, sans-serif' }}>
            applytic
          </span>
        </button>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-8">
          {navLinks.map(({ label, id }) => (
            <button
              key={id}
              onClick={() => scrollTo(id)}
              className="text-sm text-gray-400 hover:text-white transition-colors"
            >
              {label}
            </button>
          ))}
        </nav>

        {/* Desktop CTAs */}
        <div className="hidden md:flex items-center gap-3">
          {isAuthenticated ? (
            // Already logged in - show a single "Go to Dashboard" link
            <button
              onClick={() => navigate('/dashboard', { replace: true })}
              className="text-sm font-medium px-4 py-2 rounded-lg text-white transition-all hover:opacity-90 hover:scale-[1.02]"
              style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
            >
              Go to Dashboard
            </button>
          ) : (
            <>
              <button
                onClick={() => openAuth('/login')}
                className="text-sm text-gray-400 hover:text-white transition-colors px-3 py-2"
              >
                Log in
              </button>
              <button
                onClick={() => openAuth('/signup')}
                className="text-sm font-medium px-4 py-2 rounded-lg text-white transition-all hover:opacity-90 hover:scale-[1.02]"
                style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
              >
                Get Started Free
              </button>
            </>
          )}
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden p-2 text-gray-400 hover:text-white"
          onClick={() => setMobileOpen(o => !o)}
          aria-label="Toggle menu"
        >
          {mobileOpen ? (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
            </svg>
          )}
        </button>
      </div>

      {/* Mobile menu */}
      <div
        className={`land-mobile-menu md:hidden border-t border-white/5 ${mobileOpen ? 'open' : ''}`}
        style={{ background: 'rgba(10,10,15,0.95)', backdropFilter: 'blur(20px)' }}
      >
        <div className="px-6 py-4 flex flex-col gap-4">
          {navLinks.map(({ label, id }) => (
            <button
              key={id}
              onClick={() => scrollTo(id)}
              className="text-sm text-gray-400 hover:text-white transition-colors text-left py-1"
            >
              {label}
            </button>
          ))}
          <div className="pt-2 border-t border-white/5 flex flex-col gap-2">
            {isAuthenticated ? (
              <button
                onClick={() => navigate('/dashboard', { replace: true })}
                className="text-sm font-medium px-4 py-2.5 rounded-lg text-white text-center"
                style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
              >
                Go to Dashboard
              </button>
            ) : (
              <>
                <button
                  onClick={() => openAuth('/login')}
                  className="text-sm text-gray-400 hover:text-white text-left py-2"
                >
                  Log in
                </button>
                <button
                  onClick={() => openAuth('/signup')}
                  className="text-sm font-medium px-4 py-2.5 rounded-lg text-white text-center"
                  style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
                >
                  Get Started Free
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
