# Contributing to Politiq AI

Thank you for your interest in contributing to Politiq AI! This document outlines the process for contributing to this project.

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct. Please be respectful and constructive in all interactions.

## Getting Started

### Prerequisites

- Python 3.10+
- Docker (for containerized development)
- Git

### Development Setup

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/dip2.git
   cd dip2
   ```
3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
4. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
5. Run tests to verify setup:
   ```bash
   pytest -q
   ```

## Development Workflow

### Branching Strategy

- `main` - Stable releases
- `develop` - Integration branch for features
- Feature branches: `feature/description`
- Bug fix branches: `fix/description`
- Release branches: `release/vX.Y.Z`

### Making Changes

1. Create a feature branch from `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/your-feature-name
   ```

2. Make your changes with clear, focused commits

3. Run tests locally:
   ```bash
   pytest -q
   ```

4. Run linting:
   ```bash
   ruff check .
   black --check .
   ```

5. Push your branch and create a Pull Request

### Pull Request Guidelines

- Fill out the PR template completely
- Ensure all tests pass
- Update documentation for any user-facing changes
- Keep PRs focused and reasonably sized
- Link related issues

## Testing

### Running Tests

```bash
# Run all tests
pytest -q

# Run specific test file
pytest tests/test_nextgen_layer4.py -q

# Run with coverage
pytest --cov=src --cov-report=term-missing
```

### Test Categories

- Unit tests: `tests/test_*.py`
- Integration tests: `tests/test_*_integration.py`
- API tests: `tests/test_api_*.py`

## Code Style

- Follow PEP 8
- Use type hints for all public functions
- Maximum line length: 100 characters
- Use `black` for formatting
- Use `ruff` for linting

## Documentation

- Update docstrings for any modified functions/classes
- Update README.md for significant changes
- Add migration notes for breaking changes

## Release Process

1. Create a release branch from `develop`
2. Update version in `pyproject.toml`
3. Update CHANGELOG.md
4. Create PR to `main`
5. Tag release after merge
6. GitHub Actions will build and publish

## Architecture Overview

DIP 2.0 follows a layered architecture:

- **Layer 1-3**: Collection, Knowledge, State Model
- **Layer 4**: Analysis (Council of Ministers)
- **Layer 5**: Trajectory & Black Swan
- **Layer 6**: Presentation & Learning
- **Layer 7**: Global Contagion
- **Layer 8**: War Gaming

Key components:
- `unified_pipeline.py` - Main orchestration
- `nextgen/` - Next-gen advisory layer
- `layer4_reasoning/` - Minister council
- `api.py` - FastAPI endpoints

## Questions?

Open an issue or start a discussion on GitHub.