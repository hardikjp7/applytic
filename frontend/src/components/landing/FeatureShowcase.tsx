import { useScrollReveal } from './useScrollReveal'

// Professional SVG icon in a rounded dark container - matches reference design
function IconBox({ color, bg, children }: { color: string; bg: string; children: React.ReactNode }) {
  return (
    <div
      className="w-12 h-12 rounded-xl flex items-center justify-center mb-5 flex-shrink-0"
      style={{ background: bg, border: `1px solid ${color}25` }}
    >
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
           stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        {children}
      </svg>
    </div>
  )
}

const FEATURES = [
  {
    icon: (
      // Kanban grid
      <>
        <rect x="3" y="3" width="7" height="7" rx="1"/>
        <rect x="14" y="3" width="7" height="7" rx="1"/>
        <rect x="3" y="14" width="7" height="7" rx="1"/>
        <rect x="14" y="14" width="7" height="4" rx="1"/>
      </>
    ),
    color: '#818cf8', bg: 'rgba(99,102,241,0.12)',
    title: 'Kanban board',
    desc: 'Drag applications through Applied - Screened - Interview - Offer. Status history logged automatically.',
  },
  {
    icon: (
      // Waveform / pulse
      <polyline points="2 12 6 6 10 18 14 8 18 14 22 12"/>
    ),
    color: '#22d3ee', bg: 'rgba(34,211,238,0.1)',
    title: 'AI pattern analysis',
    desc: 'Computes response rates across 6 dimensions: source channel, resume version, company size, role level, velocity, and funnel stage.',
  },
  {
    icon: (
      // Chat bubble with dots
      <>
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        <line x1="9" y1="11" x2="9" y2="11" strokeWidth="2.5"/>
        <line x1="12" y1="11" x2="12" y2="11" strokeWidth="2.5"/>
        <line x1="15" y1="11" x2="15" y2="11" strokeWidth="2.5"/>
      </>
    ),
    color: '#a78bfa', bg: 'rgba(167,139,250,0.1)',
    title: 'AI coaching chat',
    desc: 'Chat with a coach that has read every application you\'ve logged. Ask "why am I getting ghosted?" and get a data-specific answer back.',
  },
  {
    icon: (
      // Clipboard with checkmark
      <>
        <path d="M9 2h6a2 2 0 0 1 2 2v1H7V4a2 2 0 0 1 2-2z"/>
        <rect x="5" y="5" width="14" height="16" rx="2"/>
        <path d="M9 11l2 2 4-4"/>
      </>
    ),
    color: '#60a5fa', bg: 'rgba(96,165,250,0.1)',
    title: 'Interview prep',
    desc: 'Generate 10 tailored interview questions from the job description with one click, powered by Amazon Nova Lite. Check them off as you practice and save your own answer notes.',
  },
  {
    icon: (
      // Warning triangle
      <>
        <path d="M12 2L1 21h22L12 2z"/>
        <line x1="12" y1="9" x2="12" y2="13"/>
        <line x1="12" y1="17" x2="12" y2="17.01"/>
      </>
    ),
    color: '#f87171', bg: 'rgba(248,113,113,0.1)',
    title: 'Rejection pattern alerts',
    desc: 'Every Monday, Applytic scans your data for dead resume versions, dead source channels, and dropping response rates - and flags them before you waste more applications on what isn\'t working.',
  },
  {
    icon: (
      // Calendar with notification
      <>
        <rect x="3" y="4" width="18" height="18" rx="2"/>
        <line x1="16" y1="2" x2="16" y2="6"/>
        <line x1="8" y1="2" x2="8" y2="6"/>
        <line x1="3" y1="10" x2="21" y2="10"/>
        <circle cx="17" cy="17" r="3" fill="rgba(248,113,113,0.2)" stroke="#f87171"/>
        <line x1="17" y1="15.5" x2="17" y2="17.5" stroke="#f87171"/>
        <line x1="17" y1="18.5" x2="17" y2="18.5" stroke="#f87171" strokeWidth="2.5"/>
      </>
    ),
    color: '#fb923c', bg: 'rgba(251,146,60,0.1)',
    title: 'Follow-up reminders',
    desc: 'Set a follow-up date on any application. Get a daily email when applications are overdue for a response.',
  },
  {
    icon: (
      // Document with version lines
      <>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="8" y1="13" x2="16" y2="13"/>
        <line x1="8" y1="17" x2="13" y2="17"/>
      </>
    ),
    color: '#4ade80', bg: 'rgba(74,222,128,0.08)',
    title: 'Resume version tracking',
    desc: 'Upload multiple PDF versions and tag each application with which one you sent. Analytics shows conversion rate per version side by side.',
  },
  {
    icon: (
      // Envelope / mail
      <>
        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
        <polyline points="22,6 12,13 2,6"/>
      </>
    ),
    color: '#fbbf24', bg: 'rgba(251,191,36,0.08)',
    title: 'Weekly digest',
    desc: 'Every Monday - a summary of your week\'s activity plus one AI-generated personalised tip powered by Amazon Nova Lite.',
  },
  {
    icon: (
      // Target / goal
      <>
        <circle cx="12" cy="12" r="10"/>
        <circle cx="12" cy="12" r="6"/>
        <circle cx="12" cy="12" r="2"/>
      </>
    ),
    color: '#f472b6', bg: 'rgba(244,114,182,0.08)',
    title: 'Weekly goal tracking',
    desc: 'Set a weekly application target. Progress bar, streak counter, and inline goal editing right on the Dashboard.',
  },
  {
    icon: (
      // Clock / notes
      <>
        <circle cx="12" cy="12" r="10"/>
        <polyline points="12 6 12 12 16 14"/>
      </>
    ),
    color: '#34d399', bg: 'rgba(52,211,153,0.08)',
    title: 'Notes timeline',
    desc: 'Add timestamped notes to any application - recruiter names, interview feedback, follow-up outcomes. Full audit trail.',
  },
  {
    icon: (
      // CSV / arrows
      <>
        <polyline points="8 17 12 21 16 17"/>
        <line x1="12" y1="12" x2="12" y2="21"/>
        <path d="M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.29"/>
      </>
    ),
    color: '#67e8f9', bg: 'rgba(103,232,249,0.08)',
    title: 'CSV export and import',
    desc: 'Export all applications in one click. Import from CSV with full validation, preview, and error reporting. Client-side and instant.',
  },
]

