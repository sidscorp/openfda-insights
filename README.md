# Enhanced FDA Explorer

**⚠️ DEVELOPMENT STATUS: This project is actively under development. Core functionality works but features are being added and refined. Questions or want to collaborate? Contact [Dr. Sidd Nambiar](https://github.com/siddnambiar).**

A tool for exploring FDA medical device data with optional AI analysis.

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![License](https://img.shields.io/badge/license-MIT-yellow.svg)

## Features

### Core Capabilities
- Access to FDA medical device databases (device events, recalls, 510k clearances, PMA approvals, classifications, UDI)
- Optional AI analysis for risk scoring and insights
- Multiple interfaces: Web UI (Streamlit), REST API, Python SDK, CLI tool
- Basic visualizations and data export

### Additional Features
- Caching for improved performance
- Device comparison functionality
- Manufacturer analysis
- Configuration management

## Architecture

```
Enhanced FDA Explorer
├── Core Engine (FDAExplorer)
│   ├── Enhanced Client (OpenFDA + Intelligence)
│   ├── AI Analysis Engine
│   └── Configuration Management
├── Interfaces
│   ├── Web UI (Streamlit)
│   ├── REST API (FastAPI)
│   ├── CLI Tool (Click + Rich)
│   └── Python SDK
├── Data Layer
│   ├── OpenFDA API Integration
│   ├── Caching (Redis/Memory)
│   └── Database (SQLite/PostgreSQL)
└── Infrastructure
    ├── Authentication & Authorization
    ├── Logging & Monitoring
    └── Deployment (Docker/Kubernetes)
```

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/siddnambiar/enhanced-fda-explorer.git
cd enhanced-fda-explorer

# Install the package
pip install -e .
```

### Configuration

```bash
# Copy environment template (if it exists)
cp .env.example .env

# Edit configuration
nano .env
```

Set your API keys:
```env
FDA_API_KEY=your_fda_api_key_here
AI_API_KEY=your_openai_api_key_here
```

### Usage Examples

#### Command Line Interface

```bash
# Search for device data
fda-explorer search "pacemaker" --type device --limit 100

# Get device intelligence
fda-explorer device "insulin pump" --lookback 12 --risk-assessment

# Compare devices
fda-explorer compare "pacemaker" "defibrillator" "insulin pump"

# Analyze trends
fda-explorer trends "hip implant" --periods 6months 1year 2years

# Start web interface
fda-explorer web

# Start API server
fda-explorer serve
```

#### Python SDK

```python
import asyncio
from enhanced_fda_explorer import FDAExplorer

async def main():
    # Initialize explorer
    explorer = FDAExplorer()
    
    # Search for device data
    response = await explorer.search(
        query="pacemaker",
        query_type="device",
        include_ai_analysis=True
    )
    
    # Get device intelligence
    intelligence = await explorer.get_device_intelligence(
        device_name="insulin pump",
        lookback_months=12,
        include_risk_assessment=True
    )
    
    # Compare devices
    comparison = await explorer.compare_devices(
        device_names=["pacemaker", "defibrillator"],
        lookback_months=12
    )
    
    explorer.close()

# Run async function
asyncio.run(main())
```

#### REST API

```bash
# Start API server
fda-explorer serve --host 0.0.0.0 --port 8000

# Search via API
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "pacemaker",
    "query_type": "device",
    "limit": 100,
    "include_ai_analysis": true
  }'

# Get device intelligence
curl -X POST "http://localhost:8000/device/intelligence" \
  -H "Content-Type: application/json" \
  -d '{
    "device_name": "insulin pump",
    "lookback_months": 12,
    "include_risk_assessment": true
  }'
```

#### Web Interface

```bash
# Start web interface
fda-explorer web

