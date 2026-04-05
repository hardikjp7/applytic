# Applytic

> AI-powered job application tracker that learns from your rejections.

**Live demo:** https://d3jumje9o63lys.cloudfront.net

Applytic tracks every job application you submit, detects patterns across rejections (which resume version converts best, which source channel works, which company sizes respond), and uses Amazon Bedrock to turn that data into actionable coaching — delivered as a chat interface and a weekly email digest.

Built end-to-end on AWS as a production-grade portfolio project. Every service is serverless, infrastructure is code, and every push auto-deploys via GitHub Actions.

---

## Why I Built This

I was job hunting and had no data on why I was getting rejected. I had a spreadsheet with company names and "rejected" written next to most of them — but no signal on *why*. Was it my resume? The channel? The company size?

So I instrumented my own job search. Every application became a data point. After a few weeks I had enough data to see that my `v1-generic` resume had a 0% response rate from enterprise companies, while `v3-ml-focused` was getting interviews from startups via referrals. That's the kind of insight you can act on.

---

## Architecture

![Architecture Diagram](architecture.png)

---

## Tech Stack

| Layer | Service |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, react-markdown |
| Auth | Amazon Cognito (email + JWT) |
| API | API Gateway REST + Lambda (Python 3.12, ARM64) |
| AI / ML | Amazon Bedrock — Amazon Nova Lite |
| Database | DynamoDB — single-table design, PAY_PER_REQUEST |
| Storage | S3 — resume versioning + frontend hosting |
| CDN | CloudFront (450+ edge locations) |
| Scheduling | EventBridge cron (Monday 8am UTC) |
| Email | Amazon SES |
| IaC | AWS CDK v2 TypeScript |
| CI/CD | GitHub Actions |

---

## Features

**Application tracking**
- Log applications with company, role, source channel, resume version, company size, job description URL
- Kanban board with drag-and-drop status updates (Applied → Screened → Interview → Offer / Rejected)
- Click any card to view full detail, edit all fields, change status, see timeline
- Search by company/role, filter by source channel
- Color-coded left border per status on kanban cards for instant visual scanning

**AI insight engine**
- Pattern analysis across 6 dimensions: source channel, company size, resume version, role seniority, weekly velocity, status funnel
- Response rate computed per bucket — shows exactly which resume version or source is working
- AI coaching chat powered by Bedrock — answers questions like "why am I getting ghosted?" using your actual data as context, not generic advice
- Markdown rendering in chat responses — bold, lists, and structure render properly
- Weekly email digest every Monday with stats + one AI-generated personalised tip

**Resume version tracker**
- Upload multiple PDF versions to S3 via presigned URLs (never passes through Lambda)
- Tag each application with which version was used
- Analytics shows conversion rate per version side-by-side

**UI / UX**
- Full dark mode with system preference detection, persisted to localStorage
- Mobile responsive — hamburger sidebar on small screens, responsive grids throughout
- Loading skeletons on every page instead of blank states
- Meaningful empty states with calls to action
- Toast notifications (top-center)

---

## Project Structure

```
applytic/
├── cdk/                    # AWS CDK v2 stack — all infrastructure as code
│   ├── bin/app.ts
│   └── lib/applytic-stack.ts
├── lambdas/                # Python 3.12 Lambda handlers
│   ├── applications/       # CRUD + presigned S3 URL generation
│   ├── insights/           # Pattern analysis + Bedrock AI coaching
│   └── digest/             # Weekly SES email digest
├── frontend/               # React + Vite + Tailwind CSS
│   └── src/
│       ├── components/     # Kanban, Analytics, Chat, Sidebar, Resume
│       ├── hooks/          # useApplications (data fetching + state)
│       ├── lib/            # API client, Amplify config, theme util
│       ├── pages/          # Dashboard
│       └── types/          # Shared TypeScript types
├── tests/                  # 48 pytest unit tests
│   ├── conftest.py
│   ├── test_applications.py
│   └── test_insights.py
├── scripts/
│   └── seed_data.py        # Populates DynamoDB with 20 realistic demo apps
└── .github/workflows/
    └── deploy.yml          # CI/CD: test → deploy backend → deploy frontend
```

---

## DynamoDB Single-Table Design

Table name: `applytic`

| Entity | PK | SK | GSI1PK | GSI1SK |
|---|---|---|---|---|
| Application | `USER#userId` | `APP#appId` | `USER#userId` | `DATE#timestamp` |
| Status event | `APP#appId` | `EVENT#timestamp` | — | — |

