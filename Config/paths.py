"""
Config.paths — re-exports from project_root.py (single source of truth).

Every consumer that already does ``from Config.paths import ...`` keeps
working without any change.  The *real* definitions live in project_root.py.
"""

from project_root import (          # noqa: F401  — re-exports
    PROJECT_ROOT,
    DATA_DIR,
    GLOBAL_RISK_DIR   as GLOBAL_RISK_DATA_PATH,
    LEGAL_MEMORY_DIR  as LEGAL_MEMORY_PATH,
    RAG_INDEX_DIR,
)

# External tool paths (Windows defaults)
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
