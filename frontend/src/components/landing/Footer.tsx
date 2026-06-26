const FOOTER_LINKS = {
  Product: [
    { label: 'Features',      href: '#features',   anchor: true },
    { label: 'How it works',  href: '#how-it-works', anchor: true },
    { label: 'Changelog',     href: 'https://github.com/hardikjp7/applytic/blob/main/CHANGELOG.md', external: true },
  ],
  Developers: [
    { label: 'GitHub Repo',       href: 'https://github.com/hardikjp7/applytic', external: true },
    { label: 'API Docs',          href: 'https://d3jumje9o63lys.cloudfront.net/api/docs/index.html', external: true },
    { label: 'Self-Host Guide',   href: 'https://github.com/hardikjp7/applytic/blob/main/CONTRIBUTING.md', external: true },
    { label: 'FAQ',               href: '#faq', anchor: true },
  ],
  Company: [
    { label: 'About',           href: '#about', anchor: true },
    { label: 'Privacy Policy',  href: '/privacy', internal: true },
    { label: 'Terms of Service', href: '/terms', internal: true },
    { label: 'Contact',         href: 'https://hardikjp7.com/#contact', external: true },
  ],
}

interface LinkItem {
  label: string
  href: string
  anchor?: boolean
  external?: boolean
  internal?: boolean
}

function FooterLink({ item }: { item: LinkItem }) {
  const cls = "text-sm text-gray-500 hover:text-indigo-400 transition-colors"

  if (item.anchor) {
    return (
      <button
        className={cls}
        onClick={() => document.getElementById(item.href.replace('#', ''))?.scrollIntoView({ behavior: 'smooth' })}
      >
        {item.label}
      </button>
    )
  }
  if (item.external) {
    return (
      <a href={item.href} target="_blank" rel="noreferrer" className={cls}>
        {item.label}
      </a>
    )
  }
  // internal route - plain anchor, React Router handles it
  return <a href={item.href} className={cls}>{item.label}</a>
}

export default function Footer() {
  return (
    <footer className="border-t border-white/5 py-16 px-6"
            style={{ background: 'rgba(5,5,10,0.8)' }}>
      <div className="max-w-6xl mx-auto">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-10 mb-12">
          {/* Brand column */}
          <div>
            <div className="flex items-center gap-2.5 mb-4">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                   style={{ background: '#534ab7' }}>
                <span className="text-white font-bold text-base leading-none">A</span>
              </div>
              <span className="text-white font-semibold text-lg"
                    style={{ fontFamily: 'Syne, sans-serif' }}>
                applytic
              </span>
            </div>
            <p className="text-gray-500 text-xs leading-relaxed max-w-[200px]">
              AI-powered job application tracker. Free to use. Built on AWS.
            </p>
          </div>

          {/* Link columns */}
          {Object.entries(FOOTER_LINKS).map(([section, links]) => (
            <div key={section}>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-4">
                {section}
              </p>
              <ul className="space-y-3">
                {links.map(link => (
                  <li key={link.label}>
                    <FooterLink item={link} />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="pt-8 border-t border-white/5 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-gray-600">
            &copy; 2026 Applytic - Built by{' '}
            <a href="https://hardikjp7.com" target="_blank" rel="noreferrer"
               className="text-gray-500 hover:text-indigo-400 transition-colors">
              Hardik
            </a>
          </p>
          <div className="flex items-center gap-5">
            <a href="https://github.com/hardikjp7/applytic" target="_blank" rel="noreferrer"
               className="text-gray-600 hover:text-indigo-400 transition-colors"
               aria-label="GitHub">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
              </svg>
            </a>
          </div>
        </div>
      </div>
    </footer>
  )
}
