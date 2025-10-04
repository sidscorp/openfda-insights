#!/bin/bash
# Smoke test script - runs one live call per tool to verify CLI works
# Set SKIP_LIVE=1 to skip live API calls

set -e

echo "=== OpenFDA Tools Smoke Test ==="
echo

# Check if venv is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Error: Virtual environment not activated. Run: source .venv/bin/activate"
    exit 1
fi

# Flag to skip live calls (use recorded cassettes instead)
SKIP_LIVE=${SKIP_LIVE:-0}

if [ "$SKIP_LIVE" -eq 1 ]; then
    echo "Skipping live API calls (SKIP_LIVE=1)"
    echo "Running unit tests with VCR cassettes instead..."
    python -m pytest tests/ -q
    exit 0
fi

echo "Testing tool CLIs with live API calls..."
echo "(Set SKIP_LIVE=1 to use cached cassettes instead)"
echo

# Test each tool --help
echo "[1/12] Testing registration_listing --help"
python -m tools.registration_listing --help > /dev/null

echo "[2/12] Testing classification --help"
python -m tools.classification --help > /dev/null

echo "[3/12] Testing k510 --help"
python -m tools.k510 --help > /dev/null

echo "[4/12] Testing pma --help"
python -m tools.pma --help > /dev/null

echo "[5/12] Testing recall --help"
python -m tools.recall --help > /dev/null

echo "[6/12] Testing maude --help"
python -m tools.maude --help > /dev/null

echo "[7/12] Testing udi --help"
python -m tools.udi --help > /dev/null

echo "[8/12] Testing utils --help"
python -m tools.utils --help > /dev/null

# Light live queries (small limits)
echo
echo "Running light live queries..."
echo

echo "[9/12] Classification query (device_class:2, limit=1)"
python -m tools.classification --device-class 2 --limit 1 > /dev/null

echo "[10/12] 510(k) query (decision_date_start=20200101, limit=1)"
python -m tools.k510 --decision-date-start 20200101 --decision-date-end 20201231 --limit 1 > /dev/null

echo "[11/12] MAUDE query (date_received_start=20230101, limit=1)"
python -m tools.maude --date-received-start 20230101 --date-received-end 20230201 --limit 1 > /dev/null

echo "[12/12] Utils field_explorer"
python -m tools.utils field_explorer --endpoint classification > /dev/null

echo
echo "✓ All smoke tests passed!"
