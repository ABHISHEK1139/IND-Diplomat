#!/usr/bin/env bash
# ============================================================================
# IND-Diplomat — First-Run Setup Script (Linux/macOS/WSL)
# ============================================================================
# Creates the virtual environment, installs dependencies, verifies paths,
# and runs a quick smoke test to ensure the system is operational.
#
# Usage:
#   chmod +x scripts/configure_first_run.sh
#   ./scripts/configure_first_run.sh
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"

cd "$PROJECT_ROOT"

echo "========================================"
echo "  IND-Diplomat — First-Run Bootstrap"
echo "========================================"
echo ""
echo "  Project root: $PROJECT_ROOT"
echo ""

# ── Step 1: Create virtual environment ────────────────────────────────────
if [ -d "$VENV_DIR" ]; then
    echo "[1/5] Virtual environment already exists at $VENV_DIR"
else
    echo "[1/5] Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ── Step 2: Upgrade pip + install dependencies ────────────────────────────
echo "[2/5] Installing dependencies..."
python -m pip install --upgrade pip setuptools wheel --quiet
pip install -r Config/requirements.txt --quiet
echo "  ✓ Dependencies installed"

# ── Step 3: Create required directories ───────────────────────────────────
echo "[3/5] Ensuring data directories exist..."
mkdir -p data/global_risk data/legal_memory data/chroma runtime
echo "  ✓ Directories ready"

# ── Step 4: Copy .env if not present ──────────────────────────────────────
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "[4/5] Creating .env from .env.example..."
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
    echo "  ✓ .env created (edit with your settings)"
else
    echo "[4/5] .env already exists — skipping"
fi

# ── Step 5: Verify installation ───────────────────────────────────────────
echo "[5/5] Running verification..."
python project_root.py
python -m pytest test/test_imports.py -q --tb=short 2>/dev/null || echo "  ⚠ Some imports may need optional services (Ollama, Redis)"

echo ""
echo "========================================"
echo "  ✓ Setup complete!"
echo "========================================"
echo ""
echo "  Activate environment:  source .venv/bin/activate"
echo "  Start web app:         python app_server.py --port 8000"
echo "  Run tests:             make test"
echo "  Build Docker:          make docker-build"
echo ""