**Access patterns:**
- List all applications for user → GSI1 query on `USER#userId` sorted by date
- Get single application → Main table get on `USER#userId` + `APP#appId`
- Get status history for an app → Query `APP#appId` with `EVENT#` prefix

Every status change writes a STATUS_EVENT record, creating a full audit trail of the application journey.

---

## Key Engineering Decisions

**Single-table DynamoDB** — two entity types (APPLICATION, STATUS_EVENT) in one table with composite keys. Every query is O(1). No joins. Scales to millions of requests/sec with no configuration changes. This demonstrates understanding of NoSQL access pattern design rather than SQL-in-NoSQL thinking.

**Pattern analysis before LLM** — the insights Lambda computes structured metrics (response rates per bucket) before calling Bedrock. The LLM receives hard numbers as context, not raw records. This makes advice data-driven and specific rather than generic — it's the difference between "apply to more startups" backed by actual numbers vs. a guess.

**Serverless-first** — no EC2, no containers, no idle servers. Lambda + API Gateway + DynamoDB means ~$0 at low volume and automatic scaling. EventBridge replaces a cron server entirely. The entire system costs roughly $2-5/month at 100 active users.

**ARM64 Lambda** — all functions run on Graviton2 (ARM64) for ~20% cost reduction and faster cold starts vs x86.

**Presigned S3 URLs for resume upload** — the Lambda generates a presigned URL and returns it to the client. The file then uploads directly from the browser to S3 — never passes through Lambda. This avoids Lambda payload limits and keeps upload fast.

**Multi-model Bedrock support** — the insights Lambda detects whether the configured model is Anthropic or Amazon (based on model ID prefix) and adjusts the request/response format accordingly. This means switching models requires only an environment variable change.

---

## Scale & Cost

| Metric | Value |
|---|---|
| API throughput | 10,000 req/sec (API Gateway default) |
| DynamoDB SLA | 99.999% availability, millions req/sec |
| Lambda cold start | ~300-400ms (Python 3.12 ARM64) |
| CloudFront edge locations | 450+ worldwide |
| Cost at 0 users | ~$0/month |
| Cost at 100 users | ~$2-5/month |
| Cost at 1,000 users | ~$15-30/month |
| Test suite runtime | under 2 seconds (48 tests) |
| Full CDK deploy from scratch | under 3 minutes |

---

## CI/CD Pipeline

Every push to `main` triggers three jobs in parallel after tests pass:

```
push to main
    └── test (pytest, 48 tests)
            ├── deploy-backend (cdk deploy)
            └── deploy-frontend (npm build → s3 sync → cloudfront invalidation)
```

Pull requests only run tests — no deploy. This means every PR is validated before merge.

---

## Local Setup

### Prerequisites
- Node.js 18+
- Python 3.12
- AWS CLI configured (`aws configure`)
- AWS CDK CLI: `npm install -g aws-cdk`

### Deploy backend
```bash
cd cdk
npm install
cdk bootstrap
cdk deploy
```

Save the outputs — you need `ApiUrl`, `UserPoolId`, `UserPoolClientId` for the frontend `.env`.

### Run frontend locally
```bash
cd frontend
cp .env.example .env
# fill in .env with CDK outputs
npm install
npm run dev
```

Opens at `http://localhost:5173`

### Deploy frontend
```bash
cd frontend
npm run build
aws s3 sync dist/ s3://applytic-frontend-YOUR_ACCOUNT_ID --delete
aws cloudfront create-invalidation --distribution-id YOUR_DIST_ID --paths "/*"
```

### Seed demo data
```bash
cd scripts
pip install boto3
python seed_data.py --user-id YOUR_COGNITO_SUB
```

To get your Cognito sub: sign in → DevTools → Application → Local Storage → find `idToken` → paste at jwt.io → copy `sub` field.

