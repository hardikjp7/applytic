# Changelog

All notable changes to Applytic are documented here.

---

## [3.2.1] - 2026-10-25

Patch release: security hardening and small, certain bug fixes. No schema change and no analytics change. App v3.2.1 + Extension 1.0.1.

### Security

- **SSRF guard on interview-prep job description fetch** - `fetch_job_description` fetched any user-supplied URL, including whatever it redirected to. It now allows only http/https on ports 80 and 443, requires the host to resolve *only* to public addresses (private, loopback, link-local, reserved, IPv4-mapped IPv6 and numeric forms such as `2130706433` or `0x7f.1` are all rejected), and checks every redirect hop itself (max 3). Blocked fetches fall back silently to role + company questions. Known limit: urllib resolves the host again at connect time, so DNS rebinding between the check and the connect is not fully closed
- **API Gateway data tracing turned off** - `dataTraceEnabled` was on, which writes request/response bodies and Authorization headers (ID tokens, notes, contacts) to CloudWatch. Method logging at INFO, metrics and X-Ray are unchanged
- **Resume bucket CORS** restricted to the app's own origins plus localhost (was `*`)
- **PII in logs** - email addresses are masked in `cognito_verify` and `digest` logs
- **CSV formula injection** - exported cells starting with `=`, `+`, `-`, `@` are neutralised with a leading apostrophe; import reverses it so a round trip returns the original text

### Added

- **Daily cap on interview-prep generation** - default 10 per user per day (`PREP_DAILY_LIMIT`), separate counter `RATELIMIT#{userId}` / `PREPGEN#{date}` with a 2-day TTL. Returns 429 with `rateLimited: true`. Checked after the ownership test so unknown applications cannot burn quota. Fails open if the counter write fails, but logs at ERROR level (the chat limiter failed open silently for months in v3.1.1)
- **Shared pagination helper** - `shared/pagination.py` (`paginate_query`, `paginate_scan`) follows `LastEvaluatedKey`. Adopted in applications, insights, digest, followup, settings, notes and contacts, and as an S3 continuation loop in `list_resumes`. Previously every query/scan silently stopped at 1 MB
- **Monthly cost budget** - AWS Budgets, USD 20, covers the whole AWS account, notifies at 80% actual and 100% forecast
- **Input validation at create/update time** - `dateApplied` must be a real YYYY-MM-DD date; `jobDescUrl` must be http(s), max 2048 characters; resume `versionName` (max 64) and `filename` (max 128) cannot contain `/`, `\` or control characters; upload `contentType` must be `application/pdf`; AI Coach `message` max 1000 characters. Stored data is never re-validated on read
- **Local development origin** - `http://localhost:5173` allowed in `ALLOWED_ORIGINS`, API Gateway CORS, Cognito callback/logout URLs and the Amplify OAuth config (resolves the long-deferred localhost CORS issue). Requests still require a valid JWT
- New `tests/test_pagination.py`, `frontend/src/test/csv.test.ts`, and new cases for the SSRF guard, redirect handling, the generate limiter, input validation, chat length and email masking

### Fixed

- Application detail modal: the Contacts section rendered inside the notes wrapper, so the "Add a note..." input appeared below Contacts. Contacts is now a sibling section
- Resume upload reported success on a failed S3 PUT, because `fetch` does not throw on 403/500. The response is now checked
- CSV import showed one "Application added" toast per row; it now shows only its summary toast
- CSV import split rows on `\n`, so a note containing a line break broke the row. The parser now reads quoted fields across lines and accepts CRLF and a BOM
- `compute_patterns` listed `funnel`, `responseRateTimeSeries` and `statusHistory` twice, computing each twice. Duplicates removed
- OpenAPI referenced an undefined `CognitoJWT` security scheme on the v3.0 routes; now `cognitoAuth`
- Interview-prep generate showed a generic error toast even for a 429; it now shows the API message
- A resume `versionName` containing `/` broke `list_resumes` parsing

### Changed

- A job URL typed without `http://` or `https://` is now rejected with a clear message (editing an old record that still holds one fails until the URL is fixed)
- A blank `dateApplied` is treated as "not provided": new applications default to today, and clearing the field in the edit form leaves the stored date unchanged instead of writing an empty string
- Hardcoded test counts removed from README, CONTRIBUTING and the PR template
- `api/openapi.yml` and `api-docs/openapi.yml` bumped to 3.2.1 with the new constraints and the 429 response (both copies are kept; the docs UI is served from `api-docs/`)

