"""
Applytic — Seed Data Script
Populates DynamoDB with realistic job applications for demo purposes.

Usage:
    pip install boto3
    python seed_data.py --user-id YOUR_COGNITO_SUB

To find your Cognito sub (user ID):
    - Sign in to your Applytic app
    - Open browser DevTools → Application → Local Storage
    - Look for the CognitoIdentityServiceProvider key, find the key ending in .userData
    - The "sub" field is your user ID
"""

import argparse
import uuid
import boto3
import json
from datetime import datetime, timezone, timedelta
from random import choice, randint, uniform

TABLE_NAME = 'applytic'
REGION = 'us-east-1'

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

# ── Realistic demo data ────────────────────────────────────────────────────────

APPLICATIONS = [
    # Offers
    {
        'company': 'Stripe', 'role': 'Senior ML Engineer',
        'status': 'offer', 'source': 'referral',
        'resumeVersion': 'v3-ml-focused', 'companySize': 'mid',
        'jobDescUrl': 'https://stripe.com/jobs', 'notes': 'Referral from college friend. Great culture fit.',
        'daysAgo': 5,
    },
    # Interviews
    {
        'company': 'Anthropic', 'role': 'ML Engineer',
        'status': 'interview', 'source': 'linkedin',
        'resumeVersion': 'v3-ml-focused', 'companySize': 'startup',
        'jobDescUrl': 'https://anthropic.com/careers', 'notes': 'Final round — system design + ML breadth',
        'daysAgo': 8,
    },
    {
        'company': 'Notion', 'role': 'Senior Software Engineer',
        'status': 'interview', 'source': 'cold',
        'resumeVersion': 'v2-fullstack', 'companySize': 'startup',
        'jobDescUrl': 'https://notion.so/jobs', 'notes': 'Cold applied via careers page. Got to onsite.',
        'daysAgo': 12,
    },
    {
        'company': 'Figma', 'role': 'Backend Engineer',
        'status': 'interview', 'source': 'job-board',
        'resumeVersion': 'v2-fullstack', 'companySize': 'mid',
        'jobDescUrl': 'https://figma.com/careers', 'notes': 'Phone screen went well.',
        'daysAgo': 15,
    },
    # Screened
    {
        'company': 'OpenAI', 'role': 'Research Engineer',
        'status': 'screened', 'source': 'linkedin',
        'resumeVersion': 'v3-ml-focused', 'companySize': 'startup',
        'jobDescUrl': 'https://openai.com/careers', 'notes': 'HR screen scheduled.',
        'daysAgo': 10,
    },
    {
        'company': 'Vercel', 'role': 'Senior Engineer',
        'status': 'screened', 'source': 'referral',
        'resumeVersion': 'v2-fullstack', 'companySize': 'startup',
        'jobDescUrl': 'https://vercel.com/careers', 'notes': 'Referred by ex-colleague.',
        'daysAgo': 18,
    },
    {
        'company': 'Linear', 'role': 'Software Engineer',
        'status': 'screened', 'source': 'cold',
        'resumeVersion': 'v2-fullstack', 'companySize': 'startup',
        'jobDescUrl': 'https://linear.app/careers', 'notes': '',
        'daysAgo': 20,
    },
    # Applied
    {
        'company': 'Databricks', 'role': 'ML Platform Engineer',
        'status': 'applied', 'source': 'linkedin',
        'resumeVersion': 'v3-ml-focused', 'companySize': 'mid',
        'jobDescUrl': 'https://databricks.com/careers', 'notes': '',
        'daysAgo': 3,
    },
    {
        'company': 'Hugging Face', 'role': 'ML Engineer',
        'status': 'applied', 'source': 'linkedin',
        'resumeVersion': 'v3-ml-focused', 'companySize': 'startup',
        'jobDescUrl': 'https://huggingface.co/jobs', 'notes': 'Dream company.',
        'daysAgo': 4,
    },
    {
        'company': 'Cloudflare', 'role': 'Backend Engineer',
        'status': 'applied', 'source': 'job-board',
        'resumeVersion': 'v2-fullstack', 'companySize': 'enterprise',
        'jobDescUrl': 'https://cloudflare.com/careers', 'notes': '',
        'daysAgo': 2,
    },
    {
        'company': 'PlanetScale', 'role': 'Senior Engineer',
        'status': 'applied', 'source': 'cold',
        'resumeVersion': 'v2-fullstack', 'companySize': 'startup',
        'jobDescUrl': 'https://planetscale.com/careers', 'notes': '',
        'daysAgo': 1,
    },
    {
        'company': 'Supabase', 'role': 'Backend Engineer',
        'status': 'applied', 'source': 'linkedin',
        'resumeVersion': 'v1-generic', 'companySize': 'startup',
        'jobDescUrl': 'https://supabase.com/careers', 'notes': '',
        'daysAgo': 6,
    },
    # Rejected
    {
        'company': 'Google', 'role': 'L5 Software Engineer',
        'status': 'rejected', 'source': 'linkedin',
        'resumeVersion': 'v1-generic', 'companySize': 'enterprise',
        'jobDescUrl': 'https://careers.google.com', 'notes': 'Rejected after phone screen. LC hard.',
        'daysAgo': 25,
    },
    {
        'company': 'Meta', 'role': 'Software Engineer E5',
        'status': 'rejected', 'source': 'linkedin',
        'resumeVersion': 'v1-generic', 'companySize': 'enterprise',
        'jobDescUrl': 'https://metacareers.com', 'notes': 'No feedback given.',
        'daysAgo': 30,
    },
    {
        'company': 'Amazon', 'role': 'SDE II',
        'status': 'rejected', 'source': 'job-board',
        'resumeVersion': 'v1-generic', 'companySize': 'enterprise',
        'jobDescUrl': 'https://amazon.jobs', 'notes': 'Failed bar raiser.',
        'daysAgo': 35,
    },
    {
        'company': 'Microsoft', 'role': 'Senior SWE',
        'status': 'rejected', 'source': 'job-board',
        'resumeVersion': 'v2-fullstack', 'companySize': 'enterprise',
        'jobDescUrl': 'https://careers.microsoft.com', 'notes': '',
        'daysAgo': 28,
    },
    {
        'company': 'Airbnb', 'role': 'Senior Engineer',
        'status': 'rejected', 'source': 'linkedin',
        'resumeVersion': 'v2-fullstack', 'companySize': 'enterprise',
        'jobDescUrl': 'https://careers.airbnb.com', 'notes': 'Ghosted after final round.',
        'daysAgo': 22,
    },
    {
        'company': 'Uber', 'role': 'Senior ML Engineer',
        'status': 'rejected', 'source': 'linkedin',
        'resumeVersion': 'v1-generic', 'companySize': 'enterprise',
        'jobDescUrl': 'https://uber.com/careers', 'notes': '',
        'daysAgo': 40,
    },
    {
        'company': 'Twilio', 'role': 'Senior Engineer',
        'status': 'rejected', 'source': 'job-board',
        'resumeVersion': 'v2-fullstack', 'companySize': 'mid',
        'jobDescUrl': 'https://twilio.com/careers', 'notes': 'Rejected after take-home.',
        'daysAgo': 32,
    },
    {
        'company': 'Snap', 'role': 'ML Engineer',
        'status': 'rejected', 'source': 'linkedin',
        'resumeVersion': 'v1-generic', 'companySize': 'enterprise',
        'jobDescUrl': 'https://careers.snap.com', 'notes': '',
        'daysAgo': 45,
    },
]


