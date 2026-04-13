"""Frontend package marker for the web UI assets."""

from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent

__all__ = ["FRONTEND_DIR"]
