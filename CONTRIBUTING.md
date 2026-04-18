# Contributing to IND-Diplomat

Thank you for your interest in contributing to IND-Diplomat. This document outlines the development workflow, coding standards, and submission process.

## Table of Contents

- [Development Setup](#development-setup)
- [Code Standards](#code-standards)
- [Architecture Overview](#architecture-overview)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)

---

## Development Setup

### Prerequisites

- **Python 3.10+** (3.11 recommended)
- **Git**
- **Docker** (optional, for containerized development)
- **Ollama** or **OpenRouter API key** (for LLM reasoning)

### Getting Started

```bash
# Clone the repository
git clone https://github.com/ABHISHEK1139/IND-Diplomat.git
cd IND-Diplomat

# Option A: Linux / macOS / WSL (recommended)
chmod +x scripts/configure_first_run.sh
./scripts/configure_first_run.sh
source .venv/bin/activate

# Option B: Windows PowerShell
powershell -ExecutionPolicy Bypass -File .\Scripts\configure_first_run.ps1 -InstallDependencies
.\.venv\Scripts\Activate.ps1

# Option C: Docker (no local Python required)
cp .env.example .env      # Configure environment
docker compose up --build  # Build and start
```

### Verify Installation

```bash
make verify           # Checks paths, imports, and config
# or manually:
python project_root.py
python -m pytest test/test_imports.py -q
```

---

## Code Standards

### Python Style

| Tool | Purpose | Configuration |
|------|---------|---------------|
| [Black](https://black.readthedocs.io/) | Code formatter | `line-length = 120` |
| [isort](https://pycqa.github.io/isort/) | Import sorting | `profile = "black"` |
| [flake8](https://flake8.pycqa.org/) | Linter | `max-line-length = 120` |
| [mypy](https://mypy.readthedocs.io/) | Type checking | `python_version = "3.11"` |

All tool configurations are centralized in [`pyproject.toml`](pyproject.toml).

### Pre-Commit Workflow

Before submitting a PR, always run:

```bash
make format   # Auto-format code with Black + isort
make lint     # Check code quality (flake8 + black --check + isort --check)
make test     # Run the full test suite
```

### Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Files | `snake_case.py` | `country_state_builder.py` |
| Classes | `PascalCase` | `CountryStateBuilder` |
| Functions / Methods | `snake_case` | `build_initial_state()` |
| Constants | `UPPER_SNAKE_CASE` | `OUTCOME_ASSESSMENT` |
| Private members | `_leading_underscore` | `_evaluate_evidence()` |
| Environment variables | `UPPER_SNAKE_CASE` | `LLM_PROVIDER` |

### Docstrings

Use **Google-style** docstrings for all public classes and functions:

```python
def evaluate_signals(
    signals: list[dict],
    threshold: float = 0.5,
) -> dict[str, float]:
    """Evaluate a batch of geopolitical signals against SRE dimensions.

    Args:
        signals: List of signal dictionaries with 'name' and 'confidence' keys.
        threshold: Minimum confidence to include a signal in scoring.

    Returns:
        Dictionary mapping SRE dimension names to aggregated scores.

    Raises:
        ValueError: If signals list is empty.
    """
```

### Type Hints

- Use type annotations for **all** public function signatures
- Use `Optional[X]` for nullable types, `list[X]` / `dict[K, V]` for containers
- Complex types should be aliased for readability

---

## Architecture Overview

The codebase follows a **7-layer pipeline architecture** with strict isolation rules.

```
Layer 1 (Collection)  →  Layer 2 (Knowledge)  →  Layer 3 (State Model)
    →  Layer 4 (Analysis / Council)  →  Layer 5 (Judgment / Gate)
    →  Layer 6 (Presentation / Backtesting)  →  Layer 7 (Global Model)
```

Before making changes, review:

- [Architecture Documentation](docs/architecture.md) — Full pipeline design
- [Repository Map](docs/repo-map.md) — Module-level reference

### Design Principles

1. **Layer isolation** — Each layer only depends on layers below it. Never import upward.
2. **No LLM in gates** — Assessment gates (Layer 5) use deterministic rules only, ensuring reproducibility.
3. **Evidence provenance** — Every signal must trace back to a data source with confidence and timestamp.
4. **Safety by default** — Refusal engine, PII masking, and HITL checks are always active.
5. **Graceful degradation** — If a service (Redis, Neo4j, Ollama) is unavailable, the pipeline continues with reduced functionality rather than crashing.

### Adding a New Module

1. Place it in the appropriate `engine/Layer*` directory
2. Ensure it only imports from layers at or below its level
3. Add a corresponding test in `test/`
4. Update `docs/repo-map.md` with the new module

---

## Testing

### Test Structure

```
test/
├── test_imports.py             # Smoke test — verifies all critical imports
├── test_core_pipeline.py       # Core pipeline unit tests (43 tests)
├── test_context.py             # State context construction
├── test_coordinator_anomaly.py # Coordinator edge cases
├── test_layer2.py              # Knowledge layer
├── test_layer3.py              # State model layer
├── test_e2e.py                 # End-to-end integration
└── ...
```

### Running Tests

```bash
make test          # Full suite
make test-smoke    # Quick validation (imports + core pipeline)
make test-cov      # Full suite with HTML coverage report

# Run a specific test file
python -m pytest test/test_core_pipeline.py -v

# Run a specific test class
python -m pytest test/test_core_pipeline.py::TestConfig -v
```

### Writing Tests

- Place all tests in the `test/` directory
- Name test files `test_*.py` and test functions `test_*`
- Use `pytest` fixtures and `tmp_path` for file I/O
- Tests **must** run without external services — use `unittest.mock` to mock LLM calls, Redis, etc.
- Use `pytest.mark.skipif` for tests that require optional dependencies (e.g., FastAPI)

Example:

```python
def test_diplomat_result_creation():
    from run import DiplomatResult

    result = DiplomatResult(
        outcome="ASSESSMENT",
        answer="Risk assessment completed",
        confidence=0.75,
        risk_level="MEDIUM",
    )
    assert result.outcome == "ASSESSMENT"
    assert 0.0 <= result.confidence <= 1.0
```

---

## Pull Request Process

1. **Branch** — Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Develop** — Make focused, well-documented commits with clear messages:
   ```bash
   git commit -m "Add signal ablation test for GDELT provider"
   ```

3. **Validate** — Ensure all checks pass:
   ```bash
   make format    # Auto-format
   make lint      # Lint check
   make test      # Test suite
   ```

4. **Document** — Update docs if adding new modules or changing APIs

5. **Submit** — Open a PR with:
   - Clear title describing what changed
   - Description of *why* the change was made
   - Link to any related issues
   - Screenshots for UI changes

6. **Review** — Address feedback and keep the CI green

---

## Reporting Issues

Open a [GitHub Issue](https://github.com/ABHISHEK1139/IND-Diplomat/issues) with:

- **Title**: Clear, specific summary of the problem
- **Environment**: Python version, OS, LLM provider (Ollama/OpenRouter)
- **Steps to reproduce**: Minimal sequence to trigger the issue
- **Expected behavior**: What should happen
- **Actual behavior**: What actually happens (include error messages / stack traces)
- **Logs**: Relevant output from `runtime/` if applicable

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
