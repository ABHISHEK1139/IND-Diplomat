"""
Compatibility layer for the new packaged path system.
"""

from __future__ import annotations

from ind_diplomat.paths import (
    DATA_DIR,
    GLOBAL_RISK_DIR,
    LEGAL_MEMORY_DIR,
    LOCAL_DIR,
    LOGS_DIR,
    PACKAGE_ROOT,
    PROJECT_ROOT,
    RAG_INDEX_DIR,
    REPORTS_DIR,
    RUNTIME_DIR,
    SRC_ROOT,
    TEST_OUTPUT_ROOT,
    VAR_DIR,
    ensure_local_layout,
    verify_paths,
)

ensure_local_layout()


if __name__ == "__main__":
    print("=== IND-Diplomat Path Verification ===")
    results = verify_paths(loud=True)
    all_ok = all(results.values())
    print(f"\n{'ALL PATHS OK' if all_ok else 'SOME PATHS MISSING - check above'}")