### Extension 1.0.1

- Removed the unused `webNavigation` permission and the empty `externally_connectable` block from `manifest.json`
- Deleted dead `content-scripts/linkedin.css` and `shared.css`; corrected the stale "not yet verified" header in `glassdoor.js`

### Infrastructure

- Resume bucket CORS moved to `addCorsRule` with explicit origins
- API Gateway stage: `throttlingRateLimit` 20 and `throttlingBurstLimit` 40 (applied per method; starting values), `dataTraceEnabled` false
- `applytic-interview-prep` environment: `PREP_DAILY_LIMIT=10`
- New `MonthlyCostBudget` (AWS Budgets)
- New layer version (adds `pagination.py`)
- No new routes, tables or Lambdas

### Known limitations

- DNS rebinding between the SSRF check and the connect is not fully closed with urllib
- API Gateway's own 4xx/429 responses carry no CORS headers, so a throttled call looks like a network error in the browser (limits are generous; a `Default4xx` gateway response is the fix)
- `digest.get_active_users` is a filtered full-table scan; it is now complete but reads the whole table each Monday (a sparse GSI is planned for v4.0)
- The budget is account-wide, not per stack; throttle values are starting points

### Upgrade notes

- `cdk deploy` is required. `build_layer.sh` does not need re-running (no pip dependency changed)
- Reload the unpacked extension (or install the 1.0.1 zip); Chrome shows no prompt because only permissions were removed

**Commit scope:** `lambdas/`, `lambdas/shared_layer/`, `cdk/`, `frontend/src/`, `extension/`, `api/`, `api-docs/`, `tests/`, `docs`

---

## [3.2.0] - 2026-10-11

### Added

**Browser extension (Chrome, Manifest V3)** - `extension/`
- Add a job from LinkedIn, Indeed, or Glassdoor to the tracker from the toolbar popup, with no manual entry. No in-page UI: content scripts only extract data when the popup asks, so there is no per-site DOM injection to maintain
- Sign-in via `chrome.identity.launchWebAuthFlow` (OAuth PKCE) against the existing Cognito Hosted UI and the existing public client - no new Cognito resources. Tokens kept in `chrome.storage.local` with silent refresh
- LinkedIn adds as source `linkedin`; Indeed and Glassdoor add as `job-board`. Records are created with `status: applied` through the existing `POST /applications`
- Offline/signed-out queue: adds that cannot sync are kept locally and drained after sign-in or before the next add. Non-retryable errors (validation) surface the real API message instead of queueing
- Duplicate detection: the popup compares the posting against `GET /applications` (job URL first, then company+role, case-insensitive) and shows the existing record's status. It never blocks Add
- Options page: view and remove queued items, manual "Sync now", auth status, supported sites
- Extraction verified on live pages: LinkedIn from `document.title` plus the company profile link; Indeed from `data-testid` hooks and `/cmp/` links; Glassdoor from the job-title id and a CSS-module class prefix
- Indeed regional subdomains supported via wildcard; Glassdoor supported on .com, .co.in, .co.uk, .ca, .com.au, .de, .fr, .ie, .sg

### Changed
- Mid-cycle design pivot: the original plan (an injected in-page "Add to Applytic" button) was replaced by the popup flow after LinkedIn's hashed class names made reliable placement impractical (see Issues 49-54)
- Lambda sender addresses moved to the verified `hardikjp7.com` SES domain: follow-up reminders send from `notifications@hardikjp7.com`, the weekly digest from `insights@hardikjp7.com`. CDK environment config only, no handler change

### Fixed (found during live testing of the extension)
- LinkedIn job title and company had no usable CSS selectors, so the in-page button never appeared
- Debounced MutationObserver never re-ran on a page that never stops mutating
- Content scripts never loaded on regional Indeed and Glassdoor domains
- Indeed extraction failed because of a wrong iframe theory
- Indeed company name was wrong: self-promo link and two different page markups
- Popup showed 'Connected' and 'Not signed in' at the same time

