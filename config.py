"""
Compatibility shim so imports like `from config.paths import ...` resolve
to the existing `Config/` package directory.
"""

from pathlib import Path

_CONFIG_DIR = Path(__file__).resolve().parent / "Config"
__path__ = [str(_CONFIG_DIR)]