# Navigate to http://localhost:8501
```

## Data Sources

Accesses FDA medical device databases via the OpenFDA API:

| Database | Description |
|----------|-------------|
| Device Events | Adverse event reports |
| Device Recalls | Product recall information |
| 510(k) Clearances | Premarket notifications |
| PMA Approvals | Premarket approvals |
| Device Classifications | Device classification database |
| UDI Database | Unique device identifier records |

## AI Analysis

Optional AI analysis features:

- Risk assessment based on regulatory data
- Basic trend analysis
- Device comparison with insights
- Configurable AI providers (OpenAI, Anthropic, OpenRouter)

## Configuration

### Environment Variables

```env
# Core
ENVIRONMENT=production
DEBUG=false

# API Keys
FDA_API_KEY=your_fda_api_key
AI_API_KEY=your_ai_api_key

# Database
DATABASE_URL=postgresql://user:pass@localhost/fda_explorer

# Cache
REDIS_URL=redis://localhost:6379

# Authentication
AUTH_ENABLED=true
SECRET_KEY=your-secret-key

# Monitoring
MONITORING_ENABLED=true
```

### Configuration File

Create `config/config.yaml`:

```yaml
app_name: "Enhanced FDA Explorer"
environment: "production"

openfda:
  api_key: "${FDA_API_KEY}"
  timeout: 30
  max_retries: 3

ai:
  provider: "openai"
  model: "gpt-4"
  api_key: "${AI_API_KEY}"

# ... additional configuration
```

## Deployment

### Docker

```bash
# Build image
docker build -t enhanced-fda-explorer .

# Run container
docker run -d \
  --name fda-explorer \
  -p 8000:8000 \
  -p 8501:8501 \
  -e FDA_API_KEY=your_key \
  -e AI_API_KEY=your_key \
  enhanced-fda-explorer
```

### Docker Compose

```yaml
version: '3.8'
services:
  fda-explorer:
    build: .
    ports:
      - "8000:8000"
      - "8501:8501"
    environment:
      - FDA_API_KEY=${FDA_API_KEY}
      - AI_API_KEY=${AI_API_KEY}
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
      - postgres
  
  redis:
    image: redis:alpine
    
  postgres:
    image: postgres:13
    environment:
      POSTGRES_DB: fda_explorer
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
```


## API Documentation

Once the API server is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Spec**: http://localhost:8000/openapi.json

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/search` | POST | Search FDA data with AI analysis |
| `/device/intelligence` | POST | Get comprehensive device intelligence |
| `/device/compare` | POST | Compare multiple devices |
| `/trends` | POST | Analyze trends over time |
| `/manufacturer/{name}/intelligence` | GET | Get manufacturer intelligence |
| `/regulatory/insights` | GET | Get regulatory insights |

## Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=enhanced_fda_explorer

# Run specific test category
pytest tests/test_api.py
pytest tests/test_ai.py
pytest tests/test_client.py
```

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone repository
git clone https://github.com/siddnambiar/enhanced-fda-explorer.git
cd enhanced-fda-explorer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Set up pre-commit hooks
pre-commit install

# Run tests
pytest
```

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **OpenFDA**: For providing comprehensive public access to FDA data
- **U.S. FDA**: For maintaining high-quality medical device databases
- **Open Source Community**: For the excellent tools and libraries that make this project possible

## 📞 Support

- **Documentation**: [https://enhanced-fda-explorer.readthedocs.io](https://enhanced-fda-explorer.readthedocs.io)
- **Issues**: [GitHub Issues](https://github.com/siddnambiar/enhanced-fda-explorer/issues)
- **Discussions**: [GitHub Discussions](https://github.com/siddnambiar/enhanced-fda-explorer/discussions)
- **Email**: support@enhanced-fda-explorer.com

## ⚠️ Disclaimer

This tool is for research and informational purposes only. It is not affiliated with, endorsed by, or representing the U.S. Food and Drug Administration. All data comes from the public openFDA API. Users should verify all information independently before making any decisions based on the analysis provided by this tool.

---

**Built with ❤️ by [Dr. Sidd Nambiar](https://github.com/siddnambiar)**