# Applytic with AI Insights

End-to-end serverless job search intelligence platform on AWS. Tracks every application, detects patterns across rejections, and uses Amazon Bedrock (Claude) to give data-driven coaching.

## Architecture

```
React (S3 + CloudFront)
    ↓  JWT via Cognito
API Gateway (REST)
    ├── /applications   → Applications Lambda (CRUD + status pipeline)
    ├── /insights       → Insights Lambda (pattern analysis)
    └── /insights/chat  → Insights Lambda (Bedrock AI coaching)

EventBridge (Monday 8am)
    → Digest Lambda → SES email

DynamoDB (single table)   S3 (resumes)   CloudWatch (logs)
```

## Tech Stack

| Layer       | Service                                      |
|-------------|----------------------------------------------|
| Frontend    | React + TypeScript, S3, CloudFront           |
| Auth        | Amazon Cognito                               |
| API         | API Gateway REST + Lambda (Python 3.12)      |
| AI/ML       | Amazon Bedrock (Claude 3.5 Sonnet)           |
| Database    | DynamoDB (single-table, PAY_PER_REQUEST)     |
| Storage     | S3 (resume versions)                         |
| Scheduling  | EventBridge cron                             |
| Email       | Amazon SES                                   |
| IaC         | AWS CDK v2 (TypeScript)                      |

## DynamoDB Access Patterns

| Pattern                        | PK              | SK                  | Index |
|--------------------------------|-----------------|---------------------|-------|
| Get single application         | USER#userId     | APP#appId           | Main  |
| List all apps for user         | USER#userId     | GSI1 (date sorted)  | GSI1  |
| Get status history for an app  | APP#appId       | EVENT#timestamp     | Main  |

## Project Structure

```
applytic/
├── cdk/
│   ├── bin/app.ts              # CDK entry point
│   ├── lib/applytic-stack.ts # All AWS resources
│   ├── cdk.json
│   ├── package.json
│   └── tsconfig.json
├── lambdas/
│   ├── applications/handler.py  # CRUD + presigned URLs
│   ├── insights/handler.py      # Pattern analysis + Bedrock chat
│   ├── digest/handler.py        # Weekly email digest
│   └── requirements.txt
└── README.md
```

## Setup & Deploy

### Prerequisites
- AWS CLI configured (`aws configure`)
- Node.js 18+
- Python 3.12
- AWS CDK CLI: `npm install -g aws-cdk`

### 1. Bootstrap CDK (first time only)
```bash
cd cdk
npm install
cdk bootstrap aws://YOUR_ACCOUNT_ID/us-east-1
```

### 2. Deploy the stack
```bash
cdk deploy
```

Note the outputs — you'll need `ApiUrl`, `UserPoolId`, `UserPoolClientId` for the frontend `.env`.

### 3. Verify Bedrock model access
In the AWS console → Amazon Bedrock → Model access → enable **Claude 3.5 Sonnet**.

### 4. Verify SES email
```bash
aws ses verify-email-identity --email-address noreply@yourdomain.com
```
Update `SES_FROM_EMAIL` in the CDK stack before deploying for digest emails.

## API Reference

### Applications

```
GET    /v1/applications               List all applications
POST   /v1/applications               Create application
GET    /v1/applications/{appId}       Get single application
PUT    /v1/applications/{appId}       Update application fields
DELETE /v1/applications/{appId}       Delete application
POST   /v1/applications/{appId}/status  Update status
POST   /v1/resumes/upload-url         Get presigned S3 URL
```

#### Create application — request body
```json
{
  "company": "Anthropic",
  "role": "Senior ML Engineer",
  "status": "applied",
  "source": "linkedin",
  "resumeVersion": "v3-ml-focused",
  "companySize": "startup",
  "jobDescUrl": "https://...",
  "notes": "Referral from Priya"
}
```

#### Status values
`applied` → `screened` → `interview` → `offer` | `rejected` | `withdrawn`

### Insights

```
GET  /v1/insights         Pattern analysis dashboard data
POST /v1/insights/chat    AI coaching chat
```

#### Chat — request body
```json
{ "message": "Why am I getting ghosted after applying?" }
```

## Talking Points (for interviews)

**On the data model:**
> "I used DynamoDB single-table design with two entity types — APPLICATION and STATUS_EVENT — so I can query a user's full application history and an individual app's complete status timeline with just two access patterns."

**On the pattern analysis:**
> "The insight engine isn't just calling an LLM — it computes response rates across six dimensions: source channel, company size, resume version, role seniority, and weekly velocity. The LLM gets this structured data as context so its advice is grounded in the actual numbers, not generic tips."

**On the architecture:**
> "Everything is serverless and event-driven. Status updates trigger the insights computation, and EventBridge fires the digest every Monday morning. There's no server to manage and the cost at low volume is essentially zero."
