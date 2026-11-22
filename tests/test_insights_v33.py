import sys
import os
import types
import importlib.util
from unittest.mock import MagicMock

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
    import json
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
_spec = importlib.util.spec_from_file_location('insights_handler_v33', _handler_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['insights_handler_v33'] = _mod
_spec.loader.exec_module(_mod)

from datetime import datetime, timezone, timedelta

_effective_max_stage = _mod._effective_max_stage
_has_responded = _mod._has_responded
_is_direct_rejection = _mod._is_direct_rejection
_days_to_first_response = _mod._days_to_first_response
_compute_response_timing = _mod._compute_response_timing
_compute_direct_rejection_stats = _mod._compute_direct_rejection_stats
_compute_funnel = _mod._compute_funnel
_compute_response_rate_time_series = _mod._compute_response_rate_time_series
compute_patterns = _mod.compute_patterns
build_context_for_llm = _mod.build_context_for_llm


def weeks_ago(n: int) -> str:
    now = datetime.now(timezone.utc)
    monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return (monday - timedelta(weeks=n) + timedelta(days=2)).strftime("%Y-%m-%d")


def make_app(app_id, status="applied", max_stage=None, first_response_at=None,
             date_applied="2024-01-01", source="linkedin", resume_version="v1"):
    app = {
        "appId": app_id, "userId": "test-user", "company": "Co", "role": "Eng",
        "status": status, "source": source, "resumeVersion": resume_version,
        "companySize": "startup", "dateApplied": date_applied,
        "createdAt": date_applied + "T00:00:00+00:00",
        "updatedAt": date_applied + "T00:00:00+00:00",
        "entityType": "APPLICATION",
    }
    if max_stage is not None:
        app["maxStage"] = max_stage
    if first_response_at is not None:
        app["firstResponseAt"] = first_response_at
    return app


class TestStageHelpers:

    def test_uses_max_stage_when_present(self):
        assert _effective_max_stage(make_app("a", "rejected", max_stage="interview")) == "interview"

    def test_falls_back_to_current_status_when_missing(self):
        assert _effective_max_stage(make_app("a", "screened")) == "screened"

    def test_rejected_without_max_stage_is_stage_applied(self):
        assert _effective_max_stage(make_app("a", "rejected")) == "applied"

    def test_invalid_max_stage_falls_back(self):
        assert _effective_max_stage(make_app("a", "offer", max_stage="bogus")) == "offer"

    def test_has_responded_after_later_rejection(self):
        assert _has_responded(make_app("a", "rejected", max_stage="interview")) is True

    def test_applied_has_not_responded(self):
        assert _has_responded(make_app("a", "applied")) is False

    def test_direct_rejection_detection(self):
        assert _is_direct_rejection(make_app("a", "rejected", max_stage="applied")) is True
        assert _is_direct_rejection(make_app("a", "rejected", max_stage="screened")) is False
        assert _is_direct_rejection(make_app("a", "applied")) is False


class TestResponseRateUsesMaxStage:

    def test_rejected_after_interview_counts_as_responded(self):
        apps = [make_app("a1", "rejected", max_stage="interview"), make_app("a2", "applied")]
        assert compute_patterns(apps)["summary"]["responseRate"] == 50.0

    def test_source_breakdown_counts_it(self):
        apps = [make_app("a1", "rejected", max_stage="interview"), make_app("a2", "applied")]
        assert compute_patterns(apps)["breakdowns"]["bySource"]["linkedin"]["responseRate"] == 50.0

    def test_new_rate_never_below_old_status_based_rate(self):
        apps = [
            make_app("a1", "offer"),
            make_app("a2", "rejected", max_stage="screened"),
            make_app("a3", "rejected"),
            make_app("a4", "applied"),
            make_app("a5", "interview"),
        ]
        old = sum(1 for a in apps if a["status"] in {"screened", "interview", "offer"}) / len(apps) * 100
        assert compute_patterns(apps)["summary"]["responseRate"] >= round(old, 1)

    def test_time_series_counts_rejected_after_interview(self):
        apps = [
            make_app("a1", "rejected", max_stage="interview", date_applied=weeks_ago(1)),
            make_app("a2", "applied", date_applied=weeks_ago(1)),
        ]
        last_week = _compute_response_rate_time_series(apps)[7]
        assert last_week["total"] == 2
        assert last_week["responseRate"] == 50.0


class TestFunnelUsesMaxStage:

    def test_interview_then_rejected_stays_in_funnel(self):
        apps = [
            make_app("a1", "rejected", max_stage="interview"),
            make_app("a2", "applied"),
            make_app("a3", "offer", max_stage="offer"),
        ]
        stages = {s["stage"]: s for s in _compute_funnel(apps)["stages"]}
        assert stages["Applied"]["count"] == 3
        assert stages["Screened"]["count"] == 2
        assert stages["Interview"]["count"] == 2
        assert stages["Offer"]["count"] == 1

    def test_legacy_items_without_max_stage_behave_as_before(self):
        apps = [make_app("a1", "applied"), make_app("a2", "screened"), make_app("a3", "rejected")]
        stages = {s["stage"]: s for s in _compute_funnel(apps)["stages"]}
        assert stages["Screened"]["count"] == 1
        assert stages["Interview"]["count"] == 0


class TestResponseTiming:

    def test_days_to_first_response(self):
        app = make_app("a", "screened", first_response_at="2024-01-04T10:00:00+00:00")
        assert _days_to_first_response(app) == 3

    def test_none_when_no_first_response(self):
        assert _days_to_first_response(make_app("a", "applied")) is None

    def test_clamped_at_zero_when_backdated(self):
        app = make_app("a", "screened", date_applied="2024-01-10", first_response_at="2024-01-05T00:00:00+00:00")
        assert _days_to_first_response(app) == 0

    def test_empty_apps_gives_none_median(self):
        result = _compute_response_timing([])
        assert result["medianDaysToFirstResponse"] is None
        assert result["sampleSize"] == 0

    def test_overall_and_per_source_medians(self):
        apps = [
            make_app("a1", "screened", source="linkedin", first_response_at="2024-01-03T09:00:00+00:00"),   # 2
            make_app("a2", "screened", source="linkedin", first_response_at="2024-01-05T09:00:00+00:00"),   # 4
            make_app("a3", "screened", source="referral", first_response_at="2024-01-11T09:00:00+00:00"),   # 10
            make_app("a4", "applied"),  # no first response, excluded
        ]
        result = _compute_response_timing(apps)
        assert result["medianDaysToFirstResponse"] == 4
        assert result["sampleSize"] == 3
        assert result["bySource"]["linkedin"] == {"medianDays": 3.0, "count": 2}
        assert result["bySource"]["referral"] == {"medianDays": 10, "count": 1}

    def test_per_resume_version(self):
        apps = [make_app("a1", "screened", resume_version="v3", first_response_at="2024-01-03T09:00:00+00:00")]
        assert _compute_response_timing(apps)["byResumeVersion"]["v3"]["count"] == 1


class TestDirectRejectionStats:

    def test_counts_and_rate(self):
        apps = [
            make_app("a1", "rejected"),                           # direct
            make_app("a2", "rejected", max_stage="interview"),    # not direct
            make_app("a3", "applied"),
            make_app("a4", "applied"),
        ]
        assert _compute_direct_rejection_stats(apps) == {"count": 1, "rate": 25.0}

    def test_empty(self):
        assert _compute_direct_rejection_stats([]) == {"count": 0, "rate": 0.0}


class TestPatternsAndContext:

    def test_new_keys_present(self):
        result = compute_patterns([make_app("a1", "applied")])
        assert "responseTiming" in result
        assert "directRejections" in result

    def test_context_includes_timing_and_direct_rejections(self):
        apps = [
            make_app("a1", "interview", max_stage="interview", first_response_at="2024-01-04T09:00:00+00:00"),
            make_app("a2", "rejected"),
            make_app("a3", "applied"),
        ]
        context = build_context_for_llm(apps, compute_patterns(apps))
        assert "Median days from applying to first response: 3" in context
        assert "Direct rejections" in context

    def test_context_omits_sections_when_no_data(self):
        apps = [make_app("a1", "applied"), make_app("a2", "applied")]
        context = build_context_for_llm(apps, compute_patterns(apps))
        assert "Median days from applying" not in context
        assert "Direct rejections" not in context


import json
from unittest.mock import patch

sanitize_history = _mod.sanitize_history
_build_chat_turns = _mod._build_chat_turns
chat_with_coach = _mod.chat_with_coach
lambda_handler = _mod.lambda_handler


def _turn(role, text="x"):
    return {"role": role, "content": text}


class TestSanitizeHistory:

    def test_none_and_non_list_give_empty(self):
        assert sanitize_history(None) == []
        assert sanitize_history("hello") == []
        assert sanitize_history({"role": "user"}) == []

    def test_drops_invalid_turns(self):
        history = [
            "not a dict",
            {"role": "system", "content": "x"},
            {"role": "user", "content": 123},
            {"role": "user", "content": "   "},
            _turn("user", "real question"),
            _turn("assistant", "real answer"),
        ]
        assert sanitize_history(history) == [_turn("user", "real question"), _turn("assistant", "real answer")]

    def test_truncates_each_turn(self):
        result = sanitize_history([_turn("user", "a" * 5000), _turn("assistant", "b" * 5000)])
        assert all(len(t["content"]) == _mod.HISTORY_MAX_CHARS_PER_TURN for t in result)

    def test_keeps_only_last_six_turns(self):
        history = [_turn("user" if i % 2 == 0 else "assistant", f"m{i}") for i in range(10)]
        result = sanitize_history(history)
        assert len(result) == 6
        assert result[0]["content"] == "m4"
        assert result[-1]["content"] == "m9"

    def test_drops_leading_assistant_greeting(self):
        result = sanitize_history([_turn("assistant", "Hi!"), _turn("user", "q"), _turn("assistant", "a")])
        assert [t["role"] for t in result] == ["user", "assistant"]

    def test_drops_trailing_user_turn(self):
        # the client may include the new message; the server appends it itself
        result = sanitize_history([_turn("user", "q1"), _turn("assistant", "a1"), _turn("user", "new")])
        assert result == [_turn("user", "q1"), _turn("assistant", "a1")]

    def test_collapses_consecutive_same_role_keeping_latest(self):
        result = sanitize_history([_turn("user", "old"), _turn("user", "newer"), _turn("assistant", "a")])
        assert result == [_turn("user", "newer"), _turn("assistant", "a")]

    def test_only_assistant_turns_give_empty(self):
        assert sanitize_history([_turn("assistant", "a"), _turn("assistant", "b")]) == []

    def test_result_always_alternates(self):
        history = [_turn("assistant"), _turn("user"), _turn("user"), _turn("assistant"),
                   _turn("assistant"), _turn("user"), _turn("assistant"), _turn("user")]
        result = sanitize_history(history)
        for a, b in zip(result, result[1:]):
            assert a["role"] != b["role"]
        assert result[0]["role"] == "user" and result[-1]["role"] == "assistant"


class TestBuildChatTurns:

    def test_no_history_is_single_turn_with_context(self):
        turns = _build_chat_turns("why ghosted?", "CTX", [])
        assert len(turns) == 1
        assert "CTX" in turns[0]["content"] and "why ghosted?" in turns[0]["content"]

    def test_context_only_in_first_turn(self):
        history = [_turn("user", "first q"), _turn("assistant", "first a")]
        turns = _build_chat_turns("follow up", "CTX", history)
        assert [t["role"] for t in turns] == ["user", "assistant", "user"]
        assert "CTX" in turns[0]["content"] and "first q" in turns[0]["content"]
        assert turns[-1]["content"] == "follow up"
        assert "CTX" not in turns[-1]["content"]


def _mock_bedrock(anthropic=False):
    mb = MagicMock()
    body = MagicMock()
    if anthropic:
        body.read.return_value = json.dumps({"content": [{"text": "reply"}]}).encode()
    else:
        body.read.return_value = json.dumps({"output": {"message": {"content": [{"text": "reply"}]}}}).encode()
    mb.invoke_model.return_value = {"body": body}
    return mb


class TestChatWithCoachPayloads:

    def test_nova_without_history_matches_legacy_shape(self):
        mb = _mock_bedrock()
        with patch("insights_handler_v33.bedrock", mb), patch("insights_handler_v33.MODEL_ID", "amazon.nova-lite-v1:0"):
            assert chat_with_coach("q", "CTX") == "reply"
        body = json.loads(mb.invoke_model.call_args[1]["body"])
        assert len(body["messages"]) == 1
        assert "inferenceConfig" in body and "anthropic_version" not in body
        text = body["messages"][0]["content"][0]["text"]
        assert "pragmatic, data-driven" in text and "CTX" in text and "My question: q" in text

    def test_nova_with_history_alternates_and_ends_with_user(self):
        mb = _mock_bedrock()
        history = [_turn("user", "q1"), _turn("assistant", "a1")]
        with patch("insights_handler_v33.bedrock", mb), patch("insights_handler_v33.MODEL_ID", "amazon.nova-lite-v1:0"):
            chat_with_coach("q2", "CTX", history)
        messages = json.loads(mb.invoke_model.call_args[1]["body"])["messages"]
        assert [m["role"] for m in messages] == ["user", "assistant", "user"]
        assert "CTX" in messages[0]["content"][0]["text"]
        assert messages[2]["content"][0]["text"] == "q2"

    def test_anthropic_uses_system_field_and_string_content(self):
        mb = _mock_bedrock(anthropic=True)
        history = [_turn("user", "q1"), _turn("assistant", "a1")]
        with patch("insights_handler_v33.bedrock", mb), patch("insights_handler_v33.MODEL_ID", "anthropic.claude-3-5-sonnet"):
            assert chat_with_coach("q2", "CTX", history) == "reply"
        body = json.loads(mb.invoke_model.call_args[1]["body"])
        assert "pragmatic, data-driven" in body["system"]
        assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user"]
        assert isinstance(body["messages"][0]["content"], str)
        assert "CTX" in body["messages"][0]["content"]


def _chat_event(body):
    return {
        "httpMethod": "POST", "path": "/insights/chat", "pathParameters": {},
        "body": json.dumps(body),
        "requestContext": {"authorizer": {"claims": {"sub": "u", "email": "t@example.com"}}},
    }


class TestChatHandlerHistoryWiring:

    def _run(self, body, rate=(True, 19)):
        apps = [make_app(f"app-{i}", "applied") for i in range(5)]
        with patch("insights_handler_v33.fetch_all_applications", return_value=apps), \
             patch("insights_handler_v33.check_rate_limit", return_value=rate), \
             patch("insights_handler_v33.build_coach_enrichment", return_value={"interviewNotes": {}, "interviewPrep": {}, "alerts": []}), \
             patch("insights_handler_v33.chat_with_coach", return_value="reply") as mock_chat:
            result = lambda_handler(_chat_event(body), None)
        return result, mock_chat

    def test_sanitised_history_reaches_coach(self):
        body = {"message": "follow up", "history": [
            _turn("assistant", "Hi!"), _turn("user", "q1"), _turn("assistant", "a1"), _turn("user", "dangling")]}
        result, mock_chat = self._run(body)
        assert result["statusCode"] == 200
        assert mock_chat.call_args[0][2] == [_turn("user", "q1"), _turn("assistant", "a1")]

    def test_missing_history_gives_empty_list(self):
        result, mock_chat = self._run({"message": "hello"})
        assert result["statusCode"] == 200
        assert mock_chat.call_args[0][2] == []

    def test_non_list_history_returns_400(self):
        result, mock_chat = self._run({"message": "hello", "history": "nope"})
        assert result["statusCode"] == 400
        mock_chat.assert_not_called()

    def test_rate_limit_still_applies_with_history(self):
        result, mock_chat = self._run({"message": "hello", "history": [_turn("user", "q"), _turn("assistant", "a")]}, rate=(False, 0))
        assert result["statusCode"] == 429
        mock_chat.assert_not_called()
