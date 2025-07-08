# Development Guide

This guide covers everything you need to know to contribute to Enhanced FDA Explorer, from setting up your development environment to understanding our development workflow.

## Getting Started

### Prerequisites

- **Python 3.8+** (3.9+ recommended)
- **Git** for version control
- **Docker** (optional, for containerized development)
- **Redis** (optional, for caching)
- **PostgreSQL** (optional, for advanced features)

### Development Environment Setup

#### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/siddnambiar/enhanced-fda-explorer.git
cd enhanced-fda-explorer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Set up pre-commit hooks
pre-commit install

# Copy environment template
cp .env.example .env
```

#### 2. Configure Environment

Edit `.env` file:
```env
# Required
FDA_API_KEY=your_fda_api_key_here

# Optional (for AI features)
AI_API_KEY=your_ai_api_key_here
AI_PROVIDER=openai

# Development settings
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# Optional (for advanced features)
DATABASE_URL=sqlite:///dev.db
REDIS_URL=redis://localhost:6379
```

#### 3. Verify Installation

```bash
# Run tests
pytest

# Check CLI works
fda-explorer --help

# Start web interface
fda-explorer web --debug

# Start API server
fda-explorer serve --reload
```

### Docker Development Environment

```bash
# Build development image
docker build -t enhanced-fda-explorer:dev .

# Run with docker-compose
docker-compose -f docker-compose.dev.yml up -d

# Access containers
docker-compose exec app bash
```

## Project Structure

```
enhanced-fda-explorer/
├── src/enhanced_fda_explorer/    # Main package
│   ├── __init__.py
│   ├── api.py                    # REST API (FastAPI)
│   ├── web.py                    # Web UI (Streamlit)
│   ├── cli.py                    # CLI tool (Click)
│   ├── client.py                 # Python SDK
│   ├── core.py                   # Core business logic
│   ├── ai.py                     # AI analysis engine
│   ├── config.py                 # Configuration management
│   ├── models.py                 # Data models
│   ├── auth.py                   # Authentication (optional)
│   ├── server.py                 # Server utilities
│   └── visualization.py         # Visualization utilities
├── tests/                        # Test suite
│   ├── unit/                     # Unit tests
│   ├── integration/              # Integration tests
│   ├── e2e/                      # End-to-end tests
│   └── fixtures/                 # Test fixtures
├── docs/                         # Documentation
├── scripts/                      # Utility scripts
├── config/                       # Configuration files
├── docker/                       # Docker files
└── .github/                      # GitHub workflows
```

## Development Workflow

### 1. Task-Driven Development

All work should be driven by tasks in `tasks.yaml`:

```bash
# List available tasks
python scripts/manage_tasks.py list --status todo

# Pick a task and mark it in progress
python scripts/manage_tasks.py update P1-T001 in_progress

# Work on the task...

# Mark task as completed
python scripts/manage_tasks.py update P1-T001 completed
```

### 2. Branch Naming Convention

```bash
# Feature branches
git checkout -b feature/P1-T001-config-validation

# Bug fix branches
git checkout -b bugfix/P2-T015-api-timeout-error

# Documentation branches
git checkout -b docs/P3-T008-api-reference
```

### 3. Commit Message Format

Use conventional commits with task references:

```bash
# Format: type(task-id): description
git commit -m "feat(P1-T001): add Pydantic BaseSettings for config validation

Implement schema validation for environment variables and config keys.
Validates presence and format at startup.

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### 4. Pull Request Process

1. **Create PR** with our template
2. **Link to task** in PR description
3. **Ensure all tests pass**
4. **Get code review**
5. **Merge to main**

## Code Standards

### Code Style

We use automated formatting and linting:

```bash
# Format code
black src/ tests/
isort src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/

# Run all pre-commit hooks
pre-commit run --all-files
```

### Python Standards

#### Type Hints
All functions should have type hints:

```python
from typing import Dict, List, Optional

async def search_devices(
    query: str,
    limit: int = 100,
    filters: Optional[Dict[str, str]] = None
) -> List[Dict[str, any]]:
    """Search for medical devices."""
    pass
```

#### Docstrings
Use Google-style docstrings:

```python
def analyze_device(device_name: str, lookback_months: int = 12) -> Dict:
    """Analyze a medical device for safety trends.
    
    Args:
        device_name: Name of the medical device to analyze
        lookback_months: Number of months to analyze
        
    Returns:
        Dictionary containing analysis results with keys:
        - risk_score: Overall risk assessment (0-10)
        - trends: List of identified trends
        - recommendations: List of recommendations
        
    Raises:
        ValueError: If device_name is empty
        APIError: If external API call fails
    """
    pass
```

