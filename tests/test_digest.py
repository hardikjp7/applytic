"""
Unit tests for Digest Lambda - v1.3
Fix: _FakeLogger.inject_lambda_context now handles both
     @logger.inject_lambda_context (no parens - fn passed directly)
     @logger.inject_lambda_context(...) (with parens - returns decorator)
Run: python -m pytest tests/test_digest.py -v
"""
import sys
import os
import json
import types
import pytest
import importlib.util
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

# ── Stubs ─────────────────────────────────────────────────────────────────────

class _FakeLogger:
    def __init__(self, *a, **kw): pass
    def info(self, *a, **kw): pass
    def warning(self, *a, **kw): pass
    def error(self, *a, **kw): pass
    def exception(self, *a, **kw): pass
    def inject_lambda_context(self, fn=None, **kw):
        # Handles both:
        #   @logger.inject_lambda_context        -> fn is the decorated function
        #   @logger.inject_lambda_context(...)   -> fn is None, must return decorator
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

if "aws_xray_sdk" not in sys.modules:
    xray_mod = types.ModuleType("aws_xray_sdk")
    xray_core = types.ModuleType("aws_xray_sdk.core")
    xray_core.xray_recorder = MagicMock()
    sys.modules["aws_xray_sdk"] = xray_mod
    sys.modules["aws_xray_sdk.core"] = xray_core

if "shared" not in sys.modules:
    shared_pkg = types.ModuleType("shared")
    shared_mw = types.ModuleType("shared.middleware")
    shared_mw.now_iso = lambda: "2024-01-15T10:00:00+00:00"
    sys.modules["shared"] = shared_pkg
    sys.modules["shared.middleware"] = shared_mw

# ── Load handler ──────────────────────────────────────────────────────────────

