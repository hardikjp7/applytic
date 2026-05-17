import os
import json
import pytest
from datetime import datetime, timezone, timedelta

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
