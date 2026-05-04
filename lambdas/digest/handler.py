"""
Digest Lambda — v1.2
Triggered every Monday 8am UTC by EventBridge.
"""
import json
import os
import boto3
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from boto3.dynamodb.conditions import Key, Attr
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from shared.middleware import now_iso

dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime")
ses = boto3.client("ses")

TABLE_NAME = os.environ["TABLE_NAME"]
MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
FROM_EMAIL = os.environ.get("SES_FROM_EMAIL", "noreply@yourdomain.com")
table = dynamodb.Table(TABLE_NAME)

logger = Logger(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "applytic"))
tracer = Tracer(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "applytic"))


@tracer.capture_method
def get_active_users() -> list[dict]:
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


@tracer.capture_method
def get_user_apps(user_id: str) -> list:
    result = table.query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq(f"USER#{user_id}"),
    )
    return [i for i in result["Items"] if i.get("entityType") == "APPLICATION"]


@tracer.capture_method
def get_week_events(user_id: str) -> list:
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


@tracer.capture_method
def generate_weekly_tip(apps: list, week_events: list) -> str:
    total = len(apps)
    status_counts = defaultdict(int)
    for app in apps:
        status_counts[app.get("status", "applied")] += 1

    week_summary = f"\nTotal applications: {total}\nStatus breakdown: {dict(status_counts)}\nThis week's activity ({len(week_events)} events):\n"
    for e in week_events[:15]:
        week_summary += f"  {e.get('company')} ({e.get('role')}): {e.get('fromStatus')} → {e.get('toStatus')}\n"

    prompt = f"You are a job search coach. Based on this week's data, give ONE specific, actionable tip (2-3 sentences max). Be direct and data-driven.\n{week_summary}\nWeekly tip:"

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(
            {"anthropic_version": "bedrock-2023-05-31", "max_tokens": 200, "messages": [{"role": "user", "content": prompt}]}
            if "anthropic" in MODEL_ID else
            {"messages": [{"role": "user", "content": [{"text": prompt}]}], "inferenceConfig": {"maxTokens": 200}}
        ),
    )
    result = json.loads(response["body"].read())
    if "anthropic" in MODEL_ID:
        return result["content"][0]["text"].strip()
    else:
        return result["output"]["message"]["content"][0]["text"].strip()


def build_email_html(apps: list, week_events: list, tip: str, user_email: str) -> str:
    total = len(apps)
    status_counts = defaultdict(int)
    for app in apps:
        status_counts[app.get("status", "applied")] += 1

    week_activity = ""
    for e in week_events:
        to_status = e.get("toStatus", "")
        color = {"interview": "#1D9E75", "offer": "#639922", "rejected": "#E24B4A", "screened": "#378ADD"}.get(to_status, "#888780")
        week_activity += f"""<tr><td style="padding:6px 0;">{e.get('company')}</td><td style="padding:6px 0;">{e.get('role')}</td><td style="padding:6px 0;"><span style="color:{color};font-weight:500;">{to_status}</span></td></tr>"""

    return f"""<!DOCTYPE html><html><body style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:24px;">
  <h2>Your weekly job search digest</h2>
  <p style="color:#73726c;font-size:13px;">{datetime.now(timezone.utc).strftime('%B %d, %Y')}</p>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0;">
    <div style="background:#f1efe8;border-radius:8px;padding:12px;text-align:center;"><div style="font-size:24px;font-weight:500;">{total}</div><div style="font-size:12px;">Total applied</div></div>
    <div style="background:#f1efe8;border-radius:8px;padding:12px;text-align:center;"><div style="font-size:24px;font-weight:500;">{status_counts.get('interview', 0)}</div><div style="font-size:12px;">Interviews</div></div>
    <div style="background:#f1efe8;border-radius:8px;padding:12px;text-align:center;"><div style="font-size:24px;font-weight:500;">{len(week_events)}</div><div style="font-size:12px;">This week</div></div>
  </div>
  {"<table style='width:100%;border-collapse:collapse;font-size:13px;'>" + week_activity + "</table>" if week_events else "<p>No activity this week.</p>"}
  <div style="background:#eeedfe;border-radius:8px;padding:16px;margin:20px 0;">
    <div style="font-size:11px;font-weight:500;color:#534ab7;text-transform:uppercase;margin-bottom:6px;">AI tip of the week</div>
    <p style="font-size:13px;color:#26215c;margin:0;">{tip}</p>
  </div>
</body></html>"""


@tracer.capture_method
def send_digest(user_email: str, html: str):
    ses.send_email(
        Source=FROM_EMAIL,
        Destination={"ToAddresses": [user_email]},
        Message={"Subject": {"Data": "Your weekly job search digest"}, "Body": {"Html": {"Data": html}}},
    )


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    logger.info("Weekly digest triggered")
    cognito = boto3.client("cognito-idp")
    user_pool_id = os.environ.get("USER_POOL_ID", "")
    active_users = get_active_users()
    logger.info(f"Found {len(active_users)} active users")

    sent = 0
    failed = 0

    for user in active_users:
        user_id = user["userId"]
        try:
            cognito_user = cognito.admin_get_user(UserPoolId=user_pool_id, Username=user_id)
            email = next((a["Value"] for a in cognito_user["UserAttributes"] if a["Name"] == "email"), None)
            if not email:
                logger.warning("No email found", extra={"user_id": user_id})
                continue
            apps = get_user_apps(user_id)
            if not apps:
                continue
            week_events = get_week_events(user_id)
            tip = generate_weekly_tip(apps, week_events)
            html = build_email_html(apps, week_events, tip, email)
            send_digest(email, html)
            sent += 1
            logger.info("Digest sent", extra={"email": email})
        except Exception:
            logger.exception(f"Failed digest for user {user_id}")
            failed += 1

    logger.info("Digest run complete", extra={"sent": sent, "failed": failed})
    return {"statusCode": 200, "body": json.dumps({"sent": sent, "failed": failed})}