### Infrastructure
- Cognito `UserPoolClient` `callbackUrls`: added `https://eghmfcibiaehpeaekkpnogbfbnelfakj.chromiumapp.org/`
- API Gateway `defaultCorsPreflightOptions.allowOrigins` and `shared/middleware.py` `ALLOWED_ORIGINS`: added `chrome-extension://eghmfcibiaehpeaekkpnogbfbnelfakj`
- No new routes, tables, or Lambdas. `build_layer.sh` does not need re-running (`middleware.py` ships as source)

### Tests
- No automated tests were added for the extension: DOM scraping and `chrome.*` APIs are not covered by the existing suites. Verified manually against live LinkedIn, Indeed (search panel and standalone page) and Glassdoor (.co.in). Backend and frontend suites are unchanged

### Known limitations
- The offline queue retries only on sign-in or the next Add (no periodic `chrome.alarms` flush)
- Site selectors will drift as LinkedIn, Indeed and Glassdoor redesign and need periodic spot-checks
- Glassdoor country domains are listed explicitly and are not exhaustive

### Upgrade notes
- Run `cdk deploy` before the extension can sign in or sync (callback URL and CORS changes). Load the extension unpacked from `extension/`; it is not yet published to the Chrome Web Store

---

## [3.1.1] - 2026-09-06

### Changed

**Salary validation cap raised**
- `expectedSalary`/`offeredSalary` max raised from 2,000,000 to 100,000,000 - the original cap silently rejected valid non-USD figures (e.g. INR salaries in the lakhs, like 25,00,000) since no currency field existed at the time and the number looked implausibly large in USD terms
- New cap is a sanity ceiling against fat-finger entry only, not a real compensation limit

**Salary currency support**
- New `salaryCurrency` field on applications (`USD`, `EUR`, `GBP`, `INR`, `CAD`, `AUD`; defaults to `USD` for both new and pre-existing records)
- One currency per application, applying to both `expectedSalary` and `offeredSalary`
- `insights/handler.py`'s salary analytics are now currency-aware: `_compute_salary_insights()`/`_compute_salary_distribution()` scope their averages and distribution buckets to the user's dominant currency (the most common currency among their salary-bearing applications), excluding applications in a different currency rather than blending incompatible raw numbers - no exchange-rate conversion is performed
- `SalaryInsights` extended with `dominantCurrency` and `excludedCurrencyCount`
- `build_context_for_llm()`'s salary section now states the currency explicitly and notes any excluded applications, so the AI coach doesn't assume USD
- INR uses a wider distribution bucket size than the other five currencies, since INR salary figures are an order of magnitude larger at typical compensation levels
- Frontend: currency dropdown next to salary fields in `AddApplicationModal.tsx` and `ApplicationDetailModal.tsx`; Analytics salary banner and distribution chart display the dominant currency and an exclusion note when applicable
- New `tests/test_insights_v311.py` - 21 tests covering dominant-currency determination and currency-scoped analytics; currency-field tests added to `tests/test_applications.py`/`test_applications_integration.py`

### Fixed

**Error messages silently swallowed on application update failure**
- `useApplications.ts`'s mutations (`create`, `update`, `remove`, `changeStatus`) all showed a generic failure toast regardless of the actual server-side error, which made the salary-cap bug above look like a mystery "Failed to update" instead of a clear validation message
- All four mutations now surface the real API error message when available, falling back to the generic message only when the server didn't provide one

**Production IAM grants missing for write paths added in earlier versions**
- `applytic-digest`: `store_alerts()` (added in v3.0) writes `ALERT#` items via `table.put_item()`, but `digestLambda` only ever had `grantReadData` - every rejection-pattern-alert write was silently failing with `AccessDeniedException` in production since v3.0 shipped
- `applytic-insights`: `check_rate_limit()` writes the daily chat counter via `table.update_item()`, but `insightsLambda` also only had `grantReadData` - the write failure was caught by an existing try/except that fails open, meaning the 20-message/day AI Coach rate limit had not been enforced at all in production since v3.0
- Both Lambdas upgraded to `grantReadWriteData` in `applytic-stack.ts`
- Found via CloudWatch log inspection, not caught by the test suite - the mocked-table unit tests can't detect an IAM permission gap, since that only manifests against the real deployed table

**Commit scope:** `lambdas/applications/`, `lambdas/insights/`, `cdk/`, `frontend/src/`, `tests/`, `api/`, `api-docs/`

---

## [3.1.0] - 2026-08-30

### Added

