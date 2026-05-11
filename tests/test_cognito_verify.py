"""
Unit tests for Cognito Post Confirmation Lambda - v1.3
Run: python -m pytest tests/test_cognito_verify.py -v
"""
import sys
import os
import json
import types
import pytest
import importlib.util
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

# ── Stubs ─────────────────────────────────────────────────────────────────────

class _FakeLogger:
    def __init__(self, *a, **kw): pass
    def info(self, *a, **kw): pass
    def warning(self, *a, **kw): pass
    def error(self, *a, **kw): pass
    def exception(self, *a, **kw): pass

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

# ── Load handler ──────────────────────────────────────────────────────────────

_handler_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'cognito_verify', 'handler.py')
)
_spec = importlib.util.spec_from_file_location('cognito_verify_handler', _handler_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['cognito_verify_handler'] = _mod
_spec.loader.exec_module(_mod)

lambda_handler = _mod.lambda_handler

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_cognito_event(email='user@example.com', trigger_source='PostConfirmation_ConfirmSignUp'):
    return {
        'triggerSource': trigger_source,
        'request': {
            'userAttributes': {
                'email': email,
                'sub': 'test-user-sub-123',
            }
        },
        'response': {}
    }


def make_ses_client_error(code='MessageRejected'):
    error = ClientError(
        {'Error': {'Code': code, 'Message': 'mock error'}},
        'VerifyEmailIdentity'
    )
    return error


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestCognitoVerifyHandler:

    def test_always_returns_event_unchanged(self):
        mock_ses = MagicMock()
        mock_ses.get_identity_verification_attributes.return_value = {
            'VerificationAttributes': {}
        }
        event = make_cognito_event()
        with patch('cognito_verify_handler.ses', mock_ses):
            result = lambda_handler(event, None)
        assert result is event

    def test_calls_ses_verify_for_unverified_email(self):
        mock_ses = MagicMock()
        mock_ses.get_identity_verification_attributes.return_value = {
            'VerificationAttributes': {}  # Not verified
        }
        event = make_cognito_event('newuser@example.com')
        with patch('cognito_verify_handler.ses', mock_ses):
            lambda_handler(event, None)
        mock_ses.verify_email_identity.assert_called_once_with(
            EmailAddress='newuser@example.com'
        )

    def test_skips_verification_for_already_verified_email(self):
        mock_ses = MagicMock()
        mock_ses.get_identity_verification_attributes.return_value = {
            'VerificationAttributes': {
                'verified@example.com': {'VerificationStatus': 'Success'}
            }
        }
        event = make_cognito_event('verified@example.com')
        with patch('cognito_verify_handler.ses', mock_ses):
            lambda_handler(event, None)
        mock_ses.verify_email_identity.assert_not_called()

    def test_returns_event_when_no_email_in_attributes(self):
        mock_ses = MagicMock()
        event = {
            'triggerSource': 'PostConfirmation_ConfirmSignUp',
            'request': {'userAttributes': {}},  # No email
            'response': {}
        }
        with patch('cognito_verify_handler.ses', mock_ses):
            result = lambda_handler(event, None)
        assert result is event
        mock_ses.verify_email_identity.assert_not_called()

    def test_does_not_raise_on_ses_client_error(self):
        mock_ses = MagicMock()
        mock_ses.get_identity_verification_attributes.return_value = {
            'VerificationAttributes': {}
        }
        mock_ses.verify_email_identity.side_effect = make_ses_client_error()
        mock_ses.exceptions.ClientError = ClientError
        event = make_cognito_event()
        with patch('cognito_verify_handler.ses', mock_ses):
            # Should not raise - must never block signup
            result = lambda_handler(event, None)
        assert result is event

    def test_does_not_raise_on_unexpected_exception(self):
        mock_ses = MagicMock()
        mock_ses.get_identity_verification_attributes.side_effect = Exception('Unexpected!')
        event = make_cognito_event()
        with patch('cognito_verify_handler.ses', mock_ses):
            # Must never block signup
            result = lambda_handler(event, None)
        assert result is event

    def test_does_not_raise_when_check_verification_fails(self):
        mock_ses = MagicMock()
        mock_ses.get_identity_verification_attributes.side_effect = Exception('Check failed')
        mock_ses.get_identity_verification_attributes.return_value = {
            'VerificationAttributes': {}
        }
        event = make_cognito_event()
        with patch('cognito_verify_handler.ses', mock_ses):
            result = lambda_handler(event, None)
        assert result is event

    def test_handles_pending_verification_status(self):
        mock_ses = MagicMock()
        mock_ses.get_identity_verification_attributes.return_value = {
            'VerificationAttributes': {
                'pending@example.com': {'VerificationStatus': 'Pending'}
            }
        }
        event = make_cognito_event('pending@example.com')
        with patch('cognito_verify_handler.ses', mock_ses):
            lambda_handler(event, None)
        # Pending is not 'Success' so should re-verify
        mock_ses.verify_email_identity.assert_called_once()

    def test_returns_event_unchanged_with_all_original_fields(self):
        mock_ses = MagicMock()
        mock_ses.get_identity_verification_attributes.return_value = {
            'VerificationAttributes': {}
        }
        event = make_cognito_event('user@example.com')
        event['customField'] = 'should_be_preserved'
        with patch('cognito_verify_handler.ses', mock_ses):
            result = lambda_handler(event, None)
        assert result['customField'] == 'should_be_preserved'
        assert result['triggerSource'] == 'PostConfirmation_ConfirmSignUp'
