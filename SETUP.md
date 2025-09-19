# FDA Explorer Setup Guide

## Prerequisites

1. **API Keys Required**:
   - **OpenRouter API Key** - for AI analysis features (access to multiple models)
   - **FDA API Key** (optional) - for higher rate limits

## Quick Setup

1. **Configure Environment**:
   ```bash
   cp .env.example .env
   nano .env
   # Add your API keys
   ```

2. **Install Dependencies**:
   ```bash
   # Backend
   pip install -e ".[dev]"
   
   # Frontend
   cd frontend
   npm install
   cd ..
   ```

3. **Start Backend API**:
   ```bash
   ./start-backend.sh
   ```

4. **Test Frontend Locally**:
   ```bash
   cd frontend
   npm run dev
   # Visit http://localhost:3002/fda
   ```

5. **Deploy to Production**:
   ```bash
   ./deploy.sh
   ```

## API Key Setup

### OpenRouter (Recommended - Multiple Models)
1. Get API key from: https://openrouter.ai/
2. Add to `.env`:
   ```
   AI_PROVIDER=openrouter
   AI_API_KEY=sk-or-...your-key...
   ```

### OpenAI (Alternative)
1. Get API key from: https://platform.openai.com/api-keys
2. Add to `.env`:
   ```
   AI_PROVIDER=openai
   AI_API_KEY=sk-...your-key...
   ```

### Anthropic Claude (Alternative)
1. Get API key from: https://console.anthropic.com/
2. Add to `.env`:
   ```
   AI_PROVIDER=anthropic
   AI_API_KEY=sk-ant-...your-key...
   ```

## Testing Without AI Features

The system works without AI keys but with limited functionality:
- ✅ Basic FDA data search
- ✅ Device event browsing
- ❌ AI risk assessment
- ❌ Intelligent insights
- ❌ Trend analysis

## Nginx Configuration

Add to `/etc/nginx/sites-enabled/portfolio.snambiar.com`:
```nginx
# Include the nginx-fda.conf content
```

Then reload nginx:
```bash
sudo systemctl reload nginx
```