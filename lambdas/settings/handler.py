"""
Settings Lambda - v2.0
Handles: GET /users/settings, PUT /users/settings

Fix: compute_streak was using a rolling 7-day window (days//7) which means
"last week" could span parts of two calendar weeks, giving wrong counts.
Now uses proper ISO week numbers so week_1 = last Mon-Sun, week_2 = the
Mon-Sun before that, etc.  This matches what the Dashboard progress bar
shows (current ISO week Mon-Sun).
"""
import os
import json
from datetime import datetime, timezone, timedelta

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import BaseModel, field_validator
from typing import Optional

from shared.middleware import resp, get_user_id, parse_body, now_iso

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ["TABLE_NAME"]
table = dynamodb.Table(TABLE_NAME)

logger = Logger(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "applytic"))
tracer = Tracer(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "applytic"))

DEFAULT_WEEKLY_GOAL = 10


class UpdateSettingsRequest(BaseModel):
    weeklyGoal: int

    @field_validator("weeklyGoal")
    @classmethod
    def goal_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("weeklyGoal must be at least 1")
        if v > 500:
            raise ValueError("weeklyGoal must be 500 or less")
        return v


@tracer.capture_method
def get_settings(user_id: str) -> dict:
    result = table.get_item(
        Key={"PK": f"USER#{user_id}", "SK": "SETTINGS"}
    )
    item = result.get("Item")
    if not item:
        return {
            "weeklyGoal": DEFAULT_WEEKLY_GOAL,
            "streakCount": 0,
            "streakLastUpdated": None,
            "exists": False,
        }
    return {
        "weeklyGoal": int(item.get("weeklyGoal", DEFAULT_WEEKLY_GOAL)),
        "streakCount": int(item.get("streakCount", 0)),
        "streakLastUpdated": item.get("streakLastUpdated"),
        "exists": True,
    }


def _get_iso_week_start(dt: datetime) -> datetime:
    """Return the Monday 00:00:00 UTC of the ISO week containing dt."""
    # weekday(): Mon=0 ... Sun=6
    monday = dt - timedelta(days=dt.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)


@tracer.capture_method
def compute_streak(user_id: str, weekly_goal: int) -> tuple[int, str]:
    """
    Compute streak using proper ISO week boundaries.

    week_0  = current week  (Mon 00:00 UTC .. now)   - excluded, may be incomplete
    week_1  = last week     (previous Mon .. Sun)
    week_2  = two weeks ago
    ...up to week_8

    A week counts toward the streak if applications >= weekly_goal.
    The streak breaks on the first week (going backward from week_1)
    that misses the goal.

    Returns (streak_count, today_str).
    """
    result = table.query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq(f"USER#{user_id}"),
    )
    apps = [i for i in result.get("Items", []) if i.get("entityType") == "APPLICATION"]

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")

    if not apps:
        return 0, today_str

    # Build week-start boundaries for the last 9 ISO weeks (0..8)
    current_week_start = _get_iso_week_start(now)
    week_starts = [current_week_start - timedelta(weeks=i) for i in range(9)]
    # week_starts[0] = start of this week
    # week_starts[1] = start of last week
    # week_starts[i+1] = end of week i (exclusive)

    # Count apps per ISO week index
    weekly_counts: dict[int, int] = {}
    for app in apps:
        date_str = app.get("dateApplied", "")
        try:
            if len(date_str) == 10:
                applied = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            else:
                applied = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if applied.tzinfo is None:
                    applied = applied.replace(tzinfo=timezone.utc)

            # Find which week bucket this app falls in
            for i in range(8):
                week_start = week_starts[i]       # Monday of week i
                week_end   = week_starts[i - 1] if i > 0 else now + timedelta(days=1)
                if week_start <= applied < week_end:
                    weekly_counts[i] = weekly_counts.get(i, 0) + 1
                    break
        except (ValueError, AttributeError):
            continue

    logger.info("Weekly counts", extra={"counts": weekly_counts, "goal": weekly_goal})

    # Walk backward from week_1 (skip week_0 - current incomplete week)
    streak = 0
    for week in range(1, 9):
        count = weekly_counts.get(week, 0)
        if count >= weekly_goal:
            streak += 1
        else:
            break

    return streak, today_str


@tracer.capture_method
def upsert_settings(user_id: str, weekly_goal: int, streak_count: int, streak_last_updated: str) -> dict:
    ts = now_iso()
    item = {
        "PK": f"USER#{user_id}",
        "SK": "SETTINGS",
        "userId": user_id,
        "weeklyGoal": weekly_goal,
        "streakCount": streak_count,
        "streakLastUpdated": streak_last_updated,
        "updatedAt": ts,
        "entityType": "USER_SETTINGS",
    }
    try:
        table.put_item(
            Item={**item, "createdAt": ts},
            ConditionExpression="attribute_not_exists(PK)",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            table.update_item(
                Key={"PK": f"USER#{user_id}", "SK": "SETTINGS"},
                UpdateExpression="SET weeklyGoal = :g, streakCount = :s, streakLastUpdated = :sl, updatedAt = :u",
                ExpressionAttributeValues={
                    ":g": weekly_goal,
                    ":s": streak_count,
                    ":sl": streak_last_updated,
                    ":u": ts,
                },
            )
        else:
            raise
    return item


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
        if method == "GET" and path.endswith("/settings"):
            settings = get_settings(user_id)
            streak, last_updated = compute_streak(user_id, settings["weeklyGoal"])

            if streak != settings["streakCount"] or not settings["exists"]:
                upsert_settings(user_id, settings["weeklyGoal"], streak, last_updated)

            return resp(200, {
                "settings": {
                    "weeklyGoal": settings["weeklyGoal"],
                    "streakCount": streak,
                    "streakLastUpdated": last_updated,
                }
            }, event)

        if method == "PUT" and path.endswith("/settings"):
            try:
                req = UpdateSettingsRequest(**body)
            except Exception as e:
                return resp(400, {"error": f"Validation error: {e}"}, event)

            streak, last_updated = compute_streak(user_id, req.weeklyGoal)
            upsert_settings(user_id, req.weeklyGoal, streak, last_updated)

            logger.info("Settings updated", extra={"user_id": user_id, "weekly_goal": req.weeklyGoal})
            return resp(200, {
                "settings": {
                    "weeklyGoal": req.weeklyGoal,
                    "streakCount": streak,
                    "streakLastUpdated": last_updated,
                }
            }, event)

        return resp(404, {"error": "Route not found"}, event)

    except Exception:
        logger.exception("Unhandled error in settings handler")
        return resp(500, {"error": "Internal server error"}, event)