#### Error Handling
Create custom exceptions and handle errors gracefully:

```python
# Custom exceptions
class FDAExplorerError(Exception):
    """Base exception for FDA Explorer."""
    pass

class APIError(FDAExplorerError):
    """API-related errors."""
    pass

# Usage
try:
    data = await api_client.fetch_data()
except APIError as e:
    logger.error(f"API error: {e}")
    raise
```

#### Async/Await
Use async/await for I/O operations:

```python
import asyncio
import aiohttp

async def fetch_fda_data(query: str) -> Dict:
    """Fetch data from FDA API."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"/api/search?q={query}") as response:
            return await response.json()

# Don't forget to await
data = await fetch_fda_data("pacemaker")
```

## Testing

### Test Structure

```
tests/
├── unit/                    # Fast, isolated tests
│   ├── test_client.py
│   ├── test_ai.py
│   └── test_config.py
├── integration/             # Tests with external dependencies
│   ├── test_api_integration.py
│   └── test_database.py
├── e2e/                     # End-to-end tests
│   ├── test_cli_workflow.py
│   └── test_web_workflow.py
└── fixtures/                # Test data and mocks
    ├── fda_responses.json
    └── mock_data.py
```

### Writing Tests

#### Unit Tests
```python
import pytest
from unittest.mock import AsyncMock, patch
from enhanced_fda_explorer.client import FDAExplorer

@pytest.fixture
async def mock_explorer():
    explorer = FDAExplorer()
    yield explorer
    await explorer.close()

async def test_search_devices(mock_explorer):
    # Mock external API call
    with patch('enhanced_fda_explorer.client.aiohttp.ClientSession.get') as mock_get:
        mock_get.return_value.__aenter__.return_value.json = AsyncMock(
            return_value={'results': [{'device_name': 'Test Device'}]}
        )
        
        results = await mock_explorer.search("test")
        
        assert len(results['results']) == 1
        assert results['results'][0]['device_name'] == 'Test Device'
```

#### Integration Tests
```python
import pytest
from enhanced_fda_explorer import FDAExplorer

@pytest.mark.integration
async def test_real_api_search():
    """Test with real FDA API (requires API key)."""
    explorer = FDAExplorer()
    
    try:
        results = await explorer.search("pacemaker", limit=5)
        assert len(results['results']) > 0
        assert 'device_name' in results['results'][0]
    finally:
        await explorer.close()
```

#### End-to-End Tests
```python
import pytest
from click.testing import CliRunner
from enhanced_fda_explorer.cli import cli

def test_cli_search_command():
    """Test CLI search command."""
    runner = CliRunner()
    result = runner.invoke(cli, ['search', 'pacemaker', '--limit', '5'])
    
    assert result.exit_code == 0
    assert 'pacemaker' in result.output.lower()
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# Run with coverage
pytest --cov=enhanced_fda_explorer --cov-report=html

# Run specific test
pytest tests/unit/test_client.py::test_search_devices

# Run tests matching pattern
pytest -k "test_search"

# Skip slow tests
pytest -m "not slow"
```

### Test Configuration

#### pytest.ini
```ini
[tool:pytest]
minversion = 6.0
addopts = 
    -ra
    --strict-markers
    --strict-config
    --cov=enhanced_fda_explorer
    --cov-report=term-missing:skip-covered
    --cov-report=html:htmlcov
    --cov-report=xml
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
    e2e: marks tests as end-to-end tests
testpaths = tests
```

#### Test Fixtures
```python
# conftest.py
import pytest
import asyncio
from enhanced_fda_explorer import FDAExplorer

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def fda_explorer():
    """Create FDA Explorer instance for testing."""
    explorer = FDAExplorer(
        fda_api_key="test_key",
        cache_enabled=False  # Disable cache for testing
    )
    yield explorer
    await explorer.close()
```

## Debugging

### Local Debugging

#### Python Debugger
```python
import pdb

async def problematic_function():
    data = await fetch_data()
    pdb.set_trace()  # Breakpoint
    processed = process_data(data)
    return processed
```

#### Logging
```python
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def debug_function():
    logger.debug("Starting function")
    try:
        result = await some_operation()
        logger.info(f"Operation successful: {result}")
        return result
    except Exception as e:
        logger.error(f"Operation failed: {e}", exc_info=True)
        raise
```

### Development Tools

#### VS Code Configuration
`.vscode/settings.json`:
```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "python.sortImports.provider": "isort",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    },
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests"]
}
```

