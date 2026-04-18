# ============================================================================
# IND-Diplomat — Makefile
# ============================================================================
# Standard build/test/run interface for Linux/macOS/WSL environments.
#
# Usage:
#   make setup       — Create virtualenv and install dependencies
#   make test        — Run the test suite
#   make lint        — Run code quality checks
#   make run         — Start the web application
#   make docker-build — Build the Docker image
#   make clean       — Remove generated artifacts
# ============================================================================

.PHONY: help setup test lint format run docker-build docker-up docker-down clean verify

PYTHON     ?= python3
VENV       := .venv
PIP        := $(VENV)/bin/pip
PYTEST     := $(VENV)/bin/pytest
BLACK      := $(VENV)/bin/black
ISORT      := $(VENV)/bin/isort
FLAKE8     := $(VENV)/bin/flake8
APP        := app_server.py
PORT       ?= 8000

# Default target
help: ## Show this help
	@echo "IND-Diplomat — Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Setup ──────────────────────────────────────────────────────────────────
setup: ## Create virtualenv and install all dependencies
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -r Config/requirements.txt
	@echo ""
	@echo "✓ Setup complete. Activate with: source $(VENV)/bin/activate"

# ── Test ───────────────────────────────────────────────────────────────────
test: ## Run the test suite with pytest
	$(PYTEST) test/ -ra --tb=short -v

test-cov: ## Run tests with coverage report
	$(PYTEST) test/ -ra --tb=short -v --cov=. --cov-report=term-missing --cov-report=html:reports/coverage

test-smoke: ## Run smoke tests only (fast)
	$(PYTEST) test/test_imports.py test/test_core_pipeline.py -ra --tb=short -v

# ── Code Quality ───────────────────────────────────────────────────────────
lint: ## Run all linters (flake8 + black check + isort check)
	$(FLAKE8) --max-line-length=120 --exclude=.venv,__pycache__,build,dist --count --statistics .
	$(BLACK) --check --diff .
	$(ISORT) --check-only --diff .

format: ## Auto-format code with black + isort
	$(BLACK) .
	$(ISORT) .

# ── Run ────────────────────────────────────────────────────────────────────
run: ## Start the web application
	$(PYTHON) $(APP) --port $(PORT)

run-cli: ## Run a CLI query (usage: make run-cli Q="your question")
	$(PYTHON) run.py "$(Q)"

verify: ## Verify installation and paths
	$(PYTHON) project_root.py
	$(PYTEST) test/test_imports.py -q

# ── Docker ─────────────────────────────────────────────────────────────────
docker-build: ## Build the Docker image
	docker build -t ind-diplomat .

docker-up: ## Start with docker compose (app only)
	docker compose up --build -d

docker-up-full: ## Start with docker compose + infra (Redis, ChromaDB)
	docker compose --profile infra up --build -d

docker-down: ## Stop all containers
	docker compose --profile infra down

docker-logs: ## Tail container logs
	docker compose logs -f app

# ── Clean ──────────────────────────────────────────────────────────────────
clean: ## Remove generated artifacts
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info/ reports/coverage/ .cache/
	@echo "✓ Cleaned."
