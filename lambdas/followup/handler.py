"""
Follow-up Lambda - v2.0
Triggered daily by EventBridge at 9am UTC.
Scans all active applications where:
  - status is 'applied' or 'screened'
  - followUpDate is set and is today or in the past
  - no response received yet (status hasn't moved to interview/offer/rejected)
Sends SES nudge email to the user.

Never raises - all errors are caught per-user so one failure doesn't block others.
"""
import json
import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key, Attr
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from shared.middleware import now_iso

dynamodb = boto3.resource("dynamodb")
ses = boto3.client("ses")
cognito = boto3.client("cognito-idp")

TABLE_NAME = os.environ["TABLE_NAME"]
USER_POOL_ID = os.environ["USER_POOL_ID"]
FROM_EMAIL = os.environ.get("SES_FROM_EMAIL", "noreply@applytic.app")

table = dynamodb.Table(TABLE_NAME)

logger = Logger(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "applytic"))
tracer = Tracer(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "applytic"))

FOLLOWUP_STATUSES = {"applied", "screened"}


@tracer.capture_method
def get_overdue_followups() -> list[dict]:
    """
    Scan for APPLICATION entities where:
    - followUpDate exists and <= today
    - status is applied or screened (still waiting for response)
    Returns list of items grouped by userId.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    result = table.scan(
        FilterExpression=(
            Attr("entityType").eq("APPLICATION") &
            Attr("followUpDate").exists() &
            Attr("followUpDate").lte(today) &
            Attr("status").is_in(list(FOLLOWUP_STATUSES))
        ),
        ProjectionExpression="appId, userId, company, #r, followUpDate, #s, dateApplied",
        ExpressionAttributeNames={"#r": "role", "#s": "status"},
    )
    return result.get("Items", [])


@tracer.capture_method
def get_user_email(user_id: str) -> str | None:
    """Fetch email from Cognito for a given user sub."""
    try:
        resp = cognito.admin_get_user(
            UserPoolId=USER_POOL_ID,
            Username=user_id,
        )
        for attr in resp.get("UserAttributes", []):
            if attr["Name"] == "email":
                return attr["Value"]
    except Exception:
        logger.exception("Failed to get user email", extra={"user_id": user_id})
    return None


def build_followup_email(apps: list[dict]) -> str:
    """Build HTML email body listing applications due for follow-up."""
    rows = ""
    for app in apps:
        company = app.get("company", "Unknown")
        role = app.get("role", "Unknown")
        follow_up_date = app.get("followUpDate", "")
        date_applied = app.get("dateApplied", "")
        rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #f0eeeb;">{company}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0eeeb;">{role}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0eeeb;">{date_applied}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0eeeb;color:#ef9f27;font-weight:500;">{follow_up_date}</td>
        </tr>
        """

    count = len(apps)
    return f"""<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px;background:#f9f8f4;">
  <div style="background:#fff;border-radius:12px;padding:32px;border:1px solid #f0eeeb;">
    <h2 style="color:#26215c;margin-top:0;">
      {"You have" if count > 1 else "You have"} {count} application{"s" if count > 1 else ""} due for follow-up
    </h2>
    <p style="color:#73726c;font-size:14px;">
      These applications have passed their follow-up date and are still waiting for a response.
      A quick follow-up email can significantly improve your response rate.
    </p>
    <table style="width:100%;border-collapse:collapse;font-size:13px;margin:20px 0;">
      <thead>
        <tr style="background:#f1efe8;">
          <th style="padding:8px 12px;text-align:left;color:#26215c;">Company</th>
          <th style="padding:8px 12px;text-align:left;color:#26215c;">Role</th>
          <th style="padding:8px 12px;text-align:left;color:#26215c;">Applied</th>
          <th style="padding:8px 12px;text-align:left;color:#26215c;">Follow-up due</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
    <div style="margin-top:24px;">
      <a href="https://hardikjp7.github.io/applytic/board"
         style="background:#534ab7;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:500;">
        Open Board
      </a>
    </div>
    <p style="color:#b0aea8;font-size:11px;margin-top:24px;">
      You're receiving this because you set a follow-up date in Applytic.
      Update the application status to stop future reminders.
    </p>
  </div>
</body>
</html>"""


@tracer.capture_method
def send_followup_email(email: str, html: str, count: int):
    subject = f"Applytic - {count} application{'s' if count > 1 else ''} due for follow-up"
    ses.send_email(
        Source=FROM_EMAIL,
        Destination={"ToAddresses": [email]},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Html": {"Data": html}},
        },
    )


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    logger.info("Follow-up check triggered")

    overdue = get_overdue_followups()
    logger.info(f"Found {len(overdue)} overdue follow-ups")

    if not overdue:
        return {"statusCode": 200, "body": json.dumps({"sent": 0, "skipped": 0})}

    # Group by userId
    by_user: dict[str, list] = {}
    for app in overdue:
        uid = app.get("userId")
        if uid:
            by_user.setdefault(uid, []).append(app)

    sent = 0
    skipped = 0

    for user_id, apps in by_user.items():
        try:
            email = get_user_email(user_id)
            if not email:
                logger.warning("No email found for user", extra={"user_id": user_id})
                skipped += 1
                continue

            html = build_followup_email(apps)
            send_followup_email(email, html, len(apps))
            sent += 1
            logger.info("Follow-up email sent", extra={"user_id": user_id, "app_count": len(apps)})

        except Exception:
            logger.exception("Failed to send follow-up for user", extra={"user_id": user_id})
            skipped += 1

    logger.info("Follow-up run complete", extra={"sent": sent, "skipped": skipped})
    return {"statusCode": 200, "body": json.dumps({"sent": sent, "skipped": skipped})}
