"""
Integration tests for Insights Lambda - v1.3
Uses moto to mock DynamoDB - tests real handler-to-database interactions.
Fix: patches module-level `table` inside each mock_aws() context so moto intercepts calls.
Fix: rate limit remaining calculation corrected to match handler logic.
Run: python -m pytest tests/test_insights_integration.py -v
"""
import sys
import os
import json
import types
import pytest
import importlib.util
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
import boto3
from moto import mock_aws

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
    os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'insights', 'handler.py')
)
_spec = importlib.util.spec_from_file_location('insights_handler_int', _handler_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['insights_handler_int'] = _mod
_spec.loader.exec_module(_mod)

fetch_all_applications = _mod.fetch_all_applications
check_rate_limit = _mod.check_rate_limit
lambda_handler = _mod.lambda_handler
CHAT_DAILY_LIMIT = _mod.CHAT_DAILY_LIMIT

# ── Helpers ───────────────────────────────────────────────────────────────────

USER_ID = 'insights-int-user'


def make_event(method='GET', path='/insights', body=None, user_id=USER_ID):
    return {
        'httpMethod': method,
        'path': path,
        'pathParameters': {},
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


def seed_application(table, user_id, app_id, company, status, source='linkedin', resume='v1', size='startup', days_ago=5):
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    date_applied = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime('%Y-%m-%d')
    table.put_item(Item={
        'PK': f'USER#{user_id}',
        'SK': f'APP#{app_id}',
        'GSI1PK': f'USER#{user_id}',
        'GSI1SK': f'DATE#{ts}',
        'appId': app_id,
        'userId': user_id,
        'company': company,
        'role': 'Software Engineer',
        'status': status,
        'source': source,
        'resumeVersion': resume,
        'companySize': size,
        'dateApplied': date_applied,
        'createdAt': ts,
        'updatedAt': ts,
        'entityType': 'APPLICATION',
        'notes': '',
        'jobDescUrl': '',
    })


# ── Tests: fetch_all_applications ─────────────────────────────────────────────

class TestFetchAllApplicationsIntegration:

    def test_returns_applications_for_user(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            seed_application(table, USER_ID, 'app-1', 'Stripe', 'offer', source='referral')
            seed_application(table, USER_ID, 'app-2', 'Google', 'rejected', source='linkedin')
            with patch('insights_handler_int.table', table):
                apps = fetch_all_applications(USER_ID)
            assert len(apps) == 2

    def test_returns_empty_for_user_with_no_apps(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('insights_handler_int.table', table):
                apps = fetch_all_applications('empty-user')
            assert apps == []

    def test_only_returns_application_entities(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            seed_application(table, USER_ID, 'app-1', 'Stripe', 'applied')
            # Insert a rate limit record - should NOT be returned
            table.put_item(Item={
                'PK': f'USER#{USER_ID}',
                'SK': 'RATELIMIT#2024-01-15',
                'GSI1PK': f'USER#{USER_ID}',
                'GSI1SK': 'DATE#2024-01-15T10:00:00+00:00',
                'count': 5,
                'entityType': 'RATELIMIT',
            })
            with patch('insights_handler_int.table', table):
                apps = fetch_all_applications(USER_ID)
            assert len(apps) == 1
            assert apps[0]['entityType'] == 'APPLICATION'

    def test_isolates_by_user_id(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            seed_application(table, USER_ID, 'app-1', 'MyCompany', 'applied')
            seed_application(table, 'other-user', 'app-2', 'TheirCompany', 'applied')
            with patch('insights_handler_int.table', table):
                apps = fetch_all_applications(USER_ID)
            assert len(apps) == 1
            assert apps[0]['company'] == 'MyCompany'

    def test_returns_all_statuses(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            for i, status in enumerate(['applied', 'screened', 'interview', 'offer', 'rejected', 'withdrawn']):
                seed_application(table, USER_ID, f'app-{i}', f'Co{i}', status)
            with patch('insights_handler_int.table', table):
                apps = fetch_all_applications(USER_ID)
            assert len(apps) == 6
            statuses = {a['status'] for a in apps}
            assert statuses == {'applied', 'screened', 'interview', 'offer', 'rejected', 'withdrawn'}


# ── Tests: check_rate_limit ───────────────────────────────────────────────────

class TestRateLimitIntegration:

    def test_first_request_is_allowed(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('insights_handler_int.table', table):
                allowed, remaining = check_rate_limit(USER_ID)
            assert allowed is True
            # After 1 call: remaining = max(0, 20 - 1) = 19
            assert remaining == 19

    def test_counter_increments_on_each_call(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('insights_handler_int.table', table):
                check_rate_limit(USER_ID)
                check_rate_limit(USER_ID)
                _, remaining = check_rate_limit(USER_ID)
            # After 3 calls: remaining = max(0, 20 - 3) = 17
            assert remaining == 17

    def test_rate_limit_blocks_after_limit_exceeded(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('insights_handler_int.table', table):
                for _ in range(20):
                    check_rate_limit(USER_ID)
                # 21st call - count becomes 21, which exceeds limit of 20
                allowed, remaining = check_rate_limit(USER_ID)
            assert allowed is False
            assert remaining == 0

    def test_rate_limit_is_per_user(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('insights_handler_int.table', table):
                for _ in range(20):
                    check_rate_limit(USER_ID)
                # Different user should still be allowed
                allowed, _ = check_rate_limit('different-user')
            assert allowed is True

    def test_rate_limit_record_has_ttl_set(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('insights_handler_int.table', table):
                check_rate_limit(USER_ID)
            today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            item = table.get_item(
                Key={'PK': f'RATELIMIT#{USER_ID}', 'SK': f'DATE#{today}'}
            ).get('Item')
            assert item is not None
            assert 'ttl' in item
            expected_ttl = int((datetime.now(timezone.utc) + timedelta(days=2)).timestamp())
            assert abs(item['ttl'] - expected_ttl) < 60


# ── Tests: lambda_handler ─────────────────────────────────────────────────────

class TestInsightsHandlerIntegration:

    def test_get_insights_returns_patterns_from_real_data(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            seed_application(table, USER_ID, 'app-1', 'Stripe', 'offer', source='referral', resume='v3')
            seed_application(table, USER_ID, 'app-2', 'Google', 'rejected', source='linkedin', resume='v1')
            seed_application(table, USER_ID, 'app-3', 'Meta', 'applied', source='linkedin', resume='v1')
            with patch('insights_handler_int.table', table):
                result = lambda_handler(make_event('GET', '/insights'), None)
            assert result['statusCode'] == 200
            body = json.loads(result['body'])
            assert body['applicationCount'] == 3
            assert body['patterns']['summary']['total'] == 3

    def test_get_insights_response_rate_reflects_real_data(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            # 1 offer (responded), 1 rejected, 1 applied = 1/3 response rate
            seed_application(table, USER_ID, 'app-1', 'Stripe', 'offer')
            seed_application(table, USER_ID, 'app-2', 'Google', 'rejected')
            seed_application(table, USER_ID, 'app-3', 'Meta', 'applied')
            with patch('insights_handler_int.table', table):
                result = lambda_handler(make_event('GET', '/insights'), None)
            body = json.loads(result['body'])
            expected_rate = round(1 / 3 * 100, 1)
            assert body['patterns']['summary']['responseRate'] == expected_rate

    def test_get_insights_empty_user_returns_message(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            with patch('insights_handler_int.table', table):
                result = lambda_handler(make_event('GET', '/insights'), None)
            assert result['statusCode'] == 200
            body = json.loads(result['body'])
            assert 'message' in body['patterns']

    def test_post_chat_insufficient_data_returns_guidance(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            seed_application(table, USER_ID, 'app-1', 'Stripe', 'applied')
            seed_application(table, USER_ID, 'app-2', 'Google', 'applied')
            # Only 2 apps - below the 3 app minimum
            with patch('insights_handler_int.table', table):
                result = lambda_handler(
                    make_event('POST', '/insights/chat', body={'message': 'what should I do?'}),
                    None
                )
            assert result['statusCode'] == 200
            body = json.loads(result['body'])
            assert body.get('dataInsufficient') is True

    def test_post_chat_rate_limited_returns_429(self):
        with mock_aws():
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = create_dynamodb_table(dynamodb)
            for i in range(5):
                seed_application(table, USER_ID, f'app-{i}', f'Co{i}', 'offer')
            with patch('insights_handler_int.table', table):
                # Exhaust rate limit inside the same mock context
                for _ in range(20):
                    check_rate_limit(USER_ID)
                with patch('insights_handler_int.chat_with_coach', return_value='mocked reply'):
                    result = lambda_handler(
                        make_event('POST', '/insights/chat', body={'message': 'help me'}),
                        None
                    )
            assert result['statusCode'] == 429
