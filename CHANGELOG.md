# Changelog

All notable changes to Applytic are documented here.

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