### Run tests
```bash
pip install pytest boto3
python -m pytest tests/ -v
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `VITE_API_URL` | API Gateway base URL from CDK output |
| `VITE_USER_POOL_ID` | Cognito User Pool ID |
| `VITE_USER_POOL_CLIENT_ID` | Cognito App Client ID |
| `VITE_AWS_REGION` | AWS region (us-east-1) |

Never commit `.env` — it is gitignored. GitHub Actions injects these values via repository secrets at build time.

---

## Issues Encountered & Fixed

This section documents every real issue hit during the build — useful for anyone replicating this project and for interviews where "tell me about a hard bug" comes up.

**1. TypeScript error on CDK deploy — `Partial<FunctionProps>` type**
Using `Partial<lambda.FunctionProps>` to share Lambda defaults made `runtime` optional, but the `Function` constructor requires it as non-optional. TypeScript rejected the spread.
Fix: removed the shared defaults object entirely and added `runtime` explicitly on each Lambda definition.

**2. esbuild crash on Windows (`npm run dev`)**
esbuild's native binary gets corrupted on Windows when Node versions mismatch or `node_modules` gets into a bad state.
Fix: delete `node_modules` and `package-lock.json`, reinstall with `npm install`, use Node 18 or 20 LTS only.

**3. pytest module name collision**
Both Lambda handlers are named `handler.py`. Python caches the first import under the name `handler`, so the second test file imports the wrong one.
Fix: use `importlib.util.spec_from_file_location` to load each handler by absolute file path, registering each under a unique module name (`applications_handler`, `insights_handler`).

**4. Timezone-aware datetime bug in velocity calculation**
`dateApplied` is stored as `YYYY-MM-DD` (date string). The velocity calculation tried to subtract it from a timezone-aware `datetime.now(timezone.utc)`, causing `TypeError: can't subtract offset-naive and offset-aware datetimes`.
Fix: detect date-only strings (length 10) and parse with `.replace(tzinfo=timezone.utc)` before subtraction.

**5. Chat history lost on page navigation**
React unmounts the component on route change, so `useState` inside `CoachChat` reset to the initial message every time the user navigated away.
Fix: lifted the `messages` state to `App.tsx` and passed it as props to `CoachChat`. State now lives at the router level and survives navigation.

**6. GitHub Actions npm cache error**
`cache: 'npm'` in `setup-node` requires a `package-lock.json` to exist. The lockfile wasn't committed.
Fix: removed `cache` and `cache-dependency-path` from both Node setup steps, changed `npm ci` to `npm install`.

**7. `import.meta.env` TypeScript error in CI**
The build failed in CI with `Property 'env' does not exist on type 'ImportMeta'`. Vite provides this type via `vite/client` but the tsconfig didn't include it.
Fix: added `"types": ["vite/client"]` to `compilerOptions` in `tsconfig.json`.

**8. Bedrock model end-of-life (`anthropic.claude-3-5-sonnet-20241022-v2:0`)**
The originally configured model reached AWS end-of-life mid-project. Lambda started throwing `ResourceNotFoundException`.
Fix: updated `BEDROCK_MODEL_ID` environment variable. Learned to use `aws logs tail` for Lambda debugging and `aws lambda update-function-configuration` for immediate hotfixes without CDK redeploy.

**9. Bedrock inference profile requirement**
Newer Claude models (3.7 Sonnet) require an inference profile ID (`us.anthropic.claude-3-7-sonnet-20250219-v1:0`) rather than the direct model ID. On-demand throughput isn't supported with the bare model ID.
Fix: prefix with `us.` for cross-region inference profiles.

**10. IAM policy not covering inference profile ARN**
The CDK IAM policy granted access to `arn:aws:bedrock:region::foundation-model/anthropic.*` but inference profiles have a different ARN format (`arn:aws:bedrock:region:accountId:inference-profile/*`). The Lambda got `AccessDeniedException`.
Fix: changed the Bedrock IAM policy resource to `*` to cover both foundation models and inference profiles.

**11. AWS Marketplace subscription required for newer models**
Both Claude 3.7 Sonnet and Claude Haiku 4.5 required AWS Marketplace subscription acceptance before use. This is a newer AWS requirement for certain Anthropic models.
Fix: switched to Amazon Nova Lite (`amazon.nova-lite-v1:0`) which works without Marketplace subscription on all AWS accounts.

**12. Amazon Nova uses different request/response format**
Nova uses a completely different API schema from Anthropic. Sending Anthropic-format requests (`anthropic_version`, `max_tokens` at top level) to Nova caused `ValidationException: extraneous key [max_tokens] is not permitted`.
Fix: updated `chat_with_coach()` to detect the model family from the model ID and use the appropriate request/response format for each. The Lambda now supports both Anthropic and Amazon model families transparently.

**13. Pie chart labels clipped at top of card**
Recharts renders percentage labels outside the pie slices by default. The top label overflowed the card boundary and got clipped by CSS overflow.
Fix: replaced external labels with a custom render function that draws white percentage text inside each slice at the midpoint radius. Labels that would be too small (< 5% slice) are skipped automatically.

---

## AWS Services Used

`Lambda` `API Gateway` `DynamoDB` `S3` `CloudFront` `Cognito` `Bedrock` `SES` `EventBridge` `CloudWatch` `IAM` `CDK`

---

## Author

**Hardik** — [Github](https://github.com/hardikjp7)