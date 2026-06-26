import { useEffect, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useScrollReveal } from './useScrollReveal'
import { useAuthStatus } from './useAuthStatus'

// Particle canvas animation
function useParticles(canvasRef: React.RefObject<HTMLCanvasElement>) {
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!

    const resize = () => {
      canvas.width  = canvas.offsetWidth
      canvas.height = canvas.offsetHeight
    }
    resize()
    window.addEventListener('resize', resize)

    const particles: { x: number; y: number; vx: number; vy: number; size: number; alpha: number }[] = []
    for (let i = 0; i < 60; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        size: Math.random() * 1.5 + 0.3,
        alpha: Math.random() * 0.4 + 0.1,
      })
    }

    let animId: number
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      particles.forEach(p => {
        p.x += p.vx
        p.y += p.vy
        if (p.x < 0) p.x = canvas.width
        if (p.x > canvas.width) p.x = 0
        if (p.y < 0) p.y = canvas.height
        if (p.y > canvas.height) p.y = 0
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(99,102,241,${p.alpha})`
        ctx.fill()
      })
      animId = requestAnimationFrame(draw)
    }
    draw()

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', resize)
    }
  }, [canvasRef])
}

export default function Hero() {
  const navigate  = useNavigate()
  const location  = useLocation()
  const isAuthenticated = useAuthStatus()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  useScrollReveal()
  useParticles(canvasRef)

  const openAuth = (path: '/login' | '/signup') => {
    if (isAuthenticated) { navigate('/dashboard', { replace: true }); return }
    navigate(path, { state: { backgroundLocation: location } })
  }

  const Tick = ({ color }: { color: string }) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.5">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
  )

  return (
    <section className="relative min-h-screen flex items-center overflow-hidden pt-24 pb-16">
      {/* Particle canvas */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full pointer-events-none"
        style={{ opacity: 0.6 }}
      />
      {/* Mesh */}
      <div className="land-mesh" />

      <div className="relative z-10 max-w-6xl mx-auto px-6 w-full">
        <div className="grid lg:grid-cols-2 gap-16 items-center">

          {/* ── Left: Copy ─────────────────────────────────────────────── */}
          <div className="space-y-7">
            {/* Badge */}
            <div className="land-reveal inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-medium"
                 style={{ background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.25)', color: '#a5b4fc' }}>
              <span className="land-pulse w-1.5 h-1.5 rounded-full bg-violet-400 inline-block" />
              Powered by Amazon Bedrock - Amazon Nova Lite
            </div>

            {/* Headline */}
            <h1
              className="land-reveal text-5xl lg:text-6xl xl:text-7xl font-bold text-white leading-[1.05] tracking-tight"
              style={{ fontFamily: 'Syne, sans-serif', transitionDelay: '0.05s' }}
            >
              Stop guessing.<br />
              <span className="land-grad-text">Start getting hired.</span>
            </h1>

            <p className="land-reveal text-gray-400 text-lg leading-relaxed max-w-lg"
               style={{ transitionDelay: '0.1s' }}>
              Applytic tracks every application you submit, detects patterns across your
              rejections, and delivers AI-powered coaching that turns your data into job offers.
            </p>

            {/* CTAs */}
            <div className="land-reveal flex flex-wrap gap-4 items-center" style={{ transitionDelay: '0.15s' }}>
              <button
                onClick={() => openAuth('/signup')}
                className="px-7 py-3.5 rounded-xl font-semibold text-white text-base transition-all hover:scale-[1.03] hover:shadow-[0_0_40px_rgba(99,102,241,0.4)]"
                style={{ background: 'linear-gradient(135deg,#6366f1,#8b5cf6)' }}
              >
                {isAuthenticated ? 'Go to Dashboard' : 'Get Started Free'}
              </button>
              <button
                onClick={() => document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' })}
                className="px-7 py-3.5 rounded-xl font-medium text-gray-300 text-sm border border-white/10 hover:border-indigo-500/40 hover:text-white transition-all flex items-center gap-2"
                style={{ background: 'rgba(255,255,255,0.03)' }}
              >
                See how it works
                <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/>
                </svg>
              </button>
            </div>
          </div>

          {/* ── Right: Animated Dashboard Mockup ───────────────────────── */}
          <div className="land-reveal relative flex items-center justify-center" style={{ transitionDelay: '0.2s' }}>
            {/* Glow rings */}
            <div className="land-glow-ring" style={{ width: 420, height: 420, top: '50%', left: '50%' }} />
            <div className="land-glow-ring" style={{ width: 340, height: 340, top: '50%', left: '50%', animationDelay: '1s' }} />

            {/* Main Dashboard Card */}
            <div
              className="land-float land-dash-card p-5 w-full max-w-sm shadow-2xl relative z-10"
              style={{ boxShadow: '0 40px 100px -20px rgba(99,102,241,0.3)' }}
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <div>
                  <div className="text-xs text-gray-500 mb-0.5">Application Pipeline</div>
                  <div className="font-bold text-white text-lg" style={{ fontFamily: 'Syne, sans-serif' }}>This Week</div>
                </div>
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs"
                     style={{ background: 'rgba(74,222,128,0.1)', color: '#4ade80', border: '1px solid rgba(74,222,128,0.2)' }}>
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="18 15 12 9 6 15"/>
                  </svg>
                  +18%
                </div>
              </div>

              {/* Bar Chart */}
              <div className="flex items-end gap-2 h-24 mb-4">
                {[
                  { h: '40%', delay: '0.1s', o: 0.5,  bg: 'linear-gradient(to top,#6366f1,#a78bfa)' },
                  { h: '60%', delay: '0.2s', o: 0.65, bg: 'linear-gradient(to top,#6366f1,#a78bfa)' },
                  { h: '75%', delay: '0.3s', o: 0.75, bg: 'linear-gradient(to top,#6366f1,#a78bfa)' },
                  { h: '55%', delay: '0.4s', o: 0.65, bg: 'linear-gradient(to top,#22d3ee,#67e8f9)' },
                  { h: '90%', delay: '0.5s', o: 1,    bg: 'linear-gradient(to top,#6366f1,#a78bfa)' },
                  { h: '70%', delay: '0.6s', o: 0.8,  bg: 'linear-gradient(to top,#6366f1,#a78bfa)' },
                  { h: '100%',delay: '0.7s', o: 1,    bg: 'linear-gradient(to top,#6366f1,#a78bfa)' },
                ].map((b, i) => (
                  <div
                    key={i}
                    className="land-bar flex-1 rounded-t"
                    style={{ height: b.h, animationDelay: b.delay, opacity: b.o, background: b.bg }}
                  />
                ))}
              </div>

              {/* Spark line */}
              <svg width="100%" height="36" viewBox="0 0 260 36" fill="none" className="mb-4">
                <path
                  d="M0 28 C40 28 40 8 80 14 C120 20 130 6 160 10 C190 14 200 4 260 6"
                  stroke="#22d3ee" strokeWidth="1.5" fill="none" className="land-spark"
                />
                <path
                  d="M0 28 C40 28 40 8 80 14 C120 20 130 6 160 10 C190 14 200 4 260 6 L260 36 L0 36Z"
                  fill="url(#heroSparkGrad)" opacity="0.12"
                />
                <defs>
                  <linearGradient id="heroSparkGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22d3ee"/>
                    <stop offset="100%" stopColor="#22d3ee" stopOpacity="0"/>
                  </linearGradient>
                </defs>
              </svg>

              {/* Status pills */}
              <div className="grid grid-cols-2 gap-2">
                {[
                  { label: 'Applied',    value: '24', bg: 'rgba(99,102,241,0.08)',  border: 'rgba(99,102,241,0.15)',  color: 'white' },
                  { label: 'Interviews', value: '7',  bg: 'rgba(34,211,238,0.06)',  border: 'rgba(34,211,238,0.15)',  color: '#22d3ee' },
                  { label: 'Offers',     value: '2',  bg: 'rgba(74,222,128,0.06)',  border: 'rgba(74,222,128,0.15)',  color: '#4ade80' },
                  { label: 'Rejected',   value: '11', bg: 'rgba(248,113,113,0.06)', border: 'rgba(248,113,113,0.15)', color: '#f87171' },
                ].map(s => (
                  <div key={s.label} className="rounded-lg p-2.5"
                       style={{ background: s.bg, border: `1px solid ${s.border}` }}>
                    <div className="text-xs text-gray-500 mb-1">{s.label}</div>
                    <div className="font-bold text-lg" style={{ fontFamily: 'Syne, sans-serif', color: s.color }}>{s.value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Floating AI Insight Card */}
            <div
              className="land-float-2 absolute -right-4 lg:-right-8 top-8 land-dash-card p-3.5 z-20"
              style={{ width: 200, boxShadow: '0 20px 50px -10px rgba(99,102,241,0.25)' }}
            >
              <div className="flex items-center gap-2 mb-2">
                <div className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
                     style={{ background: 'linear-gradient(135deg,#6366f1,#a78bfa)' }}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
                    <circle cx="12" cy="12" r="3"/>
                    <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
                  </svg>
                </div>
                <span className="text-xs font-medium text-violet-300">AI Coach</span>
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-green-400 land-pulse" />
              </div>
              <p className="text-xs text-gray-300 leading-relaxed">
                "LinkedIn is converting 3x better than Indeed for you. Switch your focus."
              </p>
            </div>

            {/* Floating Resume Card */}
            <div
              className="land-float absolute -left-4 lg:-left-8 bottom-12 land-dash-card p-3 z-20"
              style={{ width: 168, animationDelay: '2s', boxShadow: '0 20px 50px -10px rgba(34,211,238,0.15)' }}
            >
              <div className="text-xs text-gray-500 mb-1.5">Resume v3 vs v2</div>
              <div className="space-y-1.5">
                {[
                  { label: 'v3', pct: '42%', w: '42%', color: '#818cf8', bar: 'linear-gradient(90deg,#6366f1,#a78bfa)' },
                  { label: 'v2', pct: '18%', w: '18%', color: '#64748b', bar: '#334155' },
                ].map(r => (
                  <div key={r.label}>
                    <div className="flex justify-between text-xs mb-0.5">
                      <span style={{ color: r.color }}>{r.label}</span>
                      <span className="text-gray-400">{r.pct}</span>
                    </div>
                    <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
                      <div className="h-full rounded-full" style={{ width: r.w, background: r.bar }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

        </div>
      </div>
    </section>
  )
}
