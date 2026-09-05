"""
Tests for v3.1.1 currency-aware salary analytics additions to Insights Lambda.
Covers: _get_salary_currency, _determine_dominant_currency,
        currency-aware _compute_salary_distribution / _compute_salary_insights,
        and the currency-aware build_context_for_llm salary section.
Run: python -m pytest tests/test_insights_v311.py -v
"""
import sys
import os
import types
import importlib.util
from unittest.mock import MagicMock

# ── Stubs (same pattern as test_insights_v31.py) ──────────────────────────────

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
_spec = importlib.util.spec_from_file_location('insights_handler_v311', _handler_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['insights_handler_v311'] = _mod
_spec.loader.exec_module(_mod)

_get_salary_currency = _mod._get_salary_currency
_determine_dominant_currency = _mod._determine_dominant_currency
_compute_salary_distribution = _mod._compute_salary_distribution
_compute_salary_insights = _mod._compute_salary_insights
compute_patterns = _mod.compute_patterns
build_context_for_llm = _mod.build_context_for_llm

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_app(app_id: str, status: str = "applied", expected_salary=None, offered_salary=None,
             currency=None, source: str = "linkedin", resume_version: str = "v1") -> dict:
    app = {
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
    if currency is not None:
        app["salaryCurrency"] = currency
    return app


# ── _get_salary_currency ────────────────────────────────────────────────────

class TestGetSalaryCurrency:

    def test_returns_stored_currency(self):
        app = make_app("a1", expected_salary=100000, currency="INR")
        assert _get_salary_currency(app) == "INR"

    def test_defaults_to_usd_when_missing(self):
        # simulates a pre-v3.1.1 record with no salaryCurrency field at all
        app = make_app("a1", expected_salary=100000)
        assert _get_salary_currency(app) == "USD"

    def test_defaults_to_usd_when_none(self):
        app = make_app("a1", expected_salary=100000)
        app["salaryCurrency"] = None
        assert _get_salary_currency(app) == "USD"


# ── _determine_dominant_currency ────────────────────────────────────────────

class TestDetermineDominantCurrency:

    def test_empty_list_returns_none(self):
        assert _determine_dominant_currency([]) == None

    def test_single_currency(self):
        apps = [make_app("a1", expected_salary=100000, currency="INR")]
        assert _determine_dominant_currency(apps) == "INR"

    def test_majority_currency_wins(self):
        apps = [
            make_app("a1", expected_salary=100000, currency="USD"),
            make_app("a2", expected_salary=110000, currency="USD"),
            make_app("a3", expected_salary=2500000, currency="INR"),
        ]
        assert _determine_dominant_currency(apps) == "USD"

    def test_apps_without_explicit_currency_count_as_usd(self):
        apps = [
            make_app("a1", expected_salary=100000),  # no currency set -> USD
            make_app("a2", expected_salary=110000),  # no currency set -> USD
            make_app("a3", expected_salary=2500000, currency="INR"),
        ]
        assert _determine_dominant_currency(apps) == "USD"


# ── _compute_salary_insights (currency-aware) ───────────────────────────────

class TestComputeSalaryInsightsCurrencyAware:

    def test_no_salary_data_returns_none_currency(self):
        apps = [make_app("a1"), make_app("a2")]
        result = _compute_salary_insights(apps)
        assert result["dominantCurrency"] is None
        assert result["excludedCurrencyCount"] == 0

    def test_all_same_currency_no_exclusions(self):
        apps = [
            make_app("a1", expected_salary=100000, currency="USD"),
            make_app("a2", expected_salary=120000, currency="USD"),
        ]
        result = _compute_salary_insights(apps)
        assert result["dominantCurrency"] == "USD"
        assert result["excludedCurrencyCount"] == 0
        assert result["avgExpectedSalary"] == 110000

    def test_minority_currency_excluded_from_averages(self):
        apps = [
            make_app("a1", expected_salary=100000, currency="USD"),
            make_app("a2", expected_salary=120000, currency="USD"),
            make_app("a3", expected_salary=2500000, currency="INR"),
        ]
        result = _compute_salary_insights(apps)
        assert result["dominantCurrency"] == "USD"
        assert result["excludedCurrencyCount"] == 1
        # average should only reflect the two USD apps, not the INR one
        assert result["avgExpectedSalary"] == 110000
        assert result["expectedCount"] == 2

    def test_offer_vs_expected_only_within_dominant_currency(self):
        apps = [
            make_app("a1", status="offer", expected_salary=100000, offered_salary=115000, currency="USD"),
            make_app("a2", status="offer", expected_salary=2500000, offered_salary=1800000, currency="INR"),
        ]
        result = _compute_salary_insights(apps)
        assert result["dominantCurrency"] == "USD"
        assert result["offerVsExpectedDiff"] == 15000
        assert result["excludedCurrencyCount"] == 1

    def test_tied_currencies_still_returns_a_single_dominant_currency(self):
        apps = [
            make_app("a1", expected_salary=100000, currency="USD"),
            make_app("a2", expected_salary=2500000, currency="INR"),
        ]
        result = _compute_salary_insights(apps)
        assert result["dominantCurrency"] in ("USD", "INR")
        assert result["excludedCurrencyCount"] == 1


# ── _compute_salary_distribution (currency-aware) ───────────────────────────

class TestComputeSalaryDistributionCurrencyAware:

    def test_excludes_non_dominant_currency_apps(self):
        apps = [
            make_app("a1", expected_salary=100000, currency="USD"),
            make_app("a2", expected_salary=110000, currency="USD"),
            make_app("a3", expected_salary=2500000, currency="INR"),
        ]
        result = _compute_salary_distribution(apps)
        total = sum(r["count"] for r in result)
        assert total == 2

    def test_uses_inr_specific_bucket_size(self):
        apps = [
            make_app("a1", expected_salary=2500000, currency="INR"),
            make_app("a2", expected_salary=2600000, currency="INR"),
        ]
        result = _compute_salary_distribution(apps)
        assert len(result) == 1
        # 2,500,000 // 500,000 = 5 -> bucket starts at 2,500,000
        assert result[0]["range"] == "2500k-3000k"
        assert result[0]["count"] == 2

    def test_usd_bucket_size_unchanged_from_v31(self):
        apps = [make_app("a1", expected_salary=125000, currency="USD")]
        result = _compute_salary_distribution(apps)
        assert result[0]["range"] == "120k-140k"

    def test_no_salary_data_returns_empty_list(self):
        apps = [make_app("a1"), make_app("a2")]
        assert _compute_salary_distribution(apps) == []


# ── compute_patterns integration ────────────────────────────────────────────

class TestComputePatternsCurrencyKeys:

    def test_salary_insights_includes_currency_keys(self):
        apps = [make_app("a1", expected_salary=100000, currency="USD")]
        result = compute_patterns(apps)
        assert "dominantCurrency" in result["salaryInsights"]
        assert "excludedCurrencyCount" in result["salaryInsights"]

    def test_mixed_currency_pipeline_end_to_end(self):
        apps = [
            make_app("a1", expected_salary=100000, currency="USD"),
            make_app("a2", expected_salary=105000, currency="USD"),
            make_app("a3", expected_salary=2500000, currency="INR"),
        ]
        result = compute_patterns(apps)
        assert result["salaryInsights"]["dominantCurrency"] == "USD"
        assert result["salaryInsights"]["excludedCurrencyCount"] == 1
        assert sum(r["count"] for r in result["salaryDistribution"]) == 2


# ── build_context_for_llm currency-aware section ────────────────────────────

class TestBuildContextForLlmCurrencyAware:

    def test_includes_currency_label(self):
        apps = [make_app("a1", expected_salary=2500000, currency="INR")]
        patterns = compute_patterns(apps)
        context = build_context_for_llm(apps, patterns)
        assert "in INR" in context
        assert "2,500,000 INR" in context

    def test_notes_excluded_currency_count_when_present(self):
        apps = [
            make_app("a1", expected_salary=100000, currency="USD"),
            make_app("a2", expected_salary=2500000, currency="INR"),
        ]
        patterns = compute_patterns(apps)
        context = build_context_for_llm(apps, patterns)
        assert "excluded from these stats" in context
        assert "1 application" in context

    def test_no_exclusion_note_when_single_currency(self):
        apps = [make_app("a1", expected_salary=100000, currency="USD")]
        patterns = compute_patterns(apps)
        context = build_context_for_llm(apps, patterns)
        assert "excluded from these stats" not in context

    def test_defaults_to_usd_label_when_currency_unset(self):
        apps = [make_app("a1", expected_salary=100000)]
        patterns = compute_patterns(apps)
        context = build_context_for_llm(apps, patterns)
        assert "in USD" in context