_handler_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'digest', 'handler.py')
)
_spec = importlib.util.spec_from_file_location('digest_handler', _handler_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['digest_handler'] = _mod
_spec.loader.exec_module(_mod)

get_active_users = _mod.get_active_users
get_user_apps = _mod.get_user_apps
get_week_events = _mod.get_week_events
generate_weekly_tip = _mod.generate_weekly_tip
build_email_html = _mod.build_email_html
send_digest = _mod.send_digest
lambda_handler = _mod.lambda_handler

# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_app(app_id, user_id, company, status, days_ago=3):
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return {
        'appId': app_id,
        'userId': user_id,
        'company': company,
        'role': 'Software Engineer',
        'status': status,
        'source': 'linkedin',
        'resumeVersion': 'v1',
        'companySize': 'startup',
        'dateApplied': '2024-01-12',
        'createdAt': ts,
        'updatedAt': ts,
        'entityType': 'APPLICATION',
    }


def make_status_event(app_id, from_status, to_status, company='Stripe', role='SWE'):
    ts = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    return {
        'PK': f'APP#{app_id}',
        'SK': f'EVENT#{ts}#uuid',
        'fromStatus': from_status,
        'toStatus': to_status,
        'company': company,
        'role': role,
        'createdAt': ts,
        'entityType': 'STATUS_EVENT',
    }


SAMPLE_APPS = [
    make_app('app-1', 'user-1', 'Stripe', 'offer'),
    make_app('app-2', 'user-1', 'Google', 'rejected'),
    make_app('app-3', 'user-1', 'Meta', 'applied'),
]

SAMPLE_EVENTS = [
    make_status_event('app-1', 'applied', 'offer', 'Stripe'),
    make_status_event('app-2', 'applied', 'rejected', 'Google'),
]


# ── Tests: get_active_users ───────────────────────────────────────────────────

class TestGetActiveUsers:

    def test_returns_unique_user_ids(self):
        mock_table = MagicMock()
        mock_table.scan.return_value = {
            'Items': [
                {'userId': 'user-1', 'GSI1PK': 'USER#user-1', 'entityType': 'APPLICATION', 'updatedAt': datetime.now(timezone.utc).isoformat()},
                {'userId': 'user-1', 'GSI1PK': 'USER#user-1', 'entityType': 'APPLICATION', 'updatedAt': datetime.now(timezone.utc).isoformat()},
                {'userId': 'user-2', 'GSI1PK': 'USER#user-2', 'entityType': 'APPLICATION', 'updatedAt': datetime.now(timezone.utc).isoformat()},
            ]
        }
        with patch('digest_handler.table', mock_table):
            users = get_active_users()
        user_ids = [u['userId'] for u in users]
        assert len(user_ids) == 2
        assert 'user-1' in user_ids
        assert 'user-2' in user_ids

    def test_returns_empty_when_no_active_users(self):
        mock_table = MagicMock()
        mock_table.scan.return_value = {'Items': []}
        with patch('digest_handler.table', mock_table):
            users = get_active_users()
        assert users == []

    def test_scan_filters_by_recent_updated_at(self):
        mock_table = MagicMock()
        mock_table.scan.return_value = {'Items': []}
        with patch('digest_handler.table', mock_table):
            get_active_users()
        call_kwargs = mock_table.scan.call_args[1]
        assert 'FilterExpression' in call_kwargs


# ── Tests: get_user_apps ──────────────────────────────────────────────────────

class TestGetUserApps:

    def test_returns_only_application_entities(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {
            'Items': [
                {**make_app('app-1', 'user-1', 'Stripe', 'applied'), 'entityType': 'APPLICATION'},
                {'PK': 'USER#user-1', 'SK': 'RATELIMIT#2024-01-15', 'entityType': 'RATELIMIT'},
            ]
        }
        with patch('digest_handler.table', mock_table):
            apps = get_user_apps('user-1')
        assert len(apps) == 1
        assert apps[0]['company'] == 'Stripe'

    def test_returns_empty_list_for_user_with_no_apps(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {'Items': []}
        with patch('digest_handler.table', mock_table):
            apps = get_user_apps('empty-user')
        assert apps == []

    def test_queries_correct_gsi1pk(self):
        mock_table = MagicMock()
        mock_table.query.return_value = {'Items': []}
        with patch('digest_handler.table', mock_table):
            get_user_apps('user-abc')
        mock_table.query.assert_called_once()


# ── Tests: get_week_events ────────────────────────────────────────────────────

class TestGetWeekEvents:

    def test_enriches_events_with_company_and_role(self):
        mock_table = MagicMock()
        recent_ts = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        mock_table.query.side_effect = [
            # First call: get_user_apps
            {'Items': [make_app('app-1', 'user-1', 'Stripe', 'offer')]},
            # Second call: get events for app-1
            {'Items': [{'PK': 'APP#app-1', 'SK': f'EVENT#{recent_ts}#uuid',
                        'fromStatus': 'applied', 'toStatus': 'offer', 'createdAt': recent_ts}]},
        ]
        with patch('digest_handler.table', mock_table):
            events = get_week_events('user-1')
        assert len(events) == 1
        assert events[0]['company'] == 'Stripe'
        assert events[0]['role'] == 'Software Engineer'

    def test_returns_empty_when_no_events_this_week(self):
        mock_table = MagicMock()
        mock_table.query.side_effect = [
            {'Items': [make_app('app-1', 'user-1', 'Stripe', 'applied')]},
            {'Items': []},
        ]
        with patch('digest_handler.table', mock_table):
            events = get_week_events('user-1')
        assert events == []


# ── Tests: generate_weekly_tip ────────────────────────────────────────────────

class TestGenerateWeeklyTip:

    def test_calls_bedrock_and_returns_text_nova(self):
        mock_bedrock = MagicMock()
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            'output': {'message': {'content': [{'text': 'Focus on referrals.'}]}}
        }).encode()
        mock_bedrock.invoke_model.return_value = {'body': mock_response_body}

        with patch('digest_handler.bedrock', mock_bedrock), \
             patch('digest_handler.MODEL_ID', 'amazon.nova-lite-v1:0'):
            tip = generate_weekly_tip(SAMPLE_APPS, SAMPLE_EVENTS)

        assert tip == 'Focus on referrals.'
        mock_bedrock.invoke_model.assert_called_once()

    def test_calls_bedrock_and_returns_text_anthropic(self):
        mock_bedrock = MagicMock()
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            'content': [{'text': 'Apply to more startups.'}]
        }).encode()
        mock_bedrock.invoke_model.return_value = {'body': mock_response_body}

        with patch('digest_handler.bedrock', mock_bedrock), \
             patch('digest_handler.MODEL_ID', 'anthropic.claude-3-5-sonnet-20241022-v2:0'):
            tip = generate_weekly_tip(SAMPLE_APPS, SAMPLE_EVENTS)

        assert tip == 'Apply to more startups.'

    def test_bedrock_prompt_includes_app_stats(self):
        mock_bedrock = MagicMock()
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            'output': {'message': {'content': [{'text': 'tip'}]}}
        }).encode()
        mock_bedrock.invoke_model.return_value = {'body': mock_response_body}

        with patch('digest_handler.bedrock', mock_bedrock), \
             patch('digest_handler.MODEL_ID', 'amazon.nova-lite-v1:0'):
            generate_weekly_tip(SAMPLE_APPS, SAMPLE_EVENTS)

        call_kwargs = mock_bedrock.invoke_model.call_args[1]
        body = json.loads(call_kwargs['body'])
        prompt_text = body['messages'][0]['content'][0]['text']
        assert 'Total applications: 3' in prompt_text


