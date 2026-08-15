# Changelog

All notable changes to Applytic are documented here.

---

## [3.0.1] - 2026-08-08

Patch release addressing bugs found after v3.0 shipped, a GitHub CodeQL security finding, and an AWS cost anomaly. No new user-facing features - all fixes and hardening ahead of v3.1 (Salary & Contact Tracking).

### Fixed

**Analytics zero-state crash**
- `AnalyticsDashboard.tsx` threw `Cannot read properties of undefined (reading 'total')` when a user had zero applications, since the empty-state guard didn't account for the insights Lambda's message-only response shape (`{"message": "..."}`, no `summary` key)
- This also left every other page stuck in the error boundary's fallback UI until a hard refresh, since `ErrorBoundary` wasn't keyed to the route
- `ErrorBoundary` is now keyed to `location.pathname`, so it self-heals on navigation for any future render error, not just this one

**Broken navigation links on Privacy Policy and Terms pages**
- Logo and "Back to Applytic" links used bare `<a href="/">`, which bypasses React Router's `basename="/applytic/"` and resolved to the wrong domain root on the custom domain deployment
- Same root cause as a prior fix in `AuthModal.tsx` - now consistently using `<Link to="/">` across both pages (4 instances total)

**FAQ accordion causing whole-page lag**
- Opening any FAQ question caused visible lag across the entire page, not just the clicked card, on both desktop and mobile
- Root cause: `backdrop-filter: blur()` on 7 stacked cards forced a live repaint of every shifting sibling on every animation frame
- FAQ cards now use a solid background instead of blur, and the open/close animation switched from `max-height` to `grid-template-rows` (also fixes a latent bug where long answers could get clipped at 400px)

**Production bundle size**
- Single JS bundle exceeded Vite's 500kB warning threshold since no route was code-split
- All page-level routes (`Dashboard`, `KanbanBoard`, `AnalyticsDashboard`, `CoachChat`, `ResumeUpload`, `Landing`, `AuthModal`, `PrivacyPolicy`, `Terms`) now load via `React.lazy()` with `Suspense` boundaries at three levels (protected routes, public routes, modal overlay routes), so users only download the code for the route they visit

### Security

**CodeQL: Bad HTML filtering regexp (`py/bad-tag-filter`)**
- `interview_prep/handler.py`'s job-description HTML stripper used a regex that could be bypassed by malformed-but-browser-accepted close tags like `</script foo="bar">`
- Replaced with Python's stdlib `html.parser.HTMLParser`, which tokenizes tag structure instead of pattern-matching - no new dependencies added
- Closes #40

### Infrastructure

**Google OAuth credentials moved off Secrets Manager**
- AWS Cost Anomaly Detection flagged ~$0.013/day in ongoing Secrets Manager charges for credentials that are only needed at CDK deploy time (Cognito stores them internally after that)
- Migrated to SSM Parameter Store (SecureString, Standard tier), which is free at this volume
- CloudFormation does not support `{{resolve:ssm-secure:...}}` dynamic references on `AWS::Cognito::UserPoolIdentityProvider`'s `ProviderDetails` property - dynamic references are only supported on a CFN-defined property allowlist, and Cognito identity providers aren't on it for this reference type. Resolved via `AwsCustomResource` instead: a CDK-managed Lambda calls `ssm:GetParameter` (with decryption) at deploy time, and the already-resolved value is passed through `Fn::GetAtt`, which has no such restriction
- Old `applytic/google-oauth` Secrets Manager secret verified and deleted post-deployment (7-day recovery window)

### Content

**Landing page updated for v3.0 features**
- FeatureShowcase, HowItWorks, DeepDive, and FAQ previously had no mention of Interview Prep or Rejection Pattern Alerts despite both shipping in v3.0 - added across all four sections
- DeepDive's alternating left/right visual layout restored (Track / Analyze / Prep / Coach zigzag) after adding the new Prep & Alerts section

