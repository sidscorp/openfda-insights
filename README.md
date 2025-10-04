# OpenFDA Agent

An intelligent FDA device database query assistant that understands natural language and provides comprehensive safety analysis using the openFDA API.

## Features

- 🤖 **Natural Language Understanding**: Ask questions in plain English about FDA device data
- 🔄 **Intelligent Cross-Referencing**: Automatically handles complex queries that require data from multiple endpoints
- 🎯 **Smart Routing**: Automatically selects the right FDA database endpoint for your query
- 📊 **Comprehensive Safety Analysis**: Performs multi-endpoint safety checks for product codes
- 🌐 **Web Dashboard**: Interactive web interface for easy querying
- 📚 **RAG-Enhanced**: Uses retrieval-augmented generation for accurate field mapping
- 🔧 **Extensible Tools**: Modular design with separate tools for each FDA endpoint

## Quick Start

### Prerequisites

- Python 3.9+
- Virtual environment (recommended)
- Anthropic API key (required)
- OpenFDA API key (optional, for higher rate limits)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd openfda_agent
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your API keys
```

### Usage

#### Web Dashboard

Start the dashboard:
```bash
python dashboard_control.py start
```

Access at: http://localhost:8000

Control commands:
```bash
python dashboard_control.py status   # Check if running
python dashboard_control.py stop     # Stop dashboard
python dashboard_control.py restart  # Restart dashboard
```

#### Command Line Interface

Query directly from terminal:
```bash
python -m agent.cli "What recalls exist for product code BZD?"
python -m agent.cli "Show me Class II devices from Abbott"
python -m agent.cli "How many PMA approvals in 2023?" --explain
```

#### Direct Tool Usage

Use specific tools directly:
```bash
# Search classifications
python -m tools.classification --product-code BZD --limit 5

# Search recalls
python -m tools.recall --firm-name Medtronic --limit 10

# Search 510(k) clearances
python -m tools.k510 --applicant "Boston Scientific" --limit 5
```

## Architecture

```
openfda_agent/
├── agent/          # LangGraph agent orchestration
│   ├── graph.py    # Main agent workflow
│   ├── router.py   # Intelligent query routing
│   └── extractor.py # Parameter extraction
├── tools/          # FDA API endpoint tools
│   ├── classification.py
│   ├── recall.py
│   ├── k510.py
│   ├── pma.py
│   ├── maude.py
│   └── udi.py
├── dashboard/      # Web interface
│   └── app.py      # FastAPI application
├── rag/           # Retrieval-augmented generation
│   ├── retrieval.py
│   └── hybrid.py   # BM25 + semantic search
└── tests/         # Test suite
```

## Key Capabilities

### 1. Intelligent Query Understanding
The agent uses LLM-based analysis to understand query intent and automatically determines:
- Query type (search, aggregation, count, safety check)
- Required endpoints
- Need for cross-referencing

### 2. Cross-Reference Resolution
Handles impossible direct queries by combining data from multiple endpoints:
- "Which product codes have recalls?" (recalls don't contain product codes directly)
- Automatically fetches classification data to enrich recall information

### 3. Safety Analysis
Comprehensive safety checks across multiple databases:
- Recalls (enforcement actions)
- MAUDE (adverse events)
- Classification details
- Related device analysis

### 4. Smart Fallbacks
- Handles future dates gracefully (e.g., "recalls in 2025")
- Suggests alternatives when no data exists
- Provides context for zero-result queries

## API Endpoints

The agent integrates with 7 FDA database endpoints:

1. **Classification**: Device classifications and product codes
2. **510(k)**: Premarket notifications
3. **PMA**: Premarket approvals
4. **Recall**: Enforcement actions and recalls
5. **MAUDE**: Adverse event reports
6. **UDI**: Unique device identification
7. **Registration & Listing**: Establishment registrations

## Configuration

### Environment Variables

Required:
- `ANTHROPIC_API_KEY`: Claude API key for natural language processing

Optional:
- `OPENFDA_API_KEY`: FDA API key for higher rate limits (get one [here](https://open.fda.gov/apis/authentication/))

### Advanced Options

CLI flags:
- `--explain`: Show detailed routing and decision process
- `--dry-run`: Test routing without API calls
- `--output json`: Return JSON formatted results

## Development

### Running Tests

```bash
make test          # Run unit tests
make integration   # Run integration tests
make smoke         # Quick functionality check
```

### Building Documentation

```bash
make docs          # Generate documentation
```

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## Troubleshooting

### Common Issues

1. **Recursion Limit Error**: The agent retries up to 10 times. Check your query syntax.
2. **No Results Found**: Try broader search terms or check date ranges.
3. **API Rate Limits**: Add an OpenFDA API key for higher limits.

### Debug Mode

Run with explain flag for detailed execution trace:
```bash
python -m agent.cli "your query" --explain
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph) and [LangChain](https://langchain.com/)
- Powered by [Claude](https://www.anthropic.com/claude) and [OpenFDA API](https://open.fda.gov/)
- RAG implementation using [sentence-transformers](https://www.sbert.net/)

## Contact

For issues, questions, or contributions, please open an issue on GitHub.