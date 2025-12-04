# Enhanced FDA Explorer

A tool for exploring FDA medical device data with AI-powered analysis.

**Status**: Active development.

## Features

- **AI Agent**: Ask natural language questions about FDA device data
- **Device Resolution**: Map device names to FDA product codes via GUDID database (180M+ devices)
- **Multi-Provider LLM**: Support for OpenRouter, AWS Bedrock, and Ollama
- **Seven FDA Databases**: Events (MAUDE), recalls, 510(k), PMA, classifications, UDI, registrations
- **Geographic Queries**: Filter by manufacturer country (China, Germany, etc.) or region
- **Multi-Turn Conversations**: Session persistence for follow-up questions
- **Async Execution**: Concurrent tool execution for faster responses
- **Multiple Interfaces**: CLI, REST API with SSE streaming

## Quick Start

### Installation

```bash
git clone https://github.com/siddnambiar/openfda-insights.git
cd openfda-insights

python -m venv venv
source venv/bin/activate

pip install -e .
```

### Configuration

```bash
cp .env.example .env
```

Set your API keys in `.env`:
```env
OPENROUTER_API_KEY=your_openrouter_key
# Or for AWS Bedrock, configure AWS credentials
# Or for Ollama, no key needed (local)
```

### Usage

#### Ask the AI Agent

```bash
# Default provider (OpenRouter)
python -m src.enhanced_fda_explorer ask "What adverse events have been reported for surgical masks?"

# Use AWS Bedrock
python -m src.enhanced_fda_explorer ask --provider bedrock "Has 3M had any device recalls?"

# Use local Ollama
python -m src.enhanced_fda_explorer ask --provider ollama --model llama3.1 "What is the product code for N95?"

# Verbose mode (shows tool calls)
python -m src.enhanced_fda_explorer ask -v "Compare pacemaker recalls vs defibrillator recalls"

# Geographic queries
python -m src.enhanced_fda_explorer ask "What mask recalls have come from China?"
python -m src.enhanced_fda_explorer ask "Show me adverse events for devices from German manufacturers"
```

#### Resolve Devices to FDA Codes

```bash
# Find FDA product codes for a device
python -m src.enhanced_fda_explorer resolve "surgical mask"

# Fuzzy search with confidence threshold
python -m src.enhanced_fda_explorer resolve "insulin pump" --limit 50 --confidence 0.8

# JSON output
python -m src.enhanced_fda_explorer resolve "3M" --json
```

#### Start the API Server

```bash
# Start API server
python -m src.enhanced_fda_explorer serve --port 8001

# With auto-reload for development
python -m src.enhanced_fda_explorer serve --port 8001 --reload
```

## Agent Tools

The AI agent has 10 specialized tools organized into two categories:

### Resolvers (Translate User Concepts)

| Tool | Purpose | Data Source |
|------|---------|-------------|
| `resolve_device` | Device names → product codes | GUDID (local SQLite) |
| `resolve_manufacturer` | Company names → FDA firm variations | GUDID |
| `resolve_location` | Countries/regions → manufacturers | OpenFDA Registrations |

### Searchers (Query FDA Databases)

| Tool | Purpose | Data Source |
|------|---------|-------------|
| `search_events` | Adverse events (MAUDE) | OpenFDA |
| `search_recalls` | Product recalls | OpenFDA |
| `search_510k` | 510(k) clearances | OpenFDA |
| `search_pma` | PMA approvals | OpenFDA |
| `search_classifications` | Device classifications | OpenFDA |
| `search_udi` | UDI records | OpenFDA |
| `search_registrations` | Establishment registrations | OpenFDA |

See [docs/tools_reference.md](docs/tools_reference.md) for complete parameter documentation.

## LLM Providers

| Provider | Model Examples | Auth |
|----------|---------------|------|
| `openrouter` | `anthropic/claude-3-haiku`, `openai/gpt-4` | `OPENROUTER_API_KEY` |
| `bedrock` | `anthropic.claude-3-haiku-20240307-v1:0` | AWS credentials |
| `ollama` | `llama3.1`, `mistral` | None (local) |

## API Endpoints

Start the server: `python -m src.enhanced_fda_explorer serve --port 8001`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/devices/resolve` | POST | Resolve device to FDA codes |
| `/api/agent/ask` | POST | Ask the AI agent |
| `/api/agent/stream/{question}` | GET | Stream agent response (SSE) |
| `/api/agent/providers` | GET | List available LLM providers |

Interactive docs at `http://localhost:8001/docs`

## Data Sources

| Database | Description | Geographic Filter |
|----------|-------------|-------------------|
| Device Events (MAUDE) | Adverse event reports | ✅ `country` parameter |
| Device Recalls | Product recall information | ✅ `country` parameter |
| 510(k) | Premarket notification clearances | ❌ |
| PMA | Premarket approval decisions | ❌ |
| Classifications | Device classification database | ❌ |
| UDI | Unique device identifier records | ❌ |
| Registrations | Establishment registrations | ✅ `iso_country_code` field |
| GUDID | Global UDI Database (local SQLite) | ❌ |

## Architecture

The system uses a single LangGraph agent with shared state for multi-turn conversations:

```
User Question → FDA Agent → [Resolver Tools] → ResolverContext
                    ↓
              [Search Tools] → FDA APIs → Response
```

Key design decisions:
- **Single Agent**: One LangGraph agent with 10 tools (not multi-agent)
- **Resolver → Searcher Pattern**: Resolvers populate shared context, searchers query databases
- **Async HTTP**: All tools use `httpx.AsyncClient` for concurrent execution
- **Session Persistence**: `MemorySaver` checkpointer for multi-turn conversations

See [docs/architecture.md](docs/architecture.md) for detailed design documentation.

## Project Structure

```
openfda-insights/
├── src/enhanced_fda_explorer/
│   ├── __init__.py      # Package exports (FDAAgent, DeviceResolver, LLMFactory)
│   ├── cli.py           # CLI commands (ask, resolve, serve)
│   ├── api_endpoints.py # FastAPI REST API
│   ├── llm_factory.py   # Multi-provider LLM factory
│   ├── config.py        # Configuration management
│   ├── agent/           # LangGraph FDA agent
│   │   ├── fda_agent.py # Main agent implementation
│   │   ├── prompts.py   # System prompts
│   │   └── tools/       # 10 FDA agent tools
│   ├── tools/           # Device resolver (GUDID)
│   ├── models/          # Pydantic models (responses, device models)
│   └── data/            # GUDID database indexer
├── frontend/            # Next.js web interface (WIP)
├── tests/               # Test suite
└── docs/                # Documentation
    ├── architecture.md  # Design decisions
    ├── fda_api.md       # FDA API reference
    └── tools_reference.md # Tool parameter documentation
```

## Documentation

- [Architecture & Design Decisions](docs/architecture.md)
- [FDA API Reference](docs/fda_api.md)
- [Tools Reference](docs/tools_reference.md)

## License

MIT License - see LICENSE file.

## Disclaimer

For research and informational purposes only. Not affiliated with the U.S. FDA. Verify all information independently before making decisions.
