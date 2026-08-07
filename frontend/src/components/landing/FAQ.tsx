import { useState } from 'react'
import { useScrollReveal } from './useScrollReveal'

const FAQS = [
  {
    q: 'Is it actually free?',
    a: 'Yes. No trial, no credit card, no usage limits. Applytic is hosted on AWS and I pay the bill myself. At low to moderate usage the AWS costs are a few dollars a month - well worth it to have a real production project running.',
  },
  {
    q: 'How does the AI coaching work?',
    a: 'When you open the AI Coach, your application data is pulled from DynamoDB and structured into a context window - response rates per source channel, per resume version, per company size, recent application history. That structured data is passed to Amazon Nova Lite on AWS Bedrock along with your question. The model gets hard numbers, not raw records, so the advice is specific to your situation rather than generic.',
  },
  {
    q: 'What is the weekly digest?',
    a: 'Every Monday at 8am UTC, a Lambda function scans for users who have had activity in the past week, generates a summary of your pipeline, and uses Amazon Nova Lite to write one personalised tip based on your patterns. It\'s delivered via Amazon SES. You need to verify your email address after signing up (a one-click link from AWS) to receive it - this is an SES sandbox requirement.',
  },
  {
    q: 'Does it work with Google sign-in?',
    a: 'Yes. You can sign up and log in with Google via Cognito\'s OAuth integration. Email/password also works. Both paths give you the same features including the weekly digest.',
  },
  {
    q: 'Can I self-host this?',
    a: 'Yes. The full source is on GitHub and CONTRIBUTING.md has step-by-step setup instructions. You need an AWS account, Node.js, Python 3.12, and the AWS CDK CLI. A full deploy from scratch takes under 3 minutes.',
  },
  {
    q: 'What data do you store?',
    a: 'Application data you enter (company, role, status, notes, dates), resume PDFs you upload to S3 (stored in your own bucket under your user ID prefix), and your email address from Cognito. Nothing is sold or shared. See the Privacy Policy for the full picture.',
  },
  {
    q: 'How does the AI chat rate limiting work?',
    a: 'Each user gets 20 AI Coach messages per day. The counter resets at midnight UTC and is stored in DynamoDB with a TTL so the record auto-expires after 2 days. This keeps Bedrock costs predictable at zero direct charge to users.',
  },
  {
    q: 'How does interview prep work?',
    a: 'Once an application reaches Interview or Offer status, you can generate interview questions from its detail view. Applytic fetches the job description URL you attached, passes the role, company, and job description text to Amazon Nova Lite, and generates 10 tailored questions. You can check off ones you\'ve practiced and save your own answer notes - everything is stored per application and persists across sessions. You can regenerate a fresh set any time.',
  },
  {
    q: 'What are rejection pattern alerts?',
    a: 'Every Monday, alongside the weekly digest, Applytic checks your data for three patterns: a resume version with a 0% response rate after 5+ applications, a source channel with a 0% response rate after 5+ applications, and a response rate that dropped more than 20 percentage points week over week. If any of those fire, you get an amber banner on the Dashboard (dismissible) and a section in the digest email - so you catch what\'s not working before you keep repeating it.',
  }
]

export default function FAQ() {
  const [open, setOpen] = useState<number | null>(null)
  useScrollReveal()

  return (
    <section id="faq" className="py-24 px-6"
             style={{ background: 'rgba(10,10,20,0.4)' }}>
      <div className="max-w-3xl mx-auto">
        <div className="text-center mb-14">
          <div className="land-reveal inline-flex items-center gap-2 px-3 py-1 rounded-full border border-cyan-500/20 bg-cyan-500/5 text-xs text-cyan-400 mb-4">
            FAQ
          </div>
          <h2
            className="land-reveal text-4xl sm:text-5xl font-bold text-white"
            style={{ fontFamily: 'Syne, sans-serif', transitionDelay: '0.1s' }}
          >
            Common questions
          </h2>
        </div>

        <div className="space-y-3">
          {FAQS.map((f, i) => (
            <div
              key={i}
              className="land-reveal land-glass overflow-hidden"
              style={{ transitionDelay: `${i * 0.05}s` }}
            >
              <button
                className="w-full flex items-center justify-between gap-4 px-6 py-5 text-left"
                onClick={() => setOpen(open === i ? null : i)}
              >
                <span className="text-white text-sm font-medium"
                      style={{ fontFamily: 'Syne, sans-serif' }}>
                  {f.q}
                </span>
                <span
                  className={`land-faq-icon flex-shrink-0 text-indigo-400 text-xl leading-none ${open === i ? 'open' : ''}`}
                >
                  +
                </span>
              </button>
              <div className={`land-faq-body px-6 ${open === i ? 'open' : ''}`}>
                <p className="text-gray-400 text-sm leading-relaxed pb-5">{f.a}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
