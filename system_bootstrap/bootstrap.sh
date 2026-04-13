#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

if [[ ! -x "diplomat_env/bin/python" ]]; then
  echo "Creating virtual environment: diplomat_env"
  python3 -m venv diplomat_env
fi

source diplomat_env/bin/activate
python system_bootstrap/bootstrap.py "$@"
