"""
Unit tests for Contacts Lambda - v3.1
Tests: verify_application_owner, list_contacts, create_contact,
       delete_contact, lambda_handler
Run: python -m pytest tests/test_contacts.py -v
"""
import sys
import os
import json
import types
import pytest
import importlib.util
from unittest.mock import MagicMock, patch

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
    os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'contacts', 'handler.py')
)
_spec = importlib.util.spec_from_file_location('contacts_handler', _handler_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['contacts_handler'] = _mod
_spec.loader.exec_module(_mod)

verify_application_owner = _mod.verify_application_owner
list_contacts = _mod.list_contacts
create_contact = _mod.create_contact
delete_contact = _mod.delete_contact
lambda_handler = _mod.lambda_handler
MAX_NAME_LENGTH = _mod.MAX_NAME_LENGTH

# ── Helpers ───────────────────────────────────────────────────────────────────

USER_ID = "test-user-123"
APP_ID = "app-abc-123"
CONTACT_ID = "contact-xyz-456"


def make_event(method="GET", path=f"/applications/{APP_ID}/contacts",
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


def make_contact_item(contact_id=CONTACT_ID, user_id=USER_ID, name="Jane Recruiter",
                       email="jane@stripe.com", linkedin_url="https://linkedin.com/in/jane", role="Recruiter"):
    ts = "2024-01-15T10:00:00+00:00"
    return {
        "PK": f"APP#{APP_ID}",
        "SK": f"CONTACT#{ts}#{contact_id}",
        "contactId": contact_id,
        "appId": APP_ID,
        "userId": user_id,
        "name": name,
        "email": email,
        "linkedinUrl": linkedin_url,
        "role": role,
        "createdAt": ts,
        "entityType": "CONTACT",
    }


# ── Tests: verify_application_owner ──────────────────────────────────────────

class TestVerifyApplicationOwner:

    def test_returns_true_when_app_exists(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": {"appId": APP_ID}}
        with patch("contacts_handler.table", mock_table):
            assert verify_application_owner(USER_ID, APP_ID) is True

    def test_returns_false_when_app_not_found(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        with patch("contacts_handler.table", mock_table):
            assert verify_application_owner(USER_ID, APP_ID) is False

    def test_queries_correct_key(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        with patch("contacts_handler.table", mock_table):
            verify_application_owner(USER_ID, APP_ID)
        call_kwargs = mock_table.get_item.call_args[1]
        assert call_kwargs["Key"]["PK"] == f"USER#{USER_ID}"
        assert call_kwargs["Key"]["SK"] == f"APP#{APP_ID}"


# ── Tests: list_contacts ──────────────────────────────────────────────────────

class TestListContacts:

    def test_returns_contacts_for_app(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [make_contact_item("contact-1", name="First Contact")]
        }
        with patch("contacts_handler.table", mock_table):
            contacts = list_contacts(APP_ID)
        assert len(contacts) == 1
        assert contacts[0]["name"] == "First Contact"

    def test_returns_empty_when_no_contacts(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        with patch("contacts_handler.table", mock_table):
            contacts = list_contacts(APP_ID)
        assert contacts == []

    def test_scan_index_forward_true_for_oldest_first(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        with patch("contacts_handler.table", mock_table):
            list_contacts(APP_ID)
        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs.get("ScanIndexForward") is True


# ── Tests: create_contact ─────────────────────────────────────────────────────

class TestCreateContact:

    def test_creates_contact_and_returns_item(self):
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        with patch("contacts_handler.table", mock_table):
            contact = create_contact(APP_ID, USER_ID, "Jane Recruiter", "jane@stripe.com", "https://linkedin.com/in/jane", "Recruiter")
        assert contact["name"] == "Jane Recruiter"
        assert contact["email"] == "jane@stripe.com"
        assert contact["appId"] == APP_ID
        assert contact["userId"] == USER_ID
        assert contact["entityType"] == "CONTACT"

    def test_contact_id_is_uuid(self):
        import re
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        with patch("contacts_handler.table", mock_table):
            contact = create_contact(APP_ID, USER_ID, "Test", "", "", "")
        assert re.match(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            contact["contactId"]
        )

    def test_sk_contains_contact_prefix(self):
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        with patch("contacts_handler.table", mock_table):
            contact = create_contact(APP_ID, USER_ID, "Test", "", "", "")
        call_kwargs = mock_table.put_item.call_args[1]
        assert call_kwargs["Item"]["SK"].startswith("CONTACT#")

    def test_pk_is_app_prefixed(self):
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        with patch("contacts_handler.table", mock_table):
            create_contact(APP_ID, USER_ID, "Test", "", "", "")
        call_kwargs = mock_table.put_item.call_args[1]
        assert call_kwargs["Item"]["PK"] == f"APP#{APP_ID}"

    def test_optional_fields_can_be_empty(self):
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        with patch("contacts_handler.table", mock_table):
            contact = create_contact(APP_ID, USER_ID, "Test", "", "", "")
        assert contact["email"] == ""
        assert contact["linkedinUrl"] == ""
        assert contact["role"] == ""


# ── Tests: delete_contact ─────────────────────────────────────────────────────

class TestDeleteContact:

    def test_returns_true_when_deleted(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [make_contact_item(CONTACT_ID, USER_ID)]}
        mock_table.delete_item.return_value = {}
        with patch("contacts_handler.table", mock_table):
            result = delete_contact(APP_ID, CONTACT_ID, USER_ID)
        assert result is True
        mock_table.delete_item.assert_called_once()

    def test_returns_false_when_contact_not_found(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        with patch("contacts_handler.table", mock_table):
            result = delete_contact(APP_ID, "nonexistent-contact", USER_ID)
        assert result is False

    def test_returns_false_when_different_user_owns_contact(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [make_contact_item(CONTACT_ID, user_id="different-user")]
        }
        with patch("contacts_handler.table", mock_table):
            result = delete_contact(APP_ID, CONTACT_ID, USER_ID)
        assert result is False
        mock_table.delete_item.assert_not_called()

    def test_delete_called_with_correct_key(self):
        contact = make_contact_item(CONTACT_ID, USER_ID)
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [contact]}
        mock_table.delete_item.return_value = {}
        with patch("contacts_handler.table", mock_table):
            delete_contact(APP_ID, CONTACT_ID, USER_ID)
        call_kwargs = mock_table.delete_item.call_args[1]
        assert call_kwargs["Key"]["PK"] == f"APP#{APP_ID}"
        assert call_kwargs["Key"]["SK"] == contact["SK"]


# ── Tests: lambda_handler ─────────────────────────────────────────────────────

class TestContactsLambdaHandler:

    # GET tests
    def test_get_returns_200_with_contacts(self):
        with patch("contacts_handler.verify_application_owner", return_value=True), \
             patch("contacts_handler.list_contacts", return_value=[make_contact_item()]):
            result = lambda_handler(make_event("GET"), None)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["count"] == 1
        assert len(body["contacts"]) == 1

    def test_get_returns_404_when_app_not_found(self):
        with patch("contacts_handler.verify_application_owner", return_value=False):
            result = lambda_handler(make_event("GET"), None)
        assert result["statusCode"] == 404

    def test_get_returns_empty_list_when_no_contacts(self):
        with patch("contacts_handler.verify_application_owner", return_value=True), \
             patch("contacts_handler.list_contacts", return_value=[]):
            result = lambda_handler(make_event("GET"), None)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["count"] == 0
        assert body["contacts"] == []

    def test_get_cleans_contact_fields(self):
        with patch("contacts_handler.verify_application_owner", return_value=True), \
             patch("contacts_handler.list_contacts", return_value=[make_contact_item()]):
            result = lambda_handler(make_event("GET"), None)
        contact = json.loads(result["body"])["contacts"][0]
        assert "contactId" in contact
        assert "name" in contact
        assert "email" in contact
        assert "linkedinUrl" in contact
        assert "role" in contact
        assert "createdAt" in contact
        assert "PK" not in contact
        assert "SK" not in contact
        assert "userId" not in contact

    # POST tests
    def test_post_creates_contact_returns_201(self):
        with patch("contacts_handler.verify_application_owner", return_value=True), \
             patch("contacts_handler.create_contact", return_value=make_contact_item()):
            result = lambda_handler(
                make_event("POST", body={"name": "Jane Recruiter", "email": "jane@stripe.com"}), None
            )
        assert result["statusCode"] == 201
        body = json.loads(result["body"])
        assert "contact" in body

    def test_post_returns_400_for_empty_name(self):
        with patch("contacts_handler.verify_application_owner", return_value=True):
            result = lambda_handler(
                make_event("POST", body={"name": ""}), None
            )
        assert result["statusCode"] == 400

    def test_post_returns_400_for_missing_name(self):
        with patch("contacts_handler.verify_application_owner", return_value=True):
            result = lambda_handler(
                make_event("POST", body={}), None
            )
        assert result["statusCode"] == 400

    def test_post_returns_400_for_name_too_long(self):
        with patch("contacts_handler.verify_application_owner", return_value=True):
            result = lambda_handler(
                make_event("POST", body={"name": "x" * (MAX_NAME_LENGTH + 1)}), None
            )
        assert result["statusCode"] == 400

    def test_post_returns_404_when_app_not_found(self):
        with patch("contacts_handler.verify_application_owner", return_value=False):
            result = lambda_handler(
                make_event("POST", body={"name": "Jane"}), None
            )
        assert result["statusCode"] == 404

    def test_post_accepts_name_only(self):
        with patch("contacts_handler.verify_application_owner", return_value=True), \
             patch("contacts_handler.create_contact", return_value=make_contact_item()):
            result = lambda_handler(
                make_event("POST", body={"name": "Jane Recruiter"}), None
            )
        assert result["statusCode"] == 201

    # DELETE tests
    def test_delete_returns_200_when_deleted(self):
        path = f"/applications/{APP_ID}/contacts/{CONTACT_ID}"
        event = make_event(
            "DELETE", path=path,
            path_params={"appId": APP_ID, "contactId": CONTACT_ID}
        )
        with patch("contacts_handler.verify_application_owner", return_value=True), \
             patch("contacts_handler.delete_contact", return_value=True):
            result = lambda_handler(event, None)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["contactId"] == CONTACT_ID

    def test_delete_returns_404_when_contact_not_found(self):
        path = f"/applications/{APP_ID}/contacts/{CONTACT_ID}"
        event = make_event(
            "DELETE", path=path,
            path_params={"appId": APP_ID, "contactId": CONTACT_ID}
        )
        with patch("contacts_handler.verify_application_owner", return_value=True), \
             patch("contacts_handler.delete_contact", return_value=False):
            result = lambda_handler(event, None)
        assert result["statusCode"] == 404

    def test_delete_returns_404_when_app_not_found(self):
        path = f"/applications/{APP_ID}/contacts/{CONTACT_ID}"
        event = make_event(
            "DELETE", path=path,
            path_params={"appId": APP_ID, "contactId": CONTACT_ID}
        )
        with patch("contacts_handler.verify_application_owner", return_value=False):
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