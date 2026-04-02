"""
Tests for the Applications Lambda — CRUD routing and business logic.

Tests the router, input validation, and status transition logic
without hitting DynamoDB (mocked via unittest.mock).

Run with:
    pip install pytest
    pytest tests/test_applications.py -v
"""
import sys
import os
import json
import pytest
import importlib.util
from unittest.mock import patch, MagicMock

# Load applications handler by file path to avoid module name collision
_handler_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'applications', 'handler.py')
)
_spec = importlib.util.spec_from_file_location('applications_handler', _handler_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['applications_handler'] = _mod
_spec.loader.exec_module(_mod)

resp = _mod.resp
get_user_id = _mod.get_user_id
now_iso = _mod.now_iso
lambda_handler = _mod.lambda_handler

from conftest import make_event


class TestHelpers:

    def test_resp_sets_status_code(self):
        r = resp(200, {'ok': True})
        assert r['statusCode'] == 200

    def test_resp_body_is_json_string(self):
        r = resp(200, {'key': 'value'})
        body = json.loads(r['body'])
        assert body['key'] == 'value'

    def test_resp_includes_cors_header(self):
        r = resp(200, {})
        assert r['headers']['Access-Control-Allow-Origin'] == '*'

    def test_resp_includes_content_type(self):
        r = resp(200, {})
        assert r['headers']['Content-Type'] == 'application/json'

    def test_get_user_id_extracts_sub(self):
        event = make_event()
        assert get_user_id(event) == 'test-user-123'

    def test_get_user_id_raises_on_missing_claims(self):
        event = {'requestContext': {}}
        with pytest.raises((KeyError, TypeError)):
            get_user_id(event)

    def test_now_iso_returns_string(self):
        ts = now_iso()
        assert isinstance(ts, str)
        assert 'T' in ts


class TestRouter:

    def test_unknown_route_returns_404(self):
        event = make_event('GET', '/unknown')
        with patch('applications_handler.table') as mock_table:
            mock_table.query.return_value = {'Items': [], 'Count': 0}
            result = lambda_handler(event, None)
        assert result['statusCode'] == 404

    def test_invalid_json_body_returns_400(self):
        event = make_event('POST', '/applications')
        event['body'] = 'not-json'
        result = lambda_handler(event, None)
        assert result['statusCode'] == 400

    def test_missing_auth_returns_401(self):
        event = make_event('GET', '/applications')
        event['requestContext'] = {}
        result = lambda_handler(event, None)
        assert result['statusCode'] == 401


class TestListApplications:

    def test_returns_200_with_items(self):
        event = make_event('GET', '/applications')
        with patch('applications_handler.table') as mock_table:
            mock_table.query.return_value = {
                'Items': [{'appId': 'a1', 'company': 'Stripe', 'status': 'applied'}],
                'Count': 1,
            }
            result = lambda_handler(event, None)
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['count'] == 1
        assert len(body['applications']) == 1

    def test_returns_empty_list_when_no_applications(self):
        event = make_event('GET', '/applications')
        with patch('applications_handler.table') as mock_table:
            mock_table.query.return_value = {'Items': [], 'Count': 0}
            result = lambda_handler(event, None)
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['applications'] == []
        assert body['count'] == 0


class TestCreateApplication:

    def test_creates_successfully_with_required_fields(self):
        event = make_event('POST', '/applications', body={
            'company': 'Anthropic', 'role': 'ML Engineer', 'status': 'applied',
        })
        with patch('applications_handler.table') as mock_table:
            mock_table.put_item.return_value = {}
            result = lambda_handler(event, None)
        assert result['statusCode'] == 201
        body = json.loads(result['body'])
        assert body['application']['company'] == 'Anthropic'
        assert 'appId' in body['application']

    def test_fails_without_company(self):
        event = make_event('POST', '/applications', body={
            'role': 'ML Engineer', 'status': 'applied',
        })
        result = lambda_handler(event, None)
        assert result['statusCode'] == 400
        assert 'company' in json.loads(result['body'])['error']

    def test_fails_without_role(self):
        event = make_event('POST', '/applications', body={
            'company': 'Anthropic', 'status': 'applied',
        })
        result = lambda_handler(event, None)
        assert result['statusCode'] == 400

    def test_fails_without_status(self):
        event = make_event('POST', '/applications', body={
            'company': 'Anthropic', 'role': 'ML Engineer',
        })
        result = lambda_handler(event, None)
        assert result['statusCode'] == 400

    def test_optional_fields_default_correctly(self):
        event = make_event('POST', '/applications', body={
            'company': 'Stripe', 'role': 'Engineer', 'status': 'applied',
        })
        with patch('applications_handler.table') as mock_table:
            mock_table.put_item.return_value = {}
            result = lambda_handler(event, None)
        app = json.loads(result['body'])['application']
        assert app['source'] == 'unknown'
        assert app['resumeVersion'] == 'default'
        assert app['notes'] == ''

    def test_generated_app_id_is_uuid_format(self):
        import re
        event = make_event('POST', '/applications', body={
            'company': 'Stripe', 'role': 'Eng', 'status': 'applied',
        })
        with patch('applications_handler.table') as mock_table:
            mock_table.put_item.return_value = {}
            result = lambda_handler(event, None)
        app_id = json.loads(result['body'])['application']['appId']
        assert re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', app_id)


class TestUpdateStatus:

    def test_valid_status_update_returns_200(self):
        event = make_event(
            'POST', '/applications/app-123/status',
            path_params={'appId': 'app-123'},
            body={'status': 'interview'},
        )
        with patch('applications_handler.table') as mock_table:
            mock_table.get_item.return_value = {
                'Item': {'PK': 'USER#test-user-123', 'SK': 'APP#app-123', 'status': 'screened', 'appId': 'app-123'}
            }
            mock_table.update_item.return_value = {}
            mock_table.put_item.return_value = {}
            result = lambda_handler(event, None)
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['to'] == 'interview'
        assert body['from'] == 'screened'

    def test_invalid_status_returns_400(self):
        event = make_event(
            'POST', '/applications/app-123/status',
            path_params={'appId': 'app-123'},
            body={'status': 'in-progress'},
        )
        result = lambda_handler(event, None)
        assert result['statusCode'] == 400

    def test_all_valid_statuses_are_accepted(self):
        for status in ['applied', 'screened', 'interview', 'offer', 'rejected', 'withdrawn']:
            event = make_event(
                'POST', '/applications/app-123/status',
                path_params={'appId': 'app-123'},
                body={'status': status},
            )
            with patch('applications_handler.table') as mock_table:
                mock_table.get_item.return_value = {
                    'Item': {'PK': 'USER#u', 'SK': 'APP#app-123', 'status': 'applied', 'appId': 'app-123'}
                }
                mock_table.update_item.return_value = {}
                mock_table.put_item.return_value = {}
                result = lambda_handler(event, None)
            assert result['statusCode'] == 200, f"Status '{status}' should be valid"

    def test_missing_status_field_returns_400(self):
        event = make_event(
            'POST', '/applications/app-123/status',
            path_params={'appId': 'app-123'},
            body={'notes': 'forgot status'},
        )
        result = lambda_handler(event, None)
        assert result['statusCode'] == 400


class TestDeleteApplication:

    def test_delete_returns_200(self):
        event = make_event('DELETE', '/applications/app-123', path_params={'appId': 'app-123'})
        with patch('applications_handler.table') as mock_table:
            mock_table.delete_item.return_value = {}
            result = lambda_handler(event, None)
        assert result['statusCode'] == 200
        assert json.loads(result['body'])['appId'] == 'app-123'


class TestGetUploadUrl:

    def test_returns_presigned_url(self):
        event = make_event('POST', '/resumes/upload-url', body={
            'filename': 'resume.pdf', 'versionName': 'v3-ml-focused',
        })
        with patch('applications_handler.s3_client') as mock_s3:
            mock_s3.generate_presigned_url.return_value = 'https://s3.amazonaws.com/fake-url'
            result = lambda_handler(event, None)
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert 'uploadUrl' in body
        assert 'v3-ml-focused' in body['s3Key']

    def test_returns_400_without_filename(self):
        event = make_event('POST', '/resumes/upload-url', body={'versionName': 'v1'})
        result = lambda_handler(event, None)
        assert result['statusCode'] == 400
