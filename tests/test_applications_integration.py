"""
Integration tests for Applications Lambda - v1.3
Uses moto to mock DynamoDB - tests real handler-to-database interactions.
Fix: patches module-level `table` inside each mock_aws() context so moto intercepts calls.
Run: python -m pytest tests/test_applications_integration.py -v
"""
import sys
import os
import json
import types
import pytest
import importlib.util
from unittest.mock import MagicMock, patch
import boto3
from moto import mock_aws

# ── Stubs (must be set before handler is loaded) ──────────────────────────────

class _FakeLogger:
    def __init__(self, *a, **kw): pass
    def info(self, *a, **kw): pass
    def warning(self, *a, **kw): pass
    def error(self, *a, **kw): pass
    def exception(self, *a, **kw): pass
    def set_correlation_id(self, *a, **kw): pass
    def inject_lambda_context(self, fn=None, **kw):
        # Handles both @logger.inject_lambda_context and @logger.inject_lambda_context(...)
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

if "pydantic" not in sys.modules:
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
    shared_mw.get_user_email = lambda event: event["requestContext"]["authorizer"]["claims"].get("email", "")
    shared_mw.parse_body = _parse_body
    shared_mw.now_iso = lambda: "2024-01-15T10:00:00+00:00"
    shared_mw.with_middleware = lambda fn: fn
    sys.modules["shared"] = shared_pkg
    sys.modules["shared.middleware"] = shared_mw

