from __future__ import annotations

import os
from pathlib import Path

from ._legacy import PROJECT_ROOT

SRC_ROOT = PROJECT_ROOT / "src"
PACKAGE_ROOT = SRC_ROOT / "ind_diplomat"
LOCAL_DIR = Path(os.getenv("IND_DIPLOMAT_LOCAL_DIR", str(PROJECT_ROOT / ".local")))
VAR_DIR = Path(os.getenv("IND_DIPLOMAT_VAR_DIR", str(LOCAL_DIR / "var")))
DATA_DIR = Path(os.getenv("DATA_DIR", str(LOCAL_DIR / "data")))
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", str(LOCAL_DIR / "reports")))
RUNTIME_DIR = Path(os.getenv("RUNTIME_DIR", str(LOCAL_DIR / "runtime")))
LOGS_DIR = Path(os.getenv("LOGS_DIR", str(LOCAL_DIR / "logs")))
TEST_OUTPUT_ROOT = Path(os.getenv("DIP_TEST_OUTPUT_DIR", str(RUNTIME_DIR / "test_runs")))


def _resolve_global_risk_dir() -> Path:
    env_value = str(os.getenv("GLOBAL_RISK_DIR", "")).strip()
    if env_value:
        return Path(env_value)

    candidates = [
        DATA_DIR / "global_risk",
        PROJECT_ROOT / "data" / "global_risk",
        PROJECT_ROOT / "data" / "global_risk_data",
        PROJECT_ROOT / "global_risk_data",
        PROJECT_ROOT / "SAVED DATA" / "global_risk_data",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return DATA_DIR / "global_risk"


def _resolve_legal_memory_dir() -> Path:
    env_value = str(os.getenv("LEGAL_MEMORY_DIR", "")).strip()
    if env_value:
        return Path(env_value)

    candidates = [
        DATA_DIR / "legal_memory",
        PROJECT_ROOT / "data" / "legal_memory",
        PROJECT_ROOT / "legal_memory",
        PROJECT_ROOT / "SAVED DATA" / "legal_memory",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return DATA_DIR / "legal_memory"


GLOBAL_RISK_DIR = _resolve_global_risk_dir()
LEGAL_MEMORY_DIR = _resolve_legal_memory_dir()
RAG_INDEX_DIR = Path(os.getenv("RAG_INDEX_DIR", str(DATA_DIR / "rag_index")))


def ensure_local_layout() -> None:
    for path in (LOCAL_DIR, VAR_DIR, DATA_DIR, RAG_INDEX_DIR, REPORTS_DIR, RUNTIME_DIR, LOGS_DIR, TEST_OUTPUT_ROOT):
        path.mkdir(parents=True, exist_ok=True)


def verify_paths(loud: bool = False) -> dict[str, bool]:
    checks = {
        "PROJECT_ROOT": PROJECT_ROOT,
        "SRC_ROOT": SRC_ROOT,
        "PACKAGE_ROOT": PACKAGE_ROOT,
        "LOCAL_DIR": LOCAL_DIR,
        "DATA_DIR": DATA_DIR,
        "GLOBAL_RISK_DIR": GLOBAL_RISK_DIR,
        "LEGAL_MEMORY_DIR": LEGAL_MEMORY_DIR,
        "RAG_INDEX_DIR": RAG_INDEX_DIR,
        "REPORTS_DIR": REPORTS_DIR,
        "RUNTIME_DIR": RUNTIME_DIR,
        "LOGS_DIR": LOGS_DIR,
    }
    results: dict[str, bool] = {}
    for name, path in checks.items():
        exists = path.exists()
        results[name] = exists
        if loud:
            tag = "OK" if exists else "MISSING"
            print(f"  [{tag:>7s}]  {name:<20s} = {path}")
    return results


ensure_local_layout()
