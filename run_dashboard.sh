#!/bin/bash

# FDA Device Query Assistant Dashboard Startup Script

echo "=========================================="
echo "FDA Device Query Assistant Dashboard"
echo "=========================================="
echo ""

# Check for virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Check for required environment variables
if [ -z "$ANTHROPIC_API_KEY" ]; then
    # Try to load from .env file
    if [ -f ".env" ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi

    if [ -z "$ANTHROPIC_API_KEY" ]; then
        echo "⚠️  WARNING: ANTHROPIC_API_KEY not set"
        echo "The dashboard requires an Anthropic API key to function."
        echo "Please set it in your .env file or environment."
        echo ""
        read -p "Do you want to continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

echo ""
echo "Starting dashboard server..."
echo "----------------------------------------"
echo "📍 Dashboard URL: http://localhost:8000"
echo "📊 API Docs:      http://localhost:8000/docs"
echo "----------------------------------------"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run the dashboard
python -m dashboard.app