### Tests
- 3 new tests in `test_interview_prep.py` covering the HTML-stripping fix
- 355 backend tests, all passing, 93% coverage (threshold: 70%)

### Upgrade notes
Self-hosters using Google OAuth: the Secrets Manager to SSM migration requires manually creating two SSM SecureString parameters before deploying (`/applytic/google-oauth/client-id`, `/applytic/google-oauth/client-secret`) - see `cdk/lib/applytic-stack.ts` comments for the exact `aws ssm put-parameter` commands.

---

## [3.0.0] - 2026-07-26

### Added

**Interview Prep Mode**
- `applytic-interview-prep` Lambda - new function handling 3 routes
- `POST /v1/applications/{appId}/interview-prep/generate` - fetches job description URL (5s timeout, 3000 char limit), passes role + company + JD to Amazon Nova Lite, generates 10 tailored questions, stores as `PREP#v1` item per application
- `GET /v1/applications/{appId}/interview-prep` - returns stored questions or `prep: null` if not yet generated
- `PUT /v1/applications/{appId}/interview-prep/{questionId}` - toggles practiced status and/or saves answer notes (read-modify-write, optimistic on frontend)
- `INTERVIEW_PREP` DynamoDB entity: `PK=APP#{appId}`, `SK=PREP#v1`, single overwritten record per app
- URL fetch falls back to role + company name only if URL is missing or fetch fails - never blocks the user
- Interview Prep tab in `ApplicationDetailModal` - visible only for `interview` and `offer` status apps
- Practiced count shown in tab label (e.g. `3/10`)
- Regenerate button available once questions exist
- Answer textarea saves on blur - no save button needed per question
- `useInterviewPrep` React Query hook with optimistic checkbox toggles
- `InterviewQuestion` and `InterviewPrep` types added to `types/index.ts`
- 40 unit tests in `tests/test_interview_prep.py`

**Rejection Pattern Alerts**
- `detect_rejection_patterns(user_id, apps)` added to `lambdas/digest/handler.py`
- Three patterns detected on every Monday digest run:
  - Resume version with 0% response rate after 5+ applications
  - Source channel with 0% response rate after 5+ applications
  - Response rate dropped more than 20 percentage points week-over-week
- Alerts stored as `ALERT#{timestamp}#{alertId}` items under `USER#{userId}`, 30-day TTL
- Alerts section included in weekly digest email HTML when patterns are found
- `GET /v1/users/alerts` - returns undismissed alerts, routed through `settingsLambda`
- `PUT /v1/users/alerts/{alertId}/dismiss` - marks alert dismissed, routed through `settingsLambda`
- Amber alert banner on `Dashboard.tsx` - renders above weekly goal card, one banner per active alert
- Optimistic dismiss - alert removed from UI instantly, API call in background with rollback on error
- `useAlerts` React Query hook with 5-minute stale time
- `PatternAlert` type added to `types/index.ts`
- 21 new tests in `tests/test_digest.py` (54 total, up from 33)
- 18 new tests in `tests/test_settings.py` (47 total, up from 29)

**Enhanced AI Coach Context**
- `build_context_for_llm()` in `lambdas/insights/handler.py` extended with optional `enrichment` dict param - fully backward compatible
- New "Active pattern alerts" section injected into coach context when undismissed alerts exist
- New "Interview context" section per app currently in `interview` status - up to 5 most recent notes + practiced question count from interview prep
- Three new helper functions: `fetch_recent_notes_for_app`, `fetch_interview_prep_for_app`, `fetch_active_alerts`
- `build_coach_enrichment(user_id, apps)` orchestrates enrichment - scoped to interview-status apps only, never raises (per-app failures logged and skipped)
- Enrichment only runs on `POST /insights/chat` after the 3-app minimum and rate-limit checks pass
- 32 new tests in `tests/test_insights_v30.py`

**OpenAPI spec**
- 5 new routes documented in `api/openapi.yml` and `api-docs/openapi.yml`
- 4 new schemas: `InterviewQuestion`, `InterviewPrep`, `UpdateInterviewQuestionRequest`, `PatternAlert`
- 2 new tags: `Interview Prep`, `Alerts`

