"""
Config.paths re-exports the canonical packaged path configuration.
"""

from ind_diplomat.paths import (  # noqa: F401
    DATA_DIR,
    GLOBAL_RISK_DIR as GLOBAL_RISK_DATA_PATH,
    LEGAL_MEMORY_DIR as LEGAL_MEMORY_PATH,
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
)

# External tool paths (Windows defaults)
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
