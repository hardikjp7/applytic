"""
Tests for the Insights Lambda — v1.2
Run: python -m pytest tests/test_insights.py -v
"""
import sys, os, json, types, pytest, importlib.util
from unittest.mock import MagicMock

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
    return {"statusCode": status, "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}, "body": json.dumps(body, default=str)}

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
        return {}, _resp(400, {"error": "Invalid JSON body"}, event)
shared_mw.parse_body = _mock_parse_body

shared_mw.now_iso = lambda: "2024-01-01T00:00:00+00:00"
shared_mw.with_middleware = lambda fn: fn
sys.modules["shared"] = shared_pkg
sys.modules["shared.middleware"] = shared_mw

_handler_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'insights', 'handler.py'))
_spec = importlib.util.spec_from_file_location('insights_handler', _handler_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['insights_handler'] = _mod
_spec.loader.exec_module(_mod)

compute_patterns = _mod.compute_patterns
build_context_for_llm = _mod.build_context_for_llm


class TestComputePatterns:

    def test_empty_applications_returns_message(self):
        assert 'message' in compute_patterns([])

    def test_summary_counts_are_correct(self, sample_applications):
        result = compute_patterns(sample_applications)
        assert result['summary']['total'] == 8
        assert result['summary']['byStatus']['rejected'] == 4
        assert result['summary']['byStatus']['interview'] == 2
        assert result['summary']['byStatus']['offer'] == 1
        assert result['summary']['byStatus']['applied'] == 1

    def test_response_rate_excludes_applied_and_rejected(self, sample_applications):
        result = compute_patterns(sample_applications)
        assert result['summary']['responseRate'] == round(3 / 8 * 100, 1)

    def test_offer_rate_is_correct(self, sample_applications):
        result = compute_patterns(sample_applications)
        assert result['summary']['offerRate'] == round(1 / 8 * 100, 1)

    def test_breakdown_by_source_contains_all_sources(self, sample_applications):
        result = compute_patterns(sample_applications)
        sources = result['breakdowns']['bySource']
        assert 'linkedin' in sources
        assert 'referral' in sources
        assert 'job-board' in sources

    def test_referral_has_highest_response_rate(self, sample_applications):
        result = compute_patterns(sample_applications)
        sources = result['breakdowns']['bySource']
        assert sources['referral']['responseRate'] > sources['linkedin']['responseRate']

    def test_v3_resume_outperforms_v1(self, sample_applications):
        result = compute_patterns(sample_applications)
        versions = result['breakdowns']['byResumeVersion']
        assert versions['v3-ml-focused']['responseRate'] > versions['v1-generic']['responseRate']

    def test_v1_generic_has_zero_response_rate(self, sample_applications):
        result = compute_patterns(sample_applications)
        assert result['breakdowns']['byResumeVersion']['v1-generic']['responseRate'] == 0.0

    def test_enterprise_companies_have_low_response_rate(self, sample_applications):
        result = compute_patterns(sample_applications)
        sizes = result['breakdowns']['byCompanySize']
        assert sizes.get('enterprise', {}).get('responseRate', 0) < sizes.get('startup', {}).get('responseRate', 100)

    def test_highlights_best_source_is_referral(self, sample_applications):
        result = compute_patterns(sample_applications)
        assert result['highlights']['bestSource'] is not None
        assert result['highlights']['bestSource']['name'] == 'referral'

    def test_highlights_best_resume_is_v3(self, sample_applications):
        result = compute_patterns(sample_applications)
        assert result['highlights']['bestResumeVersion'] is not None
        assert result['highlights']['bestResumeVersion']['name'] == 'v3-ml-focused'

    def test_response_rate_never_exceeds_100(self, sample_applications):
        result = compute_patterns(sample_applications)
        for source, data in result['breakdowns']['bySource'].items():
            assert data['responseRate'] <= 100.0

    def test_response_rate_never_below_zero(self, sample_applications):
        result = compute_patterns(sample_applications)
        for source, data in result['breakdowns']['bySource'].items():
            assert data['responseRate'] >= 0.0

    def test_velocity_returns_4_weeks(self, sample_applications):
        assert len(compute_patterns(sample_applications)['velocity']) == 4

    def test_breakdown_totals_match_per_source(self, sample_applications):
        result = compute_patterns(sample_applications)
        source_total = sum(d['total'] for d in result['breakdowns']['bySource'].values())
        assert source_total == result['summary']['total']

    def test_single_application_does_not_crash(self):
        apps = [{'appId': 'x', 'userId': 'u', 'company': 'Acme', 'role': 'Eng',
                 'status': 'applied', 'source': 'linkedin', 'resumeVersion': 'v1',
                 'companySize': 'startup', 'dateApplied': '2024-01-01',
                 'createdAt': '2024-01-01T00:00:00+00:00', 'updatedAt': '2024-01-01T00:00:00+00:00',
                 'entityType': 'APPLICATION'}]
        result = compute_patterns(apps)
        assert result['summary']['total'] == 1
        assert result['summary']['responseRate'] == 0.0

    def test_all_offers_gives_100_percent_response_rate(self):
        apps = [{'appId': f'app-{i}', 'userId': 'u', 'company': f'Co{i}', 'role': 'Eng',
                 'status': 'offer', 'source': 'referral', 'resumeVersion': 'v1',
                 'companySize': 'startup', 'dateApplied': '2024-01-01',
                 'createdAt': '2024-01-01T00:00:00+00:00', 'updatedAt': '2024-01-01T00:00:00+00:00',
                 'entityType': 'APPLICATION'} for i in range(5)]
        assert compute_patterns(apps)['summary']['responseRate'] == 100.0


class TestBuildContextForLlm:

    def test_context_includes_total(self, sample_applications):
        patterns = compute_patterns(sample_applications)
        assert 'Total applications: 8' in build_context_for_llm(sample_applications, patterns)

    def test_context_includes_response_rate(self, sample_applications):
        patterns = compute_patterns(sample_applications)
        assert 'response rate' in build_context_for_llm(sample_applications, patterns).lower()

    def test_context_includes_source_breakdown(self, sample_applications):
        patterns = compute_patterns(sample_applications)
        context = build_context_for_llm(sample_applications, patterns)
        assert 'referral' in context
        assert 'linkedin' in context

    def test_context_includes_resume_versions(self, sample_applications):
        patterns = compute_patterns(sample_applications)
        context = build_context_for_llm(sample_applications, patterns)
        assert 'v3-ml-focused' in context
        assert 'v1-generic' in context

    def test_context_is_string(self, sample_applications):
        patterns = compute_patterns(sample_applications)
        context = build_context_for_llm(sample_applications, patterns)
        assert isinstance(context, str) and len(context) > 100

    def test_context_caps_recent_apps_at_20(self):
        apps = [{'appId': f'app-{i}', 'userId': 'u', 'company': f'Co{i}', 'role': 'Eng',
                 'status': 'applied', 'source': 'linkedin', 'resumeVersion': 'v1',
                 'companySize': 'startup', 'dateApplied': '2024-01-01',
                 'createdAt': f'2024-01-{str(i % 28 + 1).zfill(2)}T00:00:00+00:00',
                 'updatedAt': f'2024-01-{str(i % 28 + 1).zfill(2)}T00:00:00+00:00',
                 'entityType': 'APPLICATION'} for i in range(50)]
        patterns = compute_patterns(apps)
        context = build_context_for_llm(apps, patterns)
        company_lines = [l for l in context.split('\n') if 'Co' in l and '|' in l]
        assert len(company_lines) <= 20
