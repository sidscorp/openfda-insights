"""Pytest configuration and fixtures."""
import pytest


@pytest.fixture(scope="module")
def vcr_config():
    """Configure VCR for recording/replaying HTTP interactions."""
    return {
        "filter_headers": ["authorization", "api_key"],
        "filter_query_parameters": ["api_key"],
        "record_mode": "once",
        "match_on": ["uri", "method"],
        "cassette_library_dir": "fixtures/vcr_cassettes",
    }
