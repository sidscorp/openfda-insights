# FDA Explorer

An AI-powered tool for exploring FDA medical device data. Ask natural language questions about adverse events, recalls, 510(k) clearances, and more across seven FDA databases.

Built as a learning project to explore agentic AI patterns while solving a real problem: making FDA regulatory data accessible without needing to know product codes, database schemas, or query syntax.

## The Problem: Why Resolution Matters

FDA databases don't understand "surgical mask" or "insulin pump." They use 3-letter product codes like `FXX` (Surgical Mask) or `LZG` (Insulin Pump). To search for mask recalls, you need to:

1. Know that masks span codes `FXX`, `MSH`, `OUK`, etc.
2. Know which FDA database to query (MAUDE for events, Recall Enforcement for recalls)
3. Construct the right API query syntax

This tool solves that by introducing a **resolution layer** between natural language and FDA APIs:

```
"Have there been recalls for surgical masks?"
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  RESOLUTION LAYER                                           │
│  ┌─────────────────┐                                        │
│  │ Device Resolver │ "surgical mask" → [FXX, MSH, OUK, ...] │
│  │ (GUDID: 180M+   │                                        │
│  │  devices)       │                                        │
│  └─────────────────┘                                        │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  SEARCH LAYER                                               │
│  search_recalls(product_codes=["FXX", "MSH", "OUK"])        │
│         │                                                   │
│         ▼                                                   │
│  OpenFDA Recall API → Results                               │
└─────────────────────────────────────────────────────────────┘
```

The resolution layer uses a local GUDID (Global Unique Device Identification Database) with 180M+ device records to map natural language to FDA's regulatory vocabulary.

## How It Works

### Architecture

The system is a LangGraph agent with 10 tools organized into two categories:

**Resolvers** translate user concepts into FDA vocabulary:
| Tool | Purpose | Data Source |
|------|---------|-------------|
| `resolve_device` | Device names → product codes | GUDID (local SQLite, 180M+ records) |
| `resolve_manufacturer` | Company names → FDA firm variations | GUDID |
| `resolve_location` | Countries/regions → ISO codes | OpenFDA Registrations |

**Searchers** query the seven FDA databases:
| Tool | Database | What It Contains |
|------|----------|------------------|
| `search_events` | MAUDE | Adverse event reports (injuries, malfunctions, deaths) |
| `search_recalls` | Recall Enforcement | Product recalls and safety alerts |
| `search_510k` | 510(k) | Premarket notification clearances |
| `search_pma` | PMA | Premarket approval decisions |
| `search_classifications` | Classifications | Device regulatory classifications |
| `search_udi` | UDI | Unique device identifier records |
| `search_registrations` | Registrations | Manufacturer facility registrations |
| `aggregate_registrations` | Registrations | Country-level manufacturer statistics |

### Context Flow

The agent maintains conversation state so follow-up questions work naturally:

```
Turn 1: "What product codes cover syringes?"
        → resolve_device("syringe")
        → Returns: FMF (Syringe, Piston), FMI (Syringe, Irrigating), ...
        → Stored in conversation context

Turn 2: "Have there been recalls for these?"
        → Agent sees previous context, extracts codes
        → search_recalls(product_codes=["FMF", "FMI", ...])
        → Returns recall data

Turn 3: "Which manufacturers are involved?"
        → Agent references recall data already in context
        → Summarizes without re-querying
```

The LangGraph `MemorySaver` checkpointer persists conversation history, and a structured `ResolverContext` stores typed data from resolver tools for downstream use.

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ (for web frontend)
- An LLM API key (OpenRouter, AWS Bedrock, or local Ollama)

### Installation

```bash
git clone https://github.com/sidscorp/openfda-insights.git
cd openfda-insights

python -m venv venv
source venv/bin/activate

pip install -e .
```

### Configuration

```bash
cp .env.example .env
```

Edit `.env` with your LLM provider credentials:

```env
# Option 1: OpenRouter (recommended for getting started)
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here

# Option 2: AWS Bedrock
AI_PROVIDER=bedrock
# Configure AWS credentials via aws configure

# Option 3: Local Ollama (no API key needed)
AI_PROVIDER=ollama
AI_MODEL=llama3.1
```

### Download GUDID Database

The device resolver requires the GUDID database (~2GB):

```bash
python -m src.enhanced_fda_explorer index-gudid
```

This downloads and indexes the FDA's GUDID data into a local SQLite database.

### Running

**CLI (quickest way to test):**

```bash
# Ask a question
python -m src.enhanced_fda_explorer ask "What adverse events have been reported for N95 masks?"

# Verbose mode (shows tool calls)
python -m src.enhanced_fda_explorer ask -v "Compare pacemaker vs defibrillator recalls"

# Resolve a device to product codes
python -m src.enhanced_fda_explorer resolve "insulin pump"
```

**API Server + Web UI:**

```bash
# Terminal 1: Start backend
python -m src.enhanced_fda_explorer serve --port 8001

# Terminal 2: Start frontend
cd frontend
npm install
npm run dev
```

Then open http://localhost:3000

## CLI Reference

```bash
# Ask the AI agent
python -m src.enhanced_fda_explorer ask "your question"
python -m src.enhanced_fda_explorer ask -v "question"           # verbose (show tool calls)
python -m src.enhanced_fda_explorer ask --provider bedrock "q"  # specify provider

# Resolve devices to FDA codes
python -m src.enhanced_fda_explorer resolve "device name"
python -m src.enhanced_fda_explorer resolve "device" --limit 20  # more results
python -m src.enhanced_fda_explorer resolve "device" --json      # JSON output

# Start API server
python -m src.enhanced_fda_explorer serve --port 8001
python -m src.enhanced_fda_explorer serve --port 8001 --reload   # dev mode

# Database management
python -m src.enhanced_fda_explorer index-gudid                  # download/index GUDID
```

## API Reference

Start the server with `python -m src.enhanced_fda_explorer serve --port 8001`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check (optionally test LLM connectivity) |
| `/api/devices/resolve` | POST | Resolve device name to FDA codes |
| `/api/agent/ask` | POST | Ask the AI agent (blocking) |
| `/api/agent/stream/{question}` | GET | Stream agent response (SSE) |
| `/api/agent/providers` | GET | List available LLM providers |

Interactive API docs: http://localhost:8001/docs

## Project Structure

```
openfda-insights/
├── src/enhanced_fda_explorer/
│   ├── cli.py              # CLI commands (ask, resolve, serve)
│   ├── api_endpoints.py    # FastAPI REST API
│   ├── llm_factory.py      # Multi-provider LLM factory
│   ├── config.py           # Configuration management
│   ├── agent/
│   │   ├── fda_agent.py    # LangGraph agent implementation
│   │   ├── prompts.py      # System prompts
│   │   └── tools/          # Resolver and searcher tools
│   ├── tools/
│   │   └── device_resolver.py  # GUDID-based device resolution
│   └── data/
│       └── gudid_indexer.py    # GUDID download and indexing
├── frontend/               # Next.js web interface
├── tests/                  # Test suite
└── docs/                   # Additional documentation
```

## Disclaimer

This tool is for research and educational purposes. It is not affiliated with the U.S. Food and Drug Administration. FDA data is provided as-is from public APIs. Always verify information independently before making regulatory or clinical decisions.
