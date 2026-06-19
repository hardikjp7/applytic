"""
Insights Lambda - v2.1
Handles: GET /insights  POST /insights/chat

v2.1 additions to compute_patterns():
  - funnel: applied -> screened -> interview -> offer counts + step conversion rates
  - responseRateTimeSeries: weekly response rate over last 8 ISO weeks
  - statusHistory: applications that moved INTO each status per ISO week (last 8 weeks)
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_iso_week_start(dt: datetime) -> datetime:
    """Return Monday 00:00:00 UTC of the ISO week containing dt."""
    monday = dt - timedelta(days=dt.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)


def _week_label(dt: datetime) -> str:
    """Return a short 'M/DD' label for the Monday of the week containing dt.
    Uses lstrip('0') instead of %-m/%-d which is Linux-only and breaks on Windows."""
    monday = _get_iso_week_start(dt)
    m = monday.strftime("%m").lstrip("0") or "0"
    d = monday.strftime("%d").lstrip("0") or "0"
    return f"{m}/{d}"


def _parse_date(date_str: str) -> datetime | None:
    """Parse dateApplied / createdAt into a timezone-aware datetime. Returns None on failure."""
    if not date_str:
        return None
    try:
        if len(date_str) == 10:
            return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return None


# ── v2.1: funnel ──────────────────────────────────────────────────────────────

def _compute_funnel(apps: list) -> dict:
    """
    Simple linear funnel: applied -> screened -> interview -> offer.
    Every application counts as 'applied'. Screened/interview/offer are
    counted by current status only - this gives a current-state snapshot,
    not a transition count, which is simpler and matches what users expect.

    Returns:
      stages: list of {stage, count, conversionFromPrev (%), conversionFromStart (%)}
    """
    total = len(apps)
    if total == 0:
        return {"stages": []}

    status_counts = defaultdict(int)
    for app in apps:
        status_counts[app.get("status", "applied")] += 1

    # Applications that ever reached screened or beyond
    screened_plus = sum(
        status_counts[s] for s in ("screened", "interview", "offer")
    )
    interview_plus = sum(status_counts[s] for s in ("interview", "offer"))
    offer_count = status_counts["offer"]

    stages_raw = [
        ("Applied", total),
        ("Screened", screened_plus),
        ("Interview", interview_plus),
        ("Offer", offer_count),
    ]

    stages = []
    for i, (stage, count) in enumerate(stages_raw):
        prev_count = stages_raw[i - 1][1] if i > 0 else count
        conv_from_prev = round(count / prev_count * 100, 1) if prev_count > 0 else 0.0
        conv_from_start = round(count / total * 100, 1) if total > 0 else 0.0
        stages.append({
            "stage": stage,
            "count": count,
            "conversionFromPrev": conv_from_prev if i > 0 else 100.0,
            "conversionFromStart": conv_from_start,
        })

    return {"stages": stages}


# ── v2.1: response rate time series ──────────────────────────────────────────

def _compute_response_rate_time_series(apps: list) -> list:
    """
    Weekly response rate over the last 8 completed ISO weeks (current week excluded).

    A week's response rate = (apps applied that week that have since moved to
    screened/interview/offer) / (total apps applied that week) * 100.

    We use dateApplied to bucket apps into their week, then look at current
    status to determine if a response was received.

    Returns list of {week (Mon DD label), responseRate (float), total (int)},
    ordered oldest -> newest.  Weeks with 0 applications are included as 0%.
    """
    if not apps:
        return []

    responded_statuses = {"screened", "interview", "offer"}
    now = datetime.now(timezone.utc)
    current_week_start = _get_iso_week_start(now)

    # Build 8 week buckets: week_starts[0] = oldest week, [7] = last completed week
    week_starts = [current_week_start - timedelta(weeks=8 - i) for i in range(8)]

    # total and responded per week index
    totals: dict[int, int] = defaultdict(int)
    responded: dict[int, int] = defaultdict(int)

    for app in apps:
        dt = _parse_date(app.get("dateApplied", ""))
        if dt is None:
            continue
        # find which bucket
        for i, ws in enumerate(week_starts):
            ws_end = ws + timedelta(weeks=1)
            if ws <= dt < ws_end:
                totals[i] += 1
                if app.get("status") in responded_statuses:
                    responded[i] += 1
                break

    result = []
    for i, ws in enumerate(week_starts):
        t = totals[i]
        r = responded[i]
        rate = round(r / t * 100, 1) if t > 0 else 0.0
        result.append({
            "week": _week_label(ws),
            "responseRate": rate,
            "total": t,
        })

    return result


# ── v2.1: status history ──────────────────────────────────────────────────────

def _compute_status_history(apps: list) -> list:
    """
    For each of the last 8 completed ISO weeks, count how many applications
    are currently in each status (applied, screened, interview, offer, rejected).

    We bucket by dateApplied for simplicity - this gives a picture of "what
    happened to apps added each week", which is intuitive for a job tracker.

    Returns list of {week, applied, screened, interview, offer, rejected},
    ordered oldest -> newest.
    """
    if not apps:
        return []

    now = datetime.now(timezone.utc)
    current_week_start = _get_iso_week_start(now)
    week_starts = [current_week_start - timedelta(weeks=8 - i) for i in range(8)]

    TRACKED_STATUSES = ["applied", "screened", "interview", "offer", "rejected"]

    # counts[week_index][status] = int
    counts: dict[int, dict[str, int]] = {i: defaultdict(int) for i in range(8)}

    for app in apps:
        dt = _parse_date(app.get("dateApplied", ""))
        if dt is None:
            continue
        status = app.get("status", "applied")
        for i, ws in enumerate(week_starts):
            ws_end = ws + timedelta(weeks=1)
            if ws <= dt < ws_end:
                if status in TRACKED_STATUSES:
                    counts[i][status] += 1
                break

    result = []
    for i, ws in enumerate(week_starts):
        entry: dict = {"week": _week_label(ws)}
        for s in TRACKED_STATUSES:
            entry[s] = counts[i][s]
        result.append(entry)

    return result


# ── Rate limiting ─────────────────────────────────────────────────────────────

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
        logger.exception("Rate limit check failed - allowing request")
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
        # v2.1 additions
        "funnel": _compute_funnel(apps),
        "responseRateTimeSeries": _compute_response_rate_time_series(apps),
        "statusHistory": _compute_status_history(apps),
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
