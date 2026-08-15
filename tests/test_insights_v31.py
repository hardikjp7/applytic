"""
Tests for v3.1 salary analytics additions to Insights Lambda.
Covers: _compute_salary_distribution, _compute_salary_insights,
        that compute_patterns includes both new keys, and that
        build_context_for_llm includes a salary section when data exists.
Run: python -m pytest tests/test_insights_v31.py -v
"""
import sys
import os
import types
import importlib.util
from unittest.mock import MagicMock

# ── Stubs (same pattern as test_insights.py) ──────────────────────────────────

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

if "aws_xray_sdk" not in sys.modules:
    xray_mod = types.ModuleType("aws_xray_sdk")
    xray_core = types.ModuleType("aws_xray_sdk.core")
    xray_core.xray_recorder = MagicMock()
    sys.modules["aws_xray_sdk"] = xray_mod
    sys.modules["aws_xray_sdk.core"] = xray_core

if "shared" not in sys.modules:
    import json
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
    shared_mw.now_iso = lambda: "2024-01-01T00:00:00+00:00"
    shared_mw.with_middleware = lambda fn: fn
    sys.modules["shared"] = shared_pkg
    sys.modules["shared.middleware"] = shared_mw

# ── Load handler under a unique module name ───────────────────────────────────

_handler_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'insights', 'handler.py')
)
_spec = importlib.util.spec_from_file_location('insights_handler_v31', _handler_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['insights_handler_v31'] = _mod
_spec.loader.exec_module(_mod)

_compute_salary_distribution = _mod._compute_salary_distribution
_compute_salary_insights = _mod._compute_salary_insights
compute_patterns = _mod.compute_patterns
build_context_for_llm = _mod.build_context_for_llm

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_app(app_id: str, status: str = "applied", expected_salary=None, offered_salary=None,
             source: str = "linkedin", resume_version: str = "v1") -> dict:
    return {
        "appId": app_id,
        "userId": "test-user",
        "company": "Co",
        "role": "Eng",
        "status": status,
        "source": source,
        "resumeVersion": resume_version,
        "companySize": "startup",
        "dateApplied": "2024-01-01",
        "createdAt": "2024-01-01T00:00:00+00:00",
        "updatedAt": "2024-01-01T00:00:00+00:00",
        "entityType": "APPLICATION",
        "expectedSalary": expected_salary,
        "offeredSalary": offered_salary,
    }


# ── _compute_salary_distribution ───────────────────────────────────────────────

class TestComputeSalaryDistribution:

    def test_empty_apps_returns_empty_list(self):
        assert _compute_salary_distribution([]) == []

    def test_apps_without_expected_salary_excluded(self):
        apps = [make_app("a1"), make_app("a2")]
        assert _compute_salary_distribution(apps) == []

    def test_single_app_lands_in_correct_bucket(self):
        apps = [make_app("a1", expected_salary=125000)]
        result = _compute_salary_distribution(apps)
        assert len(result) == 1
        assert result[0]["range"] == "$120k-140k"
        assert result[0]["count"] == 1

    def test_multiple_apps_same_bucket_aggregated(self):
        apps = [
            make_app("a1", expected_salary=101000),
            make_app("a2", expected_salary=115000),
            make_app("a3", expected_salary=119999),
        ]
        result = _compute_salary_distribution(apps)
        assert len(result) == 1
        assert result[0]["range"] == "$100k-120k"
        assert result[0]["count"] == 3

    def test_buckets_sorted_ascending(self):
        apps = [
            make_app("a1", expected_salary=180000),
            make_app("a2", expected_salary=100000),
            make_app("a3", expected_salary=140000),
        ]
        result = _compute_salary_distribution(apps)
        ranges = [r["range"] for r in result]
        assert ranges == ["$100k-120k", "$140k-160k", "$180k-200k"]

    def test_apps_with_salary_and_without_mixed(self):
        apps = [
            make_app("a1", expected_salary=110000),
            make_app("a2"),  # no salary - excluded
        ]
        result = _compute_salary_distribution(apps)
        total = sum(r["count"] for r in result)
        assert total == 1

    def test_exact_bucket_boundary_value(self):
        apps = [make_app("a1", expected_salary=120000)]
        result = _compute_salary_distribution(apps)
        assert result[0]["range"] == "$120k-140k"


# ── _compute_salary_insights ───────────────────────────────────────────────────

class TestComputeSalaryInsights:

    def test_no_salary_data_returns_none_values(self):
        apps = [make_app("a1"), make_app("a2")]
        result = _compute_salary_insights(apps)
        assert result["avgExpectedSalary"] is None
        assert result["avgOfferedSalary"] is None
        assert result["offerVsExpectedDiff"] is None
        assert result["offerVsExpectedPct"] is None
        assert result["expectedCount"] == 0
        assert result["offeredCount"] == 0

    def test_avg_expected_salary_computed_correctly(self):
        apps = [
            make_app("a1", expected_salary=100000),
            make_app("a2", expected_salary=120000),
        ]
        result = _compute_salary_insights(apps)
        assert result["avgExpectedSalary"] == 110000
        assert result["expectedCount"] == 2

    def test_avg_offered_salary_computed_correctly(self):
        apps = [
            make_app("a1", status="offer", offered_salary=150000),
            make_app("a2", status="offer", offered_salary=170000),
        ]
        result = _compute_salary_insights(apps)
        assert result["avgOfferedSalary"] == 160000
        assert result["offeredCount"] == 2

    def test_offer_vs_expected_diff_positive(self):
        apps = [make_app("a1", status="offer", expected_salary=130000, offered_salary=145000)]
        result = _compute_salary_insights(apps)
        assert result["offerVsExpectedDiff"] == 15000
        assert result["offerVsExpectedPct"] == round(15000 / 130000 * 100, 1)

    def test_offer_vs_expected_diff_negative(self):
        apps = [make_app("a1", status="offer", expected_salary=150000, offered_salary=140000)]
        result = _compute_salary_insights(apps)
        assert result["offerVsExpectedDiff"] == -10000
        assert result["offerVsExpectedPct"] < 0

    def test_diff_only_computed_for_apps_with_both_fields(self):
        apps = [
            make_app("a1", expected_salary=100000),  # no offer - excluded from diff
            make_app("a2", status="offer", offered_salary=160000),  # no expectation - excluded from diff
            make_app("a3", status="offer", expected_salary=120000, offered_salary=135000),  # counts
        ]
        result = _compute_salary_insights(apps)
        assert result["offerVsExpectedDiff"] == 15000
        assert result["expectedCount"] == 2
        assert result["offeredCount"] == 2

    def test_expected_only_no_offers_yields_none_diff(self):
        apps = [make_app("a1", expected_salary=100000)]
        result = _compute_salary_insights(apps)
        assert result["avgExpectedSalary"] == 100000
        assert result["offerVsExpectedDiff"] is None

    def test_multiple_offers_diff_is_averaged(self):
        apps = [
            make_app("a1", status="offer", expected_salary=100000, offered_salary=110000),  # +10000
            make_app("a2", status="offer", expected_salary=100000, offered_salary=90000),   # -10000
        ]
        result = _compute_salary_insights(apps)
        assert result["offerVsExpectedDiff"] == 0


# ── compute_patterns (integration) ────────────────────────────────────────────

class TestComputePatternsV31Keys:

    def test_new_keys_present_in_output(self):
        apps = [make_app("a1", expected_salary=100000)]
        result = compute_patterns(apps)
        assert "salaryInsights" in result
        assert "salaryDistribution" in result

    def test_salary_insights_is_dict(self):
        apps = [make_app("a1", expected_salary=100000)]
        result = compute_patterns(apps)
        assert isinstance(result["salaryInsights"], dict)

    def test_salary_distribution_is_list(self):
        apps = [make_app("a1", expected_salary=100000)]
        result = compute_patterns(apps)
        assert isinstance(result["salaryDistribution"], list)

    def test_empty_apps_does_not_include_new_keys(self):
        result = compute_patterns([])
        assert "salaryInsights" not in result
        assert "salaryDistribution" not in result

    def test_apps_with_no_salary_data_still_returns_valid_shape(self):
        apps = [make_app("a1"), make_app("a2")]
        result = compute_patterns(apps)
        assert result["salaryDistribution"] == []
        assert result["salaryInsights"]["expectedCount"] == 0


# ── build_context_for_llm salary section ──────────────────────────────────────

class TestBuildContextForLlmSalarySection:

    def test_includes_salary_section_when_expected_present(self):
        apps = [make_app("a1", expected_salary=120000)]
        patterns = compute_patterns(apps)
        context = build_context_for_llm(apps, patterns)
        assert "Salary data" in context
        assert "$120,000" in context

    def test_includes_offer_comparison_when_both_present(self):
        apps = [make_app("a1", status="offer", expected_salary=120000, offered_salary=135000)]
        patterns = compute_patterns(apps)
        context = build_context_for_llm(apps, patterns)
        assert "offer vs expectation" in context
        assert "$15,000" in context or "+$15,000" in context

    def test_no_salary_section_when_no_salary_data(self):
        apps = [make_app("a1")]
        patterns = compute_patterns(apps)
        context = build_context_for_llm(apps, patterns)
        assert "Salary data" not in context

    def test_context_still_includes_existing_sections(self):
        apps = [
            make_app("a1", status="offer", expected_salary=120000, offered_salary=130000, source="referral"),
            make_app("a2", status="rejected", source="linkedin"),
        ]
        patterns = compute_patterns(apps)
        context = build_context_for_llm(apps, patterns)
        assert "Response rates by source channel" in context
        assert "Recent applications" in context
        assert "Salary data" in context