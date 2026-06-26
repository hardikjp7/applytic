import { useScrollReveal } from './useScrollReveal'

// Checkmark bullet shared across all three sections
function Check({ color }: { color: string }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.5">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
  )
}

// ── Track ──────────────────────────────────────────────────────────────────────
function TrackSection() {
  return (
    <div className="grid lg:grid-cols-2 gap-16 items-center">

      {/* Visual - left */}
      <div className="land-reveal slide-left order-2 lg:order-1">
        <div className="land-grad-border">
          <div className="land-dash-card p-6 rounded-2xl">
            {/* Window chrome */}
            <div className="flex items-center gap-2 mb-5">
              <div className="w-2 h-2 rounded-full bg-red-500" />
              <div className="w-2 h-2 rounded-full bg-yellow-500" />
              <div className="w-2 h-2 rounded-full bg-green-500" />
              <span className="ml-2 text-xs text-gray-500">Application Board</span>
            </div>

            {/* Kanban columns */}
            <div className="grid grid-cols-4 gap-2 text-xs">
              {/* Applied */}
              <div>
                <div className="text-gray-500 mb-2 text-center font-semibold">Applied</div>
                <div className="space-y-2">
                  <div className="rounded-lg p-2" style={{ background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)' }}>
                    <div className="text-white font-semibold text-xs mb-0.5">Stripe</div>
                    <div className="text-gray-500 text-xs">SWE II</div>
                    <div className="mt-1.5 land-tag-applied px-1.5 py-0.5 rounded text-xs inline-block">Applied</div>
                  </div>
                  <div className="rounded-lg p-2" style={{ background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.12)' }}>
                    <div className="text-white font-semibold text-xs mb-0.5">Linear</div>
                    <div className="text-gray-500 text-xs">Backend</div>
                  </div>
                </div>
              </div>

              {/* Screen */}
              <div>
                <div className="text-gray-500 mb-2 text-center font-semibold">Screen</div>
                <div>
                  <div className="rounded-lg p-2" style={{ background: 'rgba(34,211,238,0.06)', border: '1px solid rgba(34,211,238,0.15)' }}>
                    <div className="text-white font-semibold text-xs mb-0.5">Vercel</div>
                    <div className="text-gray-500 text-xs">Fullstack</div>
                  </div>
                </div>
              </div>

              {/* Interview */}
              <div>
                <div className="text-gray-500 mb-2 text-center font-semibold">Interview</div>
                <div>
                  <div className="rounded-lg p-2" style={{ background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.2)' }}>
                    <div className="text-white font-semibold text-xs mb-0.5">Notion</div>
                    <div className="text-gray-500 text-xs">Platform</div>
                    <div className="mt-1.5 land-tag-interview px-1.5 py-0.5 rounded text-xs inline-block">Round 2</div>
                  </div>
                </div>
              </div>

              {/* Offer */}
              <div>
                <div className="text-gray-500 mb-2 text-center font-semibold">Offer</div>
                <div>
                  <div className="rounded-lg p-2" style={{ background: 'rgba(74,222,128,0.08)', border: '1px solid rgba(74,222,128,0.2)' }}>
                    <div className="text-white font-semibold text-xs mb-0.5">Figma</div>
                    <div className="text-gray-500 text-xs">Eng Lead</div>
                    <div className="mt-1.5 land-tag-offer px-1.5 py-0.5 rounded text-xs inline-block">Offer!</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Text - right */}
      <div className="land-reveal slide-right order-1 lg:order-2 space-y-6">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs"
             style={{ background: 'rgba(99,102,241,0.1)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.2)' }}>
          Track
        </div>
        <h2 className="text-3xl lg:text-4xl font-bold text-white leading-tight"
            style={{ fontFamily: 'Syne, sans-serif' }}>
          Your entire pipeline. One board.
        </h2>
        <p className="text-gray-400 leading-relaxed">
          Visualize every application in a drag-and-drop Kanban board. Click any card to see the
          full status timeline, edit details, or attach notes - all without losing context.
        </p>
        <ul className="space-y-3">
          {[
            'Drag-and-drop between status columns',
            'Full status event timeline per application',
            'Search + filter by company, role, or channel',
          ].map(t => (
            <li key={t} className="flex items-center gap-3 text-sm text-gray-300">
              <Check color="#6366f1" />{t}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

// ── Analyze ────────────────────────────────────────────────────────────────────
function AnalyzeSection() {
  const BARS = [
    { label: 'LinkedIn',     pct: '34%', w: '34%', color: '#4ade80',  bar: 'linear-gradient(90deg,#22d3ee,#67e8f9)' },
    { label: 'Referral',     pct: '61%', w: '61%', color: '#a78bfa',  bar: 'linear-gradient(90deg,#a78bfa,#c4b5fd)' },
    { label: 'Indeed',       pct: '11%', w: '11%', color: '#64748b',  bar: '#334155' },
    { label: 'Company Site', pct: '22%', w: '22%', color: '#818cf8',  bar: 'linear-gradient(90deg,#6366f1,#818cf8)' },
    { label: 'AngelList',    pct: '8%',  w: '8%',  color: '#64748b',  bar: '#1e293b' },
  ]

  return (
    <div className="grid lg:grid-cols-2 gap-16 items-center">

      {/* Text - left */}
      <div className="land-reveal slide-left space-y-6">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs"
             style={{ background: 'rgba(34,211,238,0.08)', color: '#22d3ee', border: '1px solid rgba(34,211,238,0.2)' }}>
          Analyze
        </div>
        <h2 className="text-3xl lg:text-4xl font-bold text-white leading-tight"
            style={{ fontFamily: 'Syne, sans-serif' }}>
          Know exactly what's working.
        </h2>
        <p className="text-gray-400 leading-relaxed">
          The pattern engine computes hard response rates - not vibes. Is LinkedIn 3x better
          than Indeed for your profile? Which resume version converts? You'll know the exact numbers.
        </p>
        <ul className="space-y-3">
          {[
            'Response rate per source channel',
            'Conversion rate per resume version',
            'Response rate by company size & role seniority',
          ].map(t => (
            <li key={t} className="flex items-center gap-3 text-sm text-gray-300">
              <Check color="#22d3ee" />{t}
            </li>
          ))}
        </ul>
      </div>

      {/* Visual - right */}
      <div className="land-reveal slide-right">
        <div className="land-grad-border">
          <div className="land-dash-card p-6 rounded-2xl">
            <div className="text-xs text-gray-500 mb-1">Source Channel Analysis</div>
            <div className="font-bold text-white mb-5" style={{ fontFamily: 'Syne, sans-serif' }}>
              Response Rate Comparison
            </div>
            <div className="space-y-3">
              {BARS.map(b => (
                <div key={b.label}>
                  <div className="flex justify-between text-xs mb-1.5">
                    <span className="text-gray-300">{b.label}</span>
                    <span className="font-semibold" style={{ color: b.color }}>{b.pct}</span>
                  </div>
                  <div className="h-2.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
                    <div className="h-full rounded-full" style={{ width: b.w, background: b.bar }} />
                  </div>
                </div>
              ))}
            </div>
            {/* AI tip */}
            <div className="mt-5 p-3 rounded-xl flex items-start gap-3"
                 style={{ background: 'rgba(167,139,250,0.07)', border: '1px solid rgba(167,139,250,0.15)' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" strokeWidth="2"
                   className="mt-0.5 flex-shrink-0">
                <circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>
              </svg>
              <p className="text-xs text-gray-400">
                AI: Referral rate is 5.5x higher than Indeed. Stop applying cold - ask your network first.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Coach ──────────────────────────────────────────────────────────────────────
function CoachSection() {
  const AIIcon = () => (
    <div className="w-6 h-6 rounded-full flex-shrink-0 flex items-center justify-center"
         style={{ background: 'linear-gradient(135deg,#6366f1,#a78bfa)' }}>
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
      </svg>
    </div>
  )

  return (
    <div className="grid lg:grid-cols-2 gap-16 items-center">

      {/* Visual - left */}
      <div className="land-reveal slide-left order-2 lg:order-1">
        <div className="land-grad-border">
          <div className="land-dash-card p-6 rounded-2xl">
            {/* Header */}
            <div className="flex items-center gap-3 mb-5 pb-4"
                 style={{ borderBottom: '1px solid rgba(99,102,241,0.12)' }}>
              <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                   style={{ background: 'linear-gradient(135deg,#6366f1,#a78bfa)' }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
                  <circle cx="12" cy="12" r="3"/>
                  <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
                </svg>
              </div>
              <div>
                <div className="text-sm font-semibold text-white">AI Coach</div>
                <div className="text-xs text-green-400">Online - analyzing your data</div>
              </div>
            </div>

            {/* Chat */}
            <div className="space-y-4">
              {/* User message */}
              <div className="flex justify-end">
                <div className="max-w-xs rounded-2xl rounded-tr-sm px-3.5 py-2.5 text-xs text-white"
                     style={{ background: 'rgba(99,102,241,0.25)', border: '1px solid rgba(99,102,241,0.3)' }}>
                  Why am I getting ghosted after applying to startups?
                </div>
              </div>

              {/* AI response */}
              <div className="flex items-start gap-2.5">
                <AIIcon />
                <div className="max-w-xs rounded-2xl rounded-tl-sm px-3.5 py-2.5 text-xs text-gray-300"
                     style={{ background: 'rgba(15,15,30,0.8)', border: '1px solid rgba(99,102,241,0.15)' }}>
                  Your data shows a{' '}
                  <span className="text-white font-semibold">4% response rate</span>
                  {' '}from startups (&lt;50 employees) vs{' '}
                  <span className="text-cyan-400 font-semibold">28%</span>
                  {' '}from Series B+. Your resume v2 uses startup language but lacks metrics.
                  Switch to{' '}
                  <span className="text-violet-300 font-semibold">resume v3</span>
                  {' '}- it's driving all your Series B responses.
                </div>
              </div>

              {/* Second user message */}
              <div className="flex justify-end">
                <div className="max-w-xs rounded-2xl rounded-tr-sm px-3.5 py-2.5 text-xs text-white"
                     style={{ background: 'rgba(99,102,241,0.25)', border: '1px solid rgba(99,102,241,0.3)' }}>
                  Which skills should I highlight for Series B companies?
                </div>
              </div>

              {/* Typing indicator */}
              <div className="flex items-start gap-2.5">
                <AIIcon />
                <div className="rounded-2xl rounded-tl-sm px-4 py-3"
                     style={{ background: 'rgba(15,15,30,0.8)', border: '1px solid rgba(99,102,241,0.15)' }}>
                  <div className="flex gap-1">
                    {[0, 0.2, 0.4].map((d, i) => (
                      <span key={i} className="w-1.5 h-1.5 rounded-full bg-gray-500 land-pulse"
                            style={{ animationDelay: `${d}s` }} />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Text - right */}
      <div className="land-reveal slide-right order-1 lg:order-2 space-y-6">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs"
             style={{ background: 'rgba(167,139,250,0.08)', color: '#a78bfa', border: '1px solid rgba(167,139,250,0.2)' }}>
          Coach
        </div>
        <h2 className="text-3xl lg:text-4xl font-bold text-white leading-tight"
            style={{ fontFamily: 'Syne, sans-serif' }}>
          An AI coach that actually knows you.
        </h2>
        <p className="text-gray-400 leading-relaxed">
          Most AI advice is generic. Applytic feeds your actual application history, response rates,
          and resume performance into Amazon Nova Lite as structured context. The answers you get
          are specific, actionable, and grounded in evidence.
        </p>
        <ul className="space-y-3">
          {[
            'Questions answered with your data as context',
            'Pattern-first analysis, LLM interprets the numbers',
            'Monday email digest: stats + one key action item',
          ].map(t => (
            <li key={t} className="flex items-center gap-3 text-sm text-gray-300">
              <Check color="#a78bfa" />{t}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

// ── DeepDive export ────────────────────────────────────────────────────────────
export default function DeepDive() {
  useScrollReveal()

  return (
    <section className="py-28 px-6 space-y-32">
      <div className="max-w-6xl mx-auto space-y-32">
        <TrackSection />
        <AnalyzeSection />
        <CoachSection />
      </div>
    </section>
  )
}
