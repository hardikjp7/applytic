// Privacy Policy page - linked from footer, public route, no auth required.
// Dark-themed to match the landing page since users arrive from the footer.

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

export default function PrivacyPolicy() {
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
            Privacy Policy
          </h1>
          <p className="text-gray-500 text-sm">Last updated: June 2026</p>
        </div>

        <Section title="Overview">
          <p>
            Applytic is a free, open-source job application tracker built and operated by Hardik
            (hardikjp7). This policy explains what data is collected when you use Applytic,
            how it is stored, and what it is used for.
          </p>
          <p>
            The short version: your data is used only to provide the service. It is never sold,
            shared with advertisers, or used for any purpose other than running Applytic for you.
          </p>
        </Section>

        <Section title="Data we collect">
          <p><span className="text-gray-200 font-medium">Account data</span> - Your email address,
          collected when you sign up via email/password or Google OAuth. Stored in Amazon Cognito
          (AWS, us-east-1).</p>

          <p><span className="text-gray-200 font-medium">Application data</span> - Job application
          records you create: company name, role, status, source channel, resume version, company size,
          job description URL, follow-up date, notes. Stored in Amazon DynamoDB (AWS, us-east-1).</p>

          <p><span className="text-gray-200 font-medium">Resume files</span> - PDF files you
          upload via the Resumes page. Stored in Amazon S3 (AWS, us-east-1) under a path
          prefixed with your user ID. Only you can access your files.</p>

          <p><span className="text-gray-200 font-medium">Usage data</span> - AI Coach chat
          messages are sent to Amazon Bedrock (Amazon Nova Lite model) to generate responses.
          Chat messages are not stored in Applytic's database beyond the current browser session.
          A daily message count per user is stored in DynamoDB to enforce the 20-message rate
          limit and auto-expires after 2 days.</p>
        </Section>

        <Section title="How data is used">
          <p>Your data is used for the following purposes only:</p>
          <ul className="list-disc pl-5 space-y-2">
            <li>Displaying your applications, analytics, and coaching on the dashboard.</li>
            <li>Sending the weekly digest email every Monday (Amazon SES).</li>
            <li>Sending follow-up reminder emails when applications are overdue (Amazon SES).</li>
            <li>Generating AI coaching responses via Amazon Bedrock using your application
            patterns as context.</li>
            <li>Verifying your email address with Amazon SES so you can receive digest emails.</li>
          </ul>
        </Section>

        <Section title="Google sign-in">
          <p>
            If you sign in with Google, your email address and name are passed to Cognito by Google
            as part of the OAuth flow. Google's own{' '}
            <a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer"
               className="text-indigo-400 hover:text-indigo-300 transition-colors">
              Privacy Policy
            </a>
            {' '}governs how Google handles data on their end. Applytic only receives and stores
            your email address from this flow.
          </p>
        </Section>

        <Section title="Data storage and security">
          <p>
            All data is stored on AWS infrastructure in the us-east-1 region (N. Virginia).
            DynamoDB tables use AWS-managed encryption at rest. S3 buckets use S3-managed
            encryption and are fully private - no public access is permitted. API routes are
            protected by Cognito JWT authorisation.
          </p>
          <p>
            Authentication tokens are stored in your browser's localStorage by the AWS Amplify
            library. These are not accessible to other sites.
          </p>
        </Section>

        <Section title="Data sharing">
          <p>
            Your data is not sold, rented, or shared with any third party for advertising,
            analytics, or any other purpose. The only third-party services that process your
            data are AWS services (Cognito, DynamoDB, S3, SES, Bedrock, Lambda) used to run
            the application, and Google (if you use Google sign-in, as described above).
          </p>
        </Section>

        <Section title="Data retention and deletion">
          <p>
            Your data is retained as long as your account exists. To request deletion of your
            account and all associated data, contact us at the address below. We will delete
            your Cognito account, DynamoDB records, and S3 files within 30 days of the request.
          </p>
          <p>
            The source code is open source - if you self-host Applytic, you control your own data entirely.
          </p>
        </Section>

        <Section title="Changes to this policy">
          <p>
            If this policy changes materially, we will update the "Last updated" date at the top.
            Continued use of Applytic after a change constitutes acceptance of the updated policy.
          </p>
        </Section>

        <Section title="Contact">
          <p>
            Questions about this policy or data deletion requests:{' '}
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
