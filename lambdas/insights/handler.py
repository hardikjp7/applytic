"""
Insights Lambda — v1.2
Handles: GET /insights  POST /insights/chat
"""
import json
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import boto3
from boto3.dynamodb.conditions import Key
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import BaseModel, field_validator

from shared.middleware import resp, get_user_id, parse_body, now_iso

dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime")

TABLE_NAME = os.environ["TABLE_NAME"]
MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
CHAT_DAILY_LIMIT = int(os.environ.get("CHAT_DAILY_LIMIT", "20"))
table = dynamodb.Table(TABLE_NAME)

logger = Logger(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "applytic"))
tracer = Tracer(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "applytic"))


class ChatRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be empty")
        return v


@tracer.capture_method
def check_rate_limit(user_id: str) -> tuple[bool, int]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pk = f"RATELIMIT#{user_id}"
    sk = f"DATE#{today}"
    try:
        result = table.update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression="ADD #count :inc SET #ttl = :ttl",
            ExpressionAttributeNames={"#count": "count", "#ttl": "ttl"},
            ExpressionAttributeValues={
                ":inc": 1,
                ":ttl": int((datetime.now(timezone.utc) + timedelta(days=2)).timestamp()),
            },
            ReturnValues="UPDATED_NEW",
        )
        count = int(result["Attributes"]["count"])
        remaining = max(0, CHAT_DAILY_LIMIT - count)
        return count <= CHAT_DAILY_LIMIT, remaining
    except Exception:
        logger.exception("Rate limit check failed — allowing request")
        return True, CHAT_DAILY_LIMIT


@tracer.capture_method
def fetch_all_applications(user_id: str) -> list:
    result = table.query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq(f"USER#{user_id}"),
    )
    return [item for item in result["Items"] if item.get("entityType") == "APPLICATION"]


@tracer.capture_method
def compute_patterns(apps: list) -> dict:
    if not apps:
        return {"message": "No applications yet. Start logging to see insights."}

    total = len(apps)
    status_counts = defaultdict(int)
    by_source = defaultdict(lambda: {"total": 0, "responded": 0})
    by_company_size = defaultdict(lambda: {"total": 0, "responded": 0})
    by_resume_version = defaultdict(lambda: {"total": 0, "responded": 0})
    by_role_keyword = defaultdict(lambda: {"total": 0, "responded": 0})
    responded_statuses = {"screened", "interview", "offer"}

    for app in apps:
        status = app.get("status", "applied")
        status_counts[status] += 1
        responded = status in responded_statuses

        source = app.get("source", "unknown")
        by_source[source]["total"] += 1
        if responded:
            by_source[source]["responded"] += 1

        size = app.get("companySize", "unknown")
        by_company_size[size]["total"] += 1
        if responded:
            by_company_size[size]["responded"] += 1

        version = app.get("resumeVersion", "default")
        by_resume_version[version]["total"] += 1
        if responded:
            by_resume_version[version]["responded"] += 1

        role = app.get("role", "").lower()
        keyword = "senior" if "senior" in role else \
                  "lead" if "lead" in role else \
                  "junior" if "junior" in role else \
                  "staff" if "staff" in role else "mid"
        by_role_keyword[keyword]["total"] += 1
        if responded:
            by_role_keyword[keyword]["responded"] += 1

    def response_rate(d):
        return round(d["responded"] / d["total"] * 100, 1) if d["total"] > 0 else 0

    best_source = max(by_source.items(), key=lambda x: response_rate(x[1]), default=None)
    best_resume = max(by_resume_version.items(), key=lambda x: response_rate(x[1]), default=None)
    best_size = max(by_company_size.items(), key=lambda x: response_rate(x[1]), default=None)

    now = datetime.now(timezone.utc)
    weekly_counts = defaultdict(int)
    for app in apps:
        try:
            date_str = app.get("dateApplied", "")
            if len(date_str) == 10:
                applied = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            else:
                applied = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if applied.tzinfo is None:
                    applied = applied.replace(tzinfo=timezone.utc)
            weeks_ago = (now - applied).days // 7
            if weeks_ago < 4:
                weekly_counts[weeks_ago] += 1
        except (ValueError, AttributeError):
            pass

    return {
        "summary": {
            "total": total,
            "byStatus": dict(status_counts),
            "responseRate": round(
                sum(1 for a in apps if a.get("status") in responded_statuses) / total * 100, 1
            ),
            "offerRate": round(status_counts["offer"] / total * 100, 1),
        },
        "breakdowns": {
            "bySource": {k: {"total": v["total"], "responseRate": response_rate(v)} for k, v in by_source.items()},
            "byCompanySize": {k: {"total": v["total"], "responseRate": response_rate(v)} for k, v in by_company_size.items()},
            "byResumeVersion": {k: {"total": v["total"], "responseRate": response_rate(v)} for k, v in by_resume_version.items()},
            "byRoleLevel": {k: {"total": v["total"], "responseRate": response_rate(v)} for k, v in by_role_keyword.items()},
        },
        "highlights": {
            "bestSource": {"name": best_source[0], "responseRate": response_rate(best_source[1])} if best_source else None,
            "bestResumeVersion": {"name": best_resume[0], "responseRate": response_rate(best_resume[1])} if best_resume else None,
            "bestCompanySize": {"name": best_size[0], "responseRate": response_rate(best_size[1])} if best_size else None,
        },
        "velocity": {f"week_{i}_ago": weekly_counts.get(i, 0) for i in range(4)},
    }


