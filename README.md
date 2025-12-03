# Enhanced FDA Explorer

A tool for exploring FDA medical device data with AI-powered analysis.

**Status**: Active development. Contact [Dr. Sidd Nambiar](https://github.com/siddnambiar) for questions or collaboration.

## Features

- **AI Agent**: Ask natural language questions about FDA device data
- **Device Resolution**: Map device names to FDA product codes via GUDID database
- **Multi-Provider LLM**: Support for OpenRouter, AWS Bedrock, and Ollama
- **Six FDA Databases**: Events, recalls, 510(k), PMA, classifications, UDI
- **Multiple Interfaces**: CLI, REST API

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

| Database | Description |
|----------|-------------|
| Device Events | Adverse event reports (MAUDE) |
| Device Recalls | Product recall information |
| 510(k) | Premarket notification clearances |
| PMA | Premarket approval decisions |
| Classifications | Device classification database |
| UDI | Unique device identifier records |
| GUDID | Global UDI Database (local SQLite) |

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
│   │   └── tools/       # 7 FDA search tools
│   ├── tools/           # Device resolver (GUDID)
│   ├── device_models/   # Pydantic models for GUDID data
│   └── data/            # GUDID database indexer
├── frontend/            # Next.js web interface (WIP)
├── tests/               # Test suite
└── docs/                # Documentation
```

## License

MIT License - see LICENSE file.

## Disclaimer

For research and informational purposes only. Not affiliated with the U.S. FDA. Verify all information independently before making decisions.
