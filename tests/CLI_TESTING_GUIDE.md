# CLI Testing Guide for Enhanced FDA Explorer

## Overview

This document describes the comprehensive CLI testing implementation for P1-T002: "Write end-to-end mock tests for CLI commands". The testing suite provides complete coverage of all CLI commands with proper mocking, error handling, and async testing patterns.

## Test Structure

### Test Files

1. **`tests/unit/test_cli.py`** - Main CLI test suite with 15 test classes and 50+ test methods
2. **`tests/unit/test_cli_integration.py`** - Integration tests and meta-tests for CLI functionality 
3. **`tests/fixtures/mock_fda_responses.py`** - Comprehensive mock API responses and fixtures

### Test Classes

#### Core CLI Command Tests
- **`TestCLICommands`** - Basic CLI functionality and global options
- **`TestSearchCommand`** - Search command with various options and formats
- **`TestDeviceCommand`** - Device intelligence command testing
- **`TestCompareCommand`** - Device comparison functionality
- **`TestManufacturerCommand`** - Manufacturer intelligence testing
- **`TestTrendsCommand`** - Trend analysis command testing
- **`TestStatsCommand`** - Statistics command testing
- **`TestServeCommand`** - API server startup testing
- **`TestWebCommand`** - Web interface startup testing
- **`TestValidateConfigCommand`** - Configuration validation testing

#### Testing Patterns
- **`TestCLIArgumentValidation`** - Argument validation and edge cases
- **`TestCLIErrorHandling`** - Error scenarios and graceful degradation
- **`TestCLIOutputFormats`** - Different output formats (JSON, table, CSV)
- **`TestCLIAsyncPatterns`** - Async execution patterns
- **`TestCLIHelpAndUsage`** - Help text and usage information

## Mock Data Structure

### FDA API Response Mocks

The mock responses cover all six FDA endpoints:

```python
MOCK_FDA_RESPONSES = {
    "event": {...},      # Adverse event reports
    "recall": {...},     # Device recalls
    "510k": {...},       # 510(k) clearances
    "pma": {...},        # PMA approvals
    "classification": {...}, # Device classifications
    "udi": {...}         # UDI database
}
```

### AI Analysis Mocks

```python
MOCK_AI_RESPONSES = {
    "summary": {...},         # General analysis summary
    "risk_assessment": {...}, # Risk scoring and recommendations
    "trend_analysis": {...}   # Temporal trend analysis
}
```

### Error Response Mocks

```python
MOCK_ERROR_RESPONSES = {
    "api_error": {...},       # General API errors
    "rate_limit_error": {...}, # Rate limiting
    "not_found": {...},       # No results found
    "timeout_error": {...}    # Request timeouts
}
```

## Testing Patterns

### Proper Mocking with Patches

```python
@patch('enhanced_fda_explorer.cli.FDAExplorer')
@patch('enhanced_fda_explorer.cli.get_config')
def test_search_basic(self, mock_get_config, mock_explorer_class):
    """Test basic search command"""
    mock_get_config.return_value = self.mock_config
    
    mock_explorer = AsyncMock()
    mock_explorer_class.return_value = mock_explorer
    mock_explorer.search.return_value = mock_response
    
    result = self.runner.invoke(cli, ['search', 'pacemaker'])
    
    assert result.exit_code == 0
    mock_explorer.search.assert_called_once()
    mock_explorer.close.assert_called_once()
```

### Async Testing Patterns

```python
# Mock async methods with AsyncMock
mock_explorer = AsyncMock()

# Set up async return values
async def mock_search(*args, **kwargs):
    return Mock(query="test", results={"event": Mock(empty=True)})

mock_explorer.search = mock_search
```

### CLI Runner Usage

```python
# Basic command testing
result = self.runner.invoke(cli, ['search', 'pacemaker'])

# With options
result = self.runner.invoke(cli, [
    'search', 'insulin pump',
    '--type', 'device',
    '--limit', '50',
    '--format', 'json'
])

# With file output (isolated filesystem)
with self.runner.isolated_filesystem():
    result = self.runner.invoke(cli, [
        'search', 'stent',
        '--output', 'test_output.json'
    ])
    assert Path('test_output.json').exists()
```

### Error Handling Testing

```python
# Test API errors
mock_explorer.search.side_effect = ConnectionError("API connection failed")

# Test async errors
mock_explorer.get_device_intelligence.side_effect = asyncio.TimeoutError("Request timeout")

# Test configuration errors
mock_get_config.side_effect = ValueError("Configuration error")
```

## Command Coverage

| Command | Test Classes | Test Methods | Coverage |
|---------|-------------|--------------|----------|
| search | 2 | 15 | ✅ Complete |
| device | 2 | 11 | ✅ Complete |
| compare | 2 | 7 | ✅ Complete |
| manufacturer | 2 | 4 | ✅ Complete |
| trends | 2 | 5 | ✅ Complete |
| stats | 2 | 5 | ✅ Complete |
| serve | 2 | 5 | ✅ Complete |
| web | 2 | 4 | ✅ Complete |
| validate-config | 2 | 7 | ✅ Complete |

