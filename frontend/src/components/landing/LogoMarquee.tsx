// Tech stack marquee strip - no external logos, text only to avoid license issues
const TECH = [
  'AWS Lambda', 'Amazon DynamoDB', 'Amazon Cognito', 'Amazon Bedrock',
  'Amazon Nova Lite', 'Amazon S3', 'Amazon SES', 'Amazon CloudFront',
  'AWS CDK', 'API Gateway', 'AWS X-Ray', 'EventBridge',
  'React', 'TypeScript', 'Python 3.12', 'ARM64 Graviton',
]

export default function LogoMarquee() {
  // Duplicate the array so the CSS infinite scroll looks seamless
  const items = [...TECH, ...TECH]

  return (
    <section className="py-12 overflow-hidden border-y border-white/5"
             style={{ background: 'rgba(10,10,20,0.6)' }}>
      <p className="text-center text-xs text-gray-600 uppercase tracking-widest mb-6">
        Built on AWS - production-grade serverless infrastructure
      </p>
      <div className="relative">
        {/* Fade edges */}
        <div className="pointer-events-none absolute left-0 top-0 bottom-0 w-24 z-10"
             style={{ background: 'linear-gradient(to right, #0a0a0f, transparent)' }} />
        <div className="pointer-events-none absolute right-0 top-0 bottom-0 w-24 z-10"
             style={{ background: 'linear-gradient(to left, #0a0a0f, transparent)' }} />

        <div className="land-marquee-track">
          {items.map((t, i) => (
            <span key={i} className="flex items-center gap-3 text-sm text-gray-500 flex-shrink-0">
              <span className="w-1 h-1 rounded-full bg-indigo-500/60 flex-shrink-0" />
              {t}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}
