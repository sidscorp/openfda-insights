#!/bin/bash

echo "🔌 Starting FDA Explorer Backend API..."

# Load environment variables if .env exists
if [ -f .env ]; then
    echo "📋 Loading environment from .env file..."
    export $(grep -v '^#' .env | xargs)
else
    echo "⚠️  No .env file found. Using defaults or environment variables."
    echo "   To configure API keys, copy .env.example to .env and add your keys."
fi

# Check for AI API key
if [ -z "$AI_API_KEY" ]; then
    echo "⚠️  WARNING: AI_API_KEY not set. AI features will be disabled."
    echo "   To enable AI features, set AI_API_KEY in your .env file."
fi

# Set defaults if not provided
export ENVIRONMENT="${ENVIRONMENT:-production}"
export AUTH_ENABLED="${AUTH_ENABLED:-false}"
export AI_PROVIDER="${AI_PROVIDER:-openrouter}"

echo "📊 Configuration:"
echo "   Environment: $ENVIRONMENT"
echo "   AI Provider: $AI_PROVIDER"
echo "   Auth Enabled: $AUTH_ENABLED"

# Start the API
echo "🚀 Starting API on port 8000..."
uvicorn enhanced_fda_explorer.api:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 2 \
    --log-level info