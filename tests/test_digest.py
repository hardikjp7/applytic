"""
Unit tests for Digest Lambda - v3.0
Fix: _FakeLogger.inject_lambda_context now handles both
     @logger.inject_lambda_context (no parens - fn passed directly)
     @logger.inject_lambda_context(...) (with parens - returns decorator)

v3.0 additions: detect_rejection_patterns, store_alerts tests.
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
detect_rejection_patterns = _mod.detect_rejection_patterns
store_alerts = _mod.store_alerts
MIN_APPS_FOR_ZERO_RESPONSE_ALERT = _mod.MIN_APPS_FOR_ZERO_RESPONSE_ALERT
RESPONSE_RATE_DROP_THRESHOLD_PP = _mod.RESPONSE_RATE_DROP_THRESHOLD_PP

# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_app(app_id, user_id, company, status, days_ago=3, resume_version='v1', source='linkedin', date_applied=None):
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    applied_date = date_applied or (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime('%Y-%m-%d')
    return {
        'appId': app_id,
        'userId': user_id,
        'company': company,
        'role': 'Software Engineer',
        'status': status,
        'source': source,
        'resumeVersion': resume_version,
        'companySize': 'startup',
        'dateApplied': applied_date,
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


def days_ago_str(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).strftime('%Y-%m-%d')


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

    # v3.0: alert section tests
    def test_no_alert_section_when_no_alerts(self):
        html = build_email_html(SAMPLE_APPS, SAMPLE_EVENTS, 'tip', 'user@test.com', alerts=[])
        assert 'Pattern alert' not in html

    def test_alert_section_renders_when_alerts_present(self):
        alerts = ["Your 'v1-generic' resume has a 0% response rate across 5 applications."]
        html = build_email_html(SAMPLE_APPS, SAMPLE_EVENTS, 'tip', 'user@test.com', alerts=alerts)
        assert 'Pattern alert' in html
        assert 'v1-generic' in html

    def test_multiple_alerts_all_rendered(self):
        alerts = ["Alert message one.", "Alert message two."]
        html = build_email_html(SAMPLE_APPS, SAMPLE_EVENTS, 'tip', 'user@test.com', alerts=alerts)
        assert 'Alert message one.' in html
        assert 'Alert message two.' in html

    def test_alerts_default_to_none_safely(self):
        # Calling without the alerts kwarg at all should not raise
        html = build_email_html(SAMPLE_APPS, SAMPLE_EVENTS, 'tip', 'user@test.com')
        assert isinstance(html, str)


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


# ── Tests: detect_rejection_patterns (v3.0) ───────────────────────────────────

class TestDetectRejectionPatterns:

    def test_empty_apps_returns_empty_list(self):
        assert detect_rejection_patterns('user-1', []) == []

    def test_no_alerts_when_data_insufficient(self):
        # Only 3 apps with a given resume version - below the 5-app minimum
        apps = [
            make_app(f'app-{i}', 'user-1', f'Co{i}', 'rejected', resume_version='v1-generic')
            for i in range(3)
        ]
        alerts = detect_rejection_patterns('user-1', apps)
        assert alerts == []

    def test_zero_response_resume_version_triggers_alert(self):
        apps = [
            make_app(f'app-{i}', 'user-1', f'Co{i}', 'rejected', resume_version='v1-generic')
            for i in range(MIN_APPS_FOR_ZERO_RESPONSE_ALERT)
        ]
        alerts = detect_rejection_patterns('user-1', apps)
        assert any('v1-generic' in a for a in alerts)

    def test_no_alert_when_resume_version_has_some_responses(self):
        apps = [
            make_app(f'app-{i}', 'user-1', f'Co{i}', 'rejected', resume_version='v2')
            for i in range(MIN_APPS_FOR_ZERO_RESPONSE_ALERT - 1)
        ]
        apps.append(make_app('app-resp', 'user-1', 'RespondedCo', 'interview', resume_version='v2'))
        alerts = detect_rejection_patterns('user-1', apps)
        assert not any('v2' in a for a in alerts)

    def test_zero_response_source_channel_triggers_alert(self):
        apps = [
            make_app(f'app-{i}', 'user-1', f'Co{i}', 'rejected', source='cold')
            for i in range(MIN_APPS_FOR_ZERO_RESPONSE_ALERT)
        ]
        alerts = detect_rejection_patterns('user-1', apps)
        assert any('cold' in a for a in alerts)

    def test_no_alert_when_source_channel_has_responses(self):
        apps = [
            make_app(f'app-{i}', 'user-1', f'Co{i}', 'offer', source='referral')
            for i in range(MIN_APPS_FOR_ZERO_RESPONSE_ALERT)
        ]
        alerts = detect_rejection_patterns('user-1', apps)
        assert not any('referral' in a for a in alerts)

    def test_response_rate_drop_triggers_alert(self):
        # Last week: 5 apps, all responded (100%)
        # This week: 5 apps, none responded (0%) -> 100pp drop, well above threshold
        apps = (
            [make_app(f'last-{i}', 'user-1', f'Co{i}', 'interview', resume_version='v3', source='referral', date_applied=days_ago_str(10)) for i in range(5)] +
            [make_app(f'this-{i}', 'user-1', f'Co{i}', 'applied', resume_version='v3', source='referral', date_applied=days_ago_str(2)) for i in range(5)]
        )
        alerts = detect_rejection_patterns('user-1', apps)
        assert any('dropped' in a.lower() for a in alerts)

    def test_no_drop_alert_when_rate_improves(self):
        # Last week: 0% response. This week: 100% response - improvement, no alert
        apps = (
            [make_app(f'last-{i}', 'user-1', f'Co{i}', 'rejected', resume_version='v3', source='referral', date_applied=days_ago_str(10)) for i in range(5)] +
            [make_app(f'this-{i}', 'user-1', f'Co{i}', 'offer', resume_version='v3', source='referral', date_applied=days_ago_str(2)) for i in range(5)]
        )
        alerts = detect_rejection_patterns('user-1', apps)
        assert not any('dropped' in a.lower() for a in alerts)

    def test_no_drop_alert_when_missing_one_week_of_data(self):
        # Only this week has apps, no last week data - can't compute a drop
        apps = [make_app(f'this-{i}', 'user-1', f'Co{i}', 'applied', date_applied=days_ago_str(2)) for i in range(5)]
        alerts = detect_rejection_patterns('user-1', apps)
        assert not any('dropped' in a.lower() for a in alerts)

    def test_multiple_patterns_can_fire_together(self):
        apps = [
            make_app(f'app-{i}', 'user-1', f'Co{i}', 'rejected', resume_version='v1-generic', source='cold')
            for i in range(MIN_APPS_FOR_ZERO_RESPONSE_ALERT)
        ]
        alerts = detect_rejection_patterns('user-1', apps)
        # Both resume version AND source channel alerts should fire since they're 0% together
        assert len(alerts) >= 2

    def test_handles_missing_resume_version_field(self):
        apps = [
            {**make_app(f'app-{i}', 'user-1', f'Co{i}', 'rejected'), 'resumeVersion': None}
            for i in range(MIN_APPS_FOR_ZERO_RESPONSE_ALERT)
        ]
        # Should not raise - falls back to 'default' bucket
        alerts = detect_rejection_patterns('user-1', apps)
        assert isinstance(alerts, list)

    def test_handles_missing_source_field(self):
        apps = [
            {**make_app(f'app-{i}', 'user-1', f'Co{i}', 'rejected'), 'source': None}
            for i in range(MIN_APPS_FOR_ZERO_RESPONSE_ALERT)
        ]
        alerts = detect_rejection_patterns('user-1', apps)
        assert isinstance(alerts, list)

    def test_handles_malformed_date_applied_gracefully(self):
        apps = [
            {**make_app('app-1', 'user-1', 'Co', 'applied'), 'dateApplied': 'not-a-date'}
        ]
        # Should not raise
        alerts = detect_rejection_patterns('user-1', apps)
        assert isinstance(alerts, list)


# ── Tests: store_alerts (v3.0) ─────────────────────────────────────────────────

class TestStoreAlerts:

    def test_writes_one_item_per_alert_message(self):
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        messages = ["Alert one.", "Alert two.", "Alert three."]
        with patch('digest_handler.table', mock_table):
            stored = store_alerts('user-1', messages)
        assert mock_table.put_item.call_count == 3
        assert len(stored) == 3

    def test_returns_empty_list_for_no_messages(self):
        mock_table = MagicMock()
        with patch('digest_handler.table', mock_table):
            stored = store_alerts('user-1', [])
        assert stored == []
        mock_table.put_item.assert_not_called()

    def test_stored_items_have_correct_pk_sk_pattern(self):
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        with patch('digest_handler.table', mock_table):
            stored = store_alerts('user-1', ["Test alert"])
        item = stored[0]
        assert item['PK'] == 'USER#user-1'
        assert item['SK'].startswith('ALERT#')

    def test_stored_items_have_dismissed_false_by_default(self):
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        with patch('digest_handler.table', mock_table):
            stored = store_alerts('user-1', ["Test alert"])
        assert stored[0]['dismissed'] is False

    def test_stored_items_have_ttl_set(self):
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        with patch('digest_handler.table', mock_table):
            stored = store_alerts('user-1', ["Test alert"])
        assert 'ttl' in stored[0]
        expected_ttl = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
        assert abs(stored[0]['ttl'] - expected_ttl) < 60

    def test_stored_items_have_entity_type_alert(self):
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        with patch('digest_handler.table', mock_table):
            stored = store_alerts('user-1', ["Test alert"])
        assert stored[0]['entityType'] == 'ALERT'

    def test_each_alert_has_unique_alert_id(self):
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        with patch('digest_handler.table', mock_table):
            stored = store_alerts('user-1', ["Alert A", "Alert B"])
        ids = [s['alertId'] for s in stored]
        assert len(ids) == len(set(ids))


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
             patch('digest_handler.detect_rejection_patterns', return_value=[]), \
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
             patch('digest_handler.detect_rejection_patterns', return_value=[]), \
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
             patch('digest_handler.detect_rejection_patterns', return_value=[]), \
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

    # v3.0: alert generation wired into the handler run
    def test_handler_calls_store_alerts_when_patterns_detected(self):
        with patch('digest_handler.get_active_users', return_value=[{'userId': 'user-1'}]), \
             patch('digest_handler.get_user_apps', return_value=SAMPLE_APPS), \
             patch('digest_handler.get_week_events', return_value=[]), \
             patch('digest_handler.generate_weekly_tip', return_value='tip'), \
             patch('digest_handler.detect_rejection_patterns', return_value=['Some alert message']), \
             patch('digest_handler.store_alerts') as mock_store_alerts, \
             patch('digest_handler.send_digest'), \
             patch('digest_handler.boto3') as mock_boto3, \
             patch.dict(os.environ, {'USER_POOL_ID': 'us-east-1_test'}):
            mock_boto3.client.return_value = self._make_cognito()
            lambda_handler({}, None)
        mock_store_alerts.assert_called_once_with('user-1', ['Some alert message'])

    def test_handler_does_not_call_store_alerts_when_no_patterns(self):
        with patch('digest_handler.get_active_users', return_value=[{'userId': 'user-1'}]), \
             patch('digest_handler.get_user_apps', return_value=SAMPLE_APPS), \
             patch('digest_handler.get_week_events', return_value=[]), \
             patch('digest_handler.generate_weekly_tip', return_value='tip'), \
             patch('digest_handler.detect_rejection_patterns', return_value=[]), \
             patch('digest_handler.store_alerts') as mock_store_alerts, \
             patch('digest_handler.send_digest'), \
             patch('digest_handler.boto3') as mock_boto3, \
             patch.dict(os.environ, {'USER_POOL_ID': 'us-east-1_test'}):
            mock_boto3.client.return_value = self._make_cognito()
            lambda_handler({}, None)
        mock_store_alerts.assert_not_called()

    def test_handler_reports_alerts_generated_count(self):
        with patch('digest_handler.get_active_users', return_value=[{'userId': 'user-1'}]), \
             patch('digest_handler.get_user_apps', return_value=SAMPLE_APPS), \
             patch('digest_handler.get_week_events', return_value=[]), \
             patch('digest_handler.generate_weekly_tip', return_value='tip'), \
             patch('digest_handler.detect_rejection_patterns', return_value=['Alert 1', 'Alert 2']), \
             patch('digest_handler.store_alerts'), \
             patch('digest_handler.send_digest'), \
             patch('digest_handler.boto3') as mock_boto3, \
             patch.dict(os.environ, {'USER_POOL_ID': 'us-east-1_test'}):
            mock_boto3.client.return_value = self._make_cognito()
            result = lambda_handler({}, None)
        body = json.loads(result['body'])
        assert body['alertsGenerated'] == 2

    def test_handler_passes_alerts_to_email_html(self):
        with patch('digest_handler.get_active_users', return_value=[{'userId': 'user-1'}]), \
             patch('digest_handler.get_user_apps', return_value=SAMPLE_APPS), \
             patch('digest_handler.get_week_events', return_value=[]), \
             patch('digest_handler.generate_weekly_tip', return_value='tip'), \
             patch('digest_handler.detect_rejection_patterns', return_value=['Alert message']), \
             patch('digest_handler.store_alerts'), \
             patch('digest_handler.build_email_html', wraps=_mod.build_email_html) as mock_build_html, \
             patch('digest_handler.send_digest'), \
             patch('digest_handler.boto3') as mock_boto3, \
             patch.dict(os.environ, {'USER_POOL_ID': 'us-east-1_test'}):
            mock_boto3.client.return_value = self._make_cognito()
            lambda_handler({}, None)
        call_kwargs = mock_build_html.call_args
        assert call_kwargs[1]['alerts'] == ['Alert message']