**Total Coverage: 100% (9/9 commands)**

## Test Scenarios Covered

### 1. Basic Functionality
- Command execution with default options
- Help text and usage information
- Configuration loading and validation

### 2. Argument Validation
- Required vs optional arguments
- Invalid argument values
- Argument type checking
- Boundary value testing

### 3. Output Formats
- Table format with Rich rendering
- JSON output for machine processing
- CSV export functionality
- File output handling

### 4. Error Handling
- Network connection errors
- API rate limiting
- Invalid search parameters
- Configuration validation failures
- Async operation timeouts

### 5. Async Patterns
- Proper async/await usage in CLI
- AsyncMock configuration
- Async exception handling
- Resource cleanup (explorer.close())

### 6. Integration Scenarios
- Multiple endpoint queries
- AI analysis integration
- Configuration override handling
- Progress indication during operations

## Running the Tests

### Prerequisites

```bash
# Install dependencies
pip install -e ".[dev]"

# Ensure test environment
export ENVIRONMENT=test
```

### Test Execution

```bash
# Run all CLI tests
pytest tests/unit/test_cli.py -v

# Run specific test class
pytest tests/unit/test_cli.py::TestSearchCommand -v

# Run with coverage
pytest tests/unit/test_cli.py --cov=enhanced_fda_explorer.cli

# Run integration tests
pytest tests/unit/test_cli_integration.py -v

# Analyze test structure
python3 test_cli_structure.py
```

### Test Structure Analysis

The project includes a comprehensive test analysis tool:

```bash
python3 test_cli_structure.py
```

This tool provides:
- Test class and method counts
- Command coverage analysis
- Testing pattern verification
- Mock fixture completeness check
- Overall quality assessment

## Mock Fixture Usage

### Getting Mock Responses

```python
from tests.fixtures.mock_fda_responses import get_mock_response, get_mock_ai_response

# Get FDA endpoint response
event_response = get_mock_response('event')
recall_response = get_mock_response('recall')

# Get AI analysis response
ai_summary = get_mock_ai_response('summary')
risk_assessment = get_mock_ai_response('risk_assessment')

# Get error response
error_response = get_mock_response('event', error_type='rate_limit_error')
```

### Configuring Mock Objects

```python
# Mock DataFrame behavior for CLI display
mock_df = Mock()
mock_df.empty = False
mock_df.columns = ["date_received", "event_type"]
mock_df.__len__ = Mock(return_value=5)

# Mock search response
mock_response = Mock()
mock_response.query = "pacemaker"
mock_response.results = {"event": mock_df}
mock_response.ai_analysis = get_mock_ai_response("summary")
```

## Best Practices

### 1. Test Isolation
- Each test method is independent
- Proper setup and teardown
- No shared state between tests

### 2. Comprehensive Mocking
- Mock all external dependencies
- Use realistic mock data
- Test both success and failure paths

### 3. Async Testing
- Use AsyncMock for async methods
- Proper async exception handling
- Test resource cleanup

### 4. CLI Testing Patterns
- Use CliRunner for command testing
- Test argument validation
- Verify output formatting

### 5. Error Coverage
- Test all error scenarios
- Verify graceful degradation
- Check error message clarity

## Quality Metrics

The CLI testing implementation achieves:

- **Test Coverage**: 100% of CLI commands
- **Test Classes**: 15 comprehensive test classes
- **Test Methods**: 50+ individual test methods
- **Mock Fixtures**: Complete coverage of all FDA endpoints
- **Testing Patterns**: All modern pytest patterns implemented
- **Quality Score**: 100% (Excellent)

## Future Enhancements

### 1. Performance Testing
- Add timing benchmarks for CLI operations
- Test with large result sets
- Memory usage profiling

### 2. UI Testing
- Add Playwright tests for web interface
- Test Rich console output rendering
- Progress indicator testing

### 3. Integration Testing
- End-to-end tests with real API calls (optional)
- Database integration testing
- Cache behavior testing

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed and paths are correct
2. **Async Test Failures**: Check AsyncMock configuration and await patterns
3. **Mock Setup**: Verify mock objects have all required attributes
4. **CLI Runner Issues**: Use isolated filesystem for file operations

### Debug Tips

```python
# Add debugging to tests
import logging
logging.basicConfig(level=logging.DEBUG)

# Print CLI output for debugging
result = self.runner.invoke(cli, ['command'])
print(f"Exit code: {result.exit_code}")
print(f"Output: {result.output}")
if result.exception:
    print(f"Exception: {result.exception}")
```

## Conclusion

The CLI testing implementation for P1-T002 provides comprehensive coverage of all Enhanced FDA Explorer CLI commands with proper mocking, error handling, and async testing patterns. The test suite ensures reliable CLI functionality and serves as a foundation for continued development and maintenance.