**Salary Tracking**
- `expectedSalary`, `offeredSalary` (nullable int, 0-2,000,000) and `salaryNotes` (free text) added to the applications schema
- Pydantic validation in `applications/handler.py` on both create and update, including explicit-null clearing for both salary fields (mirrors the existing `followUpDate` pattern)
- `insights/handler.py`: `_compute_salary_distribution()` buckets applications into $20k expected-salary ranges; `_compute_salary_insights()` computes average expected/offered salary and the average offer-vs-expectation gap (both count and percentage), scoped only to applications with both fields set
- Both wired into `compute_patterns()` output as `salaryInsights` and `salaryDistribution`
- `build_context_for_llm()` extended with a "Salary data" section so the AI coach can answer questions like "am I targeting the right salary range?"
- Frontend: expected salary + salary notes fields in `AddApplicationModal.tsx`; expected/offered salary + notes in `ApplicationDetailModal.tsx` edit form; salary insights banner + expected-salary distribution bar chart in `AnalyticsDashboard.tsx`
- 39 new tests in `tests/test_insights_v31.py`, plus salary-field tests added to `tests/test_applications.py` and `tests/test_applications_integration.py`

**Contact Tracking**
- New `applytic-contacts` Lambda (`lambdas/contacts/handler.py`) - `GET/POST /applications/{appId}/contacts`, `DELETE /applications/{appId}/contacts/{contactId}`
- `CONTACT` DynamoDB entity: `PK=APP#{appId}`, `SK=CONTACT#{timestamp}#{contactId}` - name (required), email, LinkedIn URL, role (all optional free text)
- Ownership verification mirrors `notes/handler.py` exactly - checks the parent APPLICATION record exists under `USER#{userId}` before any read/write
- CDK: new Lambda (ARM64, 512MB, 30s), 3 new API Gateway routes, X-Ray IAM, CloudWatch error alarm, dashboard widget entries
- Frontend: new `useContacts.ts` React Query hook (mirrors `useNotes.ts`); Contacts section in `ApplicationDetailModal.tsx` with inline add form and hover-to-delete list
- New `tests/test_contacts.py` - 30 unit tests

### Fixed

**Google Search favicon not displaying**
- Site only served `favicon.svg` with no PNG/ICO fallback and a referenced-but-nonexistent `apple-touch-icon.png`. Google's Search favicon crawler has unreliable SVG support and expects a static PNG/ICO at a stable URL, ideally a multiple of 48px
- Generated `favicon.ico` (16/32/48px embedded), PNG favicons at 16/32/48/96/192/512px, and a real `apple-touch-icon.png` (180px), all matching the existing purple rounded-square "A" mark
- `index.html` `<link rel="icon">` block extended with PNG/ICO fallbacks alongside the existing SVG; `_headers` updated to long-cache the new static assets

**Privacy/Terms "Back to Applytic" returned to the wrong scroll position**
- Returning from `/privacy` or `/terms` landed on the landing page's Features section instead of wherever the user had scrolled to before navigating away
- Root cause: the browser's native `history.scrollRestoration` ('auto' by default) tracks scroll per history entry independently of React Router and reapplies a stale offset against freshly re-mounted (and lazy-loaded) content, which doesn't line up
- Fix: `App.tsx` sets `window.history.scrollRestoration = 'manual'`; `Landing.tsx` now saves scroll position via a live `scroll` listener (not unmount-cleanup, which is unreliable under React 18 StrictMode's dev-only double-invoke) and restores it only on `POP` navigation (back button), retried across a few animation frames so lazy-loaded/scroll-reveal sections have settled first. `PrivacyPolicy.tsx`/`Terms.tsx` explicitly scroll to top on mount, since manual restoration mode means the browser no longer does this automatically. "Back to Applytic" changed from `<Link to="/">` to a `navigate(-1)` handler so it triggers real back-navigation (falls back to `navigate('/')` if there's no history to go back to)

**CSV import missing new required Application fields**
- `KanbanBoard.tsx`'s CSV import path builds an `Application`-shaped object for `create()`; after `expectedSalary`/`offeredSalary`/`salaryNotes` were added to the type, this failed to compile
- Fix: import defaults all three to empty/null - CSV import does not yet support salary columns

**Commit scope:** `lambdas/contacts/` (new), `lambdas/applications/`, `lambdas/insights/`, `cdk/`, `frontend/src/`, `frontend/public/`, `frontend/index.html`, `tests/`, `api/`, `api-docs/`

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
