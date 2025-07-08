# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Enhanced FDA Explorer is a next-generation platform designed for policy scientists and regulatory analysts to explore FDA medical device data. It combines unified access to six FDA medical device databases with AI-powered analysis, supporting data-driven policy research and regulatory decision-making.

## Core Architecture

The project follows a sophisticated modular architecture:

### Core Engine
- **FDAExplorer** (`src/enhanced_fda_explorer/core.py`): Main orchestrator class
- **EnhancedFDAClient** (`src/enhanced_fda_explorer/client.py`): OpenFDA API integration with reliability features
- **AIAnalysisEngine** (`src/enhanced_fda_explorer/ai.py`): AI-powered risk scoring and insights
- **Configuration Management** (`src/enhanced_fda_explorer/config.py`): Centralized settings with environment validation

### Interface Layer
- **CLI Tool** (`src/enhanced_fda_explorer/cli.py`): Rich CLI using Click + Rich
- **Web UI** (`src/enhanced_fda_explorer/web.py`): Streamlit-based dashboard
- **REST API** (`src/enhanced_fda_explorer/api.py`): FastAPI-based API server  
- **Python SDK**: Async client for programmatic access

### Data Layer
- **OpenFDA Integration**: All six FDA device databases (events, recalls, 510k, PMA, classification, UDI)
- **Caching**: Redis/Memory-based caching with configurable TTL
- **Database**: Optional SQLite/PostgreSQL for advanced features

### Future: Conversational Orchestrator
The roadmap includes a conversational agent that will:
- Interpret natural language device queries
- Plan and execute multi-endpoint OpenFDA calls
- Aggregate and normalize results from multiple databases
- Generate coherent conversational responses via AI

## Task-Driven Development

**CRITICAL**: This project uses a centralized task management system in `tasks.yaml`. Always work according to existing tasks:

### Before Starting Work
1. **Read `tasks.yaml`** to understand current priorities
2. **Use task management script**: `python scripts/manage_tasks.py list --status todo --priority P1`
3. **Pick a task** from the appropriate priority level
4. **Update task status**: `python scripts/manage_tasks.py update [TASK_ID] in_progress`

### Commit Message Format
All commits must reference task IDs:
```
feat(P1-T001): add Pydantic BaseSettings for config validation

Implement schema validation for environment variables and config keys.
Validates presence and format at startup.

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Current Priority Tasks (P1)
- **P1-T001**: Add Pydantic BaseSettings for config validation
- **P1-T002**: Write end-to-end mock tests for CLI commands
- **P1-T003**: Implement API rate-limit instrumentation
- **P1-T004**: Add core end-to-end tests with API mocking
- **P1-T005**: Improve CLI help and UX polish
- **P1-T018**: Evaluate LLM frameworks for orchestrator
- **P1-T019**: Research HuggingFace smolagents integration

## Development Commands

### Installation & Setup
```bash
# Install in development mode
pip install -e ".[dev]"

# Set up environment
cp .env.example .env
# Edit .env with FDA_API_KEY and AI_API_KEY
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=enhanced_fda_explorer

# Run by category
pytest -m unit          # Unit tests
pytest -m integration   # Integration tests  
pytest -m e2e           # End-to-end tests

# Quick test suite
python tests/run_all_tests.py
```

### Code Quality
```bash
# Format code
black src/ tests/

# Lint
flake8 src/ tests/

# Type checking
mypy src/enhanced_fda_explorer/

# All pre-commit hooks
pre-commit run --all-files
```

### Task Management
```bash
# List tasks by priority
python scripts/manage_tasks.py list --priority P1

# Show task details
python scripts/manage_tasks.py show P1-T001

# Update task status
python scripts/manage_tasks.py update P1-T001 in_progress
python scripts/manage_tasks.py update P1-T001 completed

# Get task suggestions
python scripts/manage_tasks.py suggest --priority P1
```

### Running the Application
```bash
# CLI commands
fda-explorer search "pacemaker" --limit 10
fda-explorer device "insulin pump" --risk-assessment
fda-explorer web                    # Launch web UI
fda-explorer serve                  # Launch API server

# Direct module execution
streamlit run src/enhanced_fda_explorer/web.py
uvicorn enhanced_fda_explorer.api:app --reload
```

## Key Implementation Details

### Async-First Architecture
- All core operations use `asyncio`
- CLI wraps async calls with `asyncio.run()`
- Use `await` for FDAExplorer methods

### Configuration System
- Environment variables loaded via `.env` file
- Main config in `config/config.yaml`
- Hierarchical override: CLI args > env vars > config file > defaults
- **Current Gap**: Needs Pydantic BaseSettings validation (P1-T001)

### Data Models
- All structures use Pydantic models in `models.py`
- Key models: `SearchRequest`, `SearchResponse`, `AIAnalysisRequest`, `RiskAssessment`

### Error Handling
- Custom exception hierarchy starting with `FDAExplorerError`
- Graceful degradation when AI services unavailable
- Robust retry logic in EnhancedFDAClient

### Testing Strategy
- Unit tests for individual components
- Integration tests for API interactions
- E2E tests for full workflows
- **Current Gap**: Missing comprehensive E2E tests with mocking (P1-T004)

## Configuration

### Environment Variables
```bash
# Required
FDA_API_KEY=your_fda_api_key

# Optional (for AI features)
AI_API_KEY=your_ai_api_key
AI_PROVIDER=openai  # or anthropic, openrouter

# Development
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# Optional infrastructure
DATABASE_URL=postgresql://user:pass@localhost/fda_explorer
REDIS_URL=redis://localhost:6379
```

### Key Configuration Sections
- `openfda`: OpenFDA API settings and rate limits
- `ai`: AI provider configuration (OpenAI, Anthropic, OpenRouter)
- `cache`: Caching backend (Redis/Memory) and TTL
- `database`: Optional database for advanced features
- `api`: API server host/port configuration
- `webui`: Web interface settings

## Entry Points

Defined in `setup.py`:
- `fda-explorer`: Main CLI (`enhanced_fda_explorer.cli:main`)
- `fda-server`: API server (`enhanced_fda_explorer.server:main`)
- `fda-web`: Web UI (`enhanced_fda_explorer.web:main`)

## Documentation Structure

The `docs/` folder contains comprehensive documentation:
- `architecture.md`: Detailed system architecture
- `development.md`: Development workflow and standards
- `task_management.md`: Task management system details
- `POLICY_SCIENTIST_SUMMARY.md`: User-focused overview
- `ROADMAP.md`: Technical roadmap and improvement plans
- `phase_3/`: Advanced roadmap and technical reviews

## Development Best Practices

1. **Always work from tasks**: Never implement features without corresponding tasks
2. **Follow task workflow**: todo → in_progress → completed
3. **Use proper commit messages**: Include task IDs and conventional commit format
4. **Maintain async patterns**: Use async/await for I/O operations
5. **Add comprehensive error handling**: Create custom exceptions with clear messages
6. **Write tests**: Unit tests for new functionality, integration tests for API changes
7. **Update documentation**: Keep docs in sync with code changes
8. **Follow code style**: Use black, flake8, and mypy before committing

## Future Roadmap Context

Be aware of upcoming major features:
- **Phase 1**: Conversational Device Orchestrator for natural language queries
- **Performance improvements**: Async batched requests, caching optimization
- **Enhanced testing**: UI automation, performance benchmarking
- **Scientific communication**: Citation integration, exportable reports
- **Observability**: OpenTelemetry tracing, comprehensive audit logging

When working on the codebase, consider how current changes align with these future directions and ensure compatibility with the planned conversational orchestrator architecture.