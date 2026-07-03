"""
Unit tests for Interview Prep Lambda - v3.0
Tests: verify_application_owner, fetch_job_description, _strip_html,
       generate_questions_with_bedrock, store_prep, get_prep,
       update_question_in_prep, lambda_handler
Run: python -m pytest tests/test_interview_prep.py -v
"""
import sys
import os
import json
import types
import uuid
import pytest
import importlib.util
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

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
    os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'interview_prep', 'handler.py')
)
_spec = importlib.util.spec_from_file_location('interview_prep_handler', _handler_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['interview_prep_handler'] = _mod
_spec.loader.exec_module(_mod)

verify_application_owner = _mod.verify_application_owner
fetch_job_description = _mod.fetch_job_description
generate_questions_with_bedrock = _mod.generate_questions_with_bedrock
store_prep = _mod.store_prep
get_prep = _mod.get_prep
update_question_in_prep = _mod.update_question_in_prep
_strip_html = _mod._strip_html
_clean_prep = _mod._clean_prep
lambda_handler = _mod.lambda_handler
NUM_QUESTIONS = _mod.NUM_QUESTIONS

# ── Helpers ───────────────────────────────────────────────────────────────────

USER_ID = "test-user-123"
APP_ID = "app-abc-123"
QUESTION_ID = "q-uuid-1"


def make_event(method="POST", path=f"/applications/{APP_ID}/interview-prep/generate",
               path_params=None, body=None, user_id=USER_ID):
    return {
        "httpMethod": method,
        "path": path,
        "pathParameters": path_params if path_params is not None else {"appId": APP_ID},
        "body": json.dumps(body) if body else None,
        "requestContext": {
            "authorizer": {
                "claims": {"sub": user_id, "email": "test@example.com"}
            }
        },
    }


def make_app_item(app_id=APP_ID, user_id=USER_ID, role="ML Engineer",
                  company="Stripe", job_desc_url="https://stripe.com/jobs/123"):
    return {
        "PK": f"USER#{user_id}",
        "SK": f"APP#{app_id}",
        "appId": app_id,
        "userId": user_id,
        "company": company,
        "role": role,
        "status": "interview",
        "jobDescUrl": job_desc_url,
        "entityType": "APPLICATION",
    }


def make_prep_item(app_id=APP_ID, user_id=USER_ID, questions=None):
    if questions is None:
        questions = [
            {"id": f"q-{i}", "text": f"Question {i}", "practiced": False, "answer": ""}
            for i in range(NUM_QUESTIONS)
        ]
    return {
        "PK": f"APP#{app_id}",
        "SK": "PREP#v1",
        "appId": app_id,
        "userId": user_id,
        "questions": questions,
        "generatedAt": "2024-01-15T10:00:00+00:00",
        "updatedAt": "2024-01-15T10:00:00+00:00",
        "entityType": "INTERVIEW_PREP",
    }


def make_bedrock_response(questions_text: str, anthropic=False):
    mock_body = MagicMock()
    if anthropic:
        mock_body.read.return_value = json.dumps({
            "content": [{"text": questions_text}]
        }).encode()
    else:
        mock_body.read.return_value = json.dumps({
            "output": {"message": {"content": [{"text": questions_text}]}}
        }).encode()
    return {"body": mock_body}


SAMPLE_QUESTIONS_TEXT = "\n".join([
    f"{i+1}. Sample interview question number {i+1}?"
    for i in range(NUM_QUESTIONS)
])


# ── Tests: _strip_html ────────────────────────────────────────────────────────

class TestStripHtml:

    def test_strips_basic_tags(self):
        assert _strip_html("<p>Hello world</p>") == "Hello world"

    def test_strips_script_blocks(self):
        result = _strip_html("<script>alert('x')</script><p>Safe</p>")
        assert "alert" not in result
        assert "Safe" in result

    def test_strips_style_blocks(self):
        result = _strip_html("<style>body{color:red}</style><p>Text</p>")
        assert "color" not in result
        assert "Text" in result

    def test_collapses_whitespace(self):
        result = _strip_html("<p>Hello    world</p>")
        assert "  " not in result

    def test_empty_string_returns_empty(self):
        assert _strip_html("") == ""

    def test_plain_text_unchanged(self):
        assert _strip_html("No tags here") == "No tags here"


# ── Tests: fetch_job_description ──────────────────────────────────────────────

class TestFetchJobDescription:

    def test_returns_empty_for_empty_url(self):
        assert fetch_job_description("") == ""

    def test_returns_empty_for_non_http_url(self):
        assert fetch_job_description("ftp://example.com") == ""

    def test_returns_empty_on_network_error(self):
        with patch("interview_prep_handler.urllib_request.urlopen", side_effect=Exception("network error")):
            result = fetch_job_description("https://example.com/job")
        assert result == ""

    def test_truncates_to_jd_max_chars(self):
        long_html = "<p>" + "x" * 10000 + "</p>"
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = long_html.encode()
        with patch("interview_prep_handler.urllib_request.urlopen", return_value=mock_response):
            with patch("interview_prep_handler.urllib_request.Request", return_value=MagicMock()):
                result = fetch_job_description("https://example.com/job")
        assert len(result) <= _mod.JD_MAX_CHARS

    def test_strips_html_from_fetched_content(self):
        html = "<html><body><h1>Software Engineer</h1><p>We are hiring.</p></body></html>"
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = html.encode()
        with patch("interview_prep_handler.urllib_request.urlopen", return_value=mock_response):
            with patch("interview_prep_handler.urllib_request.Request", return_value=MagicMock()):
                result = fetch_job_description("https://example.com/job")
        assert "<h1>" not in result
        assert "Software Engineer" in result


# ── Tests: generate_questions_with_bedrock ────────────────────────────────────

class TestGenerateQuestionsWithBedrock:

    def test_returns_list_of_question_dicts(self):
        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model.return_value = make_bedrock_response(SAMPLE_QUESTIONS_TEXT)
        with patch("interview_prep_handler.bedrock", mock_bedrock), \
             patch("interview_prep_handler.MODEL_ID", "amazon.nova-lite-v1:0"):
            questions = generate_questions_with_bedrock("ML Engineer", "Stripe", "")
        assert isinstance(questions, list)
        assert len(questions) == NUM_QUESTIONS

    def test_each_question_has_required_fields(self):
        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model.return_value = make_bedrock_response(SAMPLE_QUESTIONS_TEXT)
        with patch("interview_prep_handler.bedrock", mock_bedrock), \
             patch("interview_prep_handler.MODEL_ID", "amazon.nova-lite-v1:0"):
            questions = generate_questions_with_bedrock("SWE", "Acme", "some jd text")
        for q in questions:
            assert "id" in q
            assert "text" in q
            assert "practiced" in q
            assert "answer" in q
            assert q["practiced"] is False
            assert q["answer"] == ""

    def test_each_question_has_unique_id(self):
        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model.return_value = make_bedrock_response(SAMPLE_QUESTIONS_TEXT)
        with patch("interview_prep_handler.bedrock", mock_bedrock), \
             patch("interview_prep_handler.MODEL_ID", "amazon.nova-lite-v1:0"):
            questions = generate_questions_with_bedrock("SWE", "Acme", "")
        ids = [q["id"] for q in questions]
        assert len(ids) == len(set(ids))

    def test_falls_back_to_generic_questions_on_bedrock_error(self):
        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model.side_effect = Exception("Bedrock unavailable")
        with patch("interview_prep_handler.bedrock", mock_bedrock), \
             patch("interview_prep_handler.MODEL_ID", "amazon.nova-lite-v1:0"):
            questions = generate_questions_with_bedrock("SWE", "Acme", "")
        assert len(questions) == NUM_QUESTIONS
        assert all(isinstance(q["text"], str) and len(q["text"]) > 0 for q in questions)

    def test_anthropic_model_uses_correct_format(self):
        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model.return_value = make_bedrock_response(SAMPLE_QUESTIONS_TEXT, anthropic=True)
        with patch("interview_prep_handler.bedrock", mock_bedrock), \
             patch("interview_prep_handler.MODEL_ID", "anthropic.claude-3-5-sonnet-v1"):
            questions = generate_questions_with_bedrock("SWE", "Acme", "")
        call_body = json.loads(mock_bedrock.invoke_model.call_args[1]["body"])
        assert "anthropic_version" in call_body
        assert len(questions) == NUM_QUESTIONS

    def test_nova_model_uses_correct_format(self):
        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model.return_value = make_bedrock_response(SAMPLE_QUESTIONS_TEXT)
        with patch("interview_prep_handler.bedrock", mock_bedrock), \
             patch("interview_prep_handler.MODEL_ID", "amazon.nova-lite-v1:0"):
            generate_questions_with_bedrock("SWE", "Acme", "")
        call_body = json.loads(mock_bedrock.invoke_model.call_args[1]["body"])
        assert "inferenceConfig" in call_body
        assert "anthropic_version" not in call_body


# ── Tests: store_prep / get_prep ──────────────────────────────────────────────

class TestStorePrepGetPrep:

    def test_store_prep_calls_put_item(self):
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        questions = [{"id": "q1", "text": "Q?", "practiced": False, "answer": ""}]
        with patch("interview_prep_handler.table", mock_table):
            item = store_prep(APP_ID, USER_ID, questions)
        mock_table.put_item.assert_called_once()
        assert item["PK"] == f"APP#{APP_ID}"
        assert item["SK"] == "PREP#v1"
        assert item["entityType"] == "INTERVIEW_PREP"

    def test_store_prep_overwrites_existing(self):
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        with patch("interview_prep_handler.table", mock_table):
            store_prep(APP_ID, USER_ID, [])
            store_prep(APP_ID, USER_ID, [])
        assert mock_table.put_item.call_count == 2

    def test_get_prep_returns_item_when_exists(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": make_prep_item()}
        with patch("interview_prep_handler.table", mock_table):
            result = get_prep(APP_ID)
        assert result is not None
        assert result["SK"] == "PREP#v1"

    def test_get_prep_returns_none_when_not_found(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        with patch("interview_prep_handler.table", mock_table):
            result = get_prep(APP_ID)
        assert result is None

    def test_get_prep_queries_correct_key(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        with patch("interview_prep_handler.table", mock_table):
            get_prep(APP_ID)
        call_kwargs = mock_table.get_item.call_args[1]
        assert call_kwargs["Key"]["PK"] == f"APP#{APP_ID}"
        assert call_kwargs["Key"]["SK"] == "PREP#v1"


# ── Tests: update_question_in_prep ────────────────────────────────────────────

class TestUpdateQuestionInPrep:

    def test_returns_false_when_no_prep_exists(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        with patch("interview_prep_handler.table", mock_table):
            result = update_question_in_prep(APP_ID, "nonexistent-q", True, None)
        assert result is False

    def test_returns_false_when_question_id_not_found(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": make_prep_item()}
        mock_table.put_item.return_value = {}
        with patch("interview_prep_handler.table", mock_table):
            result = update_question_in_prep(APP_ID, "nonexistent-question-id", True, None)
        assert result is False
        mock_table.put_item.assert_not_called()

    def test_updates_practiced_field(self):
        questions = [{"id": "q-1", "text": "Q?", "practiced": False, "answer": ""}]
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": make_prep_item(questions=questions)}
        mock_table.put_item.return_value = {}
        with patch("interview_prep_handler.table", mock_table):
            result = update_question_in_prep(APP_ID, "q-1", True, None)
        assert result is True
        put_item_call = mock_table.put_item.call_args[1]["Item"]
        updated_q = next(q for q in put_item_call["questions"] if q["id"] == "q-1")
        assert updated_q["practiced"] is True

    def test_updates_answer_field(self):
        questions = [{"id": "q-1", "text": "Q?", "practiced": False, "answer": ""}]
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": make_prep_item(questions=questions)}
        mock_table.put_item.return_value = {}
        with patch("interview_prep_handler.table", mock_table):
            result = update_question_in_prep(APP_ID, "q-1", None, "My answer here")
        assert result is True
        put_item_call = mock_table.put_item.call_args[1]["Item"]
        updated_q = next(q for q in put_item_call["questions"] if q["id"] == "q-1")
        assert updated_q["answer"] == "My answer here"

    def test_returns_true_on_successful_update(self):
        questions = [{"id": "q-1", "text": "Q?", "practiced": False, "answer": ""}]
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": make_prep_item(questions=questions)}
        mock_table.put_item.return_value = {}
        with patch("interview_prep_handler.table", mock_table):
            result = update_question_in_prep(APP_ID, "q-1", True, "answer")
        assert result is True


# ── Tests: lambda_handler ─────────────────────────────────────────────────────

class TestInterviewPrepLambdaHandler:

    # POST /generate
    def test_generate_returns_201_on_success(self):
        with patch("interview_prep_handler.verify_application_owner", return_value=make_app_item()), \
             patch("interview_prep_handler.fetch_job_description", return_value="some jd text"), \
             patch("interview_prep_handler.generate_questions_with_bedrock", return_value=[
                 {"id": f"q-{i}", "text": f"Q{i}?", "practiced": False, "answer": ""}
                 for i in range(NUM_QUESTIONS)
             ]), \
             patch("interview_prep_handler.store_prep", return_value=make_prep_item()):
            result = lambda_handler(make_event("POST", f"/applications/{APP_ID}/interview-prep/generate"), None)
        assert result["statusCode"] == 201
        body = json.loads(result["body"])
        assert "prep" in body

    def test_generate_returns_404_when_app_not_found(self):
        with patch("interview_prep_handler.verify_application_owner", return_value=None):
            result = lambda_handler(make_event("POST", f"/applications/{APP_ID}/interview-prep/generate"), None)
        assert result["statusCode"] == 404

    def test_generate_returns_401_when_no_auth(self):
        event = make_event("POST", f"/applications/{APP_ID}/interview-prep/generate")
        event["requestContext"] = {}
        result = lambda_handler(event, None)
        assert result["statusCode"] == 401

    # GET /interview-prep
    def test_get_returns_200_with_prep_when_exists(self):
        with patch("interview_prep_handler.verify_application_owner", return_value=make_app_item()), \
             patch("interview_prep_handler.get_prep", return_value=make_prep_item()):
            result = lambda_handler(
                make_event("GET", f"/applications/{APP_ID}/interview-prep",
                           path_params={"appId": APP_ID}),
                None
            )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["prep"] is not None
        assert len(body["prep"]["questions"]) == NUM_QUESTIONS

    def test_get_returns_200_with_none_when_not_generated(self):
        with patch("interview_prep_handler.verify_application_owner", return_value=make_app_item()), \
             patch("interview_prep_handler.get_prep", return_value=None):
            result = lambda_handler(
                make_event("GET", f"/applications/{APP_ID}/interview-prep",
                           path_params={"appId": APP_ID}),
                None
            )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["prep"] is None

    def test_get_returns_404_when_app_not_found(self):
        with patch("interview_prep_handler.verify_application_owner", return_value=None):
            result = lambda_handler(
                make_event("GET", f"/applications/{APP_ID}/interview-prep",
                           path_params={"appId": APP_ID}),
                None
            )
        assert result["statusCode"] == 404

    # PUT /interview-prep/{questionId}
    def test_put_returns_200_on_success(self):
        with patch("interview_prep_handler.verify_application_owner", return_value=make_app_item()), \
             patch("interview_prep_handler.update_question_in_prep", return_value=True):
            result = lambda_handler(
                make_event(
                    "PUT",
                    f"/applications/{APP_ID}/interview-prep/{QUESTION_ID}",
                    path_params={"appId": APP_ID, "questionId": QUESTION_ID},
                    body={"practiced": True}
                ),
                None
            )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["questionId"] == QUESTION_ID

    def test_put_returns_404_when_question_not_found(self):
        with patch("interview_prep_handler.verify_application_owner", return_value=make_app_item()), \
             patch("interview_prep_handler.update_question_in_prep", return_value=False):
            result = lambda_handler(
                make_event(
                    "PUT",
                    f"/applications/{APP_ID}/interview-prep/{QUESTION_ID}",
                    path_params={"appId": APP_ID, "questionId": QUESTION_ID},
                    body={"practiced": True}
                ),
                None
            )
        assert result["statusCode"] == 404

    def test_put_returns_400_when_no_fields_provided(self):
        with patch("interview_prep_handler.verify_application_owner", return_value=make_app_item()):
            result = lambda_handler(
                make_event(
                    "PUT",
                    f"/applications/{APP_ID}/interview-prep/{QUESTION_ID}",
                    path_params={"appId": APP_ID, "questionId": QUESTION_ID},
                    body={}
                ),
                None
            )
        assert result["statusCode"] == 400

    def test_put_returns_400_when_answer_too_long(self):
        with patch("interview_prep_handler.verify_application_owner", return_value=make_app_item()):
            result = lambda_handler(
                make_event(
                    "PUT",
                    f"/applications/{APP_ID}/interview-prep/{QUESTION_ID}",
                    path_params={"appId": APP_ID, "questionId": QUESTION_ID},
                    body={"answer": "x" * 5001}
                ),
                None
            )
        assert result["statusCode"] == 400

    def test_missing_app_id_returns_400(self):
        event = make_event("GET", f"/applications/{APP_ID}/interview-prep", path_params={})
        result = lambda_handler(event, None)
        assert result["statusCode"] == 400

    def test_unknown_route_returns_404(self):
        result = lambda_handler(
            make_event("DELETE", f"/applications/{APP_ID}/interview-prep"),
            None
        )
        assert result["statusCode"] == 404

    def test_clean_prep_strips_internal_fields(self):
        prep_item = make_prep_item()
        cleaned = _clean_prep(prep_item)
        assert "PK" not in cleaned
        assert "SK" not in cleaned
        assert "userId" not in cleaned
        assert "entityType" not in cleaned
        assert "appId" in cleaned
        assert "questions" in cleaned
        assert "generatedAt" in cleaned
