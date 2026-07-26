"""
Digest Lambda - v3.0
Triggered every Monday 8am UTC by EventBridge.

v3.0 addition: detect_rejection_patterns() - scans a user's applications for
three alert-worthy patterns and stores them as ALERT# items for the Dashboard
banner + includes them in the weekly digest email.
"""
import json
import os
import uuid
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

# ── v3.0: rejection pattern alert thresholds ──────────────────────────────────
MIN_APPS_FOR_ZERO_RESPONSE_ALERT = 5
RESPONSE_RATE_DROP_THRESHOLD_PP = 20  # percentage points
ALERT_TTL_DAYS = 30
RESPONDED_STATUSES = {"screened", "interview", "offer"}


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


# ── v3.0: rejection pattern detection ─────────────────────────────────────────

def _response_rate(apps: list) -> float:
    if not apps:
        return 0.0
    responded = sum(1 for a in apps if a.get("status") in RESPONDED_STATUSES)
    return round(responded / len(apps) * 100, 1)


@tracer.capture_method
def detect_rejection_patterns(user_id: str, apps: list) -> list[str]:
    """
    Scans a user's applications for three alert-worthy patterns:
      (a) A resume version with 0% response rate after 5+ applications
      (b) A source channel with 0% response rate after 5+ applications
      (c) Response rate dropped >20 percentage points week-over-week

    Returns a list of human-readable alert message strings. Empty list if
    no patterns found or insufficient data (always safe to call with few apps).
    """
    if not apps:
        return []

    alerts: list[str] = []

    # (a) resume version 0% response after 5+ apps
    by_resume: dict[str, list] = defaultdict(list)
    for app in apps:
        version = app.get("resumeVersion") or "default"
        by_resume[version].append(app)

    for version, version_apps in by_resume.items():
        if len(version_apps) >= MIN_APPS_FOR_ZERO_RESPONSE_ALERT and _response_rate(version_apps) == 0.0:
            alerts.append(
                f"Your '{version}' resume has a 0% response rate across "
                f"{len(version_apps)} applications. Consider revising it or switching versions."
            )

    # (b) source channel 0% response after 5+ apps
    by_source: dict[str, list] = defaultdict(list)
    for app in apps:
        source = app.get("source") or "unknown"
        by_source[source].append(app)

    for source, source_apps in by_source.items():
        if len(source_apps) >= MIN_APPS_FOR_ZERO_RESPONSE_ALERT and _response_rate(source_apps) == 0.0:
            alerts.append(
                f"Your '{source}' applications have a 0% response rate across "
                f"{len(source_apps)} applications. This channel may not be working for you."
            )

    # (c) response rate dropped >20pp week-over-week
    now = datetime.now(timezone.utc)
    this_week_start = now - timedelta(days=7)
    last_week_start = now - timedelta(days=14)

    this_week_apps = []
    last_week_apps = []
    for app in apps:
        date_str = app.get("dateApplied", "")
        try:
            if len(date_str) == 10:
                applied = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            else:
                applied = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if applied.tzinfo is None:
                    applied = applied.replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            continue

        if applied >= this_week_start:
            this_week_apps.append(app)
        elif last_week_start <= applied < this_week_start:
            last_week_apps.append(app)

    if this_week_apps and last_week_apps:
        this_rate = _response_rate(this_week_apps)
        last_rate = _response_rate(last_week_apps)
        drop = last_rate - this_rate
        if drop >= RESPONSE_RATE_DROP_THRESHOLD_PP:
            alerts.append(
                f"Your response rate dropped from {last_rate}% last week to {this_rate}% "
                f"this week - a {round(drop, 1)} point decline. Worth reviewing what changed."
            )

    return alerts


