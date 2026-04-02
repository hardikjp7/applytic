"""
Tests for the Insights Lambda — pattern analysis engine.

These tests cover the core ML logic: response rate computation,
breakdown by dimension, highlights detection, and LLM context building.

Run with:
    pip install pytest
    pytest tests/test_insights.py -v
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambdas', 'insights'))

from insights_handler import compute_patterns, build_context_for_llm


class TestComputePatterns:

    def test_empty_applications_returns_message(self):
        result = compute_patterns([])
        assert 'message' in result

    def test_summary_counts_are_correct(self, sample_applications):
        result = compute_patterns(sample_applications)
        assert result['summary']['total'] == 8
        assert result['summary']['byStatus']['rejected'] == 4
        assert result['summary']['byStatus']['interview'] == 2
        assert result['summary']['byStatus']['offer'] == 1
        assert result['summary']['byStatus']['applied'] == 1

    def test_response_rate_excludes_applied_and_rejected(self, sample_applications):
        # responded = screened + interview + offer = 0 + 2 + 1 = 3 out of 8
        result = compute_patterns(sample_applications)
        expected = round(3 / 8 * 100, 1)
        assert result['summary']['responseRate'] == expected

    def test_offer_rate_is_correct(self, sample_applications):
        result = compute_patterns(sample_applications)
        expected = round(1 / 8 * 100, 1)
        assert result['summary']['offerRate'] == expected

    def test_breakdown_by_source_contains_all_sources(self, sample_applications):
        result = compute_patterns(sample_applications)
        sources = result['breakdowns']['bySource']
        assert 'linkedin' in sources
        assert 'referral' in sources
        assert 'job-board' in sources

    def test_referral_has_highest_response_rate(self, sample_applications):
        """Referrals (app-1 offer + app-3 interview) should beat LinkedIn."""
        result = compute_patterns(sample_applications)
        sources = result['breakdowns']['bySource']
        referral_rate = sources['referral']['responseRate']
        linkedin_rate = sources['linkedin']['responseRate']
        assert referral_rate > linkedin_rate

    def test_v3_resume_outperforms_v1(self, sample_applications):
        """v3-ml-focused should have higher response rate than v1-generic."""
        result = compute_patterns(sample_applications)
        versions = result['breakdowns']['byResumeVersion']
        assert versions['v3-ml-focused']['responseRate'] > versions['v1-generic']['responseRate']

    def test_v1_generic_has_zero_response_rate(self, sample_applications):
        """All v1-generic apps are rejected — response rate should be 0."""
        result = compute_patterns(sample_applications)
        versions = result['breakdowns']['byResumeVersion']
        assert versions['v1-generic']['responseRate'] == 0.0

    def test_enterprise_companies_have_low_response_rate(self, sample_applications):
        """Enterprise rejections should drag enterprise response rate below startup."""
        result = compute_patterns(sample_applications)
        sizes = result['breakdowns']['byCompanySize']
        enterprise_rate = sizes.get('enterprise', {}).get('responseRate', 0)
        startup_rate = sizes.get('startup', {}).get('responseRate', 100)
        assert enterprise_rate < startup_rate

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
            assert data['responseRate'] <= 100.0, f"{source} response rate > 100"

    def test_response_rate_never_below_zero(self, sample_applications):
        result = compute_patterns(sample_applications)
        for source, data in result['breakdowns']['bySource'].items():
            assert data['responseRate'] >= 0.0, f"{source} response rate < 0"

    def test_velocity_returns_4_weeks(self, sample_applications):
        result = compute_patterns(sample_applications)
        assert len(result['velocity']) == 4

    def test_breakdown_totals_match_per_source(self, sample_applications):
        """Sum of all source totals should equal total applications."""
        result = compute_patterns(sample_applications)
        source_total = sum(d['total'] for d in result['breakdowns']['bySource'].values())
        assert source_total == result['summary']['total']

    def test_single_application_does_not_crash(self):
        apps = [{
            'appId': 'x', 'userId': 'u', 'company': 'Acme', 'role': 'Engineer',
            'status': 'applied', 'source': 'linkedin', 'resumeVersion': 'v1',
            'companySize': 'startup', 'dateApplied': '2024-01-01',
            'createdAt': '2024-01-01T00:00:00+00:00',
            'updatedAt': '2024-01-01T00:00:00+00:00', 'entityType': 'APPLICATION',
        }]
        result = compute_patterns(apps)
        assert result['summary']['total'] == 1
        assert result['summary']['responseRate'] == 0.0

    def test_all_offers_gives_100_percent_response_rate(self):
        apps = [
            {
                'appId': f'app-{i}', 'userId': 'u', 'company': f'Co{i}', 'role': 'Eng',
                'status': 'offer', 'source': 'referral', 'resumeVersion': 'v1',
                'companySize': 'startup', 'dateApplied': '2024-01-01',
                'createdAt': '2024-01-01T00:00:00+00:00',
                'updatedAt': '2024-01-01T00:00:00+00:00', 'entityType': 'APPLICATION',
            }
            for i in range(5)
        ]
        result = compute_patterns(apps)
        assert result['summary']['responseRate'] == 100.0


class TestBuildContextForLlm:

    def test_context_includes_total(self, sample_applications):
        patterns = compute_patterns(sample_applications)
        context = build_context_for_llm(sample_applications, patterns)
        assert 'Total applications: 8' in context

    def test_context_includes_response_rate(self, sample_applications):
        patterns = compute_patterns(sample_applications)
        context = build_context_for_llm(sample_applications, patterns)
        assert 'response rate' in context.lower()

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
        assert isinstance(context, str)
        assert len(context) > 100

    def test_context_caps_recent_apps_at_20(self):
        """Context should not grow unbounded for large datasets."""
        apps = [
            {
                'appId': f'app-{i}', 'userId': 'u', 'company': f'Co{i}', 'role': 'Eng',
                'status': 'applied', 'source': 'linkedin', 'resumeVersion': 'v1',
                'companySize': 'startup', 'dateApplied': '2024-01-01',
                'createdAt': f'2024-01-{str(i % 28 + 1).zfill(2)}T00:00:00+00:00',
                'updatedAt': f'2024-01-{str(i % 28 + 1).zfill(2)}T00:00:00+00:00',
                'entityType': 'APPLICATION',
            }
            for i in range(50)
        ]
        patterns = compute_patterns(apps)
        context = build_context_for_llm(apps, patterns)
        # Count company mentions — should be capped at 20 recent apps
        company_lines = [l for l in context.split('\n') if 'Co' in l and '|' in l]
        assert len(company_lines) <= 20
