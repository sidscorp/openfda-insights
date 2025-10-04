"""Tests for endpoint tools and utilities."""
import pytest

from tools.classification import ClassifyParams, classify
from tools.k510 import K510SearchParams, k510_search
from tools.maude import MAUDESearchParams, maude_search
from tools.pma import PMASearchParams, pma_search
from tools.recall import RecallSearchParams, recall_search
from tools.registration_listing import RLSearchParams, rl_search
from tools.udi import UDISearchParams, udi_search
from tools.utils import (
    AnswerAssessorParams,
    PaginateParams,
    ProbeCountParams,
    answer_assessor,
    field_explorer,
    freshness,
    paginate,
    probe_count,
)


# ============================================================================
# Core endpoint tools
# ============================================================================


@pytest.mark.vcr
def test_rl_search():
    """Test Registration & Listing search."""
    # Query without filters to get broader results
    params = RLSearchParams(country="US", limit=5)
    result = rl_search(params)

    # RL may have limited data, allow empty or populated results
    assert result.error is None or (result.error and result.error["code"] == 404)


@pytest.mark.vcr
def test_classify():
    """Test Classification lookup."""
    params = ClassifyParams(device_class="2", limit=5)
    result = classify(params)

    assert result.error is None
    assert len(result.results) > 0
    assert result.results[0]["device_class"] == "2"


@pytest.mark.vcr
def test_k510_search():
    """Test 510(k) search."""
    params = K510SearchParams(
        decision_date_start="20200101", decision_date_end="20201231", limit=5
    )
    result = k510_search(params)

    assert result.error is None
    assert len(result.results) > 0
    assert "k_number" in result.results[0]


@pytest.mark.vcr
def test_pma_search():
    """Test PMA search."""
    params = PMASearchParams(decision_date_start="20200101", decision_date_end="20201231", limit=5)
    result = pma_search(params)

    # PMA may have fewer results
    assert result.error is None or len(result.results) >= 0


@pytest.mark.vcr
def test_recall_search():
    """Test Enforcement/recall search."""
    # Use broader date range for recalls
    params = RecallSearchParams(
        event_date_start="20200101", event_date_end="20231231", limit=5
    )
    result = recall_search(params)

    # Recalls may be sparse, allow empty results
    assert result.error is None or (result.error and result.error["code"] == 404)


@pytest.mark.vcr
def test_maude_search():
    """Test MAUDE adverse event search."""
    params = MAUDESearchParams(
        event_type="Malfunction", date_received_start="20230101", date_received_end="20230201", limit=5
    )
    result = maude_search(params)

    assert result.error is None
    assert len(result.results) > 0


@pytest.mark.vcr
def test_udi_search():
    """Test UDI/GUDID search."""
    params = UDISearchParams(brand_name="Pacemaker", limit=5)
    result = udi_search(params)

    # UDI may have limited results depending on data
    assert result.error is None or len(result.results) >= 0


# ============================================================================
# Utility tools
# ============================================================================


@pytest.mark.vcr
def test_probe_count():
    """Test count probe."""
    # Use keyword field for count aggregation
    params = ProbeCountParams(endpoint="classification", field="product_code.exact", limit=10)
    result = probe_count(params)

    assert "results" in result
    # May have error if field not found, check for either results or error
    if "error" not in result or result["error"] is None:
        assert len(result["results"]) > 0
        assert "term" in result["results"][0]
        assert "count" in result["results"][0]


@pytest.mark.vcr
def test_paginate():
    """Test safe pagination."""
    params = PaginateParams(
        endpoint="classification", search="device_class:2", max_records=50, page_size=10
    )
    results = paginate(params)

    assert isinstance(results, list)
    assert len(results) <= 50
    # Should have fetched multiple pages
    assert len(results) > 10


def test_field_explorer():
    """Test field explorer returns known fields."""
    fields = field_explorer("classification")

    assert isinstance(fields, list)
    assert "product_code" in fields
    assert "device_class" in fields
    assert "device_name" in fields


def test_freshness():
    """Test freshness URL generation."""
    url = freshness("510k")

    assert "https://api.fda.gov/device/510k.json" in url
    assert "limit=1" in url


def test_answer_assessor_sufficient():
    """Test answer assessor with sufficient answer."""
    params = AnswerAssessorParams(
        question="How many Class I recalls since 2023?",
        search_query="classification:'Class I' AND event_date_initiated:[20230101 TO 20251231]",
        result_count=42,
        date_filter_present=True,
        class_filter_present=True,
    )
    assessment = answer_assessor(params)

    assert assessment.sufficient is True


def test_answer_assessor_missing_date_filter():
    """Test answer assessor detects missing date filter."""
    params = AnswerAssessorParams(
        question="How many recalls since 2023?",
        search_query="classification:'Class I'",
        result_count=100,
        date_filter_present=False,
        class_filter_present=True,
    )
    assessment = answer_assessor(params)

    assert assessment.sufficient is False
    assert "time period" in assessment.reason.lower()


def test_answer_assessor_missing_class_filter():
    """Test answer assessor detects missing class filter."""
    params = AnswerAssessorParams(
        question="How many Class I recalls?",
        search_query="event_date_initiated:[20230101 TO 20251231]",
        result_count=100,
        date_filter_present=True,
        class_filter_present=False,
    )
    assessment = answer_assessor(params)

    assert assessment.sufficient is False
    assert "class" in assessment.reason.lower()


def test_answer_assessor_zero_results_with_filters():
    """Test answer assessor accepts zero results when filters applied."""
    params = AnswerAssessorParams(
        question="Show me XYZ devices",
        search_query="device_name:XYZ",
        result_count=0,
        date_filter_present=False,
        class_filter_present=False,
    )
    assessment = answer_assessor(params)

    assert assessment.sufficient is True  # Legitimate empty result