def now_iso(days_ago: int = 0, jitter_hours: int = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=jitter_hours)
    return dt.isoformat()


def seed(user_id: str):
    print(f"\nSeeding {len(APPLICATIONS)} applications for user: {user_id}")
    print(f"Table: {TABLE_NAME} | Region: {REGION}\n")

    created = 0
    with table.batch_writer() as batch:
        for app_data in APPLICATIONS:
            app_id = str(uuid.uuid4())
            days_ago = app_data['daysAgo']
            created_at = now_iso(days_ago, jitter_hours=randint(0, 8))
            updated_at = now_iso(max(0, days_ago - randint(1, 5)), jitter_hours=randint(0, 4))
            date_applied = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime('%Y-%m-%d')

            # Write application record
            item = {
                'PK': f'USER#{user_id}',
                'SK': f'APP#{app_id}',
                'GSI1PK': f'USER#{user_id}',
                'GSI1SK': f'DATE#{created_at}',
                'appId': app_id,
                'userId': user_id,
                'company': app_data['company'],
                'role': app_data['role'],
                'status': app_data['status'],
                'dateApplied': date_applied,
                'resumeVersion': app_data['resumeVersion'],
                'source': app_data['source'],
                'companySize': app_data['companySize'],
                'jobDescUrl': app_data['jobDescUrl'],
                'notes': app_data['notes'],
                'createdAt': created_at,
                'updatedAt': updated_at,
                'entityType': 'APPLICATION',
            }
            batch.put_item(Item=item)

            # Write initial status event
            batch.put_item(Item={
                'PK': f'APP#{app_id}',
                'SK': f'EVENT#{created_at}#{str(uuid.uuid4())}',
                'userId': user_id,
                'fromStatus': None,
                'toStatus': 'applied',
                'notes': '',
                'createdAt': created_at,
                'entityType': 'STATUS_EVENT',
            })

            # Write additional status events for non-applied statuses
            status_chain = {
                'screened':  ['applied', 'screened'],
                'interview': ['applied', 'screened', 'interview'],
                'offer':     ['applied', 'screened', 'interview', 'offer'],
                'rejected':  ['applied', 'rejected'],
                'withdrawn': ['applied', 'withdrawn'],
            }
            chain = status_chain.get(app_data['status'], [])
            for i in range(1, len(chain)):
                event_days = max(0, days_ago - (i * randint(2, 5)))
                event_ts = now_iso(event_days, jitter_hours=randint(0, 6))
                batch.put_item(Item={
                    'PK': f'APP#{app_id}',
                    'SK': f'EVENT#{event_ts}#{str(uuid.uuid4())}',
                    'userId': user_id,
                    'fromStatus': chain[i - 1],
                    'toStatus': chain[i],
                    'notes': '',
                    'createdAt': event_ts,
                    'entityType': 'STATUS_EVENT',
                })

            created += 1
            print(f"  ✓ {app_data['company']} — {app_data['role']} ({app_data['status']})")

    print(f"\n✅ Done — {created} applications seeded.")
    print(f"\nOpen your app and refresh: https://d3jumje9o63lys.cloudfront.net")
    print("\nPattern highlights in this seed data:")
    print("  • v3-ml-focused resume: highest response rate (referral + LinkedIn)")
    print("  • v1-generic resume: mostly rejections from enterprise companies")
    print("  • Referral source: 2/2 got past screening (100% response rate)")
    print("  • Enterprise companies: 5/5 rejections with v1-generic")
    print("  This gives the AI coach clear patterns to surface.\n")


def clear(user_id: str):
    """Remove all seeded data for a user — use with caution."""
    print(f"Clearing all applications for user: {user_id}")
    result = table.query(
        IndexName='GSI1',
        KeyConditionExpression=boto3.dynamodb.conditions.Key('GSI1PK').eq(f'USER#{user_id}'),
    )
    deleted = 0
    for item in result.get('Items', []):
        if item.get('entityType') == 'APPLICATION':
            table.delete_item(Key={'PK': item['PK'], 'SK': item['SK']})
            deleted += 1
    print(f"Deleted {deleted} applications.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Seed Applytic demo data')
    parser.add_argument('--user-id', required=True, help='Your Cognito sub (user ID)')
    parser.add_argument('--clear', action='store_true', help='Delete all seeded data instead')
    args = parser.parse_args()

    if args.clear:
        clear(args.user_id)
    else:
        seed(args.user_id)
