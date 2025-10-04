# Makefile for openFDA agent development
#
# Targets:
#   make dev     - Run full dev check (deps, tests, smoke)
#   make test    - Run unit tests only
#   make smoke   - Run CLI smoke tests (live API calls)
#   make clean   - Remove cache and temp files

.PHONY: dev test integration smoke clean help

# Default target
help:
	@echo "OpenFDA Agent Development"
	@echo ""
	@echo "Targets:"
	@echo "  make dev         - Run full dev check (deps, tests, smoke)"
	@echo "  make test        - Run unit tests with pytest"
	@echo "  make integration - Run integration tests (requires ANTHROPIC_API_KEY)"
	@echo "  make smoke       - Run CLI smoke tests (live API calls)"
	@echo "  make clean       - Remove cache and temp files"
	@echo ""
	@echo "Prerequisites:"
	@echo "  source .venv/bin/activate"

# Full dev check
dev:
	@./scripts/dev_check.sh

# Unit tests only
test:
	@python -m pytest tests/ -v --ignore=tests/integration

# Integration tests (requires ANTHROPIC_API_KEY)
integration:
	@python -m pytest tests/integration/ -v -k routing

# Smoke tests (live)
smoke:
	@python -m pytest tests/integration/test_e2e.py::test_routing_accuracy -v

# Clean up
clean:
	@echo "Cleaning cache and temp files..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✓ Clean complete"
