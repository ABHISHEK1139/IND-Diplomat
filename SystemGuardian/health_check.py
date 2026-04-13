"""Environment health checks for the Layer-0 System Guardian."""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from Config.paths import GLOBAL_RISK_DATA_PATH
from engine.Layer3_StateModel.providers.dataset_catalog import list_catalog_keys, resolve_dataset_paths

REQUIRED_BINARIES: Dict[str, List[str]] = {
    "tesseract": ["tesseract", "--version"],
    "ollama": ["ollama", "--version"],
}

REQUIRED_PYTHON_LIBS = [
    "pytesseract",
    "bs4",
    "ddgs",
    "sentence_transformers",
    "chromadb",
    "spacy",
    "pandas",
    "faiss",
]


def _binary_available(command: List[str]) -> bool:
    if not command:
        return False
    if shutil.which(command[0]) is None:
        return False
    try:
        subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=20,
            text=True,
        )
        return True
    except Exception:
        return False


def check_binaries() -> Dict[str, bool]:
    report: Dict[str, bool] = {}
    for name, command in REQUIRED_BINARIES.items():
        report[name] = _binary_available(command)
    return report


def check_python_packages() -> Dict[str, bool]:
    report: Dict[str, bool] = {}
    for pkg in REQUIRED_PYTHON_LIBS:
        try:
            importlib.import_module(pkg)
            report[pkg] = True
        except Exception:
            report[pkg] = False
    return report


def check_global_risk_data(*, include_provider_load: bool = False) -> Dict[str, Any]:
    root = Path(GLOBAL_RISK_DATA_PATH)
    datasets: Dict[str, Any] = {}
    for key in list_catalog_keys():
        matches = resolve_dataset_paths(key, root)
        datasets[key] = {
            "present": bool(matches),
            "path": str(matches[0]) if matches else "",
            "count": len(matches),
        }

    report: Dict[str, Any] = {
        "root_path": str(root),
        "root_exists": bool(root.exists()),
        "datasets": datasets,
    }

    if include_provider_load:
        try:
            from engine.Layer3_StateModel.construction.country_state_builder import CountryStateBuilder

            builder = CountryStateBuilder()
            report["providers"] = builder.get_provider_health(refresh=True)
        except Exception as exc:
            report["providers"] = {"error": str(exc)}

    return report


def full_health_report() -> Dict[str, Any]:
    return {
        "binaries": check_binaries(),
        "python_packages": check_python_packages(),
        "runtime": {
            "python_executable": sys.executable,
        },
        "global_risk_data": check_global_risk_data(include_provider_load=False),
    }
