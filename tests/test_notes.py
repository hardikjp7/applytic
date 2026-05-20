"""
Unit tests for Notes Lambda - v2.0
Tests: verify_application_owner, list_notes, create_note,
       delete_note, lambda_handler
Run: python -m pytest tests/test_notes.py -v
"""
import sys
import os
import json
import types
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
    os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'notes', 'handler.py')
)
_spec = importlib.util.spec_from_file_location('notes_handler', _handler_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['notes_handler'] = _mod
_spec.loader.exec_module(_mod)

verify_application_owner = _mod.verify_application_owner
list_notes = _mod.list_notes
create_note = _mod.create_note
delete_note = _mod.delete_note
lambda_handler = _mod.lambda_handler
MAX_NOTE_LENGTH = _mod.MAX_NOTE_LENGTH

# ── Helpers ───────────────────────────────────────────────────────────────────

USER_ID = "test-user-123"
APP_ID = "app-abc-123"
NOTE_ID = "note-xyz-456"


def make_event(method="GET", path=f"/applications/{APP_ID}/notes",
               path_params=None, body=None, user_id=USER_ID):
    return {
        "httpMethod": method,
        "path": path,
        "pathParameters": {"appId": APP_ID} if path_params is None else path_params,
        "body": json.dumps(body) if body else None,
        "requestContext": {
            "authorizer": {
                "claims": {"sub": user_id, "email": "test@example.com"}
            }
        },
    }


def make_note_item(note_id=NOTE_ID, user_id=USER_ID, content="Test note"):
    ts = "2024-01-15T10:00:00+00:00"
    return {
        "PK": f"APP#{APP_ID}",
        "SK": f"NOTE#{ts}#{note_id}",
        "noteId": note_id,
        "appId": APP_ID,
        "userId": user_id,
        "content": content,
        "createdAt": ts,
        "entityType": "NOTE",
    }


# ── Tests: verify_application_owner ──────────────────────────────────────────

class TestVerifyApplicationOwner:

    def test_returns_true_when_app_exists(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": {"appId": APP_ID}}
        with patch("notes_handler.table", mock_table):
            assert verify_application_owner(USER_ID, APP_ID) is True

    def test_returns_false_when_app_not_found(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        with patch("notes_handler.table", mock_table):
            assert verify_application_owner(USER_ID, APP_ID) is False

    def test_queries_correct_key(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        with patch("notes_handler.table", mock_table):
            verify_application_owner(USER_ID, APP_ID)
        call_kwargs = mock_table.get_item.call_args[1]
        assert call_kwargs["Key"]["PK"] == f"USER#{USER_ID}"
        assert call_kwargs["Key"]["SK"] == f"APP#{APP_ID}"


# ── Tests: list_notes ─────────────────────────────────────────────────────────

class TestListNotes:

    def test_returns_notes_for_app(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [make_note_item("note-1", content="First note")]
        }
        with patch("notes_handler.table", mock_table):
            notes = list_notes(APP_ID)
        assert len(notes) == 1
        assert notes[0]["content"] == "First note"

    def test_returns_empty_when_no_notes(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        with patch("notes_handler.table", mock_table):
            notes = list_notes(APP_ID)
        assert notes == []

    def test_queries_correct_pk_and_prefix(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        with patch("notes_handler.table", mock_table):
            list_notes(APP_ID)
        mock_table.query.assert_called_once()

    def test_scan_index_forward_true_for_oldest_first(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        with patch("notes_handler.table", mock_table):
            list_notes(APP_ID)
        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs.get("ScanIndexForward") is True


# ── Tests: create_note ────────────────────────────────────────────────────────

class TestCreateNote:

    def test_creates_note_and_returns_item(self):
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        with patch("notes_handler.table", mock_table):
            note = create_note(APP_ID, USER_ID, "Interview went well")
        assert note["content"] == "Interview went well"
        assert note["appId"] == APP_ID
        assert note["userId"] == USER_ID
        assert note["entityType"] == "NOTE"

    def test_note_id_is_uuid(self):
        import re
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        with patch("notes_handler.table", mock_table):
            note = create_note(APP_ID, USER_ID, "Test")
        assert re.match(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            note["noteId"]
        )

    def test_sk_contains_note_prefix(self):
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        with patch("notes_handler.table", mock_table):
            note = create_note(APP_ID, USER_ID, "Test")
        call_kwargs = mock_table.put_item.call_args[1]
        assert call_kwargs["Item"]["SK"].startswith("NOTE#")

    def test_pk_is_app_prefixed(self):
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        with patch("notes_handler.table", mock_table):
            create_note(APP_ID, USER_ID, "Test")
        call_kwargs = mock_table.put_item.call_args[1]
        assert call_kwargs["Item"]["PK"] == f"APP#{APP_ID}"


# ── Tests: delete_note ────────────────────────────────────────────────────────

class TestDeleteNote:

    def test_returns_true_when_deleted(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [make_note_item(NOTE_ID, USER_ID)]}
        mock_table.delete_item.return_value = {}
        with patch("notes_handler.table", mock_table):
            result = delete_note(APP_ID, NOTE_ID, USER_ID)
        assert result is True
        mock_table.delete_item.assert_called_once()

    def test_returns_false_when_note_not_found(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        with patch("notes_handler.table", mock_table):
            result = delete_note(APP_ID, "nonexistent-note", USER_ID)
        assert result is False

    def test_returns_false_when_different_user_owns_note(self):
        mock_table = MagicMock()
        # Note belongs to different-user, but caller is USER_ID
        mock_table.query.return_value = {
            "Items": [make_note_item(NOTE_ID, user_id="different-user")]
        }
        with patch("notes_handler.table", mock_table):
            result = delete_note(APP_ID, NOTE_ID, USER_ID)
        assert result is False
        mock_table.delete_item.assert_not_called()

    def test_delete_called_with_correct_key(self):
        note = make_note_item(NOTE_ID, USER_ID)
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [note]}
        mock_table.delete_item.return_value = {}
        with patch("notes_handler.table", mock_table):
            delete_note(APP_ID, NOTE_ID, USER_ID)
        call_kwargs = mock_table.delete_item.call_args[1]
        assert call_kwargs["Key"]["PK"] == f"APP#{APP_ID}"
        assert call_kwargs["Key"]["SK"] == note["SK"]


# ── Tests: lambda_handler ─────────────────────────────────────────────────────

class TestNotesLambdaHandler:

    # GET tests
    def test_get_returns_200_with_notes(self):
        with patch("notes_handler.verify_application_owner", return_value=True), \
             patch("notes_handler.list_notes", return_value=[make_note_item()]):
            result = lambda_handler(make_event("GET"), None)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["count"] == 1
        assert len(body["notes"]) == 1

    def test_get_returns_404_when_app_not_found(self):
        with patch("notes_handler.verify_application_owner", return_value=False):
            result = lambda_handler(make_event("GET"), None)
        assert result["statusCode"] == 404

    def test_get_returns_empty_list_when_no_notes(self):
        with patch("notes_handler.verify_application_owner", return_value=True), \
             patch("notes_handler.list_notes", return_value=[]):
            result = lambda_handler(make_event("GET"), None)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["count"] == 0
        assert body["notes"] == []

    def test_get_cleans_note_fields(self):
        with patch("notes_handler.verify_application_owner", return_value=True), \
             patch("notes_handler.list_notes", return_value=[make_note_item()]):
            result = lambda_handler(make_event("GET"), None)
        note = json.loads(result["body"])["notes"][0]
        # Should have only cleaned fields
        assert "noteId" in note
        assert "content" in note
        assert "createdAt" in note
        # Should NOT expose internal DynamoDB fields
        assert "PK" not in note
        assert "SK" not in note
        assert "userId" not in note

    # POST tests
    def test_post_creates_note_returns_201(self):
        with patch("notes_handler.verify_application_owner", return_value=True), \
             patch("notes_handler.create_note", return_value=make_note_item()):
            result = lambda_handler(
                make_event("POST", body={"content": "Great interview"}), None
            )
        assert result["statusCode"] == 201
        body = json.loads(result["body"])
        assert "note" in body

    def test_post_returns_400_for_empty_content(self):
        with patch("notes_handler.verify_application_owner", return_value=True):
            result = lambda_handler(
                make_event("POST", body={"content": ""}), None
            )
        assert result["statusCode"] == 400

    def test_post_returns_400_for_missing_content(self):
        with patch("notes_handler.verify_application_owner", return_value=True):
            result = lambda_handler(
                make_event("POST", body={}), None
            )
        assert result["statusCode"] == 400

    def test_post_returns_400_for_content_too_long(self):
        with patch("notes_handler.verify_application_owner", return_value=True):
            result = lambda_handler(
                make_event("POST", body={"content": "x" * (MAX_NOTE_LENGTH + 1)}), None
            )
        assert result["statusCode"] == 400

    def test_post_returns_404_when_app_not_found(self):
        with patch("notes_handler.verify_application_owner", return_value=False):
            result = lambda_handler(
                make_event("POST", body={"content": "Note"}), None
            )
        assert result["statusCode"] == 404

    def test_post_accepts_max_length_content(self):
        with patch("notes_handler.verify_application_owner", return_value=True), \
             patch("notes_handler.create_note", return_value=make_note_item()):
            result = lambda_handler(
                make_event("POST", body={"content": "x" * MAX_NOTE_LENGTH}), None
            )
        assert result["statusCode"] == 201

    # DELETE tests
    def test_delete_returns_200_when_deleted(self):
        path = f"/applications/{APP_ID}/notes/{NOTE_ID}"
        event = make_event(
            "DELETE", path=path,
            path_params={"appId": APP_ID, "noteId": NOTE_ID}
        )
        with patch("notes_handler.verify_application_owner", return_value=True), \
             patch("notes_handler.delete_note", return_value=True):
            result = lambda_handler(event, None)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["noteId"] == NOTE_ID

    def test_delete_returns_404_when_note_not_found(self):
        path = f"/applications/{APP_ID}/notes/{NOTE_ID}"
        event = make_event(
            "DELETE", path=path,
            path_params={"appId": APP_ID, "noteId": NOTE_ID}
        )
        with patch("notes_handler.verify_application_owner", return_value=True), \
             patch("notes_handler.delete_note", return_value=False):
            result = lambda_handler(event, None)
        assert result["statusCode"] == 404

    def test_delete_returns_404_when_app_not_found(self):
        path = f"/applications/{APP_ID}/notes/{NOTE_ID}"
        event = make_event(
            "DELETE", path=path,
            path_params={"appId": APP_ID, "noteId": NOTE_ID}
        )
        with patch("notes_handler.verify_application_owner", return_value=False):
            result = lambda_handler(event, None)
        assert result["statusCode"] == 404

    # Auth tests
    def test_missing_auth_returns_401(self):
        event = make_event("GET")
        event["requestContext"] = {}
        result = lambda_handler(event, None)
        assert result["statusCode"] == 401

    def test_missing_app_id_returns_400(self):
        event = make_event("GET", path_params={})
        result = lambda_handler(event, None)
        assert result["statusCode"] == 400

    def test_invalid_json_returns_400(self):
        event = make_event("POST")
        event["body"] = "not-json"
        result = lambda_handler(event, None)
        assert result["statusCode"] == 400

    def test_unknown_route_returns_404(self):
        event = make_event("PATCH")
        result = lambda_handler(event, None)
        assert result["statusCode"] == 404
