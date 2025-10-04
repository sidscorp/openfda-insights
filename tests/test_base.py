"""Tests for base HTTP client."""
import pytest

from tools.base import OpenFDAClient


@pytest.mark.vcr
def test_client_query_success():
    """Test successful query returns results."""
    client = OpenFDAClient()
    resp = client.query(endpoint="classification", search="device_class:2", limit=5)

    assert resp.error is None
    assert len(resp.results) > 0
    assert "results" in resp.meta  # meta.results contains skip/limit/total


@pytest.mark.vcr
def test_client_query_with_count():
    """Test count aggregation."""
    client = OpenFDAClient()
    # Use valid count field - product_code without .exact
    resp = client.query(endpoint="510k", count="product_code", limit=10)

    assert resp.error is None
    assert len(resp.results) > 0
    # Count results have 'term' and 'count' fields
    assert "term" in resp.results[0]
    assert "count" in resp.results[0]


@pytest.mark.vcr
def test_client_query_not_found():
    """Test query with no results."""
    client = OpenFDAClient()
    resp = client.query(endpoint="classification", search="device_class:999", limit=5)

    # openFDA returns error for invalid queries
    assert resp.error is not None or len(resp.results) == 0
