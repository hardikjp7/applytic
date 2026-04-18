#!/bin/bash
# =============================================================================
# Applytic v1.1 — OIDC Role Setup Script
# Run this ONCE manually before deploying v1.1.
# After running, add AWS_DEPLOY_ROLE_ARN to GitHub Secrets.
# =============================================================================

set -e

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REPO="hardikjp7/applytic"
REGION="us-east-1"
ROLE_NAME="applytic-github-deploy"

echo "Setting up OIDC deploy role for:"
echo "  Account: $ACCOUNT_ID"
echo "  Repo:    $REPO"
echo "  Role:    $ROLE_NAME"
echo ""

# ── Step 1: Create the OIDC identity provider (idempotent) ────────────────────
echo "Creating GitHub OIDC provider..."
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 \
  2>/dev/null || echo "  OIDC provider already exists, skipping."

# ── Step 2: Create the trust policy ──────────────────────────────────────────
TRUST_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:${REPO}:*"
        }
      }
    }
  ]
}
EOF
)

# ── Step 3: Create the IAM role ───────────────────────────────────────────────
echo "Creating IAM role: $ROLE_NAME..."
aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document "$TRUST_POLICY" \
  --description "GitHub Actions OIDC deploy role for Applytic" \
  2>/dev/null || echo "  Role already exists, updating trust policy..."

# Update trust policy in case role already exists
aws iam update-assume-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-document "$TRUST_POLICY"

# ── Step 4: Attach required permissions ──────────────────────────────────────
echo "Attaching permissions..."

# CDK deploy needs broad permissions — scope down if needed after v1.1
DEPLOY_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CDKDeploy",
      "Effect": "Allow",
      "Action": [
        "cloudformation:*",
        "s3:*",
        "lambda:*",
        "apigateway:*",
        "dynamodb:*",
        "cognito-idp:*",
        "events:*",
        "iam:*",
        "cloudfront:*",
        "logs:*",
        "cloudwatch:*",
        "sns:*",
        "bedrock:*",
        "ses:*",
        "sts:AssumeRole"
      ],
      "Resource": "*"
    }
  ]
}
EOF
)

aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "applytic-deploy-policy" \
  --policy-document "$DEPLOY_POLICY"

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

echo ""
echo "✅ OIDC role created successfully."
echo ""
echo "Next steps:"
echo "  1. Go to GitHub → Settings → Secrets → Actions"
echo "  2. Add secret: AWS_DEPLOY_ROLE_ARN = ${ROLE_ARN}"
echo "  3. Remove old secrets: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY"
echo "  4. Run CDK bootstrap if not already done:"
echo "     cd cdk && cdk bootstrap aws://${ACCOUNT_ID}/${REGION}"
echo ""
echo "Role ARN: ${ROLE_ARN}"
