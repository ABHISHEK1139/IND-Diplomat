"""
Root-level shim: redirects all ``ind_diplomat.*`` imports to ``src/ind_diplomat/``.
"""
from pathlib import Path

_real_package = str(Path(__file__).resolve().parent.parent / "src" / "ind_diplomat")
__path__ = [_real_package]
