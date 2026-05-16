"""
Tests for the Applications Lambda - v2.0
v2.0 additions: followUpDate field tests in create and update.
Stubs shared layer, powertools, pydantic, xray before loading handler.
Run: python -m pytest tests/test_applications.py -v
"""
import sys
import os
import json
import types
import pytest
import importlib.util
from unittest.mock import patch, MagicMock

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

xray_mod = types.ModuleType("aws_xray_sdk")
xray_core = types.ModuleType("aws_xray_sdk.core")
xray_core.xray_recorder = MagicMock()
sys.modules["aws_xray_sdk"] = xray_mod
sys.modules["aws_xray_sdk.core"] = xray_core

shared_pkg = types.ModuleType("shared")
shared_mw = types.ModuleType("shared.middleware")

def _resp(status, body, event=None):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(body, default=str),
    }

shared_mw.resp = _resp
shared_mw.get_user_id = lambda event: event["requestContext"]["authorizer"]["claims"]["sub"]
shared_mw.get_user_email = lambda event: event["requestContext"]["authorizer"]["claims"].get("email", "")

def _mock_parse_body(event):
    raw = event.get("body")
    if not raw:
        return {}, None
    try:
        return json.loads(raw), None
    except (json.JSONDecodeError, TypeError):
        return {}, shared_mw.resp(400, {"error": "Invalid JSON body"}, event)

shared_mw.parse_body = _mock_parse_body
shared_mw.now_iso = lambda: "2024-01-01T00:00:00+00:00"
shared_mw.with_middleware = lambda fn: fn
sys.modules["shared"] = shared_pkg
sys.modules["shared.middleware"] = shared_mw