export default function FeatureShowcase() {
  useScrollReveal()

  return (
    <section id="features" className="py-24 px-6">
      <div className="max-w-6xl mx-auto">
        {/* Section header */}
        <div className="text-center mb-16">
          <p className="land-reveal text-xs font-semibold tracking-widest uppercase mb-4"
             style={{ color: '#22d3ee', letterSpacing: '0.15em' }}>
            Everything you need
          </p>
          <h2
            className="land-reveal text-4xl sm:text-5xl font-bold text-white mb-4 leading-tight"
            style={{ fontFamily: 'Syne, sans-serif', transitionDelay: '0.05s' }}
          >
            Your entire job search.<br />Intelligently organized.
          </h2>
          <p className="land-reveal text-gray-400 text-lg max-w-2xl mx-auto" style={{ transitionDelay: '0.1s' }}>
            From the moment you apply to the day you sign an offer, Applytic has every
            data point you need to make smarter decisions.
          </p>
        </div>

        {/* Feature grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURES.map((f, i) => (
            <div
              key={f.title}
              className="land-reveal land-glass p-6"
              style={{ transitionDelay: `${0.04 * (i % 3)}s` }}
            >
              <IconBox color={f.color} bg={f.bg}>
                {f.icon}
              </IconBox>
              <h3 className="text-white font-semibold text-base mb-2"
                  style={{ fontFamily: 'Syne, sans-serif' }}>
                {f.title}
              </h3>
              <p className="text-gray-400 text-sm leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
