#!/bin/bash
# Development check script - runs lint, tests, and smoke test
# Enforces quality gates for local dev and CI

set -e

echo "=== OpenFDA Agent Dev Check ==="
echo

# Check if venv is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Error: Virtual environment not activated. Run: source .venv/bin/activate"
    exit 1
fi

# 1. Install/upgrade dependencies
echo "[1/4] Checking dependencies..."
pip install -q -r requirements.txt

# 2. Lint check (if available - optional for now)
echo "[2/4] Lint check (skipped - add pre-commit or ruff later)"

# 3. Run unit tests
echo "[3/4] Running unit tests..."
python -m pytest tests/ -q

# 4. Smoke test (use cached responses)
echo "[4/4] Running smoke test (offline mode)..."
SKIP_LIVE=1 ./scripts/smoke_test.sh

echo
echo "✓ All dev checks passed!"
echo "Ready to commit."
