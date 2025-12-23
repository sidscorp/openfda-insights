"""
Tests for the DeviceResolver tool.
"""
import pytest
from pathlib import Path

from enhanced_fda_explorer.tools.device_resolver import DeviceResolver
from enhanced_fda_explorer.config import get_config


@pytest.fixture(scope="module")
def resolver():
    """Create a DeviceResolver instance with the real GUDID database."""
    config = get_config()
    db_path = config.gudid_db_path
    if not Path(db_path).exists():
        pytest.skip(f"GUDID database not found at {db_path}")
    return DeviceResolver(db_path=db_path)


class TestGetProductCodesFast:
    """Tests for the layered search in get_product_codes_fast()"""

    def test_device_type_search_syringe(self, resolver):
        """Searching 'syringe' should return product codes with syringe in the name."""
        result = resolver.get_product_codes_fast("syringe", limit=100)

        assert result["query"] == "syringe"
        assert len(result["product_codes"]) > 10
        assert result["total_devices"] > 5000

        codes = [p["code"] for p in result["product_codes"]]
        assert "FMF" in codes

        fmf = next(p for p in result["product_codes"] if p["code"] == "FMF")
        assert fmf["device_count"] > 3000
        assert "syringe" in fmf["name"].lower()

    def test_exact_product_code_match(self, resolver):
        """Searching for an exact product code should return that code."""
        result = resolver.get_product_codes_fast("FMF", limit=100)

        assert len(result["product_codes"]) == 1
        assert result["product_codes"][0]["code"] == "FMF"
        assert result["product_codes"][0]["device_count"] > 3000
        assert result["product_codes"][0]["match_type"] == "exact_code"

    def test_company_search(self, resolver):
        """Searching for a company name should return their product codes."""
        result = resolver.get_product_codes_fast("Becton", limit=100)

        assert len(result["product_codes"]) > 10
        assert result["total_devices"] > 1000

        match_types = {p.get("match_type") for p in result["product_codes"]}
        assert "company_brand" in match_types

    def test_no_match_query(self, resolver):
        """Searching for nonsense should return empty or minimal results."""
        result = resolver.get_product_codes_fast("xyzzy12345nonexistent", limit=100)

        assert result["total_devices"] < 100

    def test_case_insensitive(self, resolver):
        """Search should be case-insensitive."""
        result_lower = resolver.get_product_codes_fast("syringe", limit=50)
        result_upper = resolver.get_product_codes_fast("SYRINGE", limit=50)
        result_mixed = resolver.get_product_codes_fast("SyRiNgE", limit=50)

        assert result_lower["total_devices"] > 0
        assert result_lower["total_devices"] == result_upper["total_devices"]
        assert result_lower["total_devices"] == result_mixed["total_devices"]

    def test_returns_companies(self, resolver):
        """Results should include top companies."""
        result = resolver.get_product_codes_fast("syringe", limit=50)

        assert "companies" in result
        assert len(result["companies"]) > 0

        for company in result["companies"]:
            assert "name" in company
            assert "device_count" in company

    def test_min_devices_filter(self, resolver):
        """min_devices parameter should filter out low-count results."""
        result = resolver.get_product_codes_fast("syringe", min_devices=100, limit=100)

        for pc in result["product_codes"]:
            assert pc["device_count"] >= 100

    def test_limit_parameter(self, resolver):
        """limit parameter should cap the number of results."""
        result = resolver.get_product_codes_fast("syringe", limit=5)

        assert len(result["product_codes"]) <= 5


class TestSearchPerformance:
    """Performance tests for search queries."""

    @pytest.mark.slow
    def test_syringe_search_under_3_seconds(self, resolver):
        """Device type search should complete in under 3 seconds."""
        import time
        start = time.time()
        resolver.get_product_codes_fast("syringe", limit=100)
        elapsed = time.time() - start

        assert elapsed < 3.0, f"Search took {elapsed:.1f}s, expected < 3s"

    @pytest.mark.slow
    def test_exact_code_search_under_1_second(self, resolver):
        """Exact product code search should be fast."""
        import time
        start = time.time()
        resolver.get_product_codes_fast("FMF", limit=100)
        elapsed = time.time() - start

        assert elapsed < 1.0, f"Search took {elapsed:.1f}s, expected < 1s"
