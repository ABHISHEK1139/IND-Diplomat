from __future__ import annotations

from ._legacy import PROJECT_ROOT, SRC_ROOT, ensure_legacy_root_on_syspath

ensure_legacy_root_on_syspath()

__all__ = ["PROJECT_ROOT", "SRC_ROOT"]