### Infrastructure
- New `interviewPrepLambda` (ARM64, Python 3.12, 512MB, 60s timeout, shared layer)
- Bedrock IAM policy attached to `interviewPrepLambda` (same as `insightsLambda`)
- `InterviewPrepLambdaErrorAlarm` CloudWatch alarm
- `interviewPrepLambda` added to CloudWatch dashboard invocations and errors widgets
- 2 new API Gateway routes on `settingsLambda` for alerts (no new Lambda)
- 3 new API Gateway routes on `interviewPrepLambda`
- Total API routes: 20 (up from 15)

### DynamoDB
- `INTERVIEW_PREP` entity: `PK=APP#{appId}`, `SK=PREP#v1`
- `ALERT` entity: `PK=USER#{userId}`, `SK=ALERT#{timestamp}#{alertId}`, 30-day TTL

### Tests
- Backend: 410 total (up from 237) - 173 new tests across 4 files
- `tests/test_interview_prep.py` - 40 new tests
- `tests/test_digest.py` - 21 new tests (54 total)
- `tests/test_settings.py` - 18 new tests (47 total)
- `tests/test_insights_v30.py` - 32 new tests

### Bug fix (pre-v3.0)
- `AuthModal.tsx` Terms and Privacy links changed from `<a href>` to `<Link to>` - bare href bypassed React Router basename and broke navigation on GitHub Pages

---

## [2.3.0] - 2026-07-05

### Added
- **Public landing page** at the root URL, replacing the direct route to the login screen. Live at https://hardikjp7.com/applytic. Sections:
  - Hero with split layout, particle canvas, animated dashboard mockup, and floating AI insight / resume comparison cards
  - Feature showcase - 9 features with professional SVG icons
  - How it works - horizontal 4-step flow with icon boxes, numbered badges, and connecting lines
  - Track / Analyze / Coach deep-dive sections with real UI mocks
  - About section with the actual story behind why Applytic was built
  - FAQ - 7 accurate questions about the stack and how it works
  - Footer with all real links, no placeholder hrefs
- **Google sign-in** via Cognito Hosted UI, alongside existing email/password. Both paths give the same features. Google sign-in users get their email SES-verified automatically for the Monday digest via the Post Authentication Cognito trigger
- **Custom auth UI** - Amplify's default form replaced with a custom modal matching the landing page design. Handles login, signup, email confirmation, forgot password, and password reset. Opens as a modal overlay on the landing page from a CTA, or renders full-page on direct navigation / hard refresh
- Authenticated users clicking any landing page CTA are redirected straight to `/dashboard` instead of seeing the auth modal
- **Privacy Policy and Terms of Service** pages - real, accurate coverage of what data is collected, how it's stored, and user rights. Linked from the footer and the signup form

### Changed
- **Routing restructure**:
  - Landing page moved to `/`
  - Dashboard moved to `/dashboard`
  - All other app routes (`/board`, `/analytics`, `/coach`, `/resumes`) unchanged
  - `/auth/callback` added to handle the OAuth redirect from Cognito Hosted UI
  - `/privacy` and `/terms` added as public routes

### Infrastructure
- Requires one manual step before CDK deploy - creating the Google OAuth secret in Secrets Manager:
  ```bash
  aws secretsmanager create-secret \
    --name applytic/google-oauth \
    --secret-string '{"client_id":"YOUR_ID","client_secret":"YOUR_SECRET"}'
  ```

---

## [2.2.0] - 2026-06-24

Theme: make the API a first-class citizen, strengthen data traceability ahead of v3.0's interview prep and rejection pattern features, and fix two production bugs found on the live custom domain deployment.

