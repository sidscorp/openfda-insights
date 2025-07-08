# Installation Guide

This guide covers all installation methods for Enhanced FDA Explorer, from quick start to advanced deployment scenarios.

## Requirements

- **Python**: 3.8 or higher
- **Operating System**: Windows, macOS, or Linux
- **Memory**: Minimum 2GB RAM (4GB+ recommended for AI features)
- **API Keys**: FDA API key (free), AI provider API key (OpenAI, Anthropic, etc.)

## Quick Installation

### Option 1: From PyPI (Recommended)

```bash
pip install enhanced-fda-explorer
```

### Option 2: From Source

```bash
# Clone repository
git clone https://github.com/siddnambiar/enhanced-fda-explorer.git
cd enhanced-fda-explorer

# Install in development mode
pip install -e .
```

### Option 3: Using Docker

```bash
# Pull and run the latest image
docker run -d \
  --name fda-explorer \
  -p 8000:8000 \
  -p 8501:8501 \
  -e FDA_API_KEY=your_fda_api_key \
  -e AI_API_KEY=your_ai_api_key \
  siddnambiar/enhanced-fda-explorer:latest
```

## Development Installation

For contributors and developers:

```bash
# Clone repository
git clone https://github.com/siddnambiar/enhanced-fda-explorer.git
cd enhanced-fda-explorer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with development dependencies
pip install -e ".[dev]"

# Set up pre-commit hooks
pre-commit install

# Verify installation
pytest
```

## Configuration

### 1. Get API Keys

#### FDA API Key (Required)
1. Visit [FDA API Key Registration](https://open.fda.gov/apis/authentication/)
2. Register for a free API key
3. Note your API key for configuration

#### AI Provider API Key (Optional, for AI features)
Choose one:
- **OpenAI**: [OpenAI API Keys](https://platform.openai.com/api-keys)
- **Anthropic**: [Anthropic Console](https://console.anthropic.com/)
- **OpenRouter**: [OpenRouter Keys](https://openrouter.ai/keys)

### 2. Environment Configuration

Create a `.env` file in your project directory:

```bash
# Copy example configuration
cp .env.example .env

# Edit configuration
nano .env
```

Minimum required configuration:
```env
FDA_API_KEY=your_fda_api_key_here
AI_API_KEY=your_ai_api_key_here  # Optional
```

### 3. Advanced Configuration

For production deployments, create `config/config.yaml`:

```yaml
app_name: "Enhanced FDA Explorer"
environment: "production"

openfda:
  api_key: "${FDA_API_KEY}"
  timeout: 30
  max_retries: 3
  rate_limit: 1000  # requests per hour

ai:
  provider: "openai"  # or "anthropic", "openrouter"
  model: "gpt-4"
  api_key: "${AI_API_KEY}"
  temperature: 0.1
  max_tokens: 2000

database:
  url: "${DATABASE_URL}"  # Optional: postgresql://...
  pool_size: 10

cache:
  provider: "redis"  # or "memory"
  url: "${REDIS_URL}"  # Optional: redis://localhost:6379
  ttl: 3600  # 1 hour

logging:
  level: "INFO"
  format: "json"
```

## Verification

Test your installation:

```bash
# Check CLI works
fda-explorer --help

# Test basic search
fda-explorer search "pacemaker" --limit 5

# Start web interface
fda-explorer web
# Visit http://localhost:8501

# Start API server
fda-explorer serve
# Visit http://localhost:8000/docs
```

## Production Deployment

### Docker Compose

```yaml
version: '3.8'
services:
  fda-explorer:
    image: siddnambiar/enhanced-fda-explorer:latest
    ports:
      - "8000:8000"
      - "8501:8501"
    environment:
      - FDA_API_KEY=${FDA_API_KEY}
      - AI_API_KEY=${AI_API_KEY}
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/fda_explorer
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  postgres:
    image: postgres:13-alpine
    environment:
      - POSTGRES_DB=fda_explorer
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:alpine
    restart: unless-stopped

volumes:
  postgres_data:
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: enhanced-fda-explorer
spec:
  replicas: 3
  selector:
    matchLabels:
      app: fda-explorer
  template:
    metadata:
      labels:
        app: fda-explorer
    spec:
      containers:
      - name: fda-explorer
        image: siddnambiar/enhanced-fda-explorer:latest
        ports:
        - containerPort: 8000
        - containerPort: 8501
        env:
        - name: FDA_API_KEY
          valueFrom:
            secretKeyRef:
              name: fda-secrets
              key: fda-api-key
        - name: AI_API_KEY
          valueFrom:
            secretKeyRef:
              name: fda-secrets
              key: ai-api-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
```

## Troubleshooting

### Common Issues

#### Import Error
```bash
ModuleNotFoundError: No module named 'enhanced_fda_explorer'
```
**Solution**: Reinstall the package:
```bash
pip uninstall enhanced-fda-explorer
pip install enhanced-fda-explorer
```

#### API Key Issues
```bash
Error: Invalid API key
```
**Solution**: Verify your API keys in `.env` file:
```bash
cat .env | grep API_KEY
```

#### Permission Errors
```bash
PermissionError: [Errno 13] Permission denied
```
**Solution**: Use virtual environment:
```bash
python -m venv venv
source venv/bin/activate
pip install enhanced-fda-explorer
```

#### Network/Firewall Issues
```bash
ConnectionError: Failed to connect to API
```
**Solution**: Check firewall settings and proxy configuration.

### Getting Help

1. **Documentation**: [https://enhanced-fda-explorer.readthedocs.io](https://enhanced-fda-explorer.readthedocs.io)
2. **GitHub Issues**: [Report a bug](https://github.com/siddnambiar/enhanced-fda-explorer/issues)
3. **Discussions**: [Community forum](https://github.com/siddnambiar/enhanced-fda-explorer/discussions)

## Next Steps

After installation:
1. Read the [Quick Start Guide](QUICK_TEST_GUIDE.md)
2. Explore the [CLI Reference](cli_reference.md)
3. Try the [Python SDK](sdk_reference.md)
4. Review [API Documentation](api_reference.md)