def build_context_for_llm(apps: list, patterns: dict) -> str:
    recent = sorted(apps, key=lambda x: x.get("createdAt", ""), reverse=True)[:20]
    lines = [
        f"Total applications: {patterns['summary']['total']}",
        f"Overall response rate: {patterns['summary']['responseRate']}%",
        f"Offer rate: {patterns['summary']['offerRate']}%",
        f"Status breakdown: {patterns['summary']['byStatus']}",
        "",
        "Response rates by source channel:",
    ]
    for source, data in patterns["breakdowns"]["bySource"].items():
        lines.append(f"  {source}: {data['responseRate']}% ({data['total']} apps)")
    lines.append("\nResponse rates by resume version:")
    for version, data in patterns["breakdowns"]["byResumeVersion"].items():
        lines.append(f"  {version}: {data['responseRate']}% ({data['total']} apps)")
    lines.append("\nResponse rates by company size:")
    for size, data in patterns["breakdowns"]["byCompanySize"].items():
        lines.append(f"  {size}: {data['responseRate']}% ({data['total']} apps)")
    lines.append("\nRecent applications (last 20):")
    for app in recent:
        lines.append(
            f"  {app.get('company')} | {app.get('role')} | {app.get('status')} | "
            f"source={app.get('source')} | resume={app.get('resumeVersion')}"
        )
    return "\n".join(lines)


@tracer.capture_method
def chat_with_coach(user_message: str, context: str) -> str:
    system_prompt = """You are a pragmatic, data-driven job search coach.
Give specific, actionable advice based on what the data actually shows.
Be direct and honest. Reference specific numbers and patterns.
Keep responses under 250 words unless asked for more detail."""

    user_prompt = f"Here is my job search data:\n\n{context}\n\nMy question: {user_message}"

    if "anthropic" in MODEL_ID:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
    else:
        body = {
            "messages": [{"role": "user", "content": [{"text": system_prompt + "\n\n" + user_prompt}]}],
            "inferenceConfig": {"maxTokens": 1024},
        }

    response = bedrock.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    result = json.loads(response["body"].read())
    if "anthropic" in MODEL_ID:
        return result["content"][0]["text"]
    else:
        return result["output"]["message"]["content"][0]["text"]


@logger.inject_lambda_context(correlation_id_path="requestContext.requestId")
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    method = event.get("httpMethod", "")
    path = event.get("path", "")

    body, parse_error = parse_body(event)
    if parse_error:
        return parse_error

    try:
        user_id = get_user_id(event)
    except (KeyError, TypeError):
        return resp(401, {"error": "Unauthorized"}, event)

    try:
        apps = fetch_all_applications(user_id)
        patterns = compute_patterns(apps)

        if method == "GET" and path.endswith("/insights"):
            return resp(200, {"patterns": patterns, "applicationCount": len(apps)}, event)

        if method == "POST" and path.endswith("/chat"):
            try:
                req = ChatRequest(**body)
            except Exception as e:
                return resp(400, {"error": f"Validation error: {e}"}, event)

            if len(apps) < 3:
                return resp(200, {
                    "reply": "Log at least 3 applications first so I have enough data to give you meaningful advice.",
                    "dataInsufficient": True,
                }, event)

            allowed, remaining = check_rate_limit(user_id)
            if not allowed:
                return resp(429, {
                    "error": "Daily chat limit reached. You can send up to 20 messages per day.",
                    "rateLimited": True,
                }, event)

            context_str = build_context_for_llm(apps, patterns)
            reply = chat_with_coach(req.message, context_str)
            logger.info("Chat response sent", extra={"remaining_chats": remaining})
            return resp(200, {"reply": reply, "patterns": patterns, "remainingChats": remaining}, event)

        return resp(404, {"error": "Route not found"}, event)

    except Exception:
        logger.exception("Unhandled error in insights handler")
        return resp(500, {"error": "Internal server error"}, event)
