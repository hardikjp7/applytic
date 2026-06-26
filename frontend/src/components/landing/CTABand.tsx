import { useNavigate, useLocation } from 'react-router-dom'
import { useScrollReveal } from './useScrollReveal'
import { useAuthStatus } from './useAuthStatus'

export default function CTABand() {
  useScrollReveal()
  const navigate = useNavigate()
  const location = useLocation()
  const isAuthenticated = useAuthStatus()

  const handlePrimary = () => {
    if (isAuthenticated) {
      navigate('/dashboard', { replace: true })
    } else {
      navigate('/signup', { state: { backgroundLocation: location } })
    }
  }

  return (
    <section className="py-24 px-6">
      <div className="max-w-4xl mx-auto">
        <div
          className="land-reveal relative rounded-3xl overflow-hidden p-10 sm:p-16 text-center"
          style={{
            background: 'linear-gradient(135deg, rgba(99,102,241,0.15) 0%, rgba(167,139,250,0.1) 50%, rgba(34,211,238,0.08) 100%)',
            border: '1px solid rgba(99,102,241,0.25)',
          }}
        >
          <div className="absolute inset-0 pointer-events-none"
               style={{ background: 'radial-gradient(ellipse 60% 60% at 50% 0%, rgba(99,102,241,0.2), transparent)' }} />

          <div className="relative z-10">
            <h2
              className="text-4xl sm:text-5xl font-bold text-white mb-4"
              style={{ fontFamily: 'Syne, sans-serif' }}
            >
              {isAuthenticated ? 'Welcome back' : 'Start tracking your search today'}
            </h2>
            <p className="text-gray-400 text-lg mb-8 max-w-xl mx-auto">
              {isAuthenticated
                ? 'Your dashboard is ready.'
                : 'Free to use. No card required. Takes 30 seconds to sign up.'}
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <button
                onClick={handlePrimary}
                className="group px-8 py-3.5 rounded-xl font-semibold text-white text-base transition-all hover:scale-[1.03] hover:shadow-[0_0_40px_rgba(99,102,241,0.4)]"
                style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
              >
                {isAuthenticated ? 'Go to Dashboard' : 'Get Started Free'}
                <span className="ml-2 group-hover:translate-x-1 inline-block transition-transform">-&gt;</span>
              </button>
              {!isAuthenticated && (
                <a
                  href="https://github.com/hardikjp7/applytic"
                  target="_blank"
                  rel="noreferrer"
                  className="px-8 py-3.5 rounded-xl font-medium text-gray-300 text-base border border-white/10 hover:border-indigo-500/40 hover:text-white transition-all text-center"
                  style={{ background: 'rgba(255,255,255,0.03)' }}
                >
                  View on GitHub
                </a>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
