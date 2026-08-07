// Terms of Service page - linked from footer and signup form, public route.

import { Link } from 'react-router-dom'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-10">
      <h2 className="text-xl font-semibold text-white mb-3"
          style={{ fontFamily: 'Syne, sans-serif' }}>
        {title}
      </h2>
      <div className="space-y-3 text-gray-400 text-sm leading-relaxed">
        {children}
      </div>
    </div>
  )
}

export default function Terms() {
  return (
    <div style={{ background: '#0a0a0f', minHeight: '100vh', color: '#f9fafb', fontFamily: 'DM Sans, system-ui, sans-serif' }}>
      {/* Minimal nav */}
      <div className="border-b border-white/5 px-6 py-4">
        <Link to="/" className="flex items-center gap-2.5 w-fit">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
               style={{ background: '#534ab7' }}>
            <span className="text-white font-bold text-sm leading-none">A</span>
          </div>
          <span className="text-white font-semibold" style={{ fontFamily: 'Syne, sans-serif' }}>
            applytic
          </span>
        </Link>
      </div>

      <div className="max-w-2xl mx-auto px-6 py-16">
        <div className="mb-12">
          <h1 className="text-4xl font-bold text-white mb-3"
              style={{ fontFamily: 'Syne, sans-serif' }}>
            Terms of Service
          </h1>
          <p className="text-gray-500 text-sm">Last updated: June 2026</p>
        </div>

        <Section title="About Applytic">
          <p>
            Applytic is a free, open-source job application tracker built and operated by Hardik
            (hardikjp7). By creating an account and using Applytic, you agree to these terms.
          </p>
        </Section>

        <Section title="The service">
          <p>
            Applytic is provided free of charge with no usage tier restrictions. You may use
            it to track your own job search activity. There is no guarantee of uptime,
            performance, or continued availability - the service is provided as-is.
          </p>
          <p>
            The AI Coach chat is limited to 20 messages per user per day to keep Bedrock costs
            manageable. This limit resets at midnight UTC.
          </p>
        </Section>

        <Section title="Your account">
          <p>
            You are responsible for maintaining the security of your account credentials.
            You may not share your account with others or create accounts on behalf of others
            without their consent.
          </p>
          <p>
            You may delete your account at any time by contacting us. See the Privacy Policy
            for what happens to your data on deletion.
          </p>
        </Section>

        <Section title="Your data">
          <p>
            You retain full ownership of all data you enter into Applytic - application records,
            notes, resume files, and settings. By using the service, you grant Applytic a
            limited licence to store and process this data solely for the purpose of providing
            the service to you.
          </p>
          <p>
            You are responsible for the content you upload. Do not upload files that contain
            malware, violate third-party intellectual property rights, or that you do not have
            the right to store.
          </p>
        </Section>

        <Section title="Acceptable use">
          <p>You agree not to:</p>
          <ul className="list-disc pl-5 space-y-2">
            <li>Use Applytic for any unlawful purpose.</li>
            <li>Attempt to bypass, disable, or circumvent any rate limits or security controls.</li>
            <li>Use the AI Coach to generate harmful, abusive, or illegal content.</li>
            <li>Attempt to access other users' data.</li>
            <li>Scrape or automate requests to the API in ways that place unreasonable load on
            the service.</li>
          </ul>
        </Section>

        <Section title="Open source">
          <p>
            Applytic's source code is available on{' '}
            <a href="https://github.com/hardikjp7/applytic" target="_blank" rel="noreferrer"
               className="text-indigo-400 hover:text-indigo-300 transition-colors">
              GitHub
            </a>
            {' '}under the Apache 2.0 licence. You are free to self-host, fork, and modify
            the code under the terms of that licence.
          </p>
        </Section>

        <Section title="Disclaimer of warranties">
          <p>
            Applytic is provided "as is" without warranties of any kind, express or implied.
            We do not warrant that the service will be uninterrupted, error-free, or that
            any data stored will be retained indefinitely. Use of the AI coaching features
            does not constitute professional career advice.
          </p>
        </Section>

        <Section title="Limitation of liability">
          <p>
            To the fullest extent permitted by applicable law, Hardik (the operator of
            Applytic) shall not be liable for any indirect, incidental, special, consequential,
            or punitive damages arising from your use of or inability to use the service,
            even if advised of the possibility of such damages.
          </p>
        </Section>

        <Section title="Changes to these terms">
          <p>
            These terms may be updated at any time. The "Last updated" date at the top of this
            page reflects the most recent revision. Continued use after a change constitutes
            acceptance of the updated terms.
          </p>
        </Section>

        <Section title="Contact">
          <p>
            Questions about these terms:{' '}
            <a href="https://hardikjp7.com/#contact" target="_blank" rel="noreferrer"
               className="text-indigo-400 hover:text-indigo-300 transition-colors">
              hardikjp7.com/#contact
            </a>
          </p>
        </Section>

        <div className="pt-8 border-t border-white/5 text-xs text-gray-600">
          <Link to="/" className="text-gray-500 hover:text-indigo-400 transition-colors">
            &larr; Back to Applytic
          </Link>
        </div>
      </div>
    </div>
  )
}
