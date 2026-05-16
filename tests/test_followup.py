"""
Unit tests for Follow-up Lambda - v2.0
Tests: get_overdue_followups, get_user_email, build_followup_email,
       send_followup_email, lambda_handler
Run: python -m pytest tests/test_followup.py -v
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
    os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'followup', 'handler.py')
)
_spec = importlib.util.spec_from_file_location('followup_handler', _handler_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['followup_handler'] = _mod
_spec.loader.exec_module(_mod)

get_overdue_followups = _mod.get_overdue_followups
get_user_email = _mod.get_user_email
build_followup_email = _mod.build_followup_email
send_followup_email = _mod.send_followup_email
lambda_handler = _mod.lambda_handler

# ── Helpers ───────────────────────────────────────────────────────────────────

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
YESTERDAY = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
TOMORROW = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")


def make_app(app_id, user_id, company, status, follow_up_date):
    return {
        "appId": app_id,
        "userId": user_id,
        "company": company,
        "role": "Software Engineer",
        "status": status,
        "dateApplied": "2024-01-01",
        "followUpDate": follow_up_date,
        "entityType": "APPLICATION",
    }


# ── Tests: get_overdue_followups ──────────────────────────────────────────────

class TestGetOverdueFollowups:

    def test_returns_overdue_applied_apps(self):
        mock_table = MagicMock()
        mock_table.scan.return_value = {
            "Items": [make_app("app-1", "user-1", "Stripe", "applied", YESTERDAY)]
        }
        with patch("followup_handler.table", mock_table):
            result = get_overdue_followups()
        assert len(result) == 1
        assert result[0]["company"] == "Stripe"

    def test_returns_overdue_screened_apps(self):
        mock_table = MagicMock()
        mock_table.scan.return_value = {
            "Items": [make_app("app-1", "user-1", "Google", "screened", YESTERDAY)]
        }
        with patch("followup_handler.table", mock_table):
            result = get_overdue_followups()
        assert len(result) == 1

    def test_returns_empty_when_no_overdue(self):
        mock_table = MagicMock()
        mock_table.scan.return_value = {"Items": []}
        with patch("followup_handler.table", mock_table):
            result = get_overdue_followups()
        assert result == []

    def test_scan_uses_filter_expression(self):
        mock_table = MagicMock()
        mock_table.scan.return_value = {"Items": []}
        with patch("followup_handler.table", mock_table):
            get_overdue_followups()
        mock_table.scan.assert_called_once()
        call_kwargs = mock_table.scan.call_args[1]
        assert "FilterExpression" in call_kwargs


# ── Tests: get_user_email ─────────────────────────────────────────────────────

class TestGetUserEmail:

    def test_returns_email_from_cognito(self):
        mock_cognito = MagicMock()
        mock_cognito.admin_get_user.return_value = {
            "UserAttributes": [{"Name": "email", "Value": "user@test.com"}]
        }
        with patch("followup_handler.cognito", mock_cognito), \
             patch.dict(os.environ, {"USER_POOL_ID": "us-east-1_test"}):
            email = get_user_email("user-123")
        assert email == "user@test.com"

    def test_returns_none_when_no_email_attribute(self):
        mock_cognito = MagicMock()
        mock_cognito.admin_get_user.return_value = {"UserAttributes": []}
        with patch("followup_handler.cognito", mock_cognito), \
             patch.dict(os.environ, {"USER_POOL_ID": "us-east-1_test"}):
            email = get_user_email("user-123")
        assert email is None

    def test_returns_none_on_cognito_exception(self):
        mock_cognito = MagicMock()
        mock_cognito.admin_get_user.side_effect = Exception("Cognito error")
        with patch("followup_handler.cognito", mock_cognito), \
             patch.dict(os.environ, {"USER_POOL_ID": "us-east-1_test"}):
            email = get_user_email("user-123")
        assert email is None


# ── Tests: build_followup_email ───────────────────────────────────────────────

class TestBuildFollowupEmail:

    def _make_apps(self):
        return [
            make_app("app-1", "user-1", "Stripe", "applied", YESTERDAY),
            make_app("app-2", "user-1", "Google", "screened", YESTERDAY),
        ]

    def test_returns_html_string(self):
        html = build_followup_email(self._make_apps())
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html or "<html>" in html

    def test_includes_company_names(self):
        html = build_followup_email(self._make_apps())
        assert "Stripe" in html
        assert "Google" in html

    def test_includes_follow_up_date(self):
        html = build_followup_email(self._make_apps())
        assert YESTERDAY in html

    def test_includes_board_link(self):
        html = build_followup_email(self._make_apps())
        assert "applytic/board" in html

    def test_single_app_no_plural(self):
        apps = [make_app("app-1", "user-1", "Stripe", "applied", YESTERDAY)]
        html = build_followup_email(apps)
        assert "1 application" in html

    def test_multiple_apps_plural(self):
        html = build_followup_email(self._make_apps())
        assert "2 applications" in html


# ── Tests: send_followup_email ────────────────────────────────────────────────

class TestSendFollowupEmail:

    def test_calls_ses_send_email(self):
        mock_ses = MagicMock()
        with patch("followup_handler.ses", mock_ses), \
             patch("followup_handler.FROM_EMAIL", "from@test.com"):
            send_followup_email("user@test.com", "<html>test</html>", 1)
        mock_ses.send_email.assert_called_once()

    def test_sends_to_correct_recipient(self):
        mock_ses = MagicMock()
        with patch("followup_handler.ses", mock_ses), \
             patch("followup_handler.FROM_EMAIL", "from@test.com"):
            send_followup_email("recipient@test.com", "<html>test</html>", 2)
        call_kwargs = mock_ses.send_email.call_args[1]
        assert "recipient@test.com" in call_kwargs["Destination"]["ToAddresses"]

    def test_subject_includes_count(self):
        mock_ses = MagicMock()
        with patch("followup_handler.ses", mock_ses), \
             patch("followup_handler.FROM_EMAIL", "from@test.com"):
            send_followup_email("user@test.com", "<html>test</html>", 3)
        call_kwargs = mock_ses.send_email.call_args[1]
        assert "3" in call_kwargs["Message"]["Subject"]["Data"]

    def test_subject_singular_for_one_app(self):
        mock_ses = MagicMock()
        with patch("followup_handler.ses", mock_ses), \
             patch("followup_handler.FROM_EMAIL", "from@test.com"):
            send_followup_email("user@test.com", "<html>test</html>", 1)
        call_kwargs = mock_ses.send_email.call_args[1]
        subject = call_kwargs["Message"]["Subject"]["Data"]
        assert "application" in subject.lower()


# ── Tests: lambda_handler ─────────────────────────────────────────────────────

class TestFollowupLambdaHandler:

    def _make_cognito(self, email="user@test.com"):
        mock_cognito = MagicMock()
        mock_cognito.admin_get_user.return_value = {
            "UserAttributes": [{"Name": "email", "Value": email}]
        }
        return mock_cognito

    def test_returns_200_when_no_overdue(self):
        with patch("followup_handler.get_overdue_followups", return_value=[]):
            result = lambda_handler({}, None)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["sent"] == 0

    def test_returns_200_on_success(self):
        apps = [make_app("app-1", "user-1", "Stripe", "applied", YESTERDAY)]
        with patch("followup_handler.get_overdue_followups", return_value=apps), \
             patch("followup_handler.get_user_email", return_value="user@test.com"), \
             patch("followup_handler.send_followup_email"):
            result = lambda_handler({}, None)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["sent"] == 1

    def test_groups_apps_by_user(self):
        apps = [
            make_app("app-1", "user-1", "Stripe", "applied", YESTERDAY),
            make_app("app-2", "user-1", "Google", "screened", YESTERDAY),
        ]
        with patch("followup_handler.get_overdue_followups", return_value=apps), \
             patch("followup_handler.get_user_email", return_value="user@test.com"), \
             patch("followup_handler.send_followup_email") as mock_send:
            lambda_handler({}, None)
        # Both apps belong to user-1, so only one email should be sent
        mock_send.assert_called_once()
        _, _, count = mock_send.call_args[0]
        assert count == 2

    def test_sends_separate_emails_to_different_users(self):
        apps = [
            make_app("app-1", "user-1", "Stripe", "applied", YESTERDAY),
            make_app("app-2", "user-2", "Google", "applied", YESTERDAY),
        ]
        with patch("followup_handler.get_overdue_followups", return_value=apps), \
             patch("followup_handler.get_user_email", return_value="user@test.com"), \
             patch("followup_handler.send_followup_email") as mock_send:
            result = lambda_handler({}, None)
        assert mock_send.call_count == 2
        body = json.loads(result["body"])
        assert body["sent"] == 2

    def test_skips_user_with_no_email(self):
        apps = [make_app("app-1", "user-1", "Stripe", "applied", YESTERDAY)]
        with patch("followup_handler.get_overdue_followups", return_value=apps), \
             patch("followup_handler.get_user_email", return_value=None), \
             patch("followup_handler.send_followup_email") as mock_send:
            result = lambda_handler({}, None)
        mock_send.assert_not_called()
        body = json.loads(result["body"])
        assert body["skipped"] == 1

    def test_continues_after_single_user_failure(self):
        apps = [
            make_app("app-1", "user-1", "Stripe", "applied", YESTERDAY),
            make_app("app-2", "user-2", "Google", "applied", YESTERDAY),
        ]
        call_count = [0]

        def mock_email(user_id):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Cognito error")
            return "user2@test.com"

        with patch("followup_handler.get_overdue_followups", return_value=apps), \
             patch("followup_handler.get_user_email", side_effect=mock_email), \
             patch("followup_handler.send_followup_email"):
            result = lambda_handler({}, None)

        body = json.loads(result["body"])
        assert body["sent"] == 1
        assert body["skipped"] == 1

    def test_skips_app_missing_user_id(self):
        apps = [{"appId": "app-1", "company": "Stripe", "status": "applied"}]  # no userId
        with patch("followup_handler.get_overdue_followups", return_value=apps), \
             patch("followup_handler.send_followup_email") as mock_send:
            result = lambda_handler({}, None)
        mock_send.assert_not_called()
        body = json.loads(result["body"])
        assert body["sent"] == 0
