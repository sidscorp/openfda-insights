"""
Shared test configuration and fixtures for Enhanced FDA Explorer.
"""
import pytest
import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add src to path for imports
import sys
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    original_env = os.environ.copy()
    
    # Set test environment variables
    os.environ.update({
        'FDA_API_KEY': 'test_fda_key',
        'AI_API_KEY': 'test_ai_key',
        'AI_PROVIDER': 'openai',
        'ENVIRONMENT': 'test',
        'DEBUG': 'true',
        'CACHE_ENABLED': 'false',
        'DATABASE_URL': 'sqlite:///:memory:'
    })
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_fda_api_response():
    """Mock FDA API response data."""
    return {
        "meta": {
            "disclaimer": "Test disclaimer",
            "terms": "Test terms",
            "license": "Test license",
            "last_updated": "2023-01-01",
            "results": {
                "skip": 0,
                "limit": 100,
                "total": 1247
            }
        },
        "results": [
            {
                "device_name": "Test Pacemaker",
                "manufacturer_name": "Test Medical Inc",
                "date_received": "2023-06-15",
                "event_type": "Malfunction",
                "patient_outcome": "Required Intervention",
                "device_problem_flag": "Y",
                "adverse_event_flag": "Y"
            },
            {
                "device_name": "Test Defibrillator",
                "manufacturer_name": "Test Devices Corp",
                "date_received": "2023-06-14", 
                "event_type": "Injury",
                "patient_outcome": "Hospitalization",
                "device_problem_flag": "Y",
                "adverse_event_flag": "Y"
            }
        ]
    }


@pytest.fixture
def mock_ai_response():
    """Mock AI analysis response."""
    return {
        "summary": "Test analysis summary of the medical device data",
        "risk_score": 7.2,
        "trends": [
            "Increasing malfunction reports",
            "Geographic clustering in urban areas"
        ],
        "recommendations": [
            "Enhanced monitoring recommended",
            "Consider additional safety protocols"
        ],
        "confidence": 0.85
    }


@pytest.fixture
async def mock_http_session():
    """Mock aiohttp ClientSession for API calls."""
    session = AsyncMock()
    response = AsyncMock()
    
    # Configure mock response
    response.status = 200
    response.json = AsyncMock()
    response.text = AsyncMock(return_value="")
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    
    session.get = AsyncMock(return_value=response)
    session.post = AsyncMock(return_value=response)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    
    return session


@pytest.fixture
def sample_device_data():
    """Sample device data for testing."""
    return {
        "device_name": "insulin pump",
        "device_class": "II",
        "regulation_number": "21CFR862.1570",
        "medical_specialty": "Endocrinology",
        "manufacturer": "Test Medical Corp",
        "clearance_date": "2023-01-15"
    }


@pytest.fixture
def sample_event_data():
    """Sample adverse event data for testing."""
    return {
        "report_id": "12345678",
        "device_name": "Test Device",
        "manufacturer_name": "Test Corp",
        "event_type": "Malfunction",
        "date_received": "2023-06-15",
        "patient_age": "65",
        "patient_sex": "F",
        "patient_outcome": "Required Intervention"
    }


@pytest.fixture
def test_config():
    """Test configuration object."""
    return {
        "openfda": {
            "api_key": "test_fda_key",
            "base_url": "https://api.fda.gov",
            "timeout": 30,
            "max_retries": 3
        },
        "ai": {
            "provider": "openai",
            "api_key": "test_ai_key",
            "model": "gpt-4",
            "temperature": 0.1
        },
        "cache": {
            "enabled": False,
            "ttl": 3600
        },
        "database": {
            "url": "sqlite:///:memory:"
        }
    }


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test" 
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as an end-to-end test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "api: mark test as requiring external API"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their location."""
    for item in items:
        # Auto-mark tests based on directory
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
        
        # Mark tests that use external APIs
        if hasattr(item, "fixturenames"):
            if any(fixture.startswith("real_") for fixture in item.fixturenames):
                item.add_marker(pytest.mark.api)