@tracer.capture_method
def store_alerts(user_id: str, alert_messages: list[str]) -> list[dict]:
    """
    Writes one ALERT# item per detected pattern. TTL set so old alerts
    auto-expire after ALERT_TTL_DAYS. Returns the stored items.
    """
    ts = now_iso()
    ttl = int((datetime.now(timezone.utc) + timedelta(days=ALERT_TTL_DAYS)).timestamp())
    stored = []
    for message in alert_messages:
        alert_id = str(uuid.uuid4())
        item = {
            "PK": f"USER#{user_id}",
            "SK": f"ALERT#{ts}#{alert_id}",
            "alertId": alert_id,
            "userId": user_id,
            "message": message,
            "dismissed": False,
            "createdAt": ts,
            "ttl": ttl,
            "entityType": "ALERT",
        }
        table.put_item(Item=item)
        stored.append(item)
    return stored


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


def build_email_html(apps: list, week_events: list, tip: str, user_email: str, alerts: list[str] = None) -> str:
    alerts = alerts or []
    total = len(apps)
    status_counts = defaultdict(int)
    for app in apps:
        status_counts[app.get("status", "applied")] += 1

    week_activity = ""
    for e in week_events:
        to_status = e.get("toStatus", "")
        color = {"interview": "#1D9E75", "offer": "#639922", "rejected": "#E24B4A", "screened": "#378ADD"}.get(to_status, "#888780")
        week_activity += f"""<tr><td style="padding:6px 0;">{e.get('company')}</td><td style="padding:6px 0;">{e.get('role')}</td><td style="padding:6px 0;"><span style="color:{color};font-weight:500;">{to_status}</span></td></tr>"""

    # v3.0: rejection pattern alert section - only rendered if alerts exist
    alerts_section = ""
    if alerts:
        alert_rows = "".join(
            f'<li style="margin-bottom:8px;">{a}</li>' for a in alerts
        )
        alerts_section = f"""<div style="background:#fdf2e9;border-radius:8px;padding:16px;margin:20px 0;border-left:3px solid #ef9f27;">
    <div style="font-size:11px;font-weight:500;color:#b8651a;text-transform:uppercase;margin-bottom:8px;">Pattern alert</div>
    <ul style="font-size:13px;color:#7c4a14;margin:0;padding-left:18px;">{alert_rows}</ul>
  </div>"""

    return f"""<!DOCTYPE html><html><body style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:24px;">
  <h2>Your weekly job search digest</h2>
  <p style="color:#73726c;font-size:13px;">{datetime.now(timezone.utc).strftime('%B %d, %Y')}</p>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0;">
    <div style="background:#f1efe8;border-radius:8px;padding:12px;text-align:center;"><div style="font-size:24px;font-weight:500;">{total}</div><div style="font-size:12px;">Total applied</div></div>
    <div style="background:#f1efe8;border-radius:8px;padding:12px;text-align:center;"><div style="font-size:24px;font-weight:500;">{status_counts.get('interview', 0)}</div><div style="font-size:12px;">Interviews</div></div>
    <div style="background:#f1efe8;border-radius:8px;padding:12px;text-align:center;"><div style="font-size:24px;font-weight:500;">{len(week_events)}</div><div style="font-size:12px;">This week</div></div>
  </div>
  {alerts_section}
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
    alerts_generated = 0

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

            # v3.0: detect and store rejection pattern alerts
            alert_messages = detect_rejection_patterns(user_id, apps)
            if alert_messages:
                store_alerts(user_id, alert_messages)
                alerts_generated += len(alert_messages)

            html = build_email_html(apps, week_events, tip, email, alerts=alert_messages)
            send_digest(email, html)
            sent += 1
            logger.info("Digest sent", extra={"email": email, "alert_count": len(alert_messages)})
        except Exception:
            logger.exception(f"Failed digest for user {user_id}")
            failed += 1

    logger.info("Digest run complete", extra={"sent": sent, "failed": failed, "alerts_generated": alerts_generated})
    return {"statusCode": 200, "body": json.dumps({"sent": sent, "failed": failed, "alertsGenerated": alerts_generated})}
