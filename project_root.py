"""
project_root.py — Single Source of Truth for All Filesystem Paths
==================================================================
Every module that needs a path imports from HERE (or from Config/paths.py,
which re-exports these).  No other file should compute its own root.

Canonical data layout::

    DIP_3_0/
    ├── data/
    │   ├── global_risk/       ← SIPRI, V-Dem, ATOP, sanctions, WorldBank, ...
    │   ├── legal_memory/      ← constitutions, treaties, country legal docs
    │   ├── rag_index/         ← ChromaDB legal article embeddings
    │   ├── chroma/            ← main vector store
    │   ├── state_history/     ← temporal memory snapshots
    │   └── ...                ← evidence_store.db, tension_history.json, etc.
    ├── reports/               ← generated assessment reports
    ├── runtime/               ← continuous_monitor state
    └── logs/                  ← application logs
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Root ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent

# ── Primary data directory ────────────────────────────────────────────
DATA_DIR = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data")))


def _resolve_global_risk_dir() -> Path:
    """Resolve global-risk dataset path with backward-compatible fallbacks."""
    env_value = str(os.getenv("GLOBAL_RISK_DIR", "")).strip()
    if env_value:
        return Path(env_value)

    candidates = [
        DATA_DIR / "global_risk",
        DATA_DIR / "global_risk_data",
        PROJECT_ROOT / "global_risk_data",
        PROJECT_ROOT / "SAVED DATA" / "global_risk_data",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return DATA_DIR / "global_risk"


def _resolve_legal_memory_dir() -> Path:
    """Resolve legal-memory dataset path with backward-compatible fallbacks."""
    env_value = str(os.getenv("LEGAL_MEMORY_DIR", "")).strip()
    if env_value:
        return Path(env_value)

    candidates = [
        DATA_DIR / "legal_memory",
        PROJECT_ROOT / "legal_memory",
        PROJECT_ROOT / "SAVED DATA" / "legal_memory",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return DATA_DIR / "legal_memory"

# ── Dataset directories ──────────────────────────────────────────────
GLOBAL_RISK_DIR = _resolve_global_risk_dir()
LEGAL_MEMORY_DIR = _resolve_legal_memory_dir()
RAG_INDEX_DIR = Path(
    os.getenv("RAG_INDEX_DIR", str(DATA_DIR / "rag_index"))
)

# ── Output / runtime directories ─────────────────────────────────────
REPORTS_DIR = PROJECT_ROOT / "reports"
RUNTIME_DIR = PROJECT_ROOT / "runtime"
LOGS_DIR = PROJECT_ROOT / "logs"


def verify_paths(loud: bool = False) -> dict:
    """
    Check that all canonical directories exist.
    Returns ``{name: bool}`` mapping.  If *loud* is True, prints results.
    """
    checks = {
        "PROJECT_ROOT":   PROJECT_ROOT,
        "DATA_DIR":       DATA_DIR,
        "GLOBAL_RISK_DIR": GLOBAL_RISK_DIR,
        "LEGAL_MEMORY_DIR": LEGAL_MEMORY_DIR,
        "RAG_INDEX_DIR":  RAG_INDEX_DIR,
        "REPORTS_DIR":    REPORTS_DIR,
    }
    results = {}
    for name, p in checks.items():
        exists = p.exists()
        results[name] = exists
        if loud:
            tag = "OK" if exists else "MISSING"
            print(f"  [{tag:>7s}]  {name:<20s} = {p}")
    return results


if __name__ == "__main__":
    print("=== IND-Diplomat Path Verification ===")
    results = verify_paths(loud=True)
    all_ok = all(results.values())
    print(f"\n{'ALL PATHS OK' if all_ok else 'SOME PATHS MISSING — check above'}")