### Added
- **OpenAPI 3.0 spec** for all 15 API routes (`api/openapi.yml`), modeled directly from the Pydantic request models and actual Lambda response shapes - applications CRUD, status transitions, notes timeline, resumes, insights/chat, and settings
- **Hosted API docs** - browsable Swagger UI at `/api/docs` on the CloudFront deployment, auto-deployed on every push to `main`
- **Resume version dropdown** - the Add/Edit application forms now pull resume versions from `GET /resumes/list` (actual S3 uploads) instead of free text, closing the gap between what's tracked and what's actually on file
- **Stale value protection** - if an application references a resume version no longer in S3 (deleted, or free-typed before this release), it's preserved and shown as a disabled, flagged option rather than silently dropped
- CI now validates the OpenAPI spec on every push/PR

### Fixed
- **SPA hard-refresh routing** - refreshing any non-root route (e.g. `/board`, `/analytics`, `/coach`) on the GitHub Pages / custom domain deployment dropped the `/applytic` base path from the URL and rendered a blank page. The GitHub Pages SPA redirect trick (`404.html` + `index.html`) now stores and restores the *full* original path instead of a base-stripped fragment that had nothing to restore the base from
- **Unauthenticated deep links** - as a consequence of the routing fix, an unauthenticated user hitting a deep link (e.g. `/applytic/board`) now correctly sees the login screen and is returned to that exact page after signing in
- **Login box centering** - the Amplify Authenticator login form was stuck at the top of the page instead of being vertically centered, a known upstream `@aws-amplify/ui-react` issue. Added an explicit flex-center override