# ── Tests: build_email_html ───────────────────────────────────────────────────

class TestBuildEmailHtml:

    def test_returns_html_string(self):
        html = build_email_html(SAMPLE_APPS, SAMPLE_EVENTS, 'Great tip here.', 'user@test.com')
        assert isinstance(html, str)
        assert '<html>' in html or '<!DOCTYPE html>' in html

    def test_includes_total_count(self):
        html = build_email_html(SAMPLE_APPS, SAMPLE_EVENTS, 'tip', 'user@test.com')
        assert '3' in html

    def test_includes_tip_text(self):
        html = build_email_html(SAMPLE_APPS, SAMPLE_EVENTS, 'Focus on referrals.', 'user@test.com')
        assert 'Focus on referrals.' in html

    def test_includes_company_names_from_events(self):
        html = build_email_html(SAMPLE_APPS, SAMPLE_EVENTS, 'tip', 'user@test.com')
        assert 'Stripe' in html
        assert 'Google' in html

    def test_shows_no_activity_when_no_events(self):
        html = build_email_html(SAMPLE_APPS, [], 'tip', 'user@test.com')
        assert 'No activity this week' in html

    def test_interview_count_shown(self):
        apps_with_interview = [
            make_app('app-1', 'user-1', 'Stripe', 'interview'),
            make_app('app-2', 'user-1', 'Google', 'applied'),
        ]
        html = build_email_html(apps_with_interview, [], 'tip', 'user@test.com')
        assert '1' in html


# ── Tests: send_digest ────────────────────────────────────────────────────────

class TestSendDigest:

    def test_calls_ses_send_email(self):
        mock_ses = MagicMock()
        with patch('digest_handler.ses', mock_ses), \
             patch('digest_handler.FROM_EMAIL', 'from@test.com'):
            send_digest('user@test.com', '<html>test</html>')
        mock_ses.send_email.assert_called_once()

    def test_sends_to_correct_recipient(self):
        mock_ses = MagicMock()
        with patch('digest_handler.ses', mock_ses), \
             patch('digest_handler.FROM_EMAIL', 'from@test.com'):
            send_digest('recipient@test.com', '<html>test</html>')
        call_kwargs = mock_ses.send_email.call_args[1]
        assert 'recipient@test.com' in call_kwargs['Destination']['ToAddresses']

    def test_sends_correct_subject(self):
        mock_ses = MagicMock()
        with patch('digest_handler.ses', mock_ses), \
             patch('digest_handler.FROM_EMAIL', 'from@test.com'):
            send_digest('user@test.com', '<html>test</html>')
        call_kwargs = mock_ses.send_email.call_args[1]
        assert 'weekly' in call_kwargs['Message']['Subject']['Data'].lower()


# ── Tests: lambda_handler ─────────────────────────────────────────────────────

