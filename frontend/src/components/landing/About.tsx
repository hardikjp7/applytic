import { useScrollReveal } from './useScrollReveal'

export default function About() {
  useScrollReveal()

  return (
    <section id="about" className="py-24 px-6">
      <div className="max-w-4xl mx-auto">
        <div className="land-reveal land-glass p-8 sm:p-12">
          <div className="flex flex-col sm:flex-row gap-8 items-start">
            {/* Avatar / logo mark */}
            <div className="flex-shrink-0">
              <div className="w-16 h-16 rounded-2xl flex items-center justify-center text-2xl font-bold text-white"
                   style={{ background: '#534ab7', fontFamily: 'Syne, sans-serif' }}>
                H
              </div>
            </div>

            <div>
              <div className="land-reveal inline-flex items-center gap-2 px-3 py-1 rounded-full border border-indigo-500/20 bg-indigo-500/5 text-xs text-indigo-400 mb-4">
                Why I built this
              </div>

              <h2
                className="text-3xl font-bold text-white mb-6"
                style={{ fontFamily: 'Syne, sans-serif' }}
              >
                I was job hunting with no data on why I was getting rejected.
              </h2>

              <div className="space-y-4 text-gray-400 text-sm sm:text-base leading-relaxed">
                <p>
                  I had a spreadsheet with company names and "rejected" written next to most of them -
                  but no signal on <em className="text-gray-300 not-italic">why</em>. Was it my resume? The channel? The company size?
                </p>
                <p>
                  So I instrumented my own job search. Every application became a data point. After a few weeks
                  I had enough data to see that my <code className="text-indigo-400 text-xs px-1.5 py-0.5 rounded bg-indigo-500/10">v1-generic</code> resume
                  had a 0% response rate from enterprise companies, while <code className="text-indigo-400 text-xs px-1.5 py-0.5 rounded bg-indigo-500/10">v3-ml-focused</code> was
                  getting interviews from startups via referrals. That's the kind of insight you can act on.
                </p>
                <p>
                  I built Applytic for myself. Then I put it on AWS properly and opened it up.
                  It's free to use - no trial, no card, no limits.
                </p>
              </div>

              <div className="mt-6 pt-6 border-t border-white/5 flex items-center gap-4">
                <a
                  href="https://github.com/hardikjp7"
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-gray-500 hover:text-indigo-400 transition-colors flex items-center gap-1.5"
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
                  </svg>
                  hardikjp7
                </a>
                <a
                  href="https://hardikjp7.com"
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-gray-500 hover:text-indigo-400 transition-colors"
                >
                  hardikjp7.com
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