### Changed
- Corrected documentation: the API actually has 15 routes, not 9 as previously stated in the roadmap (the smaller count predated v2.0's notes/settings additions)
- Default `resumeVersion` on new applications changed from `'v1'` to empty, forcing an explicit, traceable selection

### Scope Notes
- The OpenAPI spec is documentation-only in this release - no runtime request/response validation is enforced against it. Pydantic remains the source of truth for actual input validation
- API docs are hosted on the AWS/CloudFront deployment only, not on the GitHub Pages mirror

---

## [2.1.0] - 2026-06-19

### Added
- React Query (`@tanstack/react-query`) replacing useState + manual fetch for `useApplications`, `useSettings`, `useNotes` - automatic cache invalidation, background refetch, built-in loading/error state
- Optimistic UI on kanban drag - card moves instantly, automatically reverts with a toast if the status update fails
- Keyboard shortcuts: `N` (new application), `Escape` (close open dialog), `?` (shortcuts help overlay)
- New `ShortcutsHelpModal` component
- Per-column kanban pagination - columns beyond 20 cards show a "Show more" button instead of rendering everything at once
- Analytics: application funnel chart (applied → screened → interview → offer) with per-stage conversion rates
- Analytics: response rate trend line over the last 8 completed weeks
- Analytics: status history stacked bar chart showing weekly application status distribution
- 30 new backend tests (`test_insights_v21.py`), 9 new frontend tests (shortcuts + pagination)

### Fixed
- `followUpDate` field now rendered in `AddApplicationModal` (was in form state but missing from the UI)
- Dark mode kanban card left-border colors no longer overridden by the generic dark border rule
- Unhandled promise rejections in `Dashboard.tsx` and `ApplicationDetailModal.tsx` after the React Query migration (mutateAsync rethrows on error; wrapped in try/catch)

### Changed
- `insights/handler.py`: `compute_patterns()` now also returns `funnel`, `responseRateTimeSeries`, `statusHistory`
- `types/index.ts`: added `FunnelStage`, `ResponseRatePoint`, `StatusHistoryPoint`
- Test suite: 237 backend tests, 23 frontend tests (up from 207 / 14)

### Infrastructure
- No CDK/IAM changes - Lambda code only, requires `cdk deploy` after merge (no layer rebuild needed)

---

## [2.0.0] - 2026-05-26

### Added
- Follow-up reminders - attach a date to any application, daily SES email for overdue items
- Weekly goal tracking on Dashboard - progress bar, inline editing, streak counter with fire icon
- Notes timeline - timestamped notes per application, sorted oldest first
- CSV export - client-side, no Lambda, downloads all applications instantly
- CSV import - full validation, preview, error reporting, template download
- Follow-up badge on kanban cards - amber pill when overdue
- `applytic-followup` Lambda - daily 9am UTC EventBridge trigger
- `applytic-settings` Lambda - GET/PUT `/users/settings`, streak computed over 8-week window
- `applytic-notes` Lambda - GET/POST/DELETE `/applications/{appId}/notes`
- `followUpDate` field on Application entity (nullable, YYYY-MM-DD)
- `USER_SETTINGS` DynamoDB entity
- `NOTE` DynamoDB entity
- `useSettings` and `useNotes` React hooks
- 85 new backend tests (207 total, 90.75% coverage)

### Infrastructure
- 3 new Lambda functions (ARM64, Python 3.12, X-Ray, shared layer)
- 5 new API Gateway routes
- Daily EventBridge rule `applytic-daily-followup`
- CloudWatch alarm for followup Lambda errors

---

## [1.3.0] - 2026-05-01

### Added
- Moto integration tests for applications Lambda (16 tests) and insights Lambda (14 tests)
- Digest Lambda unit tests - 0% to 73% coverage (22 tests)
- cognito_verify Lambda unit tests - 0% to 93% coverage (9 tests)
- 70% backend coverage threshold enforced in CI via `--cov-fail-under=70`
- Vitest + React Testing Library frontend test suite (14 critical path tests)
- `test-frontend` CI job - runs on every push and PR
- All 3 deploy jobs now gate on both `test` and `test-frontend` passing

### Fixed
- `pytest.ini` `addopts` with `--cov` flags caused exit code 4 when pytest-cov absent - moved to CI run command
- `frontend/tsconfig.json` excludes `src/test` to prevent Vitest globals breaking `tsc`

---

## [1.2.0] - 2026-04-20

### Added
- Lambda Layer (`applytic-shared`) - shared middleware, Pydantic v2, X-Ray SDK, aws-lambda-powertools
- Shared middleware module - single source of truth for resp(), auth extraction, CORS, correlation IDs
- Pydantic request validation on all Lambda routes
- AWS X-Ray tracing on all 4 Lambdas + API Gateway
- Structured logging via aws-lambda-powertools
- CloudWatch dashboard (`applytic-overview`)
- Cognito Post Confirmation trigger - auto-verifies new user emails in SES sandbox
- `applytic-cognito-verify` Lambda

### Fixed
- Lambda ARM64 vs x86_64 architecture mismatch - build_layer.sh now uses `--platform manylinux2014_aarch64`
- CDK construct ID mismatch on redeploy - preserved original IDs for existing alarms

---

## [1.1.0] - 2026-04-10

### Added
- OIDC role assumption replacing static AWS access keys in GitHub Actions
- npm and pip dependency caching in CI
- Concurrency controls for rapid pushes
- Dependabot - monthly cadence, manual merge only
- CodeQL security scanning (Python + TypeScript)
- DynamoDB TTL attribute enabled for rate limit record cleanup
- CloudWatch alarms for Lambda error rates and p99 latency
- Branch protection rules on main
- CONTRIBUTING.md, pull_request_template.md, ROADMAP.md

### Fixed
- CORS tightened from wildcard `*` to specific CloudFront and GitHub Pages origins

---

## [1.0.0] - 2026-04-01

### Added
- Initial production release
- Kanban board with drag-and-drop status updates
- AI coaching chat powered by Amazon Bedrock (Nova Lite)
- Pattern analysis across 6 dimensions (source, company size, resume version, role level, velocity, funnel)
- Weekly email digest every Monday via SES + EventBridge
- Resume version upload to S3 via presigned URLs
- Analytics dashboard with bar charts, pie chart, weekly velocity
- Full dark mode with system preference detection
- Mobile responsive layout
- GitHub Pages + CloudFront dual deployment from same build
- 48 pytest unit tests
- GitHub Actions CI/CD with OIDC
- AWS CDK v2 TypeScript infrastructure