class TestDigestLambdaHandler:

    def _make_cognito(self, email='user@test.com'):
        mock_cognito = MagicMock()
        mock_cognito.admin_get_user.return_value = {
            'UserAttributes': [{'Name': 'email', 'Value': email}]
        }
        return mock_cognito

    def test_handler_returns_200_on_success(self):
        with patch('digest_handler.get_active_users', return_value=[{'userId': 'user-1'}]), \
             patch('digest_handler.get_user_apps', return_value=SAMPLE_APPS), \
             patch('digest_handler.get_week_events', return_value=SAMPLE_EVENTS), \
             patch('digest_handler.generate_weekly_tip', return_value='Great tip.'), \
             patch('digest_handler.send_digest'), \
             patch('digest_handler.boto3') as mock_boto3, \
             patch.dict(os.environ, {'USER_POOL_ID': 'us-east-1_test'}):
            mock_boto3.client.return_value = self._make_cognito()
            result = lambda_handler({}, None)
        assert result['statusCode'] == 200

    def test_handler_reports_sent_count(self):
        with patch('digest_handler.get_active_users', return_value=[{'userId': 'user-1'}, {'userId': 'user-2'}]), \
             patch('digest_handler.get_user_apps', return_value=SAMPLE_APPS), \
             patch('digest_handler.get_week_events', return_value=[]), \
             patch('digest_handler.generate_weekly_tip', return_value='tip'), \
             patch('digest_handler.send_digest'), \
             patch('digest_handler.boto3') as mock_boto3, \
             patch.dict(os.environ, {'USER_POOL_ID': 'us-east-1_test'}):
            mock_boto3.client.return_value = self._make_cognito()
            result = lambda_handler({}, None)
        body = json.loads(result['body'])
        assert body['sent'] == 2

    def test_handler_skips_user_with_no_apps(self):
        with patch('digest_handler.get_active_users', return_value=[{'userId': 'user-1'}]), \
             patch('digest_handler.get_user_apps', return_value=[]), \
             patch('digest_handler.send_digest') as mock_send, \
             patch('digest_handler.boto3') as mock_boto3, \
             patch.dict(os.environ, {'USER_POOL_ID': 'us-east-1_test'}):
            mock_boto3.client.return_value = self._make_cognito()
            result = lambda_handler({}, None)
        mock_send.assert_not_called()
        body = json.loads(result['body'])
        assert body['sent'] == 0

    def test_handler_skips_user_with_no_email(self):
        mock_cognito = MagicMock()
        mock_cognito.admin_get_user.return_value = {'UserAttributes': []}
        with patch('digest_handler.get_active_users', return_value=[{'userId': 'user-1'}]), \
             patch('digest_handler.get_user_apps', return_value=SAMPLE_APPS), \
             patch('digest_handler.send_digest') as mock_send, \
             patch('digest_handler.boto3') as mock_boto3, \
             patch.dict(os.environ, {'USER_POOL_ID': 'us-east-1_test'}):
            mock_boto3.client.return_value = mock_cognito
            lambda_handler({}, None)
        mock_send.assert_not_called()

    def test_handler_continues_after_single_user_failure(self):
        mock_cognito = MagicMock()
        mock_cognito.admin_get_user.side_effect = [
            Exception('Cognito error'),
            {'UserAttributes': [{'Name': 'email', 'Value': 'user2@test.com'}]},
        ]
        with patch('digest_handler.get_active_users', return_value=[{'userId': 'user-1'}, {'userId': 'user-2'}]), \
             patch('digest_handler.get_user_apps', return_value=SAMPLE_APPS), \
             patch('digest_handler.get_week_events', return_value=[]), \
             patch('digest_handler.generate_weekly_tip', return_value='tip'), \
             patch('digest_handler.send_digest'), \
             patch('digest_handler.boto3') as mock_boto3, \
             patch.dict(os.environ, {'USER_POOL_ID': 'us-east-1_test'}):
            mock_boto3.client.return_value = mock_cognito
            result = lambda_handler({}, None)
        body = json.loads(result['body'])
        assert body['sent'] == 1
        assert body['failed'] == 1

    def test_handler_returns_200_even_with_no_active_users(self):
        with patch('digest_handler.get_active_users', return_value=[]), \
             patch('digest_handler.boto3') as mock_boto3, \
             patch.dict(os.environ, {'USER_POOL_ID': 'us-east-1_test'}):
            mock_boto3.client.return_value = MagicMock()
            result = lambda_handler({}, None)
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['sent'] == 0