# ── Load handler ──────────────────────────────────────────────────────────────
_handler_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'applications', 'handler.py')
)
_spec = importlib.util.spec_from_file_location('applications_handler', _handler_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['applications_handler'] = _mod
_spec.loader.exec_module(_mod)

lambda_handler = _mod.lambda_handler

from conftest import make_event


class TestHelpers:
    def test_resp_sets_status_code(self):
        assert _resp(200, {})['statusCode'] == 200

    def test_resp_body_is_json_string(self):
        assert json.loads(_resp(200, {'key': 'value'})['body'])['key'] == 'value'

    def test_resp_includes_cors_header(self):
        assert 'Access-Control-Allow-Origin' in _resp(200, {})['headers']

    def test_resp_includes_content_type(self):
        assert _resp(200, {})['headers']['Content-Type'] == 'application/json'

    def test_get_user_id_extracts_sub(self):
        assert shared_mw.get_user_id(make_event()) == 'test-user-123'

    def test_get_user_id_raises_on_missing_claims(self):
        with pytest.raises((KeyError, TypeError)):
            shared_mw.get_user_id({'requestContext': {}})


class TestRouter:
    def test_unknown_route_returns_404(self):
        event = make_event('GET', '/unknown')
        with patch('applications_handler.table') as mt:
            mt.query.return_value = {'Items': [], 'Count': 0}
            assert lambda_handler(event, None)['statusCode'] == 404

    def test_invalid_json_body_returns_400(self):
        event = make_event('POST', '/applications')
        event['body'] = 'not-json'
        result = lambda_handler(event, None)
        assert result['statusCode'] == 400

    def test_missing_auth_returns_401(self):
        event = make_event('GET', '/applications')
        event['requestContext'] = {}
        assert lambda_handler(event, None)['statusCode'] == 401


class TestListApplications:
    def test_returns_200_with_items(self):
        event = make_event('GET', '/applications')
        with patch('applications_handler.table') as mt:
            mt.query.return_value = {
                'Items': [{'appId': 'a1', 'company': 'Stripe', 'status': 'applied'}], 'Count': 1
            }
            result = lambda_handler(event, None)
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['count'] == 1
        assert len(body['applications']) == 1

    def test_returns_empty_list_when_no_applications(self):
        event = make_event('GET', '/applications')
        with patch('applications_handler.table') as mt:
            mt.query.return_value = {'Items': [], 'Count': 0}
            result = lambda_handler(event, None)
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['applications'] == []
        assert body['count'] == 0


class TestCreateApplication:
    def test_creates_successfully_with_required_fields(self):
        event = make_event('POST', '/applications', body={
            'company': 'Anthropic', 'role': 'ML Engineer', 'status': 'applied'
        })
        with patch('applications_handler.table') as mt:
            mt.put_item.return_value = {}
            result = lambda_handler(event, None)
        assert result['statusCode'] == 201
        body = json.loads(result['body'])
        assert body['application']['company'] == 'Anthropic'
        assert 'appId' in body['application']

    def test_fails_without_company(self):
        event = make_event('POST', '/applications', body={'role': 'ML Engineer', 'status': 'applied'})
        assert lambda_handler(event, None)['statusCode'] == 400

    def test_fails_without_role(self):
        event = make_event('POST', '/applications', body={'company': 'Anthropic', 'status': 'applied'})
        assert lambda_handler(event, None)['statusCode'] == 400

    def test_fails_without_status(self):
        event = make_event('POST', '/applications', body={'company': 'Anthropic', 'role': 'ML Engineer'})
        assert lambda_handler(event, None)['statusCode'] == 400

    def test_optional_fields_default_correctly(self):
        event = make_event('POST', '/applications', body={'company': 'Stripe', 'role': 'Eng', 'status': 'applied'})
        with patch('applications_handler.table') as mt:
            mt.put_item.return_value = {}
            result = lambda_handler(event, None)
        app = json.loads(result['body'])['application']
        assert app['source'] == 'unknown'
        assert app['resumeVersion'] == 'default'
        assert app['notes'] == ''

    def test_generated_app_id_is_uuid_format(self):
        import re
        event = make_event('POST', '/applications', body={'company': 'Stripe', 'role': 'Eng', 'status': 'applied'})
        with patch('applications_handler.table') as mt:
            mt.put_item.return_value = {}
            result = lambda_handler(event, None)
        app_id = json.loads(result['body'])['application']['appId']
        assert re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', app_id)

    # v2.0: followUpDate tests
    def test_creates_with_follow_up_date(self):
        event = make_event('POST', '/applications', body={
            'company': 'Stripe', 'role': 'Eng', 'status': 'applied',
            'followUpDate': '2024-02-01'
        })
        with patch('applications_handler.table') as mt:
            mt.put_item.return_value = {}
            result = lambda_handler(event, None)
        assert result['statusCode'] == 201
        app = json.loads(result['body'])['application']
        assert app['followUpDate'] == '2024-02-01'

    def test_creates_without_follow_up_date_defaults_to_none(self):
        event = make_event('POST', '/applications', body={
            'company': 'Stripe', 'role': 'Eng', 'status': 'applied'
        })
        with patch('applications_handler.table') as mt:
            mt.put_item.return_value = {}
            result = lambda_handler(event, None)
        app = json.loads(result['body'])['application']
        assert app['followUpDate'] is None

    def test_invalid_follow_up_date_format_returns_400(self):
        event = make_event('POST', '/applications', body={
            'company': 'Stripe', 'role': 'Eng', 'status': 'applied',
            'followUpDate': 'not-a-date'
        })
        result = lambda_handler(event, None)
        assert result['statusCode'] == 400


class TestUpdateApplication:
    def test_update_follow_up_date(self):
        event = make_event('PUT', '/applications/app-123',
                           path_params={'appId': 'app-123'},
                           body={'followUpDate': '2024-03-01'})
        with patch('applications_handler.table') as mt:
            mt.update_item.return_value = {}
            result = lambda_handler(event, None)
        assert result['statusCode'] == 200

    def test_clear_follow_up_date_with_null(self):
        event = make_event('PUT', '/applications/app-123',
                           path_params={'appId': 'app-123'},
                           body={'followUpDate': None})
        with patch('applications_handler.table') as mt:
            mt.update_item.return_value = {}
            result = lambda_handler(event, None)
        assert result['statusCode'] == 200

    def test_invalid_follow_up_date_format_on_update_returns_400(self):
        event = make_event('PUT', '/applications/app-123',
                           path_params={'appId': 'app-123'},
                           body={'followUpDate': 'bad-date'})
        result = lambda_handler(event, None)
        assert result['statusCode'] == 400


class TestUpdateStatus:
    def test_valid_status_update_returns_200(self):
        event = make_event('POST', '/applications/app-123/status',
                           path_params={'appId': 'app-123'}, body={'status': 'interview'})
        with patch('applications_handler.table') as mt:
            mt.get_item.return_value = {
                'Item': {'PK': 'USER#test-user-123', 'SK': 'APP#app-123', 'status': 'screened', 'appId': 'app-123'}
            }
            mt.update_item.return_value = {}
            mt.put_item.return_value = {}
            result = lambda_handler(event, None)
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['to'] == 'interview'
        assert body['from'] == 'screened'

    def test_invalid_status_returns_400(self):
        event = make_event('POST', '/applications/app-123/status',
                           path_params={'appId': 'app-123'}, body={'status': 'in-progress'})
        assert lambda_handler(event, None)['statusCode'] == 400

    def test_all_valid_statuses_are_accepted(self):
        for status in ['applied', 'screened', 'interview', 'offer', 'rejected', 'withdrawn']:
            event = make_event('POST', '/applications/app-123/status',
                               path_params={'appId': 'app-123'}, body={'status': status})
            with patch('applications_handler.table') as mt:
                mt.get_item.return_value = {
                    'Item': {'PK': 'USER#u', 'SK': 'APP#app-123', 'status': 'applied', 'appId': 'app-123'}
                }
                mt.update_item.return_value = {}
                mt.put_item.return_value = {}
                result = lambda_handler(event, None)
            assert result['statusCode'] == 200, f"Status '{status}' should be valid"

    def test_missing_status_field_returns_400(self):
        event = make_event('POST', '/applications/app-123/status',
                           path_params={'appId': 'app-123'}, body={'notes': 'forgot status'})
        assert lambda_handler(event, None)['statusCode'] == 400


class TestDeleteApplication:
    def test_delete_returns_200(self):
        event = make_event('DELETE', '/applications/app-123', path_params={'appId': 'app-123'})
        with patch('applications_handler.table') as mt:
            mt.delete_item.return_value = {}
            result = lambda_handler(event, None)
        assert result['statusCode'] == 200
        assert json.loads(result['body'])['appId'] == 'app-123'


class TestGetUploadUrl:
    def test_returns_presigned_url(self):
        event = make_event('POST', '/resumes/upload-url', body={
            'filename': 'resume.pdf', 'versionName': 'v3-ml-focused'
        })
        with patch('applications_handler.s3_client') as ms3:
            ms3.generate_presigned_url.return_value = 'https://s3.amazonaws.com/fake-url'
            result = lambda_handler(event, None)
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert 'uploadUrl' in body
        assert 'v3-ml-focused' in body['s3Key']

    def test_returns_400_without_filename(self):
        event = make_event('POST', '/resumes/upload-url', body={'versionName': 'v1'})
        assert lambda_handler(event, None)['statusCode'] == 400
