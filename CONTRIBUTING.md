# Contributing to Applytic

Thanks for your interest in contributing! Applytic is an AI-powered job application tracker built on AWS serverless infrastructure. This guide will get you set up and contributing quickly.

---

## Table of Contents

- [Project Overview](#project-overview)
- [First-Time Developer Checklist](#first-time-developer-checklist)
- [Local Development Setup](#local-development-setup)
- [Running Tests](#running-tests)
- [Project Structure](#project-structure)
- [Branching & Workflow](#branching--workflow)
- [Commit Message Convention](#commit-message-convention)
- [Pull Request Process](#pull-request-process)
- [Code Style](#code-style)
- [Reporting Issues](#reporting-issues)

---

## Project Overview

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Auth | Amazon Cognito |
| API | API Gateway + Lambda (Python 3.12, ARM64) |
| AI/ML | Amazon Bedrock — Amazon Nova Lite |
| Database | DynamoDB single-table design |
| IaC | AWS CDK v2 TypeScript |
| CI/CD | GitHub Actions |

**Live URLs:**
- GitHub Pages: https://hardikjp7.github.io/applytic
- CloudFront: https://d3jumje9o63lys.cloudfront.net

---

## First-Time Developer Checklist

Before you start, make sure you have the following ready:

- [ ] **Node.js 18 or 20** — required for CDK and frontend builds
- [ ] **Python 3.12** — required for Lambda development and tests
- [ ] **AWS CLI** — configured with credentials (`aws configure`)
- [ ] **AWS CDK v2** — `npm install -g aws-cdk`
- [ ] **AWS account access** — IAM permissions for Lambda, DynamoDB, S3, Cognito, Bedrock
- [ ] **Amazon Bedrock model access** — enable `amazon.nova-lite-v1:0` in the AWS console under Bedrock → Model access (us-east-1)
- [ ] **Verified SES email** — if testing the weekly digest Lambda, verify your email with `aws ses verify-email-identity --email-address you@example.com`
- [ ] **pytest and boto3** — `pip install pytest boto3`
- [ ] Fork the repo and clone your fork locally

---

## Local Development Setup

### 1. Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173` by default.

> The dev build connects to the deployed AWS backend by default. You can override API endpoints via `.env.local` if needed.

### 2. Backend (CDK deploy)

```bash
cd cdk
npm install
cdk deploy
```

This deploys all AWS infrastructure including Lambda, API Gateway, DynamoDB, S3, Cognito, and EventBridge.

### 3. Lambda development

Lambda handlers are plain Python files in `lambdas/`. You can edit and test them locally using pytest — no AWS deployment needed for unit tests.

```bash
pip install pytest boto3
python -m pytest tests/ -v --tb=short
```

### 4. Seed demo data (optional)

```bash
cd scripts
python seed_data.py --user-id YOUR_COGNITO_SUB
```

To find your Cognito sub: sign in → DevTools → Application → Local Storage → find `idToken` → paste at jwt.io → copy the `sub` field.

To clear seeded data:
```bash
python seed_data.py --user-id YOUR_COGNITO_SUB --clear
```

---

## Running Tests

```bash
# Run all 48 tests
python -m pytest tests/ -v --tb=short

# Run only applications handler tests
python -m pytest tests/test_applications.py -v

# Run only insights handler tests
python -m pytest tests/test_insights.py -v
```

Tests use `importlib.util.spec_from_file_location` to avoid module name collisions between `applications/handler.py` and `insights/handler.py`. All env vars are set in `conftest.py` — no real AWS credentials needed for unit tests.

**All 48 tests must pass before opening a PR.**

---

## Project Structure

```
applytic/
├── cdk/                    # AWS CDK v2 TypeScript — all infrastructure
├── lambdas/
│   ├── applications/       # CRUD, status pipeline, S3 presigned URLs
│   ├── insights/           # Pattern analysis, Bedrock chat, rate limiting
│   └── digest/             # Weekly SES email digest
├── frontend/src/
│   ├── components/         # React components (kanban, chat, analytics, resume)
│   ├── hooks/              # Custom React hooks
│   ├── lib/                # API client, Amplify config, utils, theme
│   └── pages/              # Route-level page components
├── tests/                  # pytest unit tests
└── scripts/                # Seed data and utility scripts
```

---

## Branching & Workflow

- **`main`** — production branch, protected. All changes go through PRs.
- **Feature branches** — branch from `main`, name as:
  - `feat/short-description` — new features
  - `fix/short-description` — bug fixes
  - `chore/short-description` — dependency updates, tooling
  - `docs/short-description` — documentation only

```bash
git checkout main
git pull origin main
git checkout -b feat/your-feature-name
```

---

## Commit Message Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

[optional body]
```

**Types:** `feat`, `fix`, `docs`, `chore`, `test`, `refactor`, `style`, `ci`

**Scopes:** `frontend`, `lambda`, `cdk`, `tests`, `docs`, `ci`

**Examples:**
```
feat(frontend): add withdrawn column to kanban board
fix(lambda): handle timezone-aware datetime in velocity calculation
chore(cdk): tighten CORS to specific allowed origins
test(insights): add rate limit boundary test cases
docs: add CONTRIBUTING.md and PR template
```

---

## Pull Request Process

1. Ensure all 48 tests pass locally (`python -m pytest tests/ -v`)
2. Run `npm run build` in `frontend/` and confirm no TypeScript errors
3. Open a PR against `main` using the PR template
4. Fill in all sections of the PR template — incomplete PRs will be asked to update
5. Link any related issues using `Closes #issue-number`
6. A maintainer will review within a few days

**PRs that break tests in CI will not be merged.**

---

## Code Style

### Python (Lambdas)
- Follow PEP 8
- Use type hints where practical
- Keep handlers focused — route logic in the handler, business logic in helper functions
- All new Lambda routes need corresponding unit tests in `tests/`

### TypeScript / React (Frontend)
- Use functional components with hooks
- Keep components under `src/components/` organized by domain (kanban, chat, analytics, resume, layout)
- Use Tailwind utility classes — avoid inline styles
- Dark mode: always add `dark:` variants when adding new color classes

### CDK (Infrastructure)
- Define all resources in `cdk/lib/applytic-stack.ts`
- Never hardcode account IDs, bucket names, or ARNs — use CDK tokens and references
- IAM policies should follow least-privilege — avoid `Resource: "*"` unless required (Bedrock inference profiles currently require it)

---

## Reporting Issues

Please use GitHub Issues with the appropriate label:

- `bug` — something is broken
- `enhancement` — new feature request
- `documentation` — docs gap or improvement
- `security` — security concern (for sensitive issues, email directly instead of opening a public issue)

Include steps to reproduce, expected vs actual behaviour, and relevant logs or screenshots where applicable.

---

## Questions?

Open a [GitHub Discussion](https://github.com/hardikjp7/applytic/discussions) or file an issue with the `question` label.
