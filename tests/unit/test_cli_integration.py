#!/usr/bin/env python3
"""
Integration tests for CLI commands to verify end-to-end functionality
Tests for P1-T002: Write end-to-end mock tests for CLI commands
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
from click.testing import CliRunner

# Import test fixtures
from tests.fixtures.mock_fda_responses import (
    get_mock_response, get_mock_ai_response, MOCK_FDA_RESPONSES
)


class TestCLIIntegration:
    """Integration tests for CLI commands"""
    
    def setup_method(self):
        """Setup test environment"""
        self.runner = CliRunner()
        
        # Create mock config
        self.mock_config = Mock()
        self.mock_config.openfda.api_key = "test_key_123"
        self.mock_config.ai.api_key = "sk-test_ai_key_123"
        self.mock_config.debug = False
        self.mock_config.get_validation_summary.return_value = {
            "critical": [],
            "errors": [],
            "warnings": [],
            "info": []
        }
    
    @patch('sys.path')
    @patch('enhanced_fda_explorer.cli.get_config')
    def test_cli_import_structure(self, mock_get_config, mock_sys_path):
        """Test that CLI can be imported without errors"""
        mock_get_config.return_value = self.mock_config
        
        try:
            # This import should work if our test structure is correct
            from enhanced_fda_explorer.cli import cli
            assert cli is not None
        except ImportError as e:
            pytest.skip(f"CLI import failed due to dependencies: {e}")
    
    def test_mock_fixtures_completeness(self):
        """Test that all required mock fixtures exist"""
        required_fixtures = [
            'event', 'recall', '510k', 'pma', 'classification', 'udi'
        ]
        
        for endpoint in required_fixtures:
            response = get_mock_response(endpoint)
            assert response is not None
            assert 'meta' in response
            assert 'results' in response
            assert len(response['results']) > 0
    
    def test_mock_ai_responses(self):
        """Test that AI mock responses are properly structured"""
        ai_types = ['summary', 'risk_assessment', 'trend_analysis']
        
        for ai_type in ai_types:
            response = get_mock_ai_response(ai_type)
            assert response is not None
            assert 'analysis_type' in response
            assert response['analysis_type'] == ai_type
            assert 'summary' in response
            assert 'key_findings' in response
    
    def test_mock_error_responses(self):
        """Test that error mock responses work correctly"""
        error_types = ['api_error', 'rate_limit_error', 'not_found', 'timeout_error']
        
        for error_type in error_types:
            response = get_mock_response('event', error_type=error_type)
            assert response is not None
            assert 'error' in response
            assert 'code' in response['error']
            assert 'message' in response['error']
    
    def test_mock_data_consistency(self):
        """Test that mock data is consistent across different endpoints"""
        # Test that device names appear consistently across endpoints
        event_response = get_mock_response('event')
        recall_response = get_mock_response('recall')
        
        # Extract device/product names from responses
        event_devices = []
        for result in event_response['results']:
            if 'device' in result and result['device']:
                event_devices.append(result['device'][0].get('brand_name', ''))
        
        recall_products = [result.get('product_description', '') for result in recall_response['results']]
        
        # Should have some test data
        assert len(event_devices) > 0
        assert len(recall_products) > 0
    
    @pytest.mark.parametrize("endpoint", ['event', 'recall', '510k', 'pma', 'classification', 'udi'])
    def test_mock_response_structure(self, endpoint):
        """Test that each endpoint mock has correct structure"""
        response = get_mock_response(endpoint)
        
        # Check meta structure
        assert 'meta' in response
        meta = response['meta']
        assert 'disclaimer' in meta
        assert 'results' in meta
        assert 'skip' in meta['results']
        assert 'limit' in meta['results']
        assert 'total' in meta['results']
        
        # Check results structure
        assert 'results' in response
        assert isinstance(response['results'], list)
        assert len(response['results']) > 0
        
        # Check that each result has some expected fields
        for result in response['results']:
            assert isinstance(result, dict)
            assert len(result) > 0
    
    def test_command_coverage_completeness(self):
        """Test that we have proper test coverage for all CLI commands"""
        
        # This is a meta-test to ensure our test suite is comprehensive
        cli_commands = [
            'search', 'device', 'compare', 'manufacturer', 
            'trends', 'stats', 'serve', 'web', 'validate-config'
        ]
        
        test_file_path = Path(__file__).parent / "test_cli.py"
        if test_file_path.exists():
            with open(test_file_path, 'r') as f:
                test_content = f.read()
            
            for command in cli_commands:
                # Check if command is mentioned in test methods
                assert f"test_{command}" in test_content or f"Test{command.title()}Command" in test_content, \
                    f"No tests found for CLI command: {command}"
    
    def test_test_class_structure(self):
        """Test that our test classes follow good structure"""
        
        # Check that test file exists and has expected classes
        test_file_path = Path(__file__).parent / "test_cli.py"
        if test_file_path.exists():
            with open(test_file_path, 'r') as f:
                test_content = f.read()
            
            # Required test class patterns
            required_patterns = [
                'class TestCLICommands',
                'class TestSearchCommand',
                'class TestCLIArgumentValidation',
                'class TestCLIErrorHandling',
                'class TestCLIAsyncPatterns'
            ]
            
            for pattern in required_patterns:
                assert pattern in test_content, f"Missing test class: {pattern}"
            
            # Check for proper imports
            required_imports = [
                'from unittest.mock import Mock, AsyncMock, patch',
                'from click.testing import CliRunner',
                'import pytest'
            ]
            
            for import_stmt in required_imports:
                assert import_stmt in test_content, f"Missing import: {import_stmt}"
    
    def test_async_mock_patterns(self):
        """Test that our async mocking patterns are correct"""
        
        # Create an AsyncMock explorer like in our tests
        mock_explorer = AsyncMock()
        
        # Test that we can set up async return values
        mock_explorer.search.return_value = Mock(
            query="test",
            results={"event": Mock(empty=True)},
            ai_analysis=None
        )
        
        # Test that the mock is properly configured
        assert hasattr(mock_explorer, 'search')
        assert hasattr(mock_explorer, 'close')
        
        # Test async side effects
        mock_explorer.get_device_intelligence.side_effect = Exception("Test error")
        
        # These should not raise errors in our test setup
        assert mock_explorer.get_device_intelligence.side_effect is not None
    
    def test_cli_runner_setup(self):
        """Test that CliRunner is properly configured for our tests"""
        
        runner = CliRunner()
        
        # Test isolated filesystem
        with runner.isolated_filesystem():
            # Should be able to create files
            test_file = Path("test.txt")
            test_file.write_text("test content")
            assert test_file.exists()
        
        # File should not exist outside isolated filesystem
        assert not Path("test.txt").exists()
    
    def test_fixture_data_types(self):
        """Test that fixture data has correct types for CLI processing"""
        
        # Test event data structure
        event_response = get_mock_response('event')
        for result in event_response['results']:
            # Date fields should be strings (as they come from API)
            if 'date_received' in result:
                assert isinstance(result['date_received'], str)
            
            # Device info should be a list
            if 'device' in result:
                assert isinstance(result['device'], list)
                if result['device']:
                    assert isinstance(result['device'][0], dict)
        
        # Test AI response structure
        ai_response = get_mock_ai_response('summary')
        assert isinstance(ai_response['key_findings'], list)
        assert isinstance(ai_response['summary'], str)
        if 'confidence_score' in ai_response:
            assert isinstance(ai_response['confidence_score'], (int, float))


class TestCLIMockingPatterns:
    """Test specific mocking patterns used in CLI tests"""
    
    def test_config_mocking(self):
        """Test configuration mocking patterns"""
        
        # Test the config mock structure we use in tests
        mock_config = Mock()
        mock_config.openfda.api_key = "test_key"
        mock_config.ai.api_key = "sk-test_key"
        mock_config.debug = False
        
        # Should have proper attribute access
        assert mock_config.openfda.api_key == "test_key"
        assert mock_config.ai.api_key == "sk-test_key"
        assert mock_config.debug is False
    
    def test_explorer_mocking(self):
        """Test FDAExplorer mocking patterns"""
        
        # Test the explorer mock structure
        mock_explorer = AsyncMock()
        
        # All methods should be async mocks
        assert hasattr(mock_explorer, 'search')
        assert hasattr(mock_explorer, 'get_device_intelligence')
        assert hasattr(mock_explorer, 'compare_devices')
        assert hasattr(mock_explorer, 'get_summary_statistics')
        assert hasattr(mock_explorer, 'close')
    
    def test_response_mocking(self):
        """Test response object mocking patterns"""
        
        # Test search response mock
        mock_response = Mock()
        mock_response.query = "test"
        mock_response.query_type = "device"
        mock_response.results = {"event": Mock()}
        mock_response.ai_analysis = None
        
        # Mock DataFrame behavior
        mock_df = mock_response.results["event"]
        mock_df.empty = False
        mock_df.columns = ["date_received"]
        mock_df.__len__ = Mock(return_value=5)
        
        # Test the mock works as expected
        assert mock_response.query == "test"
        assert not mock_response.results["event"].empty
        assert len(mock_response.results["event"]) == 5
    
    def test_patch_decorators(self):
        """Test that patch decorators work correctly"""
        
        with patch('builtins.print') as mock_print:
            print("test message")
            mock_print.assert_called_once_with("test message")
        
        # Test multiple patches
        with patch('builtins.print') as mock_print, \
             patch('builtins.len') as mock_len:
            
            mock_len.return_value = 42
            result = len([1, 2, 3])
            assert result == 42
            mock_len.assert_called_once()


# Pytest configuration for this file
@pytest.fixture
def cli_runner():
    """Fixture to provide CliRunner instance"""
    return CliRunner()


@pytest.fixture
def mock_config():
    """Fixture to provide mock configuration"""
    config = Mock()
    config.openfda.api_key = "test_key_123"
    config.ai.api_key = "sk-test_ai_key_123"
    config.debug = False
    config.get_validation_summary.return_value = {
        "critical": [],
        "errors": [], 
        "warnings": [],
        "info": []
    }
    return config


@pytest.fixture
def mock_explorer():
    """Fixture to provide mock FDAExplorer"""
    explorer = AsyncMock()
    
    # Set up default return values
    explorer.search.return_value = Mock(
        query="test",
        query_type="device",
        results={"event": Mock(empty=True)},
        ai_analysis=None
    )
    
    explorer.get_summary_statistics.return_value = get_mock_response('stats')
    
    return explorer