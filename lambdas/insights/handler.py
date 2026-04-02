"""
Insights Lambda
Handles: GET /insights (pattern analysis dashboard data)
         POST /insights/chat (AI coaching via Bedrock)
"""
import json
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime")

TABLE_NAME = os.environ["TABLE_NAME"]
MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
table = dynamodb.Table(TABLE_NAME)


# Helpers

def resp(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str),
    }

def get_user_id(event: dict) -> str:
    return event["requestContext"]["authorizer"]["claims"]["sub"]

def get_user_email(event: dict) -> str:
    return event["requestContext"]["authorizer"]["claims"].get("email", "")


# Fetch all applications for a user

def fetch_all_applications(user_id: str) -> list:
    result = table.query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq(f"USER#{user_id}"),
    )
    return [item for item in result["Items"] if item.get("entityType") == "APPLICATION"]


# Pattern analysis

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

        # by source channel
        source = app.get("source", "unknown")
        by_source[source]["total"] += 1
        if responded:
            by_source[source]["responded"] += 1

        # by company size
        size = app.get("companySize", "unknown")
        by_company_size[size]["total"] += 1
        if responded:
            by_company_size[size]["responded"] += 1

        # by resume version
        version = app.get("resumeVersion", "default")
        by_resume_version[version]["total"] += 1
        if responded:
            by_resume_version[version]["responded"] += 1

        # by role keyword (senior/junior/lead/etc from title)
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

    # find best performing buckets
    best_source = max(by_source.items(), key=lambda x: response_rate(x[1]), default=None)
    best_resume = max(by_resume_version.items(), key=lambda x: response_rate(x[1]), default=None)
    best_size = max(by_company_size.items(), key=lambda x: response_rate(x[1]), default=None)

    # weekly application velocity (last 4 weeks)
    now = datetime.now(timezone.utc)
    weekly_counts = defaultdict(int)
    for app in apps:
        try:
            applied = datetime.fromisoformat(app.get("dateApplied", "").replace("Z", "+00:00"))
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
            "bySource": {
                k: {"total": v["total"], "responseRate": response_rate(v)}
                for k, v in by_source.items()
            },
            "byCompanySize": {
                k: {"total": v["total"], "responseRate": response_rate(v)}
                for k, v in by_company_size.items()
            },
            "byResumeVersion": {
                k: {"total": v["total"], "responseRate": response_rate(v)}
                for k, v in by_resume_version.items()
            },
            "byRoleLevel": {
                k: {"total": v["total"], "responseRate": response_rate(v)}
                for k, v in by_role_keyword.items()
            },
        },
        "highlights": {
            "bestSource": {"name": best_source[0], "responseRate": response_rate(best_source[1])} if best_source else None,
            "bestResumeVersion": {"name": best_resume[0], "responseRate": response_rate(best_resume[1])} if best_resume else None,
            "bestCompanySize": {"name": best_size[0], "responseRate": response_rate(best_size[1])} if best_size else None,
        },
        "velocity": {
            f"week_{i}_ago": weekly_counts.get(i, 0) for i in range(4)
        },
    }


# Build context summary for Bedrock

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


# Bedrock chat

def chat_with_coach(user_message: str, context: str) -> str:
    system_prompt = """You are a pragmatic, data-driven job search coach. 
You have access to the user's actual application history and pattern analysis data.
Give specific, actionable advice based on what the data actually shows.
Be direct and honest. Don't pad responses with generic platitudes.
Reference specific numbers and patterns from their data when making recommendations.
Keep responses under 250 words unless the user asks for something detailed."""

    user_prompt = f"""Here is my job search data:

{context}

My question: {user_message}"""

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }),
    )

    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


# Router

def lambda_handler(event: dict, context) -> dict:
    method = event.get("httpMethod", "")
    path = event.get("path", "")
    body = {}

    if event.get("body"):
        try:
            body = json.loads(event["body"])
        except json.JSONDecodeError:
            return resp(400, {"error": "Invalid JSON body"})

    try:
        user_id = get_user_id(event)
    except (KeyError, TypeError):
        return resp(401, {"error": "Unauthorized"})

    try:
        apps = fetch_all_applications(user_id)
        patterns = compute_patterns(apps)

        # GET /insights — return pattern dashboard data
        if method == "GET" and path.endswith("/insights"):
            return resp(200, {"patterns": patterns, "applicationCount": len(apps)})

        # POST /insights/chat — AI coaching
        if method == "POST" and path.endswith("/chat"):
            user_message = body.get("message", "").strip()
            if not user_message:
                return resp(400, {"error": "message is required"})

            if len(apps) < 3:
                return resp(200, {
                    "reply": "Log at least 3 applications first so I have enough data to give you meaningful advice.",
                    "dataInsufficient": True,
                })

            context_str = build_context_for_llm(apps, patterns)
            reply = chat_with_coach(user_message, context_str)
            return resp(200, {"reply": reply, "patterns": patterns})

        return resp(404, {"error": "Route not found"})

    except Exception as e:
        print(f"Unhandled error: {e}")
        return resp(500, {"error": "Internal server error"})
