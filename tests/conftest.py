"""
Shared pytest fixtures for Applytic Lambda tests.
"""
import os
import pytest
import json
from datetime import datetime, timezone, timedelta

# Set env vars before any Lambda handler is imported —
# boto3 reads these at module-level init time
os.environ.setdefault('AWS_DEFAULT_REGION', 'us-east-1')
os.environ.setdefault('AWS_ACCESS_KEY_ID', 'test')
os.environ.setdefault('AWS_SECRET_ACCESS_KEY', 'test')
os.environ.setdefault('TABLE_NAME', 'applytic')
os.environ.setdefault('RESUME_BUCKET', 'applytic-resumes-test')
os.environ.setdefault('USER_POOL_ID', 'us-east-1_test')
os.environ.setdefault('BEDROCK_MODEL_ID', 'amazon.nova-lite-v1:0')
os.environ.setdefault('LOG_LEVEL', 'INFO')
os.environ.setdefault('POWERTOOLS_SERVICE_NAME', 'applytic')


def make_event(method='GET', path='/applications', path_params=None, body=None, user_id='test-user-123'):
    """Build a mock API Gateway event."""
    return {
        'httpMethod': method,
        'path': path,
        'pathParameters': path_params or {},
        'body': json.dumps(body) if body else None,
        'requestContext': {
            'authorizer': {
                'claims': {
                    'sub': user_id,
                    'email': 'test@example.com',
                }
            }
        },
    }


def days_ago(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()


@pytest.fixture
def user_id():
    return 'test-user-123'


@pytest.fixture
def sample_applications():
    """Realistic set of applications that mirrors the seed data patterns."""
    return [
        # Offers — referral + v3-ml-focused
        {
            'appId': 'app-1', 'userId': 'test-user-123',
            'company': 'Stripe', 'role': 'Senior ML Engineer',
            'status': 'offer', 'source': 'referral',
            'resumeVersion': 'v3-ml-focused', 'companySize': 'mid',
            'dateApplied': '2024-01-10', 'createdAt': days_ago(5),
            'updatedAt': days_ago(2), 'entityType': 'APPLICATION',
        },
        # Interviews
        {
            'appId': 'app-2', 'userId': 'test-user-123',
            'company': 'Anthropic', 'role': 'ML Engineer',
            'status': 'interview', 'source': 'linkedin',
            'resumeVersion': 'v3-ml-focused', 'companySize': 'startup',
            'dateApplied': '2024-01-08', 'createdAt': days_ago(8),
            'updatedAt': days_ago(3), 'entityType': 'APPLICATION',
        },
        {
            'appId': 'app-3', 'userId': 'test-user-123',
            'company': 'Notion', 'role': 'Senior Engineer',
            'status': 'interview', 'source': 'referral',
            'resumeVersion': 'v3-ml-focused', 'companySize': 'startup',
            'dateApplied': '2024-01-05', 'createdAt': days_ago(12),
            'updatedAt': days_ago(4), 'entityType': 'APPLICATION',
        },
        # Applied
        {
            'appId': 'app-4', 'userId': 'test-user-123',
            'company': 'Databricks', 'role': 'ML Platform Engineer',
            'status': 'applied', 'source': 'linkedin',
            'resumeVersion': 'v3-ml-focused', 'companySize': 'mid',
            'dateApplied': '2024-01-15', 'createdAt': days_ago(3),
            'updatedAt': days_ago(3), 'entityType': 'APPLICATION',
        },
        # Rejections — enterprise + v1-generic
        {
            'appId': 'app-5', 'userId': 'test-user-123',
            'company': 'Google', 'role': 'L5 Software Engineer',
            'status': 'rejected', 'source': 'linkedin',
            'resumeVersion': 'v1-generic', 'companySize': 'enterprise',
            'dateApplied': '2023-12-20', 'createdAt': days_ago(25),
            'updatedAt': days_ago(20), 'entityType': 'APPLICATION',
        },
        {
            'appId': 'app-6', 'userId': 'test-user-123',
            'company': 'Meta', 'role': 'Software Engineer E5',
            'status': 'rejected', 'source': 'linkedin',
            'resumeVersion': 'v1-generic', 'companySize': 'enterprise',
            'dateApplied': '2023-12-15', 'createdAt': days_ago(30),
            'updatedAt': days_ago(25), 'entityType': 'APPLICATION',
        },
        {
            'appId': 'app-7', 'userId': 'test-user-123',
            'company': 'Amazon', 'role': 'SDE II',
            'status': 'rejected', 'source': 'job-board',
            'resumeVersion': 'v1-generic', 'companySize': 'enterprise',
            'dateApplied': '2023-12-10', 'createdAt': days_ago(35),
            'updatedAt': days_ago(28), 'entityType': 'APPLICATION',
        },
        {
            'appId': 'app-8', 'userId': 'test-user-123',
            'company': 'Uber', 'role': 'Senior ML Engineer',
            'status': 'rejected', 'source': 'linkedin',
            'resumeVersion': 'v2-fullstack', 'companySize': 'enterprise',
            'dateApplied': '2023-12-05', 'createdAt': days_ago(40),
            'updatedAt': days_ago(35), 'entityType': 'APPLICATION',
        },
    ]