# ── Load handler ──────────────────────────────────────────────────────────────
_handler_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'applications', 'handler.py')
)
_spec = importlib.util.spec_from_file_location('applications_handler_int', _handler_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['applications_handler_int'] = _mod
_spec.loader.exec_module(_mod)

create_application = _mod.create_application
list_applications = _mod.list_applications
get_application = _mod.get_application
update_application = _mod.update_application
delete_application = _mod.delete_application
update_status = _mod.update_status

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_event(method='GET', path='/applications', path_params=None, body=None, user_id='user-int-123'):
    return {
        'httpMethod': method,
        'path': path,
        'pathParameters': path_params or {},
        'body': json.dumps(body) if body else None,
        'requestContext': {
            'authorizer': {
                'claims': {'sub': user_id, 'email': 'test@example.com'}
            }
        },
    }


def create_dynamodb_table(dynamodb_resource):
    return dynamodb_resource.create_table(
        TableName='applytic',
        KeySchema=[
            {'AttributeName': 'PK', 'KeyType': 'HASH'},
            {'AttributeName': 'SK', 'KeyType': 'RANGE'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'PK', 'AttributeType': 'S'},
            {'AttributeName': 'SK', 'AttributeType': 'S'},
            {'AttributeName': 'GSI1PK', 'AttributeType': 'S'},
            {'AttributeName': 'GSI1SK', 'AttributeType': 'S'},
        ],
        GlobalSecondaryIndexes=[{
            'IndexName': 'GSI1',
            'KeySchema': [
                {'AttributeName': 'GSI1PK', 'KeyType': 'HASH'},
                {'AttributeName': 'GSI1SK', 'KeyType': 'RANGE'},
            ],
            'Projection': {'ProjectionType': 'ALL'},
        }],
        BillingMode='PAY_PER_REQUEST',
    )


USER_ID = 'user-int-123'


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestCreateApplicationIntegration:

    def test_create_writes_application_item_to_dynamodb(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('applications_handler_int.table', table):
                result = create_application(USER_ID, {
                    'company': 'Stripe', 'role': 'ML Engineer', 'status': 'applied'
                }, make_event())
                assert result['statusCode'] == 201
                app_id = json.loads(result['body'])['application']['appId']
                item = table.get_item(Key={'PK': f'USER#{USER_ID}', 'SK': f'APP#{app_id}'})['Item']
                assert item['company'] == 'Stripe'
                assert item['role'] == 'ML Engineer'
                assert item['status'] == 'applied'

    def test_create_writes_correct_gsi1_keys(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('applications_handler_int.table', table):
                result = create_application(USER_ID, {
                    'company': 'Stripe', 'role': 'SWE', 'status': 'applied'
                }, make_event())
                app_id = json.loads(result['body'])['application']['appId']
                item = table.get_item(Key={'PK': f'USER#{USER_ID}', 'SK': f'APP#{app_id}'})['Item']
                assert item['GSI1PK'] == f'USER#{USER_ID}'
                assert item['GSI1SK'].startswith('DATE#')

    def test_create_writes_status_event_to_dynamodb(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('applications_handler_int.table', table):
                result = create_application(USER_ID, {
                    'company': 'Stripe', 'role': 'SWE', 'status': 'applied'
                }, make_event())
                app_id = json.loads(result['body'])['application']['appId']
                events = table.query(
                    KeyConditionExpression=boto3.dynamodb.conditions.Key('PK').eq(f'APP#{app_id}')
                )['Items']
                assert len(events) == 1
                assert events[0]['toStatus'] == 'applied'
                assert events[0]['fromStatus'] is None

    def test_create_stores_all_optional_fields(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('applications_handler_int.table', table):
                result = create_application(USER_ID, {
                    'company': 'Google', 'role': 'SWE', 'status': 'applied',
                    'source': 'referral', 'resumeVersion': 'v3', 'companySize': 'enterprise',
                    'notes': 'referred by friend', 'jobDescUrl': 'https://google.com/jobs'
                }, make_event())
                app_id = json.loads(result['body'])['application']['appId']
                item = table.get_item(Key={'PK': f'USER#{USER_ID}', 'SK': f'APP#{app_id}'})['Item']
                assert item['source'] == 'referral'
                assert item['resumeVersion'] == 'v3'
                assert item['companySize'] == 'enterprise'
                assert item['notes'] == 'referred by friend'

    def test_create_sets_entity_type(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('applications_handler_int.table', table):
                result = create_application(USER_ID, {
                    'company': 'Meta', 'role': 'Eng', 'status': 'applied'
                }, make_event())
                app_id = json.loads(result['body'])['application']['appId']
                item = table.get_item(Key={'PK': f'USER#{USER_ID}', 'SK': f'APP#{app_id}'})['Item']
                assert item['entityType'] == 'APPLICATION'


class TestListApplicationsIntegration:

    def test_list_returns_applications_via_gsi1(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('applications_handler_int.table', table):
                create_application(USER_ID, {'company': 'A', 'role': 'SWE', 'status': 'applied'}, make_event())
                create_application(USER_ID, {'company': 'B', 'role': 'SWE', 'status': 'applied'}, make_event())
                items, count = list_applications(USER_ID)
                assert count == 2
                companies = {item['company'] for item in items}
                assert companies == {'A', 'B'}

    def test_list_returns_empty_for_new_user(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('applications_handler_int.table', table):
                items, count = list_applications('new-user-999')
                assert items == []
                assert count == 0

    def test_list_isolates_by_user_id(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('applications_handler_int.table', table):
                create_application(USER_ID, {'company': 'MyCompany', 'role': 'SWE', 'status': 'applied'}, make_event())
                create_application('other-user', {'company': 'OtherCompany', 'role': 'SWE', 'status': 'applied'}, make_event('POST', '/applications', user_id='other-user'))
                items, count = list_applications(USER_ID)
                assert count == 1
                assert items[0]['company'] == 'MyCompany'


class TestGetApplicationIntegration:

    def test_get_returns_correct_item(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('applications_handler_int.table', table):
                created = create_application(USER_ID, {
                    'company': 'Anthropic', 'role': 'ML Eng', 'status': 'applied'
                }, make_event())
                app_id = json.loads(created['body'])['application']['appId']
                result = get_application(USER_ID, app_id, make_event())
                assert result['statusCode'] == 200
                body = json.loads(result['body'])
                assert body['application']['company'] == 'Anthropic'
                assert body['application']['appId'] == app_id

    def test_get_returns_404_for_nonexistent(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('applications_handler_int.table', table):
                result = get_application(USER_ID, 'nonexistent-app-id', make_event())
                assert result['statusCode'] == 404


class TestUpdateApplicationIntegration:

    def test_update_modifies_field_in_dynamodb(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('applications_handler_int.table', table):
                created = create_application(USER_ID, {
                    'company': 'OldName', 'role': 'SWE', 'status': 'applied'
                }, make_event())
                app_id = json.loads(created['body'])['application']['appId']
                result = update_application(USER_ID, app_id, {'company': 'NewName'}, make_event())
                assert result['statusCode'] == 200
                item = table.get_item(Key={'PK': f'USER#{USER_ID}', 'SK': f'APP#{app_id}'})['Item']
                assert item['company'] == 'NewName'

    def test_update_changes_updated_at_timestamp(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('applications_handler_int.table', table):
                created = create_application(USER_ID, {
                    'company': 'Corp', 'role': 'Eng', 'status': 'applied'
                }, make_event())
                app_id = json.loads(created['body'])['application']['appId']
                update_application(USER_ID, app_id, {'notes': 'updated notes'}, make_event())
                updated_item = table.get_item(Key={'PK': f'USER#{USER_ID}', 'SK': f'APP#{app_id}'})['Item']
                assert 'updatedAt' in updated_item


class TestUpdateStatusIntegration:

    def test_update_status_changes_status_in_dynamodb(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('applications_handler_int.table', table):
                created = create_application(USER_ID, {
                    'company': 'Figma', 'role': 'Eng', 'status': 'applied'
                }, make_event())
                app_id = json.loads(created['body'])['application']['appId']
                result = update_status(USER_ID, app_id, {'status': 'interview'}, make_event())
                assert result['statusCode'] == 200
                item = table.get_item(Key={'PK': f'USER#{USER_ID}', 'SK': f'APP#{app_id}'})['Item']
                assert item['status'] == 'interview'

    def test_update_status_writes_new_status_event(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('applications_handler_int.table', table):
                created = create_application(USER_ID, {
                    'company': 'Figma', 'role': 'Eng', 'status': 'applied'
                }, make_event())
                app_id = json.loads(created['body'])['application']['appId']
                update_status(USER_ID, app_id, {'status': 'screened'}, make_event())
                events = table.query(
                    KeyConditionExpression=boto3.dynamodb.conditions.Key('PK').eq(f'APP#{app_id}')
                )['Items']
                assert len(events) == 2
                statuses = {e['toStatus'] for e in events}
                assert 'applied' in statuses
                assert 'screened' in statuses

    def test_update_status_records_from_status_correctly(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('applications_handler_int.table', table):
                created = create_application(USER_ID, {
                    'company': 'Figma', 'role': 'Eng', 'status': 'applied'
                }, make_event())
                app_id = json.loads(created['body'])['application']['appId']
                update_status(USER_ID, app_id, {'status': 'interview'}, make_event())
                events = table.query(
                    KeyConditionExpression=boto3.dynamodb.conditions.Key('PK').eq(f'APP#{app_id}')
                )['Items']
                transition_event = next(e for e in events if e['toStatus'] == 'interview')
                assert transition_event['fromStatus'] == 'applied'


class TestDeleteApplicationIntegration:

    def test_delete_removes_item_from_dynamodb(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('applications_handler_int.table', table):
                created = create_application(USER_ID, {
                    'company': 'DeleteMe', 'role': 'Eng', 'status': 'applied'
                }, make_event())
                app_id = json.loads(created['body'])['application']['appId']
                result = delete_application(USER_ID, app_id, make_event())
                assert result['statusCode'] == 200
                item = table.get_item(Key={'PK': f'USER#{USER_ID}', 'SK': f'APP#{app_id}'}).get('Item')
                assert item is None

    def test_delete_item_no_longer_in_list(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('applications_handler_int.table', table):
                created = create_application(USER_ID, {
                    'company': 'DeleteMe', 'role': 'Eng', 'status': 'applied'
                }, make_event())
                app_id = json.loads(created['body'])['application']['appId']
                delete_application(USER_ID, app_id, make_event())
                items, count = list_applications(USER_ID)
                assert count == 0
                assert all(a['appId'] != app_id for a in items)
