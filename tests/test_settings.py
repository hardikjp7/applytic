"""
Unit tests for Settings Lambda - v2.0
Tests: get_settings, compute_streak, upsert_settings, lambda_handler
Run: python -m pytest tests/test_settings.py -v
"""
import sys
import os
import json
import types
import pytest
import importlib.util
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

# ── Stubs ─────────────────────────────────────────────────────────────────────

class _FakeLogger:
    def __init__(self, *a, **kw): pass
    def info(self, *a, **kw): pass
    def warning(self, *a, **kw): pass
    def error(self, *a, **kw): pass
    def exception(self, *a, **kw): pass
    def set_correlation_id(self, *a, **kw): pass
    def inject_lambda_context(self, fn=None, **kw):
        def decorator(f): return f
        if fn is not None:
            return fn
        return decorator

class _FakeTracer:
    def __init__(self, *a, **kw): pass
    def capture_method(self, fn): return fn
    def capture_lambda_handler(self, fn): return fn

if "aws_lambda_powertools" not in sys.modules:
    plt = types.ModuleType("aws_lambda_powertools")
    plt.Logger = _FakeLogger
    plt.Tracer = _FakeTracer
    plt_typing = types.ModuleType("aws_lambda_powertools.utilities.typing")
    plt_typing.LambdaContext = object
    sys.modules["aws_lambda_powertools"] = plt
    sys.modules["aws_lambda_powertools.utilities"] = types.ModuleType("aws_lambda_powertools.utilities")
    sys.modules["aws_lambda_powertools.utilities.typing"] = plt_typing

try:
    import pydantic
except ImportError:
    pydantic_mod = types.ModuleType("pydantic")
    class _BaseModel:
        def __init__(self, **kw):
            for k, v in kw.items(): setattr(self, k, v)
        def model_dump(self, exclude_none=False):
            return {k: v for k, v in self.__dict__.items() if not (exclude_none and v is None)}
    pydantic_mod.BaseModel = _BaseModel
    pydantic_mod.field_validator = lambda *a, **kw: (lambda fn: fn)
    sys.modules["pydantic"] = pydantic_mod

if "aws_xray_sdk" not in sys.modules:
    xray_mod = types.ModuleType("aws_xray_sdk")
    xray_core = types.ModuleType("aws_xray_sdk.core")
    xray_core.xray_recorder = MagicMock()
    sys.modules["aws_xray_sdk"] = xray_mod
    sys.modules["aws_xray_sdk.core"] = xray_core

if "shared" not in sys.modules:
    shared_pkg = types.ModuleType("shared")
    shared_mw = types.ModuleType("shared.middleware")

    def _resp(status, body, event=None):
        return {
            "statusCode": status,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps(body, default=str),
        }

    def _parse_body(event):
        raw = event.get("body")
        if not raw:
            return {}, None
        try:
            return json.loads(raw), None
        except (json.JSONDecodeError, TypeError):
            return {}, _resp(400, {"error": "Invalid JSON body"}, event)

    shared_mw.resp = _resp
    shared_mw.get_user_id = lambda event: event["requestContext"]["authorizer"]["claims"]["sub"]
    shared_mw.parse_body = _parse_body
    shared_mw.now_iso = lambda: "2024-01-15T10:00:00+00:00"
    sys.modules["shared"] = shared_pkg
    sys.modules["shared.middleware"] = shared_mw

# ── Load handler ──────────────────────────────────────────────────────────────

_handler_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'settings', 'handler.py')
)
_spec = importlib.util.spec_from_file_location('settings_handler', _handler_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['settings_handler'] = _mod
_spec.loader.exec_module(_mod)

get_settings = _mod.get_settings
compute_streak = _mod.compute_streak
upsert_settings = _mod.upsert_settings
lambda_handler = _mod.lambda_handler
DEFAULT_WEEKLY_GOAL = _mod.DEFAULT_WEEKLY_GOAL

# ── Helpers ───────────────────────────────────────────────────────────────────

USER_ID = "test-user-123"


def make_event(method="GET", path="/users/settings", body=None):
    return {
        "httpMethod": method,
        "path": path,
        "pathParameters": {},
        "body": json.dumps(body) if body else None,
        "requestContext": {
            "authorizer": {
                "claims": {"sub": USER_ID, "email": "test@example.com"}
            }
        },
    }


def make_app(app_id, date_applied):
    return {
        "appId": app_id,
        "userId": USER_ID,
        "company": "TestCo",
        "role": "Engineer",
        "status": "applied",
        "dateApplied": date_applied,
        "entityType": "APPLICATION",
    }


def date_weeks_ago(n: int) -> str:
    """Return a YYYY-MM-DD date n*7 days ago."""
    return (datetime.now(timezone.utc) - timedelta(days=n * 7)).strftime("%Y-%m-%d")


# ── Tests: get_settings ───────────────────────────────────────────────────────

class TestGetSettings:

    def test_returns_defaults_when_no_record(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        with patch("settings_handler.table", mock_table):
            result = get_settings(USER_ID)
        assert result["weeklyGoal"] == DEFAULT_WEEKLY_GOAL
        assert result["streakCount"] == 0
        assert result["streakLastUpdated"] is None
        assert result["exists"] is False

    def test_returns_stored_values(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "PK": f"USER#{USER_ID}",
                "SK": "SETTINGS",
                "weeklyGoal": 15,
                "streakCount": 3,
                "streakLastUpdated": "2024-01-14",
            }
        }
        with patch("settings_handler.table", mock_table):
            result = get_settings(USER_ID)
        assert result["weeklyGoal"] == 15
        assert result["streakCount"] == 3
        assert result["streakLastUpdated"] == "2024-01-14"
        assert result["exists"] is True

    def test_queries_correct_key(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        with patch("settings_handler.table", mock_table):
            get_settings(USER_ID)
        call_kwargs = mock_table.get_item.call_args[1]
        assert call_kwargs["Key"]["PK"] == f"USER#{USER_ID}"
        assert call_kwargs["Key"]["SK"] == "SETTINGS"

    def test_casts_weekly_goal_to_int(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "PK": f"USER#{USER_ID}", "SK": "SETTINGS",
                "weeklyGoal": "20",  # stored as string (DynamoDB can do this)
                "streakCount": "1",
            }
        }
        with patch("settings_handler.table", mock_table):
            result = get_settings(USER_ID)
        assert isinstance(result["weeklyGoal"], int)
        assert result["weeklyGoal"] == 20


# ── Tests: compute_streak ─────────────────────────────────────────────────────

class TestComputeStreak:

    def test_returns_zero_when_no_apps(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        with patch("settings_handler.table", mock_table):
            streak, _ = compute_streak(USER_ID, 10)
        assert streak == 0

    def test_streak_of_one_when_last_week_hits_goal(self):
        mock_table = MagicMock()
        # 12 apps applied last week (week 1 ago) - goal is 10
        apps = [make_app(f"app-{i}", date_weeks_ago(1)) for i in range(12)]
        mock_table.query.return_value = {"Items": apps}
        with patch("settings_handler.table", mock_table):
            streak, _ = compute_streak(USER_ID, 10)
        assert streak == 1

    def test_streak_of_two_when_two_consecutive_weeks_hit_goal(self):
        mock_table = MagicMock()
        apps = (
            [make_app(f"app-w1-{i}", date_weeks_ago(1)) for i in range(10)] +
            [make_app(f"app-w2-{i}", date_weeks_ago(2)) for i in range(10)]
        )
        mock_table.query.return_value = {"Items": apps}
        with patch("settings_handler.table", mock_table):
            streak, _ = compute_streak(USER_ID, 10)
        assert streak == 2

    def test_streak_breaks_on_missed_week(self):
        mock_table = MagicMock()
        # week 1: 10 apps (hits goal)
        # week 2: 3 apps (misses goal of 10)
        # week 3: 10 apps (would continue but blocked by week 2)
        apps = (
            [make_app(f"app-w1-{i}", date_weeks_ago(1)) for i in range(10)] +
            [make_app(f"app-w2-{i}", date_weeks_ago(2)) for i in range(3)] +
            [make_app(f"app-w3-{i}", date_weeks_ago(3)) for i in range(10)]
        )
        mock_table.query.return_value = {"Items": apps}
        with patch("settings_handler.table", mock_table):
            streak, _ = compute_streak(USER_ID, 10)
        # streak stops at week 1 because week 2 is a miss
        assert streak == 1

    def test_current_week_not_counted_in_streak(self):
        mock_table = MagicMock()
        # 20 apps this week (week 0) - should NOT count toward streak
        apps = [make_app(f"app-{i}", date_weeks_ago(0)) for i in range(20)]
        mock_table.query.return_value = {"Items": apps}
        with patch("settings_handler.table", mock_table):
            streak, _ = compute_streak(USER_ID, 10)
        assert streak == 0

    def test_streak_respects_custom_goal(self):
        mock_table = MagicMock()
        # 5 apps last week - hits goal of 5 but not 10
        apps = [make_app(f"app-{i}", date_weeks_ago(1)) for i in range(5)]
        mock_table.query.return_value = {"Items": apps}
        with patch("settings_handler.table", mock_table):
            streak_low_goal, _ = compute_streak(USER_ID, 5)
            streak_high_goal, _ = compute_streak(USER_ID, 10)
        assert streak_low_goal == 1
        assert streak_high_goal == 0

    def test_returns_today_as_last_updated(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        with patch("settings_handler.table", mock_table):
            _, last_updated = compute_streak(USER_ID, 10)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert last_updated == today

    def test_ignores_apps_older_than_8_weeks(self):
        mock_table = MagicMock()
        # Apps 9 weeks ago - should not affect streak
        apps = [make_app(f"app-{i}", date_weeks_ago(9)) for i in range(20)]
        mock_table.query.return_value = {"Items": apps}
        with patch("settings_handler.table", mock_table):
            streak, _ = compute_streak(USER_ID, 10)
        assert streak == 0


# ── Tests: upsert_settings ────────────────────────────────────────────────────

class TestUpsertSettings:

    def test_put_item_called_on_first_write(self):
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        with patch("settings_handler.table", mock_table):
            upsert_settings(USER_ID, 10, 2, "2024-01-14")
        mock_table.put_item.assert_called_once()

    def test_update_item_called_when_record_exists(self):
        from botocore.exceptions import ClientError
        mock_table = MagicMock()
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "exists"}},
            "PutItem"
        )
        mock_table.update_item.return_value = {}
        with patch("settings_handler.table", mock_table):
            upsert_settings(USER_ID, 15, 3, "2024-01-14")
        mock_table.update_item.assert_called_once()

    def test_other_client_error_is_reraised(self):
        from botocore.exceptions import ClientError
        mock_table = MagicMock()
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "throttled"}},
            "PutItem"
        )
        with patch("settings_handler.table", mock_table):
            with pytest.raises(ClientError):
                upsert_settings(USER_ID, 10, 0, "2024-01-14")


# ── Tests: lambda_handler ─────────────────────────────────────────────────────

class TestSettingsLambdaHandler:

    def test_get_returns_200_with_defaults(self):
        with patch("settings_handler.get_settings", return_value={
            "weeklyGoal": 10, "streakCount": 0,
            "streakLastUpdated": None, "exists": False
        }), patch("settings_handler.compute_streak", return_value=(0, "2024-01-15")), \
           patch("settings_handler.upsert_settings"):
            result = lambda_handler(make_event("GET", "/users/settings"), None)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["settings"]["weeklyGoal"] == 10
        assert body["settings"]["streakCount"] == 0

    def test_get_returns_stored_settings(self):
        with patch("settings_handler.get_settings", return_value={
            "weeklyGoal": 15, "streakCount": 3,
            "streakLastUpdated": "2024-01-07", "exists": True
        }), patch("settings_handler.compute_streak", return_value=(3, "2024-01-15")), \
           patch("settings_handler.upsert_settings"):
            result = lambda_handler(make_event("GET", "/users/settings"), None)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["settings"]["weeklyGoal"] == 15
        assert body["settings"]["streakCount"] == 3

    def test_get_persists_updated_streak(self):
        with patch("settings_handler.get_settings", return_value={
            "weeklyGoal": 10, "streakCount": 1,  # old streak
            "streakLastUpdated": "2024-01-08", "exists": True
        }), patch("settings_handler.compute_streak", return_value=(2, "2024-01-15")), \
           patch("settings_handler.upsert_settings") as mock_upsert:
            lambda_handler(make_event("GET", "/users/settings"), None)
        mock_upsert.assert_called_once_with(USER_ID, 10, 2, "2024-01-15")

    def test_put_updates_weekly_goal(self):
        with patch("settings_handler.compute_streak", return_value=(1, "2024-01-15")), \
             patch("settings_handler.upsert_settings"):
            result = lambda_handler(make_event("PUT", "/users/settings", body={"weeklyGoal": 20}), None)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["settings"]["weeklyGoal"] == 20

    def test_put_recomputes_streak_with_new_goal(self):
        with patch("settings_handler.compute_streak", return_value=(2, "2024-01-15")) as mock_streak, \
             patch("settings_handler.upsert_settings"):
            lambda_handler(make_event("PUT", "/users/settings", body={"weeklyGoal": 5}), None)
        mock_streak.assert_called_once_with(USER_ID, 5)

    def test_put_returns_400_for_goal_zero(self):
        result = lambda_handler(make_event("PUT", "/users/settings", body={"weeklyGoal": 0}), None)
        assert result["statusCode"] == 400

    def test_put_returns_400_for_negative_goal(self):
        result = lambda_handler(make_event("PUT", "/users/settings", body={"weeklyGoal": -5}), None)
        assert result["statusCode"] == 400

    def test_put_returns_400_for_goal_over_500(self):
        result = lambda_handler(make_event("PUT", "/users/settings", body={"weeklyGoal": 501}), None)
        assert result["statusCode"] == 400

    def test_put_returns_400_for_missing_body(self):
        result = lambda_handler(make_event("PUT", "/users/settings", body={}), None)
        assert result["statusCode"] == 400

    def test_unknown_route_returns_404(self):
        result = lambda_handler(make_event("DELETE", "/users/settings"), None)
        assert result["statusCode"] == 404

    def test_missing_auth_returns_401(self):
        event = make_event("GET", "/users/settings")
        event["requestContext"] = {}
        result = lambda_handler(event, None)
        assert result["statusCode"] == 401

    def test_invalid_json_body_returns_400(self):
        event = make_event("PUT", "/users/settings")
        event["body"] = "not-json"
        result = lambda_handler(event, None)
        assert result["statusCode"] == 400

    def test_put_accepts_goal_of_500(self):
        with patch("settings_handler.compute_streak", return_value=(0, "2024-01-15")), \
             patch("settings_handler.upsert_settings"):
            result = lambda_handler(make_event("PUT", "/users/settings", body={"weeklyGoal": 500}), None)
        assert result["statusCode"] == 200

    def test_put_accepts_goal_of_one(self):
        with patch("settings_handler.compute_streak", return_value=(0, "2024-01-15")), \
             patch("settings_handler.upsert_settings"):
            result = lambda_handler(make_event("PUT", "/users/settings", body={"weeklyGoal": 1}), None)
        assert result["statusCode"] == 200
