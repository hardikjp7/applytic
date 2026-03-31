"""
Digest Lambda
Triggered every Monday 8am UTC by EventBridge.
Queries all users, generates AI-powered weekly summary, sends via SES.
"""
import json
import os
import boto3
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from boto3.dynamodb.conditions import Key, Attr

dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime")
ses = boto3.client("ses")

TABLE_NAME = os.environ["TABLE_NAME"]
MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
FROM_EMAIL = os.environ.get("SES_FROM_EMAIL", "noreply@yourdomain.com")
table = dynamodb.Table(TABLE_NAME)


# ── Fetch users with activity in the last 7 days ──────────────────────────────

def get_active_users() -> list[dict]:
    """
    Scan for status events created in the last 7 days to find active users.
    In production, maintain a USERS entity instead of scanning.
    """
    one_week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    result = table.scan(
        FilterExpression=Attr("entityType").eq("APPLICATION") &
                         Attr("updatedAt").gte(one_week_ago),
        ProjectionExpression="userId, GSI1PK",
    )
    seen = set()
    users = []
    for item in result.get("Items", []):
        uid = item.get("userId")
        if uid and uid not in seen:
            seen.add(uid)
            users.append({"userId": uid})
    return users


def get_user_apps(user_id: str) -> list:
    result = table.query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq(f"USER#{user_id}"),
    )
    return [i for i in result["Items"] if i.get("entityType") == "APPLICATION"]


def get_week_events(user_id: str) -> list:
    """Get all status events from the last 7 days for a user's apps."""
    apps = get_user_apps(user_id)
    one_week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    events = []

    for app in apps:
        app_id = app.get("appId")
        result = table.query(
            KeyConditionExpression=Key("PK").eq(f"APP#{app_id}") &
                                   Key("SK").begins_with("EVENT#"),
            FilterExpression=Attr("createdAt").gte(one_week_ago),
        )
        for event in result["Items"]:
            event["company"] = app.get("company", "Unknown")
            event["role"] = app.get("role", "Unknown")
            events.append(event)

    return events


# ── Generate weekly tip via Bedrock ───────────────────────────────────────────

def generate_weekly_tip(apps: list, week_events: list) -> str:
    total = len(apps)
    status_counts = defaultdict(int)
    for app in apps:
        status_counts[app.get("status", "applied")] += 1

    week_summary = f"""
Total applications: {total}
Status breakdown: {dict(status_counts)}
This week's activity ({len(week_events)} events):
"""
    for e in week_events[:15]:
        week_summary += f"  {e.get('company')} ({e.get('role')}): {e.get('fromStatus')} → {e.get('toStatus')}\n"

    prompt = f"""You are a job search coach. Based on this week's job search data, 
give ONE specific, actionable tip (2-3 sentences max). Be direct and data-driven.

{week_summary}

Weekly tip:"""

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}],
        }),
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"].strip()


# ── Build and send email ───────────────────────────────────────────────────────

def build_email_html(apps: list, week_events: list, tip: str, user_email: str) -> str:
    total = len(apps)
    status_counts = defaultdict(int)
    for app in apps:
        status_counts[app.get("status", "applied")] += 1

    week_activity = ""
    for e in week_events:
        to_status = e.get("toStatus", "")
        color = {
            "interview": "#1D9E75",
            "offer": "#639922",
            "rejected": "#E24B4A",
            "screened": "#378ADD",
        }.get(to_status, "#888780")
        week_activity += f"""
            <tr>
              <td style="padding:6px 0;color:#3d3d3a;">{e.get('company')}</td>
              <td style="padding:6px 0;color:#3d3d3a;">{e.get('role')}</td>
              <td style="padding:6px 0;">
                <span style="color:{color};font-weight:500;">{to_status}</span>
              </td>
            </tr>"""

    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:24px;color:#3d3d3a;">
  <h2 style="font-size:20px;font-weight:500;margin-bottom:4px;">Your weekly job search digest</h2>
  <p style="color:#73726c;font-size:13px;margin-top:0;">
    {datetime.now(timezone.utc).strftime('%B %d, %Y')}
  </p>

  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0;">
    <div style="background:#f1efe8;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:24px;font-weight:500;">{total}</div>
      <div style="font-size:12px;color:#73726c;">Total applied</div>
    </div>
    <div style="background:#f1efe8;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:24px;font-weight:500;">{status_counts.get('interview', 0)}</div>
      <div style="font-size:12px;color:#73726c;">Interviews</div>
    </div>
    <div style="background:#f1efe8;border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:24px;font-weight:500;">{len(week_events)}</div>
      <div style="font-size:12px;color:#73726c;">This week</div>
    </div>
  </div>

  {"<h3 style='font-size:15px;font-weight:500;'>This week's activity</h3><table style='width:100%;border-collapse:collapse;font-size:13px;'>" + week_activity + "</table>" if week_events else "<p style='color:#73726c;'>No activity this week — try to apply to at least 5 roles.</p>"}

  <div style="background:#eeedfe;border-radius:8px;padding:16px;margin:20px 0;">
    <div style="font-size:11px;font-weight:500;color:#534ab7;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:6px;">
      AI tip of the week
    </div>
    <p style="font-size:13px;color:#26215c;margin:0;line-height:1.6;">{tip}</p>
  </div>

  <p style="font-size:11px;color:#73726c;margin-top:24px;">
    Applytic — <a href="#" style="color:#185FA5;">View dashboard</a>
  </p>
</body>
</html>"""


def send_digest(user_email: str, html: str):
    ses.send_email(
        Source=FROM_EMAIL,
        Destination={"ToAddresses": [user_email]},
        Message={
            "Subject": {"Data": "Your weekly job search digest"},
            "Body": {"Html": {"Data": html}},
        },
    )


# ── Entry point ────────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    print(f"Weekly digest triggered at {datetime.now(timezone.utc).isoformat()}")

    cognito = boto3.client("cognito-idp")
    user_pool_id = os.environ.get("USER_POOL_ID", "")

    active_users = get_active_users()
    print(f"Found {len(active_users)} active users")

    sent = 0
    failed = 0

    for user in active_users:
        user_id = user["userId"]
        try:
            # look up email from Cognito
            cognito_user = cognito.admin_get_user(
                UserPoolId=user_pool_id,
                Username=user_id,
            )
            email = next(
                (a["Value"] for a in cognito_user["UserAttributes"] if a["Name"] == "email"),
                None,
            )
            if not email:
                print(f"No email for user {user_id}, skipping")
                continue

            apps = get_user_apps(user_id)
            if not apps:
                continue

            week_events = get_week_events(user_id)
            tip = generate_weekly_tip(apps, week_events)
            html = build_email_html(apps, week_events, tip, email)
            send_digest(email, html)
            sent += 1
            print(f"Digest sent to {email}")

        except Exception as e:
            print(f"Failed for user {user_id}: {e}")
            failed += 1

    return {
        "statusCode": 200,
        "body": json.dumps({"sent": sent, "failed": failed}),
    }
