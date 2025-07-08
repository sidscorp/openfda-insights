# Contributing to Enhanced FDA Explorer

Thank you for your interest in contributing to Enhanced FDA Explorer! This document provides comprehensive guidelines for contributing to our project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)
- [Issue Guidelines](#issue-guidelines)
- [Community Guidelines](#community-guidelines)

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- **Python 3.8+** (3.9+ recommended)
- **Git** for version control
- **FDA API Key** (free from [open.fda.gov](https://open.fda.gov/apis/authentication/))
- **AI API Key** (optional, for AI features)

### Development Environment Setup

1. **Fork and Clone**
   ```bash
   # Fork the repository on GitHub
   # Then clone your fork
   git clone https://github.com/your-username/enhanced-fda-explorer.git
   cd enhanced-fda-explorer
   ```

2. **Set up Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Development Dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Configure Pre-commit Hooks**
   ```bash
   pre-commit install
   ```

5. **Set up Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

6. **Verify Setup**
   ```bash
   pytest tests/unit/
   fda-explorer --help
   ```

## Development Workflow

### Task-Driven Development

All contributions should be driven by tasks in our centralized task management system:

1. **Check Available Tasks**
   ```bash
   python scripts/manage_tasks.py list --status todo --priority P1
   ```

2. **Pick a Task**
   ```bash
   python scripts/manage_tasks.py show P1-T001
   ```

3. **Mark Task as In Progress**
   ```bash
   python scripts/manage_tasks.py update P1-T001 in_progress
   ```

4. **Work on the Task**
   - Follow the task requirements exactly
   - Reference the task ID in commits
   - Update task status when blocked or completed

### Branch Naming Convention

Create descriptive branch names that reference the task:

```bash
# Feature branches
git checkout -b feature/P1-T001-config-validation

# Bug fix branches  
git checkout -b bugfix/P2-T015-api-timeout-error

# Documentation branches
git checkout -b docs/P3-T008-api-reference

# Enhancement branches
git checkout -b enhancement/P2-T012-performance-optimization
```

### Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/) with task references:

```
<type>(<task-id>): <description>

[optional body]

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `ci`: CI/CD changes

**Examples:**
```bash
git commit -m "feat(P1-T001): add Pydantic BaseSettings for config validation

Implement schema validation for environment variables and config keys.
Validates presence and format at startup.

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

## Code Standards

### Commit Hooks

We enforce that every commit message include an AI agent review sign-off.  A pre-commit commit-msg hook will reject any commit without a `Reviewed-by: <agent>` header.

### Python Code Style

We enforce strict code quality standards:

#### Formatting and Linting
```bash
# Format code (run automatically via pre-commit)
black src/ tests/
isort src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/

# Security scanning
bandit -r src/
```

#### Type Hints
All functions must have type hints:

```python
from typing import Dict, List, Optional, Union
import asyncio

async def search_devices(
    query: str,
    limit: int = 100,
    include_ai: bool = False,
    filters: Optional[Dict[str, str]] = None
) -> Dict[str, Union[List[Dict], int, str]]:
    """Search for medical devices with optional AI analysis."""
    pass
```

#### Documentation
Use Google-style docstrings:

```python
def analyze_device_risk(device_data: Dict, historical_data: List[Dict]) -> float:
    """Calculate risk score for a medical device.
    
    Args:
        device_data: Current device information including name, manufacturer, class
        historical_data: List of historical adverse events and recalls
        
    Returns:
        Risk score between 0.0 and 10.0, where higher values indicate higher risk
        
    Raises:
        ValueError: If device_data is missing required fields
        APIError: If external data sources are unavailable
        
    Example:
        >>> device = {"name": "pacemaker", "manufacturer": "Acme Corp"}
        >>> events = [{"event_type": "malfunction", "date": "2023-01-01"}]
        >>> risk_score = analyze_device_risk(device, events)
        >>> print(f"Risk score: {risk_score}")
        Risk score: 6.8
    """
    pass
```

#### Error Handling
Use custom exceptions and proper error handling:

```python
# Define custom exceptions
class FDAExplorerError(Exception):
    """Base exception for FDA Explorer."""
    pass

class APIError(FDAExplorerError):
    """API-related errors."""
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code

# Use exceptions properly
async def fetch_device_data(device_id: str) -> Dict:
    """Fetch device data from FDA API."""
    try:
        response = await api_client.get(f"/devices/{device_id}")
        if response.status_code == 404:
            raise APIError(f"Device {device_id} not found", 404)
        elif response.status_code != 200:
            raise APIError(f"API request failed: {response.status_code}")
        return response.json()
    except asyncio.TimeoutError:
        raise APIError("Request timed out")
    except Exception as e:
        logger.error(f"Unexpected error fetching device data: {e}")
        raise FDAExplorerError(f"Failed to fetch device data: {e}")
```

#### Async/Await Best Practices
Use async/await correctly:

```python
import asyncio
import aiohttp
from typing import List

async def fetch_multiple_devices(device_ids: List[str]) -> List[Dict]:
    """Fetch data for multiple devices concurrently."""
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_device_data(session, device_id) for device_id in device_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions in results
        successful_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Failed to fetch device: {result}")
            else:
                successful_results.append(result)
                
        return successful_results

# Context manager usage
async def process_devices():
    async with FDAExplorer() as explorer:
        results = await explorer.search("pacemaker")
        analysis = await explorer.analyze_trends(results)
        return analysis
```

### Configuration Management

Use environment variables and configuration files:

```python
from pydantic import BaseSettings, Field
from typing import Optional

class Settings(BaseSettings):
    """Application settings with validation."""
    
    # Required settings
    fda_api_key: str = Field(..., env="FDA_API_KEY")
    
    # Optional settings with defaults
    ai_api_key: Optional[str] = Field(None, env="AI_API_KEY")
    ai_provider: str = Field("openai", env="AI_PROVIDER")
    environment: str = Field("development", env="ENVIRONMENT")
    debug: bool = Field(False, env="DEBUG")
    
    # Database settings
    database_url: Optional[str] = Field(None, env="DATABASE_URL")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
```

## Testing Guidelines

### Test Organization

Tests are organized into three categories:

```
tests/
├── unit/          # Fast, isolated tests
├── integration/   # Tests with external dependencies  
├── e2e/          # End-to-end workflow tests
└── fixtures/     # Test data and mocks
```

### Writing Tests

#### Unit Tests
Test individual functions and classes in isolation:

```python
import pytest
from unittest.mock import AsyncMock, patch
from enhanced_fda_explorer.client import FDAExplorer

@pytest.mark.unit
async def test_search_devices_success(mock_env_vars, mock_fda_api_response):
    """Test successful device search."""
    with patch('aiohttp.ClientSession.get') as mock_get:
        # Setup mock
        mock_response = AsyncMock()
        mock_response.json.return_value = mock_fda_api_response
        mock_response.status = 200
        mock_get.return_value.__aenter__.return_value = mock_response
        
        # Test
        explorer = FDAExplorer()
        results = await explorer.search("pacemaker", limit=10)
        
        # Assertions
        assert "results" in results
        assert len(results["results"]) == 2
        assert results["results"][0]["device_name"] == "Test Pacemaker"
        
        # Cleanup
        await explorer.close()

@pytest.mark.unit
def test_config_validation():
    """Test configuration validation."""
    from enhanced_fda_explorer.config import Settings
    
    # Test valid config
    settings = Settings(fda_api_key="test_key")
    assert settings.fda_api_key == "test_key"
    
    # Test invalid config
    with pytest.raises(ValueError):
        Settings()  # Missing required fda_api_key
```

#### Integration Tests
Test interactions with external services:

```python
import pytest
from enhanced_fda_explorer import FDAExplorer

@pytest.mark.integration
@pytest.mark.api
async def test_real_api_search():
    """Test with real FDA API (requires API key)."""
    explorer = FDAExplorer()
    
    try:
        results = await explorer.search("pacemaker", limit=5)
        
        assert "results" in results
        assert len(results["results"]) > 0
        assert "device_name" in results["results"][0]
        
    finally:
        await explorer.close()

@pytest.mark.integration
async def test_database_operations():
    """Test database operations."""
    from enhanced_fda_explorer.database import Database
    
    db = Database("sqlite:///:memory:")
    await db.initialize()
    
    try:
        # Test database operations
        await db.save_search_result({"query": "test", "results": []})
        results = await db.get_search_history()
        
        assert len(results) == 1
        assert results[0]["query"] == "test"
        
    finally:
        await db.close()
```

#### End-to-End Tests
Test complete user workflows:

```python
import pytest
from click.testing import CliRunner
from enhanced_fda_explorer.cli import cli

@pytest.mark.e2e
def test_cli_search_workflow():
    """Test complete CLI search workflow."""
    runner = CliRunner()
    
    # Test search command
    result = runner.invoke(cli, [
        'search', 'pacemaker', 
        '--limit', '5',
        '--format', 'json'
    ])
    
    assert result.exit_code == 0
    assert 'results' in result.output
    
    # Parse and validate JSON output
    import json
    data = json.loads(result.output)
    assert isinstance(data['results'], list)
    assert len(data['results']) <= 5
```

### Test Configuration

#### pytest.ini
Already configured with appropriate markers and settings.

#### Running Tests
```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/           # Fast unit tests
pytest tests/integration/    # Integration tests
pytest tests/e2e/           # End-to-end tests

# Run with coverage
pytest --cov=enhanced_fda_explorer --cov-report=html

# Run specific test file
pytest tests/unit/test_client.py

# Run tests matching pattern
pytest -k "test_search"

# Skip slow tests
pytest -m "not slow"

# Skip tests requiring API access
pytest -m "not api"
```

### Test Coverage Requirements

- **Unit tests**: Minimum 90% code coverage
- **Integration tests**: Cover all external integrations
- **E2E tests**: Cover primary user workflows
- **New features**: Must include comprehensive tests

## Documentation

### Types of Documentation

#### Code Documentation
- **Docstrings**: Required for all public functions and classes
- **Type hints**: Required for all function signatures
- **Comments**: For complex logic and algorithms

#### User Documentation
- **API Reference**: Auto-generated from docstrings
- **CLI Reference**: Complete command documentation
- **User Guides**: Step-by-step tutorials
- **Examples**: Code examples and use cases

#### Developer Documentation
- **Architecture Guide**: System design and patterns
- **Development Guide**: Setup and workflow
- **Contributing Guide**: This document
- **Task Management**: Workflow documentation

### Documentation Standards

#### Writing Style
- Use clear, concise language
- Include examples where helpful
- Structure with headers and lists
- Link to related documentation

#### Code Examples
```python
# Always include complete, runnable examples
import asyncio
from enhanced_fda_explorer import FDAExplorer

async def example_device_analysis():
    """Example: Analyze a medical device for safety trends."""
    async with FDAExplorer() as explorer:
        # Search for device data
        results = await explorer.search(
            query="insulin pump",
            query_type="device",
            limit=100
        )
        
        # Get device intelligence
        intelligence = await explorer.get_device_intelligence(
            device_name="insulin pump",
            include_risk_assessment=True,
            include_trends=True
        )
        
        # Print results
        print(f"Found {len(results['results'])} results")
        print(f"Risk Score: {intelligence['risk_assessment']['overall_risk_score']}")
        
        return intelligence

# Run the example
if __name__ == "__main__":
    result = asyncio.run(example_device_analysis())
```

#### Documentation Updates
- Update documentation when changing APIs
- Include migration guides for breaking changes
- Keep examples current and tested
- Update README for major features

## Pull Request Process

### Before Creating a PR

1. **Ensure task reference**: Link to valid task ID
2. **Run tests locally**: All tests must pass
3. **Update documentation**: For any API changes
4. **Run pre-commit hooks**: Ensure code quality
5. **Test manually**: Verify changes work as expected

### PR Template

Our PR template ensures consistent submissions:

- **Task Reference**: Link to specific task
- **Type of Change**: Feature, bugfix, docs, etc.
- **Changes Made**: Detailed description
- **Testing**: Test plan and results
- **Documentation**: Updates made
- **Checklist**: Quality gates

### Review Process

1. **Automated Checks**: CI pipeline must pass
2. **Code Review**: At least one maintainer approval
3. **Manual Testing**: Reviewer tests changes
4. **Documentation Review**: Check docs are updated
5. **Final Approval**: Maintainer approves and merges

### CI/CD Pipeline

Our GitHub Actions pipeline runs:

- **Linting**: Code style and quality checks
- **Security**: Vulnerability scanning
- **Testing**: Unit, integration, and E2E tests
- **Documentation**: Build and link validation
- **Task Validation**: Commit message compliance

## Issue Guidelines

### Reporting Bugs

Use our bug report template:

- **Component**: Which part is affected
- **Environment**: OS, Python version, etc.
- **Steps to Reproduce**: Detailed steps
- **Expected vs Actual**: What should happen vs what does
- **Logs**: Error messages and stack traces

### Feature Requests

Use our feature request template:

- **Problem Statement**: What need does this address
- **Proposed Solution**: Detailed feature description
- **User Stories**: Specific use cases
- **Acceptance Criteria**: Definition of done

### Issue Labels

- **Priority**: `P1` (high), `P2` (medium), `P3` (low)
- **Type**: `bug`, `enhancement`, `documentation`
- **Component**: `api`, `cli`, `web`, `sdk`, `docs`
- **Status**: `triage`, `approved`, `in-progress`, `blocked`

## Community Guidelines

### Code of Conduct

We are committed to providing a welcoming and inclusive environment:

- **Be respectful**: Treat everyone with respect and courtesy
- **Be inclusive**: Welcome people of all backgrounds and experience levels
- **Be collaborative**: Work together constructively
- **Be professional**: Maintain professionalism in all interactions

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and community discussions
- **Pull Requests**: Code contributions and reviews

### Getting Help

1. **Check documentation**: [enhanced-fda-explorer.readthedocs.io](https://enhanced-fda-explorer.readthedocs.io)
2. **Search existing issues**: Someone may have already asked
3. **Ask in discussions**: Community Q&A
4. **Create an issue**: For bugs or feature requests

### Recognition

Contributors are recognized through:

- **Contributor list**: In README and documentation
- **Release notes**: Acknowledgment in changelogs
- **GitHub insights**: Contribution statistics

## Quick Reference

### Common Commands

```bash
# Development setup
git clone <fork-url>
cd enhanced-fda-explorer
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
pre-commit install

# Task management
python scripts/manage_tasks.py list --status todo
python scripts/manage_tasks.py update <task-id> in_progress
python scripts/manage_tasks.py update <task-id> completed

# Testing
pytest tests/unit/          # Unit tests
pytest tests/integration/   # Integration tests  
pytest tests/e2e/          # End-to-end tests
pytest --cov              # With coverage

# Code quality
black src/ tests/          # Format code
flake8 src/ tests/         # Lint code
mypy src/                  # Type check
pre-commit run --all-files # All hooks

# Documentation
mkdocs serve               # Serve docs locally
mkdocs build              # Build docs
```

### Helpful Resources

- **Project Repository**: [github.com/siddnambiar/enhanced-fda-explorer](https://github.com/siddnambiar/enhanced-fda-explorer)
- **Documentation**: [enhanced-fda-explorer.readthedocs.io](https://enhanced-fda-explorer.readthedocs.io)
- **FDA API Docs**: [open.fda.gov/apis](https://open.fda.gov/apis)
- **Conventional Commits**: [conventionalcommits.org](https://www.conventionalcommits.org)
- **Python Style Guide**: [pep8.org](https://pep8.org)

Thank you for contributing to Enhanced FDA Explorer! Your contributions help make medical device data more accessible and actionable for researchers, policy scientists, and healthcare professionals worldwide.