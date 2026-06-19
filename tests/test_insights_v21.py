"""
Tests for v2.1 analytics additions to Insights Lambda.
Covers: _compute_funnel, _compute_response_rate_time_series, _compute_status_history,
        and that compute_patterns includes all three new keys.
Run: python -m pytest tests/test_insights_v21.py -v
"""
import sys
import os
import json
import types
import importlib.util
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta

# ── Stubs (same pattern as test_insights.py) ──────────────────────────────────

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
    shared_mw.get_user_email = lambda event: event["requestContext"]["authorizer"]["claims"].get("email", "")
    shared_mw.parse_body = _parse_body
    shared_mw.now_iso = lambda: "2024-01-01T00:00:00+00:00"
    shared_mw.with_middleware = lambda fn: fn
    sys.modules["shared"] = shared_pkg
    sys.modules["shared.middleware"] = shared_mw

# ── Load handler under a unique module name ───────────────────────────────────

_handler_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'insights', 'handler.py')
)
_spec = importlib.util.spec_from_file_location('insights_handler_v21', _handler_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['insights_handler_v21'] = _mod
_spec.loader.exec_module(_mod)

_compute_funnel = _mod._compute_funnel
_compute_response_rate_time_series = _mod._compute_response_rate_time_series
_compute_status_history = _mod._compute_status_history
compute_patterns = _mod.compute_patterns

# ── Helpers ───────────────────────────────────────────────────────────────────

def days_ago(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).strftime("%Y-%m-%d")

def weeks_ago(n: int) -> str:
    """Return a dateApplied string that falls n complete ISO weeks ago."""
    now = datetime.now(timezone.utc)
    # Monday of current week
    monday = now - timedelta(days=now.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    target = monday - timedelta(weeks=n)
    # Use Wednesday of that week to safely land in the middle
    return (target + timedelta(days=2)).strftime("%Y-%m-%d")

def make_app(app_id: str, status: str, date_applied: str, source: str = "linkedin") -> dict:
    return {
        "appId": app_id,
        "userId": "test-user",
        "company": "Co",
        "role": "Eng",
        "status": status,
        "source": source,
        "resumeVersion": "v1",
        "companySize": "startup",
        "dateApplied": date_applied,
        "createdAt": date_applied + "T00:00:00+00:00",
        "updatedAt": date_applied + "T00:00:00+00:00",
        "entityType": "APPLICATION",
    }


# ── _compute_funnel ───────────────────────────────────────────────────────────

class TestComputeFunnel:

    def test_empty_apps_returns_empty_stages(self):
        result = _compute_funnel([])
        assert result == {"stages": []}

    def test_all_applied_gives_100_pct_applied_zero_rest(self):
        apps = [make_app(f"a{i}", "applied", days_ago(i + 1)) for i in range(5)]
        result = _compute_funnel(apps)
        stages = {s["stage"]: s for s in result["stages"]}
        assert stages["Applied"]["count"] == 5
        assert stages["Applied"]["conversionFromPrev"] == 100.0
        assert stages["Screened"]["count"] == 0
        assert stages["Interview"]["count"] == 0
        assert stages["Offer"]["count"] == 0

    def test_funnel_counts_are_cumulative(self):
        # 4 applied, 3 screened, 2 interview, 1 offer
        apps = [
            make_app("a1", "applied",   days_ago(10)),
            make_app("a2", "screened",  days_ago(9)),
            make_app("a3", "screened",  days_ago(8)),
            make_app("a4", "interview", days_ago(7)),
            make_app("a5", "interview", days_ago(6)),
            make_app("a6", "offer",     days_ago(5)),
            make_app("a7", "rejected",  days_ago(4)),
        ]
        result = _compute_funnel(apps)
        stages = {s["stage"]: s for s in result["stages"]}
        assert stages["Applied"]["count"] == 7
        # screened_plus = screened(2) + interview(2) + offer(1) = 5
        assert stages["Screened"]["count"] == 5
        assert stages["Interview"]["count"] == 3
        assert stages["Offer"]["count"] == 1

    def test_conversion_from_start_is_percentage_of_total(self):
        apps = [
            make_app("a1", "applied",  days_ago(5)),
            make_app("a2", "applied",  days_ago(4)),
            make_app("a3", "screened", days_ago(3)),
            make_app("a4", "offer",    days_ago(2)),
        ]
        result = _compute_funnel(apps)
        stages = {s["stage"]: s for s in result["stages"]}
        # 4 total, 2 screened_plus (screened + offer)
        assert stages["Screened"]["conversionFromStart"] == round(2 / 4 * 100, 1)
        assert stages["Offer"]["conversionFromStart"] == round(1 / 4 * 100, 1)

    def test_four_stages_always_present(self):
        apps = [make_app("a1", "applied", days_ago(1))]
        result = _compute_funnel(apps)
        assert len(result["stages"]) == 4
        names = [s["stage"] for s in result["stages"]]
        assert names == ["Applied", "Screened", "Interview", "Offer"]

    def test_conversion_from_prev_is_relative_to_previous_stage(self):
        apps = [
            make_app("a1", "screened",  days_ago(5)),
            make_app("a2", "screened",  days_ago(4)),
            make_app("a3", "interview", days_ago(3)),
        ]
        result = _compute_funnel(apps)
        stages = {s["stage"]: s for s in result["stages"]}
        # screened_plus = 3, interview_plus = 1
        # conv interview from screened = 1/3 * 100
        assert stages["Interview"]["conversionFromPrev"] == round(1 / 3 * 100, 1)

    def test_all_offers_gives_100_pct_all_stages(self):
        apps = [make_app(f"a{i}", "offer", days_ago(i + 1)) for i in range(3)]
        result = _compute_funnel(apps)
        stages = {s["stage"]: s for s in result["stages"]}
        assert stages["Applied"]["count"] == 3
        assert stages["Offer"]["count"] == 3
        assert stages["Offer"]["conversionFromStart"] == 100.0


# ── _compute_response_rate_time_series ────────────────────────────────────────

class TestComputeResponseRateTimeSeries:

    def test_empty_apps_returns_empty_list(self):
        assert _compute_response_rate_time_series([]) == []

    def test_returns_8_weeks(self):
        apps = [make_app("a1", "applied", days_ago(10))]
        result = _compute_response_rate_time_series(apps)
        assert len(result) == 8

    def test_each_entry_has_required_keys(self):
        apps = [make_app("a1", "applied", days_ago(10))]
        result = _compute_response_rate_time_series(apps)
        for entry in result:
            assert "week" in entry
            assert "responseRate" in entry
            assert "total" in entry

    def test_response_rate_is_zero_for_all_applied(self):
        apps = [
            make_app(f"a{i}", "applied", weeks_ago(i % 7 + 1))
            for i in range(7)
        ]
        result = _compute_response_rate_time_series(apps)
        for entry in result:
            assert entry["responseRate"] == 0.0

    def test_response_rate_100_when_all_responded(self):
        # 3 apps in week 1 ago, all screened/interview/offer
        apps = [
            make_app("a1", "screened",  weeks_ago(1)),
            make_app("a2", "interview", weeks_ago(1)),
            make_app("a3", "offer",     weeks_ago(1)),
        ]
        result = _compute_response_rate_time_series(apps)
        # week index 7 = last completed week (weeks_ago(1))
        last_week = result[7]
        assert last_week["total"] == 3
        assert last_week["responseRate"] == 100.0

    def test_weeks_with_no_apps_show_zero_total_and_zero_rate(self):
        # Only one app 2 weeks ago, all other weeks empty
        apps = [make_app("a1", "offer", weeks_ago(2))]
        result = _compute_response_rate_time_series(apps)
        empty_weeks = [e for e in result if e["total"] == 0]
        assert all(e["responseRate"] == 0.0 for e in empty_weeks)

    def test_current_week_is_excluded(self):
        # App applied today (current week) should not appear in any bucket
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        apps = [make_app("a1", "offer", today)]
        result = _compute_response_rate_time_series(apps)
        assert sum(e["total"] for e in result) == 0

    def test_response_rate_mixed(self):
        # 2 apps last week: 1 responded, 1 still applied -> 50%
        apps = [
            make_app("a1", "interview", weeks_ago(1)),
            make_app("a2", "applied",   weeks_ago(1)),
        ]
        result = _compute_response_rate_time_series(apps)
        last_week = result[7]
        assert last_week["total"] == 2
        assert last_week["responseRate"] == 50.0

    def test_results_ordered_oldest_to_newest(self):
        # All 8 results should have monotonically non-decreasing week labels
        # (we can't check exact dates, just that the list is stable and has 8 items)
        apps = [make_app("a1", "applied", weeks_ago(3))]
        result = _compute_response_rate_time_series(apps)
        assert len(result) == 8
        # The entry with total > 0 should be 5th from end (index 5 = 8-3=5)
        assert result[5]["total"] == 1


# ── _compute_status_history ───────────────────────────────────────────────────

class TestComputeStatusHistory:

    def test_empty_apps_returns_empty_list(self):
        assert _compute_status_history([]) == []

    def test_returns_8_weeks(self):
        apps = [make_app("a1", "applied", days_ago(10))]
        result = _compute_status_history(apps)
        assert len(result) == 8

    def test_each_entry_has_all_status_keys(self):
        apps = [make_app("a1", "applied", days_ago(10))]
        result = _compute_status_history(apps)
        for entry in result:
            assert "week" in entry
            for s in ("applied", "screened", "interview", "offer", "rejected"):
                assert s in entry

    def test_counts_app_in_correct_week_bucket(self):
        apps = [make_app("a1", "interview", weeks_ago(2))]
        result = _compute_status_history(apps)
        # weeks_ago(2) lands in bucket index 6 (8 - 2 = 6)
        assert result[6]["interview"] == 1
        assert result[6]["applied"] == 0

    def test_multiple_apps_same_week_same_status(self):
        apps = [
            make_app("a1", "rejected", weeks_ago(1)),
            make_app("a2", "rejected", weeks_ago(1)),
            make_app("a3", "rejected", weeks_ago(1)),
        ]
        result = _compute_status_history(apps)
        assert result[7]["rejected"] == 3

    def test_different_statuses_same_week_counted_separately(self):
        apps = [
            make_app("a1", "applied",   weeks_ago(3)),
            make_app("a2", "screened",  weeks_ago(3)),
            make_app("a3", "interview", weeks_ago(3)),
        ]
        result = _compute_status_history(apps)
        bucket = result[5]  # 8 - 3 = 5
        assert bucket["applied"] == 1
        assert bucket["screened"] == 1
        assert bucket["interview"] == 1

    def test_current_week_is_excluded(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        apps = [make_app("a1", "applied", today)]
        result = _compute_status_history(apps)
        total = sum(
            sum(e[s] for s in ("applied", "screened", "interview", "offer", "rejected"))
            for e in result
        )
        assert total == 0

    def test_withdrawn_status_not_in_output(self):
        apps = [make_app("a1", "withdrawn", weeks_ago(1))]
        result = _compute_status_history(apps)
        for entry in result:
            assert "withdrawn" not in entry


# ── compute_patterns (integration) ───────────────────────────────────────────

class TestComputePatternsV21Keys:

    def test_new_keys_present_in_output(self):
        apps = [make_app(f"a{i}", "applied", days_ago(i + 1)) for i in range(5)]
        result = compute_patterns(apps)
        assert "funnel" in result
        assert "responseRateTimeSeries" in result
        assert "statusHistory" in result

    def test_funnel_is_dict_with_stages(self):
        apps = [make_app("a1", "offer", days_ago(5))]
        result = compute_patterns(apps)
        assert isinstance(result["funnel"], dict)
        assert "stages" in result["funnel"]

    def test_response_rate_time_series_is_list_of_8(self):
        apps = [make_app("a1", "applied", days_ago(10))]
        result = compute_patterns(apps)
        assert isinstance(result["responseRateTimeSeries"], list)
        assert len(result["responseRateTimeSeries"]) == 8

    def test_status_history_is_list_of_8(self):
        apps = [make_app("a1", "applied", days_ago(10))]
        result = compute_patterns(apps)
        assert isinstance(result["statusHistory"], list)
        assert len(result["statusHistory"]) == 8

    def test_empty_apps_does_not_include_new_keys(self):
        # empty apps returns the early-exit message dict, no analytics keys
        result = compute_patterns([])
        assert "funnel" not in result
        assert "responseRateTimeSeries" not in result
        assert "statusHistory" not in result
