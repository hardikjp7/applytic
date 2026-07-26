"""
Tests for v3.0 Enhanced AI Coach Context additions to Insights Lambda.
Covers: fetch_recent_notes_for_app, fetch_interview_prep_for_app,
        fetch_active_alerts, build_coach_enrichment, build_context_for_llm
        (with enrichment), and that lambda_handler wires enrichment in
        for /chat but not /insights.
Run: python -m pytest tests/test_insights_v30.py -v
"""
import sys
import os
import json
import types
import importlib.util
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

# ── Stubs (same pattern as test_insights.py / test_insights_v21.py) ──────────

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
_spec = importlib.util.spec_from_file_location('insights_handler_v30', _handler_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['insights_handler_v30'] = _mod
_spec.loader.exec_module(_mod)

fetch_recent_notes_for_app = _mod.fetch_recent_notes_for_app
fetch_interview_prep_for_app = _mod.fetch_interview_prep_for_app
fetch_active_alerts = _mod.fetch_active_alerts
build_coach_enrichment = _mod.build_coach_enrichment
build_context_for_llm = _mod.build_context_for_llm
compute_patterns = _mod.compute_patterns
lambda_handler = _mod.lambda_handler
NOTES_PER_APP_LIMIT = _mod.NOTES_PER_APP_LIMIT
MAX_INTERVIEW_APPS_FOR_CONTEXT = _mod.MAX_INTERVIEW_APPS_FOR_CONTEXT

# ── Helpers ───────────────────────────────────────────────────────────────────

USER_ID = "test-user-v30"


def make_app(app_id: str, status: str, company="Co", role="Eng", source="linkedin",
             resume_version="v1", days_ago=5) -> dict:
    date_str = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    return {
        "appId": app_id,
        "userId": USER_ID,
        "company": company,
        "role": role,
        "status": status,
        "source": source,
        "resumeVersion": resume_version,
        "companySize": "startup",
        "dateApplied": date_str,
        "createdAt": date_str + "T00:00:00+00:00",
        "updatedAt": date_str + "T00:00:00+00:00",
        "entityType": "APPLICATION",
    }


def make_note(app_id: str, content: str, note_id="n1"):
    ts = "2024-01-10T10:00:00+00:00"
    return {
        "PK": f"APP#{app_id}",
        "SK": f"NOTE#{ts}#{note_id}",
        "noteId": note_id,
        "appId": app_id,
        "content": content,
        "createdAt": ts,
        "entityType": "NOTE",
    }


def make_prep_item(app_id: str, questions=None):
    if questions is None:
        questions = [
            {"id": "q1", "text": "Question 1?", "practiced": True, "answer": "My answer"},
            {"id": "q2", "text": "Question 2?", "practiced": False, "answer": ""},
        ]
    return {
        "PK": f"APP#{app_id}",
        "SK": "PREP#v1",
        "appId": app_id,
        "questions": questions,
        "generatedAt": "2024-01-09T10:00:00+00:00",
        "entityType": "INTERVIEW_PREP",
    }


def make_alert_item(message: str, dismissed=False, alert_id="a1"):
    return {
        "PK": f"USER#{USER_ID}",
        "SK": f"ALERT#2024-01-10T10:00:00+00:00#{alert_id}",
        "alertId": alert_id,
        "userId": USER_ID,
        "message": message,
        "dismissed": dismissed,
        "createdAt": "2024-01-10T10:00:00+00:00",
        "entityType": "ALERT",
    }


def make_event(method="GET", path="/insights", body=None):
    return {
        "httpMethod": method,
        "path": path,
        "pathParameters": {},
        "body": json.dumps(body) if body else None,
        "requestContext": {
            "authorizer": {"claims": {"sub": USER_ID, "email": "test@example.com"}}
        },
    }


# ── Tests: fetch_recent_notes_for_app ─────────────────────────────────────────

class TestFetchRecentNotesForApp:

    def test_returns_notes_from_table(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [make_note("app-1", "Great call with recruiter")]}
        with patch("insights_handler_v30.table", mock_table):
            notes = fetch_recent_notes_for_app("app-1")
        assert len(notes) == 1
        assert notes[0]["content"] == "Great call with recruiter"

    def test_returns_empty_list_when_no_notes(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        with patch("insights_handler_v30.table", mock_table):
            notes = fetch_recent_notes_for_app("app-1")
        assert notes == []

    def test_uses_limit_and_newest_first(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        with patch("insights_handler_v30.table", mock_table):
            fetch_recent_notes_for_app("app-1", limit=5)
        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["Limit"] == 5
        assert call_kwargs["ScanIndexForward"] is False

    def test_default_limit_matches_constant(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        with patch("insights_handler_v30.table", mock_table):
            fetch_recent_notes_for_app("app-1")
        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["Limit"] == NOTES_PER_APP_LIMIT


# ── Tests: fetch_interview_prep_for_app ───────────────────────────────────────

class TestFetchInterviewPrepForApp:

    def test_returns_questions_when_prep_exists(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": make_prep_item("app-1")}
        with patch("insights_handler_v30.table", mock_table):
            questions = fetch_interview_prep_for_app("app-1")
        assert len(questions) == 2

    def test_returns_empty_list_when_no_prep(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        with patch("insights_handler_v30.table", mock_table):
            questions = fetch_interview_prep_for_app("app-1")
        assert questions == []

    def test_queries_correct_key(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        with patch("insights_handler_v30.table", mock_table):
            fetch_interview_prep_for_app("app-1")
        call_kwargs = mock_table.get_item.call_args[1]
        assert call_kwargs["Key"]["PK"] == "APP#app-1"
        assert call_kwargs["Key"]["SK"] == "PREP#v1"


# ── Tests: fetch_active_alerts ─────────────────────────────────────────────────

class TestFetchActiveAlerts:

    def test_returns_undismissed_alert_messages(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                make_alert_item("Resume X has 0% response rate", dismissed=False),
                make_alert_item("Dismissed alert", dismissed=True, alert_id="a2"),
            ]
        }
        with patch("insights_handler_v30.table", mock_table):
            alerts = fetch_active_alerts(USER_ID)
        assert alerts == ["Resume X has 0% response rate"]

    def test_returns_empty_list_when_no_alerts(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        with patch("insights_handler_v30.table", mock_table):
            alerts = fetch_active_alerts(USER_ID)
        assert alerts == []

    def test_skips_alerts_with_empty_message(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [{"alertId": "a1", "dismissed": False, "message": ""}]
        }
        with patch("insights_handler_v30.table", mock_table):
            alerts = fetch_active_alerts(USER_ID)
        assert alerts == []


# ── Tests: build_coach_enrichment ─────────────────────────────────────────────

class TestBuildCoachEnrichment:

    def test_only_processes_interview_status_apps(self):
        apps = [
            make_app("app-1", "interview"),
            make_app("app-2", "applied"),
            make_app("app-3", "rejected"),
        ]
        with patch("insights_handler_v30.fetch_recent_notes_for_app", return_value=[make_note("app-1", "note")]), \
             patch("insights_handler_v30.fetch_interview_prep_for_app", return_value=[]), \
             patch("insights_handler_v30.fetch_active_alerts", return_value=[]):
            enrichment = build_coach_enrichment(USER_ID, apps)
        assert "app-1" in enrichment["interviewNotes"]
        assert "app-2" not in enrichment["interviewNotes"]
        assert "app-3" not in enrichment["interviewNotes"]

    def test_empty_apps_returns_empty_enrichment(self):
        with patch("insights_handler_v30.fetch_active_alerts", return_value=[]):
            enrichment = build_coach_enrichment(USER_ID, [])
        assert enrichment["interviewNotes"] == {}
        assert enrichment["interviewPrep"] == {}

    def test_includes_alerts_regardless_of_interview_apps(self):
        apps = [make_app("app-1", "applied")]
        with patch("insights_handler_v30.fetch_active_alerts", return_value=["Some alert"]):
            enrichment = build_coach_enrichment(USER_ID, apps)
        assert enrichment["alerts"] == ["Some alert"]

    def test_caps_at_max_interview_apps_for_context(self):
        apps = [make_app(f"app-{i}", "interview") for i in range(MAX_INTERVIEW_APPS_FOR_CONTEXT + 5)]
        with patch("insights_handler_v30.fetch_recent_notes_for_app", return_value=[]), \
             patch("insights_handler_v30.fetch_interview_prep_for_app", return_value=[{"id": "q1", "text": "Q?", "practiced": False, "answer": ""}]), \
             patch("insights_handler_v30.fetch_active_alerts", return_value=[]):
            enrichment = build_coach_enrichment(USER_ID, apps)
        assert len(enrichment["interviewPrep"]) <= MAX_INTERVIEW_APPS_FOR_CONTEXT

    def test_skips_apps_with_no_app_id(self):
        apps = [{"status": "interview", "company": "Broken"}]  # no appId field
        with patch("insights_handler_v30.fetch_active_alerts", return_value=[]):
            enrichment = build_coach_enrichment(USER_ID, apps)
        assert enrichment["interviewNotes"] == {}
        assert enrichment["interviewPrep"] == {}

    def test_per_app_fetch_failure_does_not_raise(self):
        apps = [make_app("app-1", "interview")]
        with patch("insights_handler_v30.fetch_recent_notes_for_app", side_effect=Exception("DynamoDB error")), \
             patch("insights_handler_v30.fetch_interview_prep_for_app", side_effect=Exception("DynamoDB error")), \
             patch("insights_handler_v30.fetch_active_alerts", return_value=[]):
            # Should not raise
            enrichment = build_coach_enrichment(USER_ID, apps)
        assert enrichment["interviewNotes"] == {}
        assert enrichment["interviewPrep"] == {}

    def test_alerts_fetch_failure_does_not_raise(self):
        apps = [make_app("app-1", "applied")]
        with patch("insights_handler_v30.fetch_active_alerts", side_effect=Exception("DynamoDB error")):
            enrichment = build_coach_enrichment(USER_ID, apps)
        assert enrichment["alerts"] == []

    def test_app_with_no_notes_or_prep_omitted_from_dicts(self):
        apps = [make_app("app-1", "interview")]
        with patch("insights_handler_v30.fetch_recent_notes_for_app", return_value=[]), \
             patch("insights_handler_v30.fetch_interview_prep_for_app", return_value=[]), \
             patch("insights_handler_v30.fetch_active_alerts", return_value=[]):
            enrichment = build_coach_enrichment(USER_ID, apps)
        assert "app-1" not in enrichment["interviewNotes"]
        assert "app-1" not in enrichment["interviewPrep"]


# ── Tests: build_context_for_llm with enrichment ──────────────────────────────

class TestBuildContextForLlmEnrichment:

    def test_backward_compatible_without_enrichment_arg(self, sample_applications=None):
        apps = [make_app("app-1", "applied")]
        patterns = compute_patterns(apps)
        # Calling without enrichment at all should not raise and behave as before
        context = build_context_for_llm(apps, patterns)
        assert isinstance(context, str)
        assert "Total applications" in context

    def test_empty_enrichment_dict_produces_same_output_as_none(self):
        apps = [make_app("app-1", "applied")]
        patterns = compute_patterns(apps)
        context_none = build_context_for_llm(apps, patterns, None)
        context_empty = build_context_for_llm(apps, patterns, {})
        assert context_none == context_empty

    def test_includes_active_alerts_section(self):
        apps = [make_app("app-1", "applied")]
        patterns = compute_patterns(apps)
        enrichment = {"interviewNotes": {}, "interviewPrep": {}, "alerts": ["Resume v1 has 0% response rate"]}
        context = build_context_for_llm(apps, patterns, enrichment)
        assert "Active pattern alerts" in context
        assert "Resume v1 has 0% response rate" in context

    def test_no_alerts_section_when_alerts_empty(self):
        apps = [make_app("app-1", "applied")]
        patterns = compute_patterns(apps)
        enrichment = {"interviewNotes": {}, "interviewPrep": {}, "alerts": []}
        context = build_context_for_llm(apps, patterns, enrichment)
        assert "Active pattern alerts" not in context

    def test_includes_interview_context_section_when_notes_present(self):
        apps = [make_app("app-1", "interview", company="Anthropic", role="ML Engineer")]
        patterns = compute_patterns(apps)
        enrichment = {
            "interviewNotes": {"app-1": [make_note("app-1", "Recruiter said final round next week")]},
            "interviewPrep": {},
            "alerts": [],
        }
        context = build_context_for_llm(apps, patterns, enrichment)
        assert "Interview context" in context
        assert "Anthropic" in context
        assert "Recruiter said final round next week" in context

    def test_includes_interview_prep_practiced_count(self):
        apps = [make_app("app-1", "interview", company="Stripe", role="SWE")]
        patterns = compute_patterns(apps)
        questions = [
            {"id": "q1", "text": "Q1?", "practiced": True, "answer": "a"},
            {"id": "q2", "text": "Q2?", "practiced": True, "answer": "b"},
            {"id": "q3", "text": "Q3?", "practiced": False, "answer": ""},
        ]
        enrichment = {
            "interviewNotes": {},
            "interviewPrep": {"app-1": questions},
            "alerts": [],
        }
        context = build_context_for_llm(apps, patterns, enrichment)
        assert "2/3 questions practiced" in context

    def test_no_interview_context_section_when_no_interview_data(self):
        apps = [make_app("app-1", "applied")]
        patterns = compute_patterns(apps)
        enrichment = {"interviewNotes": {}, "interviewPrep": {}, "alerts": []}
        context = build_context_for_llm(apps, patterns, enrichment)
        assert "Interview context" not in context

    def test_context_still_includes_existing_sections(self):
        apps = [
            make_app("app-1", "offer", source="referral", resume_version="v3"),
            make_app("app-2", "rejected", source="linkedin", resume_version="v1"),
        ]
        patterns = compute_patterns(apps)
        enrichment = {"interviewNotes": {}, "interviewPrep": {}, "alerts": ["Some alert"]}
        context = build_context_for_llm(apps, patterns, enrichment)
        # Existing sections must still be present
        assert "Response rates by source channel" in context
        assert "Response rates by resume version" in context
        assert "Recent applications" in context

    def test_multiple_interview_apps_each_get_own_section(self):
        apps = [
            make_app("app-1", "interview", company="Stripe", role="SWE"),
            make_app("app-2", "interview", company="Notion", role="Backend"),
        ]
        patterns = compute_patterns(apps)
        enrichment = {
            "interviewNotes": {
                "app-1": [make_note("app-1", "Note for Stripe")],
                "app-2": [make_note("app-2", "Note for Notion")],
            },
            "interviewPrep": {},
            "alerts": [],
        }
        context = build_context_for_llm(apps, patterns, enrichment)
        assert "Stripe" in context
        assert "Notion" in context
        assert "Note for Stripe" in context
        assert "Note for Notion" in context


# ── Tests: lambda_handler wiring ──────────────────────────────────────────────

class TestLambdaHandlerEnrichmentWiring:

    def test_chat_route_calls_build_coach_enrichment(self):
        apps = [make_app(f"app-{i}", "applied") for i in range(5)]
        with patch("insights_handler_v30.fetch_all_applications", return_value=apps), \
             patch("insights_handler_v30.check_rate_limit", return_value=(True, 19)), \
             patch("insights_handler_v30.build_coach_enrichment", return_value={
                 "interviewNotes": {}, "interviewPrep": {}, "alerts": []
             }) as mock_enrich, \
             patch("insights_handler_v30.chat_with_coach", return_value="Some reply"):
            result = lambda_handler(make_event("POST", "/insights/chat", body={"message": "help"}), None)
        assert result["statusCode"] == 200
        mock_enrich.assert_called_once()

    def test_insights_get_route_does_not_call_enrichment(self):
        apps = [make_app("app-1", "applied")]
        with patch("insights_handler_v30.fetch_all_applications", return_value=apps), \
             patch("insights_handler_v30.build_coach_enrichment") as mock_enrich:
            result = lambda_handler(make_event("GET", "/insights"), None)
        assert result["statusCode"] == 200
        mock_enrich.assert_not_called()

    def test_chat_route_skips_enrichment_when_data_insufficient(self):
        apps = [make_app("app-1", "applied"), make_app("app-2", "applied")]  # only 2, below min of 3
        with patch("insights_handler_v30.fetch_all_applications", return_value=apps), \
             patch("insights_handler_v30.build_coach_enrichment") as mock_enrich:
            result = lambda_handler(make_event("POST", "/insights/chat", body={"message": "help"}), None)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body.get("dataInsufficient") is True
        mock_enrich.assert_not_called()

    def test_chat_route_skips_enrichment_when_rate_limited(self):
        apps = [make_app(f"app-{i}", "applied") for i in range(5)]
        with patch("insights_handler_v30.fetch_all_applications", return_value=apps), \
             patch("insights_handler_v30.check_rate_limit", return_value=(False, 0)), \
             patch("insights_handler_v30.build_coach_enrichment") as mock_enrich:
            result = lambda_handler(make_event("POST", "/insights/chat", body={"message": "help"}), None)
        assert result["statusCode"] == 429
        mock_enrich.assert_not_called()

    def test_enrichment_data_flows_into_context_builder(self):
        apps = [make_app(f"app-{i}", "applied") for i in range(5)]
        fake_enrichment = {"interviewNotes": {}, "interviewPrep": {}, "alerts": ["test alert"]}
        with patch("insights_handler_v30.fetch_all_applications", return_value=apps), \
             patch("insights_handler_v30.check_rate_limit", return_value=(True, 19)), \
             patch("insights_handler_v30.build_coach_enrichment", return_value=fake_enrichment), \
             patch("insights_handler_v30.build_context_for_llm", wraps=_mod.build_context_for_llm) as mock_build_context, \
             patch("insights_handler_v30.chat_with_coach", return_value="reply"):
            lambda_handler(make_event("POST", "/insights/chat", body={"message": "help"}), None)
        call_args = mock_build_context.call_args[0]
        assert call_args[2] == fake_enrichment