#### VS Code Launch Configuration
`.vscode/launch.json`:
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: FastAPI",
            "type": "python",
            "request": "launch",
            "program": "-m uvicorn",
            "args": ["enhanced_fda_explorer.api:app", "--reload"],
            "console": "integratedTerminal",
            "env": {
                "FDA_API_KEY": "your_key_here"
            }
        },
        {
            "name": "Python: CLI",
            "type": "python",
            "request": "launch",
            "program": "-m enhanced_fda_explorer.cli",
            "args": ["search", "pacemaker"],
            "console": "integratedTerminal"
        }
    ]
}
```

## Performance Optimization

### Profiling
```python
import cProfile
import pstats

def profile_function():
    """Profile a function's performance."""
    pr = cProfile.Profile()
    pr.enable()
    
    # Your code here
    result = expensive_function()
    
    pr.disable()
    stats = pstats.Stats(pr)
    stats.sort_stats('tottime')
    stats.print_stats(10)  # Top 10 functions
    
    return result
```

### Memory Usage
```python
import tracemalloc

def track_memory():
    """Track memory usage."""
    tracemalloc.start()
    
    # Your code here
    data = load_large_dataset()
    
    current, peak = tracemalloc.get_traced_memory()
    print(f"Current memory usage: {current / 1024 / 1024:.1f} MB")
    print(f"Peak memory usage: {peak / 1024 / 1024:.1f} MB")
    
    tracemalloc.stop()
```

### Async Performance
```python
import asyncio
import time

async def benchmark_async():
    """Benchmark async operations."""
    start_time = time.time()
    
    # Sequential
    results = []
    for i in range(10):
        result = await api_call(i)
        results.append(result)
    
    sequential_time = time.time() - start_time
    
    # Concurrent
    start_time = time.time()
    tasks = [api_call(i) for i in range(10)]
    results = await asyncio.gather(*tasks)
    concurrent_time = time.time() - start_time
    
    print(f"Sequential: {sequential_time:.2f}s")
    print(f"Concurrent: {concurrent_time:.2f}s")
    print(f"Speedup: {sequential_time / concurrent_time:.2f}x")
```

## Database Development

### Migrations
```python
# Using Alembic for database migrations
from alembic import command
from alembic.config import Config

def run_migrations():
    """Run database migrations."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
```

### Test Database
```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="session")
def test_db():
    """Create test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.close()
```

## Release Process

### Version Management
```bash
# Update version in setup.py and __init__.py
# Create and push tag
git tag v1.0.0
git push origin v1.0.0

# GitHub Actions will automatically:
# - Run tests
# - Build package
# - Publish to PyPI
# - Build and push Docker image
# - Update documentation
```

### Changelog Generation
```bash
# Generate changelog from commits
conventional-changelog -p angular -i CHANGELOG.md -s

# Or use our script
python scripts/generate_changelog.py
```

## Troubleshooting

### Common Issues

#### Import Errors
```bash
# Reinstall in development mode
pip uninstall enhanced-fda-explorer
pip install -e .
```

#### API Key Issues
```bash
# Check environment variables
echo $FDA_API_KEY
echo $AI_API_KEY

# Test API connectivity
fda-explorer search "test" --limit 1
```

#### Database Issues
```bash
# Reset database
rm dev.db
python -c "from enhanced_fda_explorer.models import init_db; init_db()"
```

#### Cache Issues
```bash
# Clear Redis cache
redis-cli FLUSHALL

# Or disable cache
export CACHE_ENABLED=false
```

### Getting Help

1. **Check documentation**: [https://enhanced-fda-explorer.readthedocs.io](https://enhanced-fda-explorer.readthedocs.io)
2. **Search issues**: [GitHub Issues](https://github.com/siddnambiar/enhanced-fda-explorer/issues)
3. **Ask questions**: [GitHub Discussions](https://github.com/siddnambiar/enhanced-fda-explorer/discussions)
4. **Contact maintainers**: Open an issue with `question` label

## Contributing Guidelines

### Before Contributing

1. Read this development guide
2. Review the [task management system](task_management.md)
3. Check open issues and tasks
4. Set up development environment
5. Make sure tests pass

### Contribution Types

- **Bug fixes**: Fix existing functionality
- **Features**: Add new functionality
- **Documentation**: Improve or add documentation
- **Tests**: Add or improve test coverage
- **Performance**: Optimize existing code
- **Refactoring**: Improve code structure

### Code Review Process

1. **Automated checks**: All CI checks must pass
2. **Manual review**: At least one maintainer approval
3. **Task validation**: Must reference valid task ID
4. **Documentation**: Update docs if needed
5. **Tests**: Add tests for new functionality

Thank you for contributing to Enhanced FDA Explorer!