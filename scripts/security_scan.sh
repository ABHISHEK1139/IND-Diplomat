#!/bin/bash
set -e

echo "=========================================="
echo "DIP 2.0 Security & Static Analysis Scanner"
echo "=========================================="
echo ""

# Ensure we are in the root directory
cd "$(dirname "$0")/.."

echo "[1/4] Running Bandit (Python Security Scanner)..."
# Scan the main Python modules, exclude tests and virtual envs
bandit -r . -x ./tests,./venv,./.venv,./frontend-next -c pyproject.toml || echo "Bandit found potential issues. Please review."
echo "Bandit scan complete."
echo ""

echo "[2/4] Running Semgrep (Static Analysis)..."
# We run semgrep using the official security rules
# Note: Requires semgrep to be installed and available in PATH
semgrep scan --config "p/security-audit" --config "p/secrets" || echo "Semgrep found potential issues. Please review."
echo "Semgrep scan complete."
echo ""

echo "[3/4] Running Trivy (Container Scanner) - Backend..."
# Check if trivy is installed
if command -v trivy &> /dev/null; then
    # Scan the backend docker image
    trivy image --severity HIGH,CRITICAL dip2-web:latest || echo "Trivy backend scan failed or found issues."
    echo "Trivy backend scan complete."
else
    echo "Warning: Trivy is not installed or not in PATH. Skipping container scan."
fi
echo ""

echo "[4/4] Running Trivy (Container Scanner) - Frontend..."
if command -v trivy &> /dev/null; then
    # Scan the frontend docker image
    trivy image --severity HIGH,CRITICAL dip2-frontend:latest || echo "Trivy frontend scan failed or found issues."
    echo "Trivy frontend scan complete."
fi

echo "=========================================="
echo "Security Scans Completed."
echo "=